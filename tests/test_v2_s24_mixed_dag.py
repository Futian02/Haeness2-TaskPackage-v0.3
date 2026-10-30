"""S2.4 Gate 2: offline bounded MIXED DAG scenarios; no paid models or upstream writes."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend.execution_ledger import SQLiteExecutionLedger
from backend.intent_router_v2 import IntentSubtask, MainRoute, RouteDecision, TaskKind
from backend.store import Store
from orchestration.mixed_dag import MixedDAGError, MixedDAGExecutor, MockTextProvider
from backend.intent_router_v2 import LocalIntentPolicy

ROOT = Path(__file__).resolve().parents[1]
_MIXED_RECOVERY_CHILD = r"""
import json, os, sys
from backend.execution_ledger import SQLiteExecutionLedger
from backend.intent_router_v2 import IntentSubtask, MainRoute, RouteDecision, TaskKind
from backend.store import Store
from orchestration.mixed_dag import MixedDAGExecutor

db, counter, cid, rid, mode = sys.argv[1:]
store = Store(db)
ledger = SQLiteExecutionLedger(db)
canonical = {"clause_id":"C-1","standard_code":"GB/T-X","clause_no":"4.1","page":12}
def tool(**kwargs):
    with open(counter, "a", encoding="utf-8") as f: f.write("called\n")
    return {"status":"ok","in_domain":True,"result":[],
            "source":[canonical],"message":"fixture"}
class Candidate:
    clauses = {"C-1":canonical}
candidate = Candidate()
decision = RouteDecision(primary_route=MainRoute.MIXED,safety_relevance=True,confidence=.8,
  reasons_public=["fixture"],subtasks=[
    IntentSubtask(id="std",kind=TaskKind.STANDARD_LOOKUP,user_goal="查询条款"),
    IntentSubtask(id="general",kind=TaskKind.GENERAL_EXPLANATION,user_goal="解释概念")])
if mode == "recover":
    assert store.recover_stale_v2_run(rid, stale_after_seconds=0)
    assert store.claim_run(rid,"worker-recovered")
if mode == "crash":
    original = ledger.finish_subtask
    def die_after_tool_commit(**kwargs):
        if kwargs["subtask_id"] == "std" and kwargs["state"] == "SUCCEEDED":
            os._exit(89)
        return original(**kwargs)
    ledger.finish_subtask = die_after_tool_commit
executor = MixedDAGExecutor(candidate=candidate,ledger=ledger,standard_tool=tool)
result = executor.execute(decision,question="fixture",context={},run_id=rid,conversation_id=cid)
assert store.finish_run_with_message(rid,"worker-recovered",
    result["final_text"],{"status":result["status"],"route_execution":result["route_execution"]})
print(json.dumps({"status":result["status"],"tool_calls":result["tool_calls"],
  "subtasks":[x["state"] for x in result["subtasks"]],
  "ledger":ledger.get_action(run_id=rid,subtask_id="std",step_id="tool:1")["state"]}))
