"""S2.5 independent-process fencing tests; temporary SQLite and offline fixtures only."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from backend.execution_ledger import LedgerUnavailable, SQLiteExecutionLedger
from backend.store import Store

ROOT = Path(__file__).resolve().parents[1]
CHILD = r'''
import os, sys, time
from pathlib import Path
from backend.execution_ledger import SQLiteExecutionLedger

db,cid,rid,started,release,counter,kind=sys.argv[1:]
ledger=SQLiteExecutionLedger(db)
def action():
    Path(counter).open("a",encoding="utf-8").write("called\\n")
    Path(started).write_text("active",encoding="utf-8")
    deadline=time.monotonic()+15
    while not Path(release).exists() and time.monotonic()<deadline:
        time.sleep(.02)
    return {"status":"returned","attempts":1,"envelope":{"status":"not_found","in_domain":True,"result":{},"source":[],"message":"test"}}
if kind=="action":
    ledger.execute_tool(conversation_id=cid,run_id=rid,subtask_id="eng",step_id="t1",
        tool_name="standard_clause_search",args={"keyword":"case"},action=action)
elif kind=="subtask":
    ledger.begin_subtask(run_id=rid,subtask_id="s1",kind="GENERAL_EXPLANATION",goal="case",dependencies=[])
    Path(started).write_text("active",encoding="utf-8")
    deadline=time.monotonic()+15
    while not Path(release).exists() and time.monotonic()<deadline:
        time.sleep(.02)
    ledger.finish_subtask(run_id=rid,subtask_id="s1",state="SUCCEEDED",result={"status":"complete"})
'''

class LeaseFencingIndependentProcessTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="aether-s25-fence-")
        self.root=Path(self.temp.name)
        self.store=Store(self.root/"fence.sqlite3")
        self.cid=self.store.create_conversation("fence")["id"]
        self.rid=self.store.create_run(self.cid,"offline",{},"V2_AGENTIC")["id"]
        self.ledger=SQLiteExecutionLedger(self.store.path)
        self.started=self.root/"started.flag"
        self.release=self.root/"release.flag"
        self.counter=self.root/"counter.txt"

    def tearDown(self):
        self.temp.cleanup()

    def _start(self,kind):
        env=os.environ.copy()
        env["PYTHONPATH"]=str(ROOT)
        proc=subprocess.Popen([sys.executable,"-c",CHILD,str(self.store.path),
            self.cid,self.rid,str(self.started),str(self.release),str(self.counter),kind],
            cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        deadline=time.monotonic()+8
        while not self.started.exists() and time.monotonic()<deadline and proc.poll() is None:
            time.sleep(.025)
        self.assertTrue(self.started.exists(), "child did not start: "+str(proc.poll()))
        return proc

    def _finish(self,proc):
        self.release.write_text("release",encoding="utf-8")
        _,err=proc.communicate(timeout=15)
        self.assertEqual(proc.returncode,0,err)

    def test_live_action_owner_is_not_taken_over_by_second_process(self):
        child=self._start("action")
        try:
            with self.assertRaises(LedgerUnavailable):
                self.ledger.execute_tool(conversation_id=self.cid,run_id=self.rid,
                    subtask_id="eng",step_id="t1",tool_name="standard_clause_search",
                    args={"keyword":"case"},action=lambda: {"status":"returned"})
            self._finish(child)
            result,replayed,delta=self.ledger.execute_tool(conversation_id=self.cid,
                run_id=self.rid,subtask_id="eng",step_id="t1",
                tool_name="standard_clause_search",args={"keyword":"case"},
                action=lambda: {"status":"error"})
            self.assertTrue(replayed)
            self.assertEqual(delta,0)
            self.assertEqual(self.counter.read_text(encoding="utf-8").count("called"),1)
            self.assertEqual(self.ledger.get_action(run_id=self.rid,subtask_id="eng",step_id="t1")["attempt_count"],1)
        finally:
            self.release.touch(exist_ok=True)
            if child.poll() is None:
                child.kill()
                child.wait(timeout=5)

    def test_live_subtask_cannot_be_marked_uncertain(self):
        child=self._start("subtask")
        try:
            with self.assertRaises(LedgerUnavailable):
                self.ledger.begin_subtask(run_id=self.rid,subtask_id="s1",
                    kind="GENERAL_EXPLANATION",goal="case",dependencies=[])
            self.assertEqual(self.ledger.get_subtasks(self.rid)[0]["state"],"RUNNING")
            self._finish(child)
            result=self.ledger.begin_subtask(run_id=self.rid,subtask_id="s1",
                kind="GENERAL_EXPLANATION",goal="case",dependencies=[])
            self.assertTrue(result["replayed"])
            self.assertEqual(result["state"],"SUCCEEDED")
        finally:
            self.release.touch(exist_ok=True)
            if child.poll() is None:
                child.kill()
                child.wait(timeout=5)


if __name__=="__main__":
    unittest.main()
