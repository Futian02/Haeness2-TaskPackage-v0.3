"""S2 API integration probes: feature gate, offline candidate adapter, and memory wiring."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.store import Store
from backend.execution_ledger import SQLiteExecutionLedger
from backend.intent_router_v2 import IntentSubtask, MainRoute, RouteDecision, TaskKind
from backend.agentic_provider import ScriptedFakePlanner
from langgraph.checkpoint.sqlite import SqliteSaver
from orchestration.agentic_v2 import AgenticV2Candidate


class _Candidate:
    def __init__(self):
        self.calls = []

    def run(self, question, context, *, run_id, thread_id):
        self.calls.append((run_id, thread_id, question))
        return {"output": {
            "status": "exploratory",
            "confirmed_engineering_conclusion": False,
            "human_review_completed": False,
            "risk_level": None,
            "candidates": [{"label": "待核候选", "source_ids": ["T-1"], "evidence_level": "POSSIBLE"}],
            "unknowns": ["temperature_c"],
            "targeted_supplement": [],
            "citations": [{"clause_id": "T-1", "standard_code": "GB/T MOCK", "clause_no": "1", "page": 1}],
            "tool_calls": [{"tool": "standard_clause_search", "arguments": {"keyword": "GB/T MOCK 第1条", "top_k": 5},
                            "status": "returned", "attempts": 1,
                            "result": {"status": "ok", "source": [{"clause_id": "T-1",
                                "standard_code": "GB/T MOCK", "clause_no": "1", "page": 1}], "result": {"private_excerpt": "not projected"}}}],
            "events": [{"kind": "sources_grounded", "node": "source_ground",
                        "public_rationale": "来源门禁通过"}],
            "review": {"status": "needs_human_review"},
        }}


class S2ApiIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="aether-s2-api-")
        self.store = Store(Path(self.temp.name) / "s2.sqlite3")
        from backend import api
        self.api = api
        self.client_context = patch.object(api, "store", self.store)
        self.client_context.start()
        self.client = TestClient(api.app)

    def tearDown(self):
        self.client.close()
        self.client_context.stop()
        self.temp.cleanup()

    def _conversation(self):
        r = self.client.post("/api/conversations", json={"title": "S2 integration"})
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()["id"]

    def test_v2_feature_flag_is_default_closed(self):
        cid = self._conversation()
        with patch.object(self.api, "AETHER_V2_AGENTIC_ENABLED", False):
            rejected = self.client.post(f"/api/conversations/{cid}/runs", json={
                "question": "换热器裂纹可能的损伤机理？", "mode": "V2_AGENTIC"})
        self.assertEqual(rejected.status_code, 503)
        self.assertEqual(rejected.json()["detail"], "v2_feature_disabled")
        self.assertEqual(self.store.messages(cid), [])

    def test_v2_candidate_is_offline_and_adapted_to_existing_run_contract(self):
        cid = self._conversation()
        candidate = _Candidate()
        with patch.object(self.api, "AETHER_V2_AGENTIC_ENABLED", True), \
             patch.object(self.api, "_get_agentic_v2_candidate", return_value=candidate), \
             patch("backend.model_profiles.safe_profile", side_effect=AssertionError("V2 must not resolve API keys")):
            created = self.client.post(f"/api/conversations/{cid}/runs", json={
                "question": "换热器裂纹可能的损伤机理？", "mode": "V2_AGENTIC"})
            self.assertEqual(created.status_code, 200, created.text)
            events_response = self.client.get(created.json()["events_url"])
        self.assertEqual(events_response.status_code, 200)
        self.assertEqual(len(candidate.calls), 1)
        rid, thread_id, _ = candidate.calls[0]
        self.assertEqual(thread_id, cid)
        run = self.store.run(rid)
        self.assertEqual(run["mode"], "V2_AGENTIC")
        self.assertEqual(run["context"]["_v2_route_execution"], "V2_AGENTIC_FAKE_CANDIDATE")
        events = self.client.get(f"/api/runs/{rid}/events").json()["events"]
        self.assertEqual(events[-1]["type"], "run_completed", events)
        self.assertEqual(events[-1]["payload"]["risk_level"], None)
        self.assertEqual(events[-1]["payload"]["route_execution"], "V2_AGENTIC_FAKE_CANDIDATE")
        tool_call = next(row for row in events if row["type"] == "tool_called")
        tool_result = next(row for row in events if row["type"] == "tool_result")
        self.assertEqual(tool_call["payload"]["args"]["keyword"], "已记录（值由服务端保留，不公开）")
        self.assertIn("keyword", tool_call["payload"]["argument_presence"])
        self.assertNotIn("GB/T MOCK 第1条", str(events))
        self.assertEqual(tool_result["payload"]["result"]["sources"][0]["clause_id"], "T-1")
        self.assertNotIn("private_excerpt", str(tool_result["payload"]))
        assistant = [m for m in self.store.messages(cid) if m.get("role") == "assistant"]
        self.assertEqual(len(assistant), 1)
        self.assertIn("待核候选", assistant[0]["content"])

    def test_explicit_mixed_route_runs_sqlite_dag_and_public_tool_projection(self):
        cid = self._conversation()
        canonical = {"clause_id": "C-1", "standard_code": "GB/T MOCK",
                     "clause_no": "5.23", "page": 12}
        class MixedCandidate:
            def __init__(self):
                self.clauses = {"C-1": canonical}
                self.replay = SQLiteExecutionLedger(str(self.store_path))
                self.tools = {"standard_clause_search": self.standard_clause_search}
                self.standard_calls = 0
            store_path = self.store.path
            def standard_clause_search(self, **kwargs):
                self.standard_calls += 1
                return {"status":"ok","in_domain":True,"result":[],
                        "source":[canonical],"message":"offline fixture"}
            def run(self, question, context, *, run_id, thread_id, subtask_id):
                return {"output":{"status":"insufficient_evidence","citations":[canonical],
                                  "candidates":[],"unknowns":["现场证据缺失"]}}
        candidate = MixedCandidate()
        decision = RouteDecision(primary_route=MainRoute.MIXED, safety_relevance=True,
            confidence=0.9, reasons_public=["fixture"],
            subtasks=[
                IntentSubtask(id="standard",kind=TaskKind.STANDARD_LOOKUP,
                              user_goal="查询GB/T条款"),
                IntentSubtask(id="engineering",kind=TaskKind.MECHANISM_EXPLORATION,
                              user_goal="初步研判",depends_on=["standard"],task_risk="SAFETY_RELEVANT"),
                IntentSubtask(id="summary",kind=TaskKind.WRITING_SYNTHESIS,
                              user_goal="证据边界内整理",depends_on=["engineering"]),
            ])
        with (patch.object(self.api, "AETHER_V2_AGENTIC_ENABLED", True),
              patch.object(self.api, "_get_agentic_v2_candidate", return_value=candidate),
              patch.object(self.api, "intent_router", type("Router", (), {"route": lambda _self, _q: decision})())):
            created = self.client.post(f"/api/conversations/{cid}/runs", json={
                "question":"换热器裂纹查询GB/T并说明", "mode":"V2_AGENTIC"})
            self.assertEqual(created.status_code, 200, created.text)
            self.client.get(created.json()["events_url"])
        events = self.client.get(f"/api/runs/{created.json()['run_id']}/events").json()["events"]
        self.assertEqual(candidate.standard_calls, 1, (events, self.store.events(created.json()["run_id"])))
        self.assertTrue(any(event["type"] == "subtask_completed" for event in events), events)
        tool = next(event for event in events if event["type"] == "tool_result")
        self.assertEqual(tool["payload"]["source_ids"], ["C-1"])
        self.assertEqual(tool["payload"]["actual_attempts"], 1)
        self.assertNotIn("查询GB/T条款", str(events))
        self.assertEqual(len([m for m in self.store.messages(cid) if m["role"] == "assistant"]), 1)

    def test_agentic_candidate_persists_thread_scoped_checkpoint_in_sqlite(self):
        planner = ScriptedFakePlanner(default_plan={
            "action": "finish", "tool_name": "", "query": "", "tool_arguments": {},
            "investigation_goal": "完成受限离线检查", "evidence_gap": "",
            "public_rationale": "本轮无需调用工具。", "focus_clause_ids": [],
        }, default_reflection={"continue_investigation": False, "next_evidence_gap": "",
                               "public_rationale": "停止于当前证据边界。"})
        tools = {name: (lambda **_kwargs: {"status": "not_found", "in_domain": True,
                  "result": {}, "source": [], "message": "offline fixture"})
                 for name in ("damage_mechanism_query", "rbi_lookup", "standard_clause_search")}
        with SqliteSaver.from_conn_string(str(self.store.path)) as saver:
            candidate = AgenticV2Candidate(planner=planner, tool_registry=tools,
                clause_index={}, enum_sets={"material": set(), "medium": set(), "equipment_type": set()},
                checkpointer=saver)
            result = candidate.run("换热器裂纹可能的损伤机理？", {}, run_id="run-checkpoint-1", thread_id="thread-cid-1")
            self.assertFalse(result["output"]["confirmed_engineering_conclusion"])
            checkpoints = list(saver.list({"configurable": {"thread_id": "thread-cid-1::aetheris-v2::run-checkpoint-1"}}))
            self.assertTrue(checkpoints, "expected persistent graph checkpoint")
            self.assertEqual(checkpoints[0].config["configurable"]["thread_id"], "thread-cid-1::aetheris-v2::run-checkpoint-1")

    def test_confirmed_memory_is_cid_scoped_and_only_used_by_engineering_route(self):
        cid_a, cid_b = self._conversation(), self._conversation()
        first = self.client.post(f"/api/conversations/{cid_a}/runs", json={
            "question": "请分析这台设备的腐蚀机理", "mode": "RULE_DEMO",
            "equipment_type": "管道", "material": "碳钢", "medium": ["湿硫化氢"]})
        self.assertEqual(first.status_code, 200, first.text)
        self.client.get(first.json()["events_url"])
        facts = self.store.fact_assertions(cid_a, confirmed_only=True)
        self.assertTrue(any(row["field"] == "material" and row["value"] == "碳钢" for row in facts))
        self.assertFalse(self.store.fact_assertions(cid_b, confirmed_only=True))

        followup = self.client.post(f"/api/conversations/{cid_a}/runs", json={
            "question": "这台设备的腐蚀情况如何？", "mode": "RULE_DEMO"})
        self.assertEqual(followup.status_code, 200, followup.text)
        run = self.store.run(followup.json()["run_id"])
        self.assertEqual(run["context"]["material"], "碳钢", run["context"] )
        self.assertEqual(run["context"]["medium"], ["湿硫化氢"])

        general = self.client.post(f"/api/conversations/{cid_a}/runs", json={
            "question": "你好", "mode": "RULE_DEMO"})
        self.assertEqual(general.status_code, 200, general.text)
        general_run = self.store.run(general.json()["run_id"])
        self.assertIsNone(general_run["context"].get("material"))
        self.assertEqual(general_run["context"].get("medium"), [])
        self.assertNotEqual(general_run["context"].get("material"), "碳钢")


if __name__ == "__main__":
    unittest.main()