"""


class FakeCandidate:
    def __init__(self, *, fail=False, citations=None):
        self.clauses = {"C-1": {"standard_code": "GB/T-X", "clause_no": "4.1", "page": 12}}
        self.fail = fail
        self.calls = 0
        self.citations = citations or [{"clause_id": "C-1"}]

    def run(self, question, context, *, run_id, thread_id, subtask_id):
        self.calls += 1
        if self.fail:
            raise TimeoutError("fake timeout")
        return {"output": {"status": "insufficient_evidence", "citations": self.citations,
                           "candidates": [], "unknowns": ["现场数据缺失"],
                           "risk_level": "L1", "tool_calls": []}}


def decision(*tasks, safety=True):
    return RouteDecision(primary_route=MainRoute.MIXED, subtasks=list(tasks),
                         safety_relevance=safety, confidence=0.8,
                         reasons_public=["fixture"], model_usage={"request_count": 0, "source": "fixture"})


def eng(id="eng", *, depends_on=None):
    return IntentSubtask(id=id, kind=TaskKind.MECHANISM_EXPLORATION,
                         user_goal="只读初步机理探索", depends_on=depends_on or [],
                         task_risk="SAFETY_RELEVANT")


class MixedDAGTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="aether-s24-mixed-")
        self.db = Path(self.temp.name) / "mixed.sqlite3"
        self.store = Store(self.db)
        self.cid = self.store.create_conversation("mixed fixture")["id"]
        self.rid = self.store.create_run(self.cid, "离线混合任务", {}, "V2_AGENTIC")["id"]
        self.ledger = SQLiteExecutionLedger(str(self.db))
        self.candidate = FakeCandidate()
        self.calls = []
        self.counter = Path(self.temp.name) / "tool-calls.txt"
        self.executor = MixedDAGExecutor(candidate=self.candidate, ledger=self.ledger,
            standard_tool=self.standard_tool, text_provider=MockTextProvider())

    def tearDown(self):
        self.temp.cleanup()

    def standard_tool(self, **kwargs):
        self.calls.append(kwargs)
        return {"status": "ok", "in_domain": True,
                "result": [{"clause_id": "C-1"}],
                "source": [{"clause_id": "C-1", "standard_code": "GB/T-X",
                            "clause_no": "4.1", "page": 12}],
                "message": "离线标准fixture"}

    def execute(self, d):
        return self.executor.execute(d, question="混合问题", context={}, run_id=self.rid,
                                     conversation_id=self.cid)

    def test_01_mixed_dag_executes_general_and_engineering(self):
        out = self.execute(decision(
            IntentSubtask(id="general", kind=TaskKind.GENERAL_EXPLANATION, user_goal="解释概念"),
            eng()))
        self.assertEqual(out["route_execution"], "MIXED_DAG_EXECUTED_OFFLINE")
        self.assertEqual([x["state"] for x in out["subtasks"]], ["SUCCEEDED", "SUCCEEDED"])
        self.assertIsNone(next(x for x in out["subtasks"] if x["id"] == "eng")["result"]["risk_level"])

    def test_02_standard_lookup_records_canonical_sources(self):
        out = self.execute(decision(
            IntentSubtask(id="standard", kind=TaskKind.STANDARD_LOOKUP, user_goal="查询标准条款"),
            eng("eng", depends_on=["standard"])))
        self.assertEqual(out["subtasks"][0]["source_ids"], ["C-1"])
        self.assertEqual(self.calls[0]["top_k"], 8)

    def test_03_synthesis_only_uses_dependency_sources(self):
        out = self.execute(decision(
            eng(), IntentSubtask(id="summary", kind=TaskKind.WRITING_SYNTHESIS,
                user_goal="只综合", depends_on=["eng"])))
        self.assertIn("不生成风险等级", out["final_text"])
        self.assertEqual(out["subtasks"][1]["source_ids"], ["C-1"])

    def test_04_candidate_timeout_is_recorded_failed_and_risk_null(self):
        self.candidate.fail = True
        out = self.execute(decision(eng(), IntentSubtask(id="summary",
            kind=TaskKind.WRITING_SYNTHESIS, user_goal="综合", depends_on=["eng"])))
        self.assertEqual(out["status"], "failed")
        self.assertEqual(out["subtasks"][0]["state"], "FAILED")
        self.assertEqual(out["subtasks"][1]["state"], "SKIPPED")

    def test_05_no_source_remains_unresolved(self):
        self.candidate.citations = []
        out = self.execute(decision(eng(), IntentSubtask(id="general",
            kind=TaskKind.GENERAL_EXPLANATION, user_goal="概念解释")))
        engineering = next(x for x in out["subtasks"] if x["id"] == "eng")
        self.assertEqual(engineering["source_ids"], [])
        self.assertIn("无已核验来源", out["final_text"])

    def test_06_fake_provider_is_explicitly_offline(self):
        result = MockTextProvider().explain(
            IntentSubtask(id="x", kind=TaskKind.GENERAL_EXPLANATION, user_goal="说明"), "q")
        self.assertIn("离线Mock", result["text"])
        self.assertEqual(result["sources"], [])

    def test_07_invalid_external_source_is_rejected(self):
        self.candidate.citations = [{"clause_id": "FORGED"}]
        out = self.execute(decision(eng(), IntentSubtask(id="general",
            kind=TaskKind.GENERAL_EXPLANATION, user_goal="概念解释")))
        self.assertEqual(next(x for x in out["subtasks"] if x["id"] == "eng")["state"], "FAILED")

    def test_08_noncanonical_standard_identity_is_rejected(self):
        def bad(**kwargs):
            return {"status":"ok","in_domain":True,"result":[],
                    "source":[{"clause_id":"C-1","standard_code":"FORGED","clause_no":"4.1","page":12}],
                    "message":"bad"}
        self.executor.standard_tool = bad
        out = self.execute(decision(
            IntentSubtask(id="std",kind=TaskKind.STANDARD_LOOKUP,user_goal="查询"),
            IntentSubtask(id="gen",kind=TaskKind.GENERAL_EXPLANATION,user_goal="说明",depends_on=["std"])))
        self.assertEqual(out["subtasks"][0]["state"], "FAILED")
        self.assertEqual(out["subtasks"][1]["state"], "SKIPPED")

    def test_09_success_without_source_is_rejected(self):
        self.executor.standard_tool = lambda **kw: {"status":"ok","in_domain":True,"result":[],
                                                      "source":[],"message":"empty"}
        out = self.execute(decision(
            IntentSubtask(id="std",kind=TaskKind.STANDARD_LOOKUP,user_goal="查询"),
            IntentSubtask(id="gen",kind=TaskKind.GENERAL_EXPLANATION,user_goal="说明",depends_on=["std"])))
        self.assertEqual(out["subtasks"][0]["state"], "FAILED")

    def test_10_unsupported_kind_is_deferred_without_tool(self):
        bad_task = IntentSubtask(id="ask", kind=TaskKind.CLARIFICATION_REQUIRED, user_goal="补充条件")
        out = self.execute(decision(eng(), bad_task))
        self.assertIn("DEFERRED", [x["state"] for x in out["subtasks"]])

    def test_11_subtasks_persist_after_execution(self):
        self.execute(decision(eng(), IntentSubtask(id="general",
            kind=TaskKind.GENERAL_EXPLANATION, user_goal="概念解释")))
        rows = self.ledger.get_subtasks(self.rid)
        self.assertEqual(rows[0]["state"], "SUCCEEDED")
        self.assertTrue(rows[0]["result_digest"])

    def test_12_successful_subtask_replays_without_candidate_reexecution(self):
        d = decision(eng(), IntentSubtask(id="general",
            kind=TaskKind.GENERAL_EXPLANATION, user_goal="概念解释"))
        self.execute(d)
        self.assertEqual(self.candidate.calls, 1)
        replay = self.execute(d)
        self.assertEqual(self.candidate.calls, 1)
        self.assertEqual(replay["subtasks"][0]["state"], "SUCCEEDED")

    def test_13_dependencies_are_enforced(self):
        d = decision(eng(), IntentSubtask(id="summary", kind=TaskKind.WRITING_SYNTHESIS,
                           user_goal="综合", depends_on=["eng"]))
        self.candidate.fail = True
        out = self.execute(d)
        self.assertEqual(out["subtasks"][1]["state"], "SKIPPED")

    def test_14_cycle_is_rejected(self):
        with self.assertRaises(ValueError):
            decision(eng("a", depends_on=["b"]),
                     IntentSubtask(id="b",kind=TaskKind.GENERAL_EXPLANATION,
                                   user_goal="b",depends_on=["a"]))

    def test_15_route_must_be_mixed(self):
        d = decision(eng(), IntentSubtask(id="g",kind=TaskKind.GENERAL_EXPLANATION,user_goal="g"))
        d.primary_route = MainRoute.ENGINEERING
        with self.assertRaises(MixedDAGError):
            self.execute(d)

    def test_16_unknown_dependency_rejected(self):
        with self.assertRaises(ValueError):
            decision(eng("a",depends_on=["missing"]),
                     IntentSubtask(id="b",kind=TaskKind.GENERAL_EXPLANATION,user_goal="b"))

    def test_17_task_count_is_bounded_to_four(self):
        tasks = [IntentSubtask(id=f"t{i}",kind=TaskKind.GENERAL_EXPLANATION,user_goal="x") for i in range(5)]
        with self.assertRaises(ValueError):
            decision(*tasks)

    def test_18_write_synthesis_does_not_claim_risk_grade(self):
        out = self.execute(decision(eng(), IntentSubtask(id="summary",
            kind=TaskKind.WRITING_SYNTHESIS, user_goal="总结", depends_on=["eng"])))
        self.assertNotIn("risk_level", out["subtasks"][1]["result"])

    def test_19_untrusted_tool_payload_is_not_used_as_fact(self):
        self.executor.standard_tool = lambda **kw: {"status":"ok","in_domain":True,
            "result":{"risk_level":"HIGH","conclusion":"设备危险"},
            "source":[{"clause_id":"C-1","standard_code":"GB/T-X","clause_no":"4.1","page":12}],
            "message":"fixture"}
        out = self.execute(decision(
            IntentSubtask(id="std",kind=TaskKind.STANDARD_LOOKUP,user_goal="查询"),
            eng("eng",depends_on=["std"])))
        self.assertNotIn("HIGH", out["final_text"])
        self.assertNotIn("设备危险", out["final_text"])

    def test_20_subtask_attempts_are_bounded_after_repeated_failure(self):
        first = self.ledger.begin_subtask(run_id=self.rid, subtask_id="bounded",
            kind="GENERAL_EXPLANATION", goal="bounded", dependencies=[], max_attempts=2)
        self.assertEqual(first["attempt_count"], 1)
        self.ledger.finish_subtask(run_id=self.rid, subtask_id="bounded", state="FAILED",
                                  result={"status":"failed"}, error="failure1")
        second = self.ledger.begin_subtask(run_id=self.rid, subtask_id="bounded",
            kind="GENERAL_EXPLANATION", goal="bounded", dependencies=[], max_attempts=2)
        self.assertEqual(second["attempt_count"], 2)
        self.ledger.finish_subtask(run_id=self.rid, subtask_id="bounded", state="FAILED",
                                  result={"status":"failed"}, error="failure2")
        third = self.ledger.begin_subtask(run_id=self.rid, subtask_id="bounded",
            kind="GENERAL_EXPLANATION", goal="bounded", dependencies=[], max_attempts=2)
        self.assertTrue(third["replayed"])
        self.assertEqual(third["state"], "FAILED")
        self.assertEqual(third["attempt_count"], 2)

    def test_21_candidate_fourth_tool_is_rejected_and_risk_grade_clamped(self):
        self.candidate.run = lambda *args, **kwargs: {"output": {
            "status":"exploratory","citations":[{"clause_id":"C-1"}],
            "candidates":[],"unknowns":[],"risk_level":"HIGH",
            "tool_calls":[{"tool":"upload_and_execute","arguments":{}}]}}
        out = self.execute(decision(eng(), IntentSubtask(id="summary",
            kind=TaskKind.WRITING_SYNTHESIS,user_goal="只综合",depends_on=["eng"])))
        self.assertEqual(out["subtasks"][0]["state"], "FAILED")
        self.assertEqual(out["subtasks"][1]["state"], "SKIPPED")
        self.assertNotIn("HIGH", out["final_text"])

    def test_22_transform_only_does_not_dispatch_engineering(self):
        route, safety, tasks, _ = LocalIntentPolicy().analyze("只翻译这份报告，不做设备研判")
        self.assertEqual(route, MainRoute.GENERAL)
        self.assertFalse(safety)
        self.assertFalse(any(task.kind in {TaskKind.MECHANISM_EXPLORATION,
            TaskKind.DEVICE_DIAGNOSIS, TaskKind.RBI_ASSESSMENT} for task in tasks))

    def test_23_risk_level_response_is_clamped_when_inputs_are_incomplete(self):
        out = self.execute(decision(eng(), IntentSubtask(id="general",
            kind=TaskKind.GENERAL_EXPLANATION,user_goal="解释概念")))
        engineering = next(row for row in out["subtasks"] if row["id"] == "eng")
        self.assertIsNone(engineering["result"]["risk_level"])
        self.assertNotIn("L1", out["final_text"])

    def test_24_standard_tool_message_cannot_add_a_field_conclusion(self):
        self.executor.standard_tool = lambda **kw: {"status":"ok","in_domain":True,
            "result":{"conclusion":"设备已经安全无风险"},"source":[
                {"clause_id":"C-1","standard_code":"GB/T-X","clause_no":"4.1","page":12}],
            "message":"设备已经安全无风险"}
        out = self.execute(decision(
            IntentSubtask(id="std",kind=TaskKind.STANDARD_LOOKUP,user_goal="查询条款"),
            IntentSubtask(id="summary",kind=TaskKind.WRITING_SYNTHESIS,
                user_goal="只整理条文定位",depends_on=["std"])))
        self.assertNotIn("安全无风险", out["final_text"])
        self.assertIn("待核", out["final_text"])

    def test_25_independent_process_mixed_dag_recovers_after_tool_result_commit(self):
        self.assertTrue(self.store.claim_run(self.rid, "worker-dead"))
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT)
        child_args = [sys.executable, "-c", _MIXED_RECOVERY_CHILD, str(self.db),
                      str(self.counter), self.cid, self.rid, "crash"]
        crashed = subprocess.run(child_args, cwd=ROOT, env=env, text=True,
                                  capture_output=True, timeout=30, check=False)
        self.assertEqual(crashed.returncode, 89, crashed.stderr)
        self.assertEqual(self.counter.read_text(encoding="utf-8").count("called"), 1)
        old = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(timespec="milliseconds")
        with self.store.session() as con:
            con.execute("UPDATE runs SET worker_heartbeat_at=? WHERE id=?", (old, self.rid))
        child_args[-1] = "recover"
        recovered = subprocess.run(child_args, cwd=ROOT, env=env, text=True,
                                   capture_output=True, timeout=30, check=False)
        self.assertEqual(recovered.returncode, 0, recovered.stderr)
        summary = json.loads(recovered.stdout.strip().splitlines()[-1])
        self.assertEqual(summary["status"], "completed")
        self.assertEqual(summary["tool_calls"], 1)
        self.assertEqual(summary["ledger"], "SUCCEEDED")
        self.assertEqual(self.counter.read_text(encoding="utf-8").count("called"), 1)
        self.assertEqual(len([m for m in self.store.messages(self.cid) if m["role"] == "assistant"]), 1)


if __name__ == "__main__":
    unittest.main()
