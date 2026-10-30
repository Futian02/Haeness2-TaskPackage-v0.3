import importlib
import json
import os
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.store import Store


class P4AStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name) / "runs.db")
        self.conversation = self.store.create_conversation("lease test")
        self.run = self.store.create_run(self.conversation["id"], "question", {}, "RULE_DEMO")

    def tearDown(self):
        self.temp.cleanup()

    def test_claim_race_has_exactly_one_winner(self):
        barrier = threading.Barrier(10)
        def claim(n):
            barrier.wait()
            return self.store.claim_run(self.run["id"], f"worker-{n}")
        with ThreadPoolExecutor(max_workers=10) as pool:
            results = list(pool.map(claim, range(10)))
        self.assertEqual(sum(results), 1)
        claimed = self.store.run(self.run["id"])
        self.assertEqual(claimed["status"], "running")
        self.assertIsNotNone(claimed["worker_token"])

    def test_stale_lease_becomes_durable_terminal_event_without_retry(self):
        self.assertTrue(self.store.claim_run(self.run["id"], "dead-worker"))
        with self.store.session() as conn:
            conn.execute("UPDATE runs SET worker_heartbeat_at='2000-01-01T00:00:00+00:00' WHERE id=?", (self.run["id"],))
        self.assertTrue(self.store.recover_stale_run(self.run["id"], stale_after_seconds=0))
        self.assertFalse(self.store.recover_stale_run(self.run["id"], stale_after_seconds=0))
        run = self.store.run(self.run["id"])
        self.assertEqual((run["status"], run["error_code"]), ("failed", "worker_lost"))
        events = self.store.events(self.run["id"])
        self.assertEqual([e["type"] for e in events], ["error"])
        self.assertEqual(events[0]["payload"]["code"], "worker_lost")

    def test_run_page_is_scoped_bounded_and_metadata_only(self):
        other = self.store.create_conversation("other")
        for i in range(4):
            self.store.create_run(self.conversation["id"], f"q{i}", {"material": "private"}, "RULE_DEMO")
        self.store.create_run(other["id"], "other", {}, "RULE_DEMO")
        page, total = self.store.list_runs_by_conversation(self.conversation["id"], 2, 1)
        self.assertEqual((len(page), total), (2, 5))
        self.assertTrue(all("context" not in row and "question" not in row for row in page))
        self.assertTrue(all(row["conversation_id"] == self.conversation["id"] for row in page))
        with self.assertRaises(ValueError):
            self.store.list_runs_by_conversation(self.conversation["id"], 101, 0)


