from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.store import Store
from backend.usage_stats import create_usage_router, get_usage_stats, period_bounds


NOW = datetime(2026, 10, 28, 15, 30, tzinfo=timezone.utc)


class UsageStatsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="p11-usage-stats-")
        self.store = Store(Path(self.temp.name) / "stats.sqlite3")
        self._seed()

    def tearDown(self):
        self.temp.cleanup()

    def _seed(self):
        c1, c2 = "conversation-active", "conversation-archived"
        with self.store.session() as con:
            con.execute("INSERT INTO conversations(id,title,created_at,updated_at,archived_at) VALUES(?,?,?,?,?)",
                         (c1, "Active", "2026-10-28T13:00:00.000+00:00", "2026-10-28T15:00:00.000+00:00", None))
            con.execute("INSERT INTO conversations(id,title,created_at,updated_at,archived_at) VALUES(?,?,?,?,?)",
                         (c2, "Archived", "2026-10-20T13:00:00.000+00:00", "2026-10-27T15:59:00.000+00:00", "2026-10-28T10:00:00.000+00:00"))
            self._insert_run(con, "run-today-ok", c1, "completed", "DEEPSEEK", "2026-10-28T14:00:00.000+00:00", "2026-10-28T14:00:01.000+00:00", "general_chat")
            self._insert_run(con, "run-today-failed", c1, "failed", "RULE_DEMO", "2026-10-28T15:00:00.000+00:00", "2026-10-28T15:00:02.000+00:00", "diagnosis")
            self._insert_run(con, "run-yesterday-archived", c2, "completed", "RULE_DEMO", "2026-10-27T15:59:00.000+00:00", "2026-10-27T16:00:00.000+00:00", "diagnosis", "insufficient_evidence")
            for run_id, cid, at in (
                ("run-today-ok", c1, "2026-10-28T14:00:00.000+00:00"),
                ("run-today-failed", c1, "2026-10-28T15:00:00.000+00:00"),
                ("run-yesterday-archived", c2, "2026-10-27T15:59:00.000+00:00"),
            ):
                con.execute("INSERT INTO messages(id,conversation_id,role,content,created_at,run_id) VALUES(?,?,?,?,?,?)",
                             (str(uuid4()), cid, "user", "question", at, run_id))
            # These are persisted tool_called projections, not inferred from text.
            for sequence, tool in ((2, "damage_mechanism_query"), (3, "standard_clause_search")):
                con.execute("INSERT INTO tool_calls VALUES(?,?,?,?,?,?,?)",
                             (str(uuid4()), "run-today-failed", sequence, tool, "{}", "{}", "2026-10-28T15:00:00.000+00:00"))
            self._insert_event(con, "run-today-ok", 3, "llm_started", "{}", "2026-10-28T14:00:00.000+00:00")

    @staticmethod
    def _insert_run(con, rid, cid, status, mode, started, ended, route, terminal_status=None):
        con.execute("""INSERT INTO runs(id,conversation_id,status,mode,question,context_json,started_at,ended_at,error_code,
                      worker_token,worker_heartbeat_at,input_message_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (rid, cid, status, mode, "question", "{}", started, ended, "mock_error" if status == "failed" else None, None, None, None))
        UsageStatsTests._insert_event(con, rid, 1, "phase_started",
            json.dumps({"phase": "route", "public_rationale": f"route={route}"}), started)
        if status == "completed":
            UsageStatsTests._insert_event(con, rid, 2, "run_completed", json.dumps({"status": terminal_status or route}), ended)

    @staticmethod
    def _insert_event(con, rid, sequence, kind, payload, at):
        con.execute("INSERT INTO agent_events VALUES(?,?,?,?,?,?,?)", (str(uuid4()), rid, sequence, kind, "test", payload, at))

    def test_local_day_and_calendar_windows_use_offset_and_half_open_edges(self):
        start, end = period_bounds("today", 480, NOW)
        self.assertEqual(start.isoformat(), "2026-10-27T16:00:00+00:00")
        self.assertEqual(end.isoformat(), "2026-10-28T16:00:00+00:00")
        seven_start, seven_end = period_bounds("7d", 480, NOW)
        self.assertEqual((end - seven_end).total_seconds(), 0)
        self.assertEqual((end - seven_start).days, 7)
        thirty_start, thirty_end = period_bounds("30d", 480, NOW)
        self.assertEqual((thirty_end - end).total_seconds(), 0)
        self.assertEqual((thirty_end - thirty_start).days, 30)

    def test_sql_aggregates_runs_messages_tools_models_status_and_archive_history(self):
        today = get_usage_stats(self.store, "today", 480, NOW)
        self.assertEqual(today["counts"], {
            "conversations": 1, "messages_sent": 2, "messages_total": 2, "runs": 2,
            "model_calls": 1, "tool_calls": 2, "average_run_ms": 1500.0,
        })
        self.assertEqual(today["status_distribution"], {"success": 1, "needs_evidence": 0, "failed": 1, "running": 0, "other": 0})
        self.assertEqual(today["task_distribution"], [{"key": "diagnosis", "count": 1}, {"key": "general_chat", "count": 1}])
        self.assertEqual(today["hourly_runs"], [{"hour": 22, "count": 1}, {"hour": 23, "count": 1}])
        self.assertEqual(today["token_usage"], {"availability": "not_recorded", "prompt_tokens": None, "completion_tokens": None, "total_tokens": None})
        week = get_usage_stats(self.store, "7d", 480, NOW)
        self.assertEqual(week["counts"]["runs"], 3)
        self.assertEqual(week["counts"]["conversations"], 2)
        self.assertEqual(week["counts"]["tool_calls"], 2)
        self.assertEqual(week["status_distribution"], {"success": 1, "needs_evidence": 1, "failed": 1, "running": 0, "other": 0})
        self.assertEqual(week["archive_policy"], "included")
        self.assertEqual({row["key"] for row in week["mode_distribution"]}, {"DEEPSEEK", "RULE_DEMO"})

    def test_only_exact_provider_usage_is_summed_and_no_usage_stays_null(self):
        without_usage = get_usage_stats(self.store, "today", 480, NOW)
        self.assertIsNone(without_usage["token_usage"]["total_tokens"])
        with self.store.session() as con:
            self._insert_event(con, "run-today-ok", 4, "llm_completed",
                json.dumps({"usage": {"prompt_tokens": 20, "completion_tokens": 7, "total_tokens": 27}}),
                "2026-10-28T14:00:01.000+00:00")
        with_usage = get_usage_stats(self.store, "today", 480, NOW)
        self.assertEqual(with_usage["token_usage"], {"availability": "recorded", "prompt_tokens": 20, "completion_tokens": 7, "total_tokens": 27})

    def test_invalid_period_and_offset_are_rejected(self):
        with self.assertRaises(ValueError):
            get_usage_stats(self.store, "90d", 0, NOW)  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            get_usage_stats(self.store, "today", 900, NOW)

    def test_api_router_is_standalone_and_returns_explicit_timezone_range(self):
        app = FastAPI()
        app.include_router(create_usage_router(lambda: self.store))
        with TestClient(app) as client:
            response = client.get("/api/stats?period=today&tz_offset=480")
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["timezone_offset_minutes"], 480)
            self.assertEqual(response.json()["token_usage"]["availability"], "not_recorded")
            self.assertEqual(client.get("/api/stats?period=90d").status_code, 422)


if __name__ == "__main__":
    unittest.main()
