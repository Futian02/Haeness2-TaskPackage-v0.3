"""Owner read-only-to-project local API performance probe.

Exercises real TestClient→FastAPI→worker→LangGraph→teacher-tool→SQLite→SSE
in a disposable temp directory. Does not benchmark browser or external LLM.
Run: ./.venv-langgraph/Scripts/python.exe -B -m evals.owner_p7_fullstack_latency
"""
from __future__ import annotations
import json
import statistics
import tempfile
import time
from pathlib import Path
from threading import Lock
from unittest.mock import patch

from fastapi.testclient import TestClient
import backend.api as api
from backend.store import Store
from orchestration.graph import AgentGraph

class TimedGraph:
    def __init__(self, path: Path):
        self.impl = AgentGraph(checkpoint_path=path)
        self.timings = []
        self.lock = Lock()
    def run(self, state, emit):
        t = time.perf_counter()
        try:
            return self.impl.run(state, emit)
        finally:
            with self.lock:
                self.timings.append((state.run_id, (time.perf_counter()-t)*1000))

def stats(xs):
    vals = sorted(xs)
    return {"n":len(vals),"p50_ms":round(statistics.median(vals),2),
            "p95_nearest_rank_ms":round(vals[max(0,__import__('math').ceil(.95*len(vals))-1)],2),
            "min_ms":round(vals[0],2),"max_ms":round(vals[-1],2)}

def main():
    scenarios = [
      ("missing_context",{"question":"现场观察铁离子升高，尚未测厚，是否有风险？"}),
      ("full_context",{"question":"塔顶水样pH5.8，铁离子4.1mg/L，尚未测厚，可能的损伤机理？","material":"碳钢","medium":["氯化氢"],"equipment_type":"换热器","field_evidence":"pH 5.8，铁离子4.1mg/L，尚未测厚"}),
      ("standard_search",{"question":"请检索关于氯化铵腐蚀的标准条款并展示来源"}),
    ]
    with tempfile.TemporaryDirectory(prefix="owner-real-stack-metrics-") as temp:
        root=Path(temp)
        store=Store(root/"audit.sqlite3")
        graph=TimedGraph(root/"graph-checkpoints.sqlite3")
        results={}
        with patch.object(api,"store",store),patch.object(api,"graph",graph):
            with TestClient(api.app) as client:
                for label, req in scenarios:
                    rows=[]
                    for i in range(8):
                        c=client.post("/api/conversations",json={"title":f"{label}-{i}"}).json()
                        t0=time.perf_counter()
                        start=client.post(f"/api/conversations/{c['id']}/runs",json=req)
                        assert start.status_code==200,(label,start.status_code,start.text)
                        url=start.json()["events_url"]
                        t1=time.perf_counter()
                        stream=client.get(url)
                        t2=time.perf_counter()
                        assert stream.status_code==200,(label,stream.status_code,stream.text[:150])
                        rid=start.json()["run_id"]
                        state=store.run(rid)
                        evs=store.events(rid)
                        assert state["status"]=="completed",(label,state)
                        assert len(store.messages(c["id"]))==2,(label,rid)
                        counts={}
                        for event in evs: counts[event["type"]]=counts.get(event["type"],0)+1
                        tool_results=[e for e in evs if e["type"]=="tool_result"]
                        rows.append({"post_ms":(t1-t0)*1000,"stream_ms":(t2-t1)*1000,
                           "total_ms":(t2-t0)*1000,"events":len(evs),"tools":len(tool_results),
                           "claims":len(store.claims(rid)),
                           "sse_frames":stream.text.count("data: ")})
                    results[label]={
                      "post":stats([r["post_ms"] for r in rows]),
                      "sse_consumption":stats([r["stream_ms"] for r in rows]),
                      "post_to_stream_terminal":stats([r["total_ms"] for r in rows]),
                      "events_minmax":[min(r["events"] for r in rows),max(r["events"] for r in rows)],
                      "teacher_tool_results_minmax":[min(r["tools"] for r in rows),max(r["tools"] for r in rows)],
                      "claim_count_minmax":[min(r["claims"] for r in rows),max(r["claims"] for r in rows)],
                      "all_sse_frames_exactly_equal_db":all(r["sse_frames"]==r["events"] for r in rows)
                    }
        byrun={rid:ms for rid,ms in graph.timings}
        results["graph_worker_run"]=stats(list(byrun.values()))
        with store.session() as con:
            integrity=con.execute("PRAGMA integrity_check").fetchone()[0]
            foreign=con.execute("PRAGMA foreign_key_check").fetchall()
            journal=con.execute("PRAGMA journal_mode").fetchone()[0]
            tables=[r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
            runs=con.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
        results["database"]={"integrity_check":integrity,"foreign_key_violations":len(foreign),
            "journal_mode":journal,"tables":tables,"runs":runs}
        results["boundary"]="Temp SQLite/TestClient local same-process; no browser/HTTP network LLM/ModelScope; cold imports excluded"
        print(json.dumps(results,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
