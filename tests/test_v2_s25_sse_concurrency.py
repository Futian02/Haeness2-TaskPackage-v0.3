"""Concurrent SSE/runs regression in an isolated SQLite database (no live LLM)."""
from __future__ import annotations

import json
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from backend import api
from backend.store import Store


class _CountingCandidate:
    def __init__(self):
        self.calls = []
        self.lock = threading.Lock()

    def run(self, question, context, *, run_id, thread_id, subtask_id="engineering"):
        with self.lock:
            self.calls.append((run_id, thread_id))
        time.sleep(0.1)
        return {"output": {"status": "unresolved", "candidates": [], "unknowns": ["material"],
                "citations": [], "tool_calls": [], "events": [], "risk_level": None,
                "review": {"status": "needs_human_review"}}}


class DoubleSSEAndRunTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="aether-s25-sse-")
        self.store = Store(Path(self.tmp.name)/"sse.sqlite3")
        self.patches = [patch.object(api, "store", self.store),
                        patch.object(api, "AETHER_V2_AGENTIC_ENABLED", True)]
        for p in self.patches:
            p.start()
        self.candidate = _CountingCandidate()
        self.candidate_patch = patch.object(api, "_get_agentic_v2_candidate", return_value=self.candidate)
        self.candidate_patch.start()
        self.client = TestClient(api.app)

    def tearDown(self):
        self.client.close()
        self.candidate_patch.stop()
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    def create(self, conversation_id=None):
        cid = conversation_id or self.client.post("/api/conversations",json={"title":"S2.5 load"}).json()["id"]
        r=self.client.post(f"/api/conversations/{cid}/runs",
            json={"question":"换热器裂纹可能有哪些损伤机理？","mode":"V2_AGENTIC"})
        self.assertEqual(r.status_code,200,r.text)
        return cid,r.json()["run_id"],r.json()["events_url"]

    def test_two_sse_clients_same_run_have_one_worker_and_ordered_replay(self):
        cid,rid,url=self.create()
        with ThreadPoolExecutor(max_workers=2) as ex:
            responses=list(ex.map(lambda _:self.client.get(url),range(2)))
        self.assertTrue(all(x.status_code==200 for x in responses))
        self.assertEqual([x[0] for x in self.candidate.calls].count(rid),1)
        self.assertEqual(self.store.run(rid)["status"],"completed")
        full=self.client.get(f"/api/runs/{rid}/events").json()["events"]
        seq=[x["sequence"] for x in full]
        self.assertEqual(seq,list(range(1,len(seq)+1)))
        self.assertEqual(sum(x["type"]=="run_completed" for x in full),1)
        replies=[m for m in self.store.messages(cid) if m.get("role")=="assistant" and m.get("run_id")==rid]
        self.assertEqual(len(replies),1)
        midpoint=seq[len(seq)//2]
        tail=self.client.get(f"/api/runs/{rid}/events?after_sequence={midpoint}").json()["events"]
        self.assertEqual([x for x in full if x["sequence"]>midpoint],tail)

    def test_two_runs_same_and_different_conversation_remain_isolated(self):
        c1,r1,u1=self.create()
        _,r2,u2=self.create(c1)
        c2,r3,u3=self.create()
        with ThreadPoolExecutor(max_workers=3) as ex:
            results=list(ex.map(self.client.get,[u1,u2,u3]))
        self.assertTrue(all(x.status_code==200 for x in results))
        for rid,cid in ((r1,c1),(r2,c1),(r3,c2)):
            self.assertEqual(self.store.run(rid)["status"],"completed")
            self.assertEqual(len([x for x in self.store.messages(cid)
                                  if x.get("role")=="assistant" and x.get("run_id")==rid]),1)
        self.assertEqual(len(self.candidate.calls),3)
        self.assertEqual(set(self.store.run(r)["conversation_id"] for r in (r1,r2)),{c1})
        self.assertEqual(self.store.run(r3)["conversation_id"],c2)


if __name__=="__main__":
    unittest.main()
