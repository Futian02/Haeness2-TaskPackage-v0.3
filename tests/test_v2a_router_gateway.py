from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
_IMPORT_TMP = tempfile.TemporaryDirectory(prefix="v2a-import-")
_OLD_DB = os.environ.get("DATABASE_URL")
os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(_IMPORT_TMP.name) / "import.sqlite")
from fastapi.testclient import TestClient
from backend import api
from backend.store import Store
from backend.intent_router_v2 import LLMStructuredIntentRouter, LocalIntentPolicy, MainRoute, RouteDecision, TaskKind, dispatch_route
from orchestration.intent import classify_intent
if _OLD_DB is None:
    os.environ.pop("DATABASE_URL", None)
else:
    os.environ["DATABASE_URL"] = _OLD_DB


class V2ARouterGatewayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="v2a-case-")
        self.store = Store(Path(self.tmp.name) / "case.sqlite")
        self.patches = [
            patch.object(api, "store", self.store),
            patch.object(api.model_profiles, "safe_profile", return_value=None),
            patch.object(api, "intent_router", LLMStructuredIntentRouter(enabled=False)),
            patch.dict(os.environ, {"APP_ENV": "development"}),
        ]
        for p in self.patches: p.start()
        self.client = TestClient(api.app)

    def tearDown(self):
        self.client.close()
        for p in reversed(self.patches): p.stop()
        self.tmp.cleanup()

    def _run(self, question, *, mode="RULE_DEMO", expected_route="ENGINEERING"):
        conv = self.client.post("/api/conversations", json={"title": "v2a test"})
        self.assertEqual(conv.status_code, 200, conv.text)
        cid = conv.json()["id"]
        response = self.client.post(f"/api/conversations/{cid}/runs", json={"question": question, "mode": mode, "web_mode": "off"})
        self.assertEqual(response.status_code, 200, response.text)
        rid = response.json()["run_id"]
        initial_stream = self.client.get(f"/api/runs/{rid}/stream")
        self.assertEqual(initial_stream.status_code, 200)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            run = self.store.run(rid)
            if run and run["status"] in {"completed", "failed"}: break
            time.sleep(.02)
        run = self.store.run(rid)
        self.assertIsNotNone(run)
        self.assertEqual(run["status"], "completed", run)
        snapshot = self.store.run_input(rid)
        self.assertEqual(snapshot["context"]["_v2_route_decision"]["dispatch_route"], expected_route)
        stream = self.client.get(f"/api/runs/{rid}/stream")
        self.assertEqual(stream.status_code, 200)
        self.assertIn(rid, stream.text)
        self.assertTrue(any(e["type"] == "run_completed" for e in self.store.events(rid)))
        self.assertTrue(any(m.get("run_id") == rid and m["role"] == "assistant" for m in self.store.messages(cid)))
        return cid, rid, run

    def test_schema_validation_and_authority_fields_rejected(self):
        valid = RouteDecision(primary_route=MainRoute.MIXED, subtasks=[
            {"id": "lookup", "kind": TaskKind.STANDARD_LOOKUP, "user_goal": "查询条文"},
            {"id": "analysis", "kind": TaskKind.DEVICE_DIAGNOSIS, "user_goal": "核查设备", "depends_on": ["lookup"]},
        ], safety_relevance=True, confidence=.7)
        self.assertEqual(dispatch_route(valid), MainRoute.ENGINEERING)
        with self.assertRaises(Exception):
            RouteDecision.model_validate({**valid.model_dump(), "authorized_tool": "rbi_lookup"})
        with self.assertRaises(Exception):
            RouteDecision.model_validate({"primary_route": "UNKNOWN", "safety_relevance": False, "confidence": .8})
        with self.assertRaises(Exception):
            RouteDecision.model_validate({"primary_route": "MIXED", "subtasks": [{"id": "one", "kind": "DEVICE_DIAGNOSIS", "user_goal": "x"}], "safety_relevance": True, "confidence": .8})

    def test_mixed_standard_and_device_question_gets_bounded_dag(self):
        route, safety, tasks, _ = LocalIntentPolicy().analyze("查询 GB/T 30579-2022 第5.23条，并分析该设备腐蚀原因，整理成报告")
        self.assertEqual(route, MainRoute.MIXED)
        self.assertTrue(safety)
        self.assertLessEqual(len(tasks), 4)
        self.assertEqual([task.id for task in tasks], ["standard", "engineering", "synthesis"])
        self.assertEqual(tasks[1].depends_on, ["standard"])
        self.assertEqual(tasks[2].depends_on, ["engineering"])

    def test_excess_subtasks_fail_to_deterministic_route(self):
        items = [{"id": f"task{i}", "kind": "GENERAL_EXPLANATION", "user_goal": "解释"} for i in range(5)]
        candidate = {"primary_route": "MIXED", "subtasks": items, "safety_relevance": False, "confidence": .8}
        decision = LLMStructuredIntentRouter(lambda _prompt: json.dumps(candidate, ensure_ascii=False), enabled=True).route("压力容器现场异常，请分析")
        self.assertTrue(decision.safety_relevance)
        self.assertEqual(dispatch_route(decision), MainRoute.ENGINEERING)
        self.assertEqual(decision.model_usage["source"], "fallback")

    def test_mock_model_proposal_is_policy_gated(self):
        proposed = {"primary_route": "GENERAL", "subtasks": [{"id": "general", "kind": "GENERAL_EXPLANATION", "user_goal": "闲聊"}], "safety_relevance": False, "confidence": .99}
        provider = Mock(return_value=json.dumps(proposed, ensure_ascii=False))
        decision = LLMStructuredIntentRouter(provider, enabled=True).route("现场设备出现裂纹，请分析原因")
        self.assertTrue(decision.safety_relevance)
        self.assertEqual(dispatch_route(decision), MainRoute.ENGINEERING)
        self.assertEqual(decision.model_usage["request_count"], 1)
        self.assertTrue(decision.model_usage["policy_gated"])
        provider.assert_called_once()

    def test_mock_failures_fallback_to_safety_route(self):
        samples = ["{bad json", TimeoutError("timeout"), ValueError("wrong tool"), RuntimeError("provider failure")]
        for sample in samples:
            with self.subTest(sample=type(sample).__name__):
                def call(_prompt, item=sample):
                    if isinstance(item, Exception): raise item
                    return item
                decision = LLMStructuredIntentRouter(call, enabled=True).route("管道现场发现泄漏，是否还能运行？")
                self.assertTrue(decision.safety_relevance)
                self.assertEqual(dispatch_route(decision), MainRoute.ENGINEERING)
                self.assertEqual(decision.model_usage["source"], "fallback")

    def test_model_cannot_claim_permission_or_human_review(self):
        for field, value in (("permission_granted", True), ("human_verified", True), ("tool_name", "rbi_lookup")):
            with self.subTest(field=field):
                body = {"primary_route": "ENGINEERING", "subtasks": [{"id": "task", "kind": "DEVICE_DIAGNOSIS", "user_goal": "专业候选"}], "safety_relevance": True, "confidence": .8, "model_usage": {field: value}}
                decision = LLMStructuredIntentRouter(lambda _prompt, x=body: json.dumps(x, ensure_ascii=False), enabled=True).route("设备现场出现异常，分析可能原因")
                self.assertEqual(decision.model_usage["source"], "fallback")
                self.assertEqual(dispatch_route(decision), MainRoute.ENGINEERING)

    def test_disabled_provider_is_never_called(self):
        provider = Mock(side_effect=AssertionError("must not call"))
        decision = LLMStructuredIntentRouter(provider, enabled=False).route("你好")
        self.assertEqual(decision.primary_route, MainRoute.GENERAL)
        self.assertEqual(decision.model_usage["request_count"], 0)
        provider.assert_not_called()

    def test_120_authored_holdout_and_owner65_zero_professional_false_negative(self):
        rows = [json.loads(line) for line in (ROOT / "evals/v2a_router_gold.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertGreaterEqual(len(rows), 100)
        alias = {"general_chat": "general", "standard_lookup": "standard"}
        misses, pro_to_general, general_to_pro, dispatch_misses, safety_misses = [], [], [], [], []
        for row in rows:
            raw = classify_intent(row["question"])
            got = alias.get(raw, "engineering")
            primary, safety, _, _ = LocalIntentPolicy().analyze(row["question"])
            actual_dispatch = "ENGINEERING" if safety or primary in {MainRoute.ENGINEERING, MainRoute.MIXED} else primary.value
            expected_dispatch = {"general": "GENERAL", "standard": "STANDARD_LOOKUP", "engineering": "ENGINEERING", "mixed": "ENGINEERING"}[row["expected"]]
            if actual_dispatch != expected_dispatch: dispatch_misses.append((row["id"], expected_dispatch, actual_dispatch))
            if "expected_safety_relevance" in row and bool(row["expected_safety_relevance"]) != safety: safety_misses.append((row["id"], row["expected_safety_relevance"], safety))
            if got != row["expected"]: misses.append((row["id"], row["expected"], got))
            if row["expected"] in {"engineering", "mixed"} and got == "general": pro_to_general.append(row["id"])
            if row["expected"] == "general" and got in {"engineering", "mixed"}: general_to_pro.append(row["id"])
        self.assertEqual(misses, [])
        self.assertEqual(pro_to_general, [])
        self.assertEqual(dispatch_misses, [])
        self.assertEqual(safety_misses, [])
        self.assertLessEqual(len(general_to_pro), 4, general_to_pro)
        env = dict(os.environ, PYTHONPATH=str(ROOT))
        result = subprocess.run([os.environ.get("PYTHON", "python"), "-B", "evals/owner_mixed_intent_route_audit.py"], cwd=ROOT, env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["total"], 65)
        self.assertEqual(payload["misrouted"], 0)

    def test_general_deepseek_is_direct_and_never_calls_graph(self):
        profile = {"profile_id": "mock-profile", "provider": "deepseek", "model": "mock-chat", "endpoint": "https://invalid.local", "api_key": "dummy-secret-key"}
        generation = Mock(return_value=("mocked general reply", 7))
        graph = Mock()
        with patch.object(api.model_profiles, "safe_profile", return_value=profile), \
             patch.object(api.model_profiles, "resolve_snapshot", return_value=profile), \
             patch.object(api.deepseek, "generate_chat", generation), \
             patch.object(api, "graph", graph):
            cid, rid, run = self._run("你好，介绍一下你能做什么", mode="DEEPSEEK", expected_route="GENERAL")
        graph.run.assert_not_called()
        generation.assert_called_once()
        self.assertEqual(run["status"], "completed")
        events = self.store.events(rid)
        self.assertTrue(any(e["type"] == "intent_routed" and e["payload"]["dispatch_route"] == "GENERAL" for e in events))
        terminal = next(e["payload"] for e in events if e["type"] == "run_completed")
        self.assertEqual(terminal["intent_model_request_count"], 0)
        self.assertEqual(terminal["generation_model_request_count"], 1)
        self.assertEqual(terminal["model_request_count"], 1)
        self.assertTrue(any(m["content"] == "mocked general reply" for m in self.store.messages(cid)))

    def test_total_model_request_count_includes_route_and_chat(self):
        profile = {"profile_id": "mock-profile", "provider": "deepseek", "model": "mock-chat", "endpoint": "https://invalid.local", "api_key": "dummy-secret-key"}
        proposal = {"primary_route": "GENERAL", "subtasks": [{"id": "general", "kind": "GENERAL_EXPLANATION", "user_goal": "闲聊"}], "safety_relevance": False, "confidence": .9}
        provider = Mock(return_value=json.dumps(proposal, ensure_ascii=False))
        with patch.object(api.model_profiles, "safe_profile", return_value=profile), \
             patch.object(api.model_profiles, "resolve_snapshot", return_value=profile), \
             patch.object(api.deepseek, "generate_chat", return_value=("ok", 1)), \
             patch.object(api, "intent_router", LLMStructuredIntentRouter(provider, enabled=True)), \
             patch.object(api, "graph", Mock()) as graph:
            _, rid, _ = self._run("你好", mode="DEEPSEEK", expected_route="GENERAL")
        provider.assert_called_once()
        graph.run.assert_not_called()
        terminal = next(e["payload"] for e in self.store.events(rid) if e["type"] == "run_completed")
        self.assertEqual(terminal["intent_model_request_count"], 1)
        self.assertEqual(terminal["generation_model_request_count"], 1)
        self.assertEqual(terminal["model_request_count"], 2)

    def test_standard_and_engineering_continue_on_compat_graph(self):
        output = {"status": "insufficient_evidence", "conclusion": "未形成结论", "citations": [], "hypotheses": [], "unknowns": [], "tool_calls": 0, "verification_level": "E0", "review_rows": []}
        graph = Mock()
        graph.run.return_value = {"output": output, "review_round": None}
        with patch.object(api, "graph", graph):
            _, standard_id, _ = self._run("查询 GB/T 30579-2022 第5.6条原文和页码", expected_route="STANDARD_LOOKUP")
            _, engineering_id, _ = self._run("设备运行中壁厚下降，请分析可能原因", expected_route="ENGINEERING")
        self.assertEqual(graph.run.call_count, 2)
        self.assertEqual(graph.run.call_args_list[0].kwargs["run_id"], standard_id)
        self.assertEqual(graph.run.call_args_list[1].kwargs["run_id"], engineering_id)


if __name__ == "__main__":
    unittest.main()

