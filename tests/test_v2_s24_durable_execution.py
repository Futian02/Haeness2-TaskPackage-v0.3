"""S2.4 Gate 1: independent-process crash/restart tests for durable read-only actions."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend.execution_ledger import LedgerConflict, SQLiteExecutionLedger
from backend.store import Store

ROOT = Path(__file__).resolve().parents[1]
_CHILD = r"""
import json, os, sys
from backend.execution_ledger import SQLiteExecutionLedger
db, counter, mode, cid, rid = sys.argv[1:]
ledger = SQLiteExecutionLedger(db)
def action():
    with open(counter, 'a', encoding='utf-8') as f:
        f.write('called\n')
    return {'status':'returned','attempts':1,'envelope':{
        'status':'ok','in_domain':True,'result':{'hits':[]},
        'source':[{'clause_id':'T-1'}],'message':'fixture'}}
def die_after_external_result(_result):
    os._exit(73)
kwargs = dict(conversation_id=cid, run_id=rid, subtask_id='engineering',
              step_id='tool:1', tool_name='standard_clause_search',
              args={'keyword':'fixture','top_k':3}, action=action, max_attempts=2)
if mode == 'crash_after_external_result':
    ledger.execute_tool(**kwargs, crash_hook=die_after_external_result)
else:
    result, replayed, delta = ledger.execute_tool(**kwargs)
    print(json.dumps({'replayed':replayed,'attempt_delta':delta,'result':result}, ensure_ascii=False))
"""


_CANDIDATE_CHILD = r"""
import json, os, sys
from datetime import datetime, timedelta, timezone
from backend.execution_ledger import SQLiteExecutionLedger
from backend.store import Store
from backend.agentic_provider import ScriptedFakePlanner
from langgraph.checkpoint.sqlite import SqliteSaver
from orchestration.agentic_v2 import AgenticV2Candidate

db, counter, cid, rid, mode = sys.argv[1:]
store = Store(db)
def tool(**kwargs):
    with open(counter, 'a', encoding='utf-8') as f:
        f.write('called\\n')
    if mode == 'crash_inside_tool':
        os._exit(78)
    return {'status':'not_found','in_domain':True,'result':{},'source':[],'message':'offline fixture'}
tools = {name: tool for name in ('damage_mechanism_query','rbi_lookup','standard_clause_search')}
planner = ScriptedFakePlanner(
    default_plan={'action':'call_tool','tool_name':'standard_clause_search','query':'换热器裂纹',
      'tool_arguments':{'keyword':'换热器裂纹','knowledge_type':'damage_mechanism','top_k':5},
      'investigation_goal':'只读恢复测试','evidence_gap':'','public_rationale':'Mock计划',
      'focus_clause_ids':[]},
    default_reflection={'continue_investigation':False,'next_evidence_gap':'','public_rationale':'结束'})
if mode in ('start','crash_inside_tool'):
    assert store.claim_run(rid, 'worker-dead')
elif mode == 'recover':
    assert store.recover_stale_v2_run(rid, stale_after_seconds=0)
    assert store.claim_run(rid, 'worker-recovered')
ledger = SQLiteExecutionLedger(db)
with SqliteSaver.from_conn_string(db) as saver:
    candidate = AgenticV2Candidate(planner=planner, tool_registry=tools, clause_index={},
      enum_sets={'material':set(),'medium':set(),'equipment_type':set()},
      replay_ledger=ledger, checkpointer=saver, tool_timeout_seconds=2)
    result = candidate.run('换热器裂纹可能的损伤机理？', {}, run_id=rid, thread_id=cid)
if mode == 'start':
    os._exit(77)  # tool result/checkpoint committed; kill before run terminal/message commit
if mode == 'crash_inside_tool':
    raise AssertionError('os._exit in the external tool should have terminated this process')
assert store.finish_run_with_message(rid, 'worker-recovered',
    json.dumps(result['output'], ensure_ascii=False),
    {'status':'completed','route_execution':'test_only_recovery'})
print(json.dumps({'status':store.run(rid)['status'],
  'assistant_count':len([m for m in store.messages(cid) if m['role']=='assistant']),
  'ledger':ledger.get_action(run_id=rid,subtask_id='engineering',step_id='tool:1')['state']}))