class P4AApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api = importlib.import_module("backend.api")

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name) / "api.db")
        self.store_patch = patch.object(self.api, "store", self.store)
        self.store_patch.start()
        self.client = TestClient(self.api.app)

    def tearDown(self):
        self.store_patch.stop()
        self.temp.cleanup()

    def test_health_does_not_expose_absolute_database_path_and_tool_contract(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(str(self.store.path), response.text)
        self.assertEqual(set(response.json()["teacher_tools"]), {"damage_mechanism_query", "rbi_lookup", "standard_clause_search"})

    def test_question_only_request_has_no_fabricated_context_or_tool_calls(self):
        conv = self.client.post("/api/conversations", json={}).json()
        created = self.client.post(f"/api/conversations/{conv['id']}/runs", json={"question": "分析设备风险"})
        self.assertEqual(created.status_code, 200)
        run_id = created.json()["run_id"]
        self.client.get(created.json()["events_url"])
        run = self.store.run(run_id)
        self.assertIsNone(run["context"]["material"])
        self.assertEqual(run["context"]["medium"], [])
        kinds = [event["type"] for event in self.store.events(run_id)]
        route = [event["payload"] for event in self.store.events(run_id) if event["type"] == "phase_started"]
        self.assertTrue(route)
        self.assertTrue(any(item.get("public_rationale") == "route=deterministic_rbi_grade" for item in route))
        self.assertNotIn("tool_called", kinds)
        conv_state = self.client.get(f"/api/conversations/{conv['id']}").json()
        self.assertEqual([x["role"] for x in conv_state["messages"]], ["user", "assistant"])

    def test_two_simultaneous_streams_execute_once_and_both_subscribe(self):
        conv = self.store.create_conversation("race")
        run = self.store.create_run(conv["id"], "q", {"material": "x", "medium": ["y"]}, "RULE_DEMO")
        count = 0
        count_lock = threading.Lock()
        class SlowGraph:
            # Match the current production graph invocation contract; this
            # adapter intentionally ignores newer candidate-only controls.
            def run(self, question, context, *, run_id=None, on_event=None, **kwargs):
                nonlocal count
                with count_lock:
                    count += 1
                on_event({"event": "phase_started", "phase": "route", "public_rationale": "route=diagnosis"})
                time.sleep(.15)
                on_event({"event": "tool_called", "phase": "investigate", "tool": "damage_mechanism_query"})
                return {"output": {"status": "unresolved", "verification_level": "E0", "conclusion": "done",
                                   "tool_calls": 1, "parallel_review": False, "citations": [], "hypotheses": []}}
        with patch.object(self.api, "graph", SlowGraph()):
            def get_stream():
                with TestClient(self.api.app) as c:
                    return c.get(f"/api/runs/{run['id']}/stream").text
            with ThreadPoolExecutor(max_workers=2) as pool:
                outputs = list(pool.map(lambda _: get_stream(), range(2)))
        self.assertEqual(count, 1)
        event_sequences = []
        for output in outputs:
            records = [json.loads(line[6:]) for line in output.splitlines() if line.startswith("data: ")]
            event_sequences.append([x["sequence"] for x in records])
            for record in records:
                self.assertTrue({"schema_version", "run_id", "session_id", "sequence", "type", "agent", "payload"}.issubset(record))
        self.assertEqual(event_sequences[0], event_sequences[1])
        self.assertEqual(event_sequences[0], sorted(set(event_sequences[0])))
        messages = self.store.messages(conv["id"])
        self.assertEqual(sum(m["role"] == "assistant" for m in messages), 1)

    def test_restart_replays_terminal_stream_without_rerun(self):
        conv = self.store.create_conversation("restart")
        run = self.store.create_run(conv["id"], "q", {}, "RULE_DEMO")
        token = "worker"
        self.assertTrue(self.store.claim_run(run["id"], token))
        self.store.append_event(run["id"], "agent_started", "x", {"n": 1})
        self.store.add_message(conv["id"], "assistant", "already done")
        self.store.finish_run(run["id"], token, "completed")
        restarted = Store(Path(self.temp.name) / "api.db")
        with patch.object(self.api, "store", restarted), patch.object(self.api, "graph") as graph:
            response = TestClient(self.api.app).get(f"/api/runs/{run['id']}/stream")
        graph.run.assert_not_called()
        records = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]
        self.assertEqual([x["sequence"] for x in records], [1])
        self.assertEqual(sum(m["role"] == "assistant" for m in restarted.messages(conv["id"])), 1)

    def test_paginated_runs_endpoint_order_scoping_and_missing_conversation(self):
        cid = self.store.create_conversation("runs")['id']
        other = self.store.create_conversation("other")['id']
        for i in range(3):
            self.store.create_run(cid, str(i), {}, "RULE_DEMO")
        self.store.create_run(other, "foreign", {}, "RULE_DEMO")
        response = self.client.get(f"/api/conversations/{cid}/runs?limit=2&offset=0")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual((len(body["runs"]), body["total"]), (2, 3))
        self.assertTrue(all(row["conversation_id"] == cid for row in body["runs"]))
        self.assertEqual(self.client.get("/api/conversations/missing/runs").status_code, 404)
        self.assertEqual(self.client.get(f"/api/conversations/{cid}/runs?limit=101").status_code, 422)

    def test_production_mode_fails_closed(self):
        with patch.dict(os.environ, {"APP_ENV": "production"}):
            response = TestClient(self.api.app).get("/api/health")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["code"], "AUTH_REQUIRED")

    def test_input_bounds_are_enforced(self):
        self.assertEqual(self.client.post("/api/conversations", json={"title": "x" * 121}).status_code, 422)
        cid = self.store.create_conversation("bounded")["id"]
        self.assertEqual(self.client.post(f"/api/conversations/{cid}/runs", json={"question": "q" * 4001}).status_code, 422)
        self.assertEqual(self.client.post("/api/conversations", content=b" " * (128 * 1024 + 1), headers={"content-type": "application/json"}).status_code, 413)

    def test_rate_gate_returns_429_and_worker_capacity_is_bounded(self):
        with patch.object(self.api, "_RATE_BUDGET", 0):
            limited = TestClient(self.api.app).get("/api/health")
        self.assertEqual((limited.status_code, limited.json()["code"]), (429, "RATE_LIMITED"))
        conv = self.store.create_conversation("capacity")
        run = self.store.create_run(conv["id"], "q", {}, "RULE_DEMO")
        slots = self.api._worker_slots
        acquired = [slots.acquire(blocking=False) for _ in range(4)]
        try:
            self.assertTrue(all(acquired))
            response = TestClient(self.api.app).get(f"/api/runs/{run['id']}/stream")
            self.assertEqual(response.status_code, 429)
            self.assertEqual(self.store.run(run["id"])["status"], "queued")
        finally:
            for _ in acquired:
                slots.release()


if __name__ == "__main__":
    unittest.main()