"""

class DurableExecutionLedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="aether-s24-ledger-")
        self.root = Path(self.temp.name)
        self.db = self.root / "s24.sqlite3"
        self.store = Store(self.db)
        self.cid = self.store.create_conversation("S2.4 durable ledger")["id"]
        self.rid = self.store.create_run(self.cid, "只读工具故障注入", {}, "V2_AGENTIC")["id"]
        self.counter = self.root / "tool-calls.txt"

    def tearDown(self):
        self.temp.cleanup()

    def _child(self, mode: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT)
        return subprocess.run([sys.executable, "-c", _CHILD,
                               str(self.db), str(self.counter), mode, self.cid, self.rid],
                              cwd=ROOT, env=env, text=True, capture_output=True,
                              timeout=20, check=False)

    def _calls(self) -> int:
        return self.counter.read_text(encoding="utf-8").count("called") if self.counter.exists() else 0

    def _candidate_worker(self, mode: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT)
        return subprocess.run([sys.executable, "-c", _CANDIDATE_CHILD, str(self.db),
                               str(self.counter), self.cid, self.rid, mode],
                              cwd=ROOT, env=env, text=True, capture_output=True,
                              timeout=40, check=False)

    def _expire_lease(self):
        old = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(timespec="milliseconds")
        with self.store.session() as con:
            con.execute("UPDATE runs SET worker_heartbeat_at=? WHERE id=?", (old, self.rid))

    def test_candidate_worker_restart_after_committed_tool_result_does_not_repeat_or_duplicate_reply(self):
        first = self._candidate_worker("start")
        self.assertEqual(first.returncode, 77, first.stderr)
        self.assertEqual(self._calls(), 1)
        self.assertEqual(self.store.run(self.rid)["status"], "running")
        self._expire_lease()
        recovered = self._candidate_worker("recover")
        self.assertEqual(recovered.returncode, 0, recovered.stderr)
        summary = json.loads(recovered.stdout.strip().splitlines()[-1])
        self.assertEqual(summary["status"], "completed")
        self.assertEqual(summary["assistant_count"], 1)
        self.assertEqual(summary["ledger"], "SUCCEEDED")
        self.assertEqual(self._calls(), 1)

    def test_candidate_worker_crash_inside_tool_is_uncertain_and_retries_read_only_once(self):
        crashed = self._candidate_worker("crash_inside_tool")
        self.assertEqual(crashed.returncode, 78, crashed.stderr)
        self.assertEqual(self._calls(), 1)
        self._expire_lease()
        recovered = self._candidate_worker("recover")
        self.assertEqual(recovered.returncode, 0, recovered.stderr)
        summary = json.loads(recovered.stdout.strip().splitlines()[-1])
        self.assertEqual(summary["status"], "completed")
        self.assertEqual(summary["assistant_count"], 1)
        self.assertEqual(summary["ledger"], "SUCCEEDED")
        self.assertEqual(self._calls(), 2)
        action = SQLiteExecutionLedger(self.db).get_action(
            run_id=self.rid, subtask_id="engineering", step_id="tool:1")
        self.assertIn("UNCERTAIN", [row["state"] for row in action["transitions"]])
        self.assertEqual(action["attempt_count"], 2)

    def test_committed_result_replays_across_process_without_second_tool_call(self):
        # Child process 1 commits the result then exits. A new interpreter opens
        # the same SQLite file and must return the ledger value, not call action.
        first = self._child("commit")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(self._calls(), 1)
        second = self._child("commit")
        self.assertEqual(second.returncode, 0, second.stderr)
        response = json.loads(second.stdout.strip().splitlines()[-1])
        self.assertTrue(response["replayed"])
        self.assertEqual(response["attempt_delta"], 0)
        self.assertEqual(self._calls(), 1)
        ledger = SQLiteExecutionLedger(self.db)
        action = ledger.get_action(run_id=self.rid, subtask_id="engineering", step_id="tool:1")
        self.assertEqual(action["state"], "SUCCEEDED")
        self.assertEqual(action["attempt_count"], 1)
        self.assertTrue(action["result_digest"])
        self.assertTrue(action["source_digest"])
        self.assertNotIn("fixture", action["args_json"])
        self.assertIn('"keyword"', action["args_json"])

    def test_process_crash_after_read_only_call_marks_uncertain_then_audits_retry(self):
        crashed = self._child("crash_after_external_result")
        self.assertEqual(crashed.returncode, 73, crashed.stderr)
        self.assertEqual(self._calls(), 1)
        ledger = SQLiteExecutionLedger(self.db)
        started = ledger.get_action(run_id=self.rid, subtask_id="engineering", step_id="tool:1")
        self.assertEqual(started["state"], "STARTED")
        self.assertEqual(started["attempt_count"], 1)

        recovered = self._child("commit")
        self.assertEqual(recovered.returncode, 0, recovered.stderr)
        response = json.loads(recovered.stdout.strip().splitlines()[-1])
        self.assertFalse(response["replayed"])
        self.assertEqual(response["attempt_delta"], 1)
        self.assertEqual(self._calls(), 2)  # allowed read-only re-query, not physical exactly-once
        action = ledger.get_action(run_id=self.rid, subtask_id="engineering", step_id="tool:1")
        states = [event["state"] for event in action["transitions"]]
        self.assertIn("UNCERTAIN", states)
        self.assertEqual(action["state"], "SUCCEEDED")
        self.assertEqual(action["attempt_count"], 2)

    def test_stable_action_identity_rejects_different_arguments_and_isolates_run(self):
        ledger = SQLiteExecutionLedger(self.db)
        action = lambda: {"status": "returned", "envelope": {"source": []}}
        ledger.execute_tool(conversation_id=self.cid, run_id=self.rid, subtask_id="engineering",
                            step_id="step-1", tool_name="standard_clause_search",
                            args={"keyword": "A"}, action=action)
        with self.assertRaises(LedgerConflict):
            ledger.execute_tool(conversation_id=self.cid, run_id=self.rid, subtask_id="engineering",
                                step_id="step-1", tool_name="standard_clause_search",
                                args={"keyword": "B"}, action=action)
        other_run = self.store.create_run(self.cid, "other", {}, "V2_AGENTIC")["id"]
        result, replayed, _ = ledger.execute_tool(conversation_id=self.cid, run_id=other_run,
                            subtask_id="engineering", step_id="step-1",
                            tool_name="standard_clause_search", args={"keyword": "A"}, action=action)
        self.assertFalse(replayed)
        self.assertFalse(result.get("_ledger_replayed", True))

    def test_same_run_action_cannot_be_replayed_across_conversations(self):
        ledger = SQLiteExecutionLedger(self.db)
        action = lambda: {"status":"returned","envelope":{"source":[]}}
        ledger.execute_tool(conversation_id=self.cid, run_id=self.rid, subtask_id="engineering",
            step_id="scope-check", tool_name="standard_clause_search", args={"keyword":"fixture"},
            action=action)
        other_cid = self.store.create_conversation("different conversation")["id"]
        with self.assertRaises(LedgerConflict):
            ledger.execute_tool(conversation_id=other_cid, run_id=self.rid, subtask_id="engineering",
                step_id="scope-check", tool_name="standard_clause_search", args={"keyword":"fixture"},
                action=action)

    def test_expired_v2_lease_is_requeued_and_audited_only_in_temp_db(self):
        token = "worker-dead"
        self.assertTrue(self.store.claim_run(self.rid, token))
        old = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(timespec="milliseconds")
        with self.store.session() as con:
            con.execute("UPDATE runs SET worker_heartbeat_at=? WHERE id=?", (old, self.rid))
        self.assertTrue(self.store.recover_stale_v2_run(self.rid, stale_after_seconds=20))
        run = self.store.run(self.rid)
        self.assertEqual(run["status"], "queued")
        events = self.store.events(self.rid)
        self.assertEqual(events[-1]["type"], "run_recovery_queued")
        self.assertFalse(self.store.recover_stale_v2_run(self.rid, stale_after_seconds=20))


if __name__ == "__main__":
    unittest.main()
