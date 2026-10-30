"""Owner P13 offline API/SSE/Graph end-to-end stress.
24 synthetic requests, isolated temporary SQLite, RULE_DEMO only.
No provider key read, network calls, user DB access, deployment or core edits.
"""
from __future__ import annotations
import json
import os
import statistics
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Lock
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend import api
from backend.store import Store

def main(total=24,concurrency=4):
    with tempfile.TemporaryDirectory(prefix="owner-api-graph-") as tmp:
        st=Store(Path(tmp)/"owner_api.sqlite")
        errors=[]
        latencies=[]
        lock=Lock()
        with patch.dict(os.environ,{"APP_ENV":"development"}),patch.object(api,"store",st),patch.object(api.model_profiles,"safe_profile",return_value=None):
            with TestClient(api.app) as client:
                cid=client.post("/api/conversations",json={"title":"owner stress"}).json()["id"]
                def run(i):
                    start=time.perf_counter()
                    queries=[
                        "你好，请介绍一下你可以做什么？",
                        "GB/T 26610.3-2014 失效可能性与后果风险矩阵有什么条款？",
                        "设备为碳钢换热器，介质氯化氢，温度95℃，可能有什么损伤机理？",
                    ]
                    q=queries[i%3]
                    try:
                        res=client.post(f"/api/conversations/{cid}/runs",json={"question":q,"mode":"RULE_DEMO","web_mode":"off"})
                        if res.status_code!=200:raise AssertionError(f"POST HTTP {res.status_code}")
                        j=res.json()
                        s=client.get(j["events_url"])
                        if s.status_code!=200:raise AssertionError(f"GET SSE {s.status_code}")
                        rid=j["run_id"]
                        current=st.run(rid)
                        if current["status"] not in {"completed","failed"}:raise AssertionError(f"run open {current['status']}")
                        events=st.events(rid)
                        seq=[e["sequence"]for e in events]
                        if seq!=list(range(1,len(seq)+1)):raise AssertionError("SSE event sequence gap")
                        terminals=[e for e in events if e["type"]in ("run_completed","run_failed")]
                        if len(terminals)!=1:raise AssertionError("terminal not unique")
                        if st.events(rid,after_sequence=seq[-1]):raise AssertionError("replay after terminal nonempty")
                        if not events or "context_resolved" not in {e["type"] for e in events}:raise AssertionError("context event missing")
                        if current["status"]=="completed":
                            assistant=[m for m in st.messages(cid) if m["run_id"]==rid and m["role"]=="assistant"]
                            if len(assistant)!=1 or not assistant[0]["content"]:raise AssertionError("missing answer")
                        with lock:latencies.append((time.perf_counter()-start)*1000)
                    except Exception as exc:
                        with lock:errors.append({"i":i,"type":type(exc).__name__,"msg":str(exc)[:170]})
                begin=time.perf_counter()
                with ThreadPoolExecutor(max_workers=concurrency) as pool:list(pool.map(run,range(total)))
                ms=(time.perf_counter()-begin)*1000
                with st.session() as db:
                    rows=db.execute("SELECT status,COUNT(*) FROM runs GROUP BY status").fetchall()
                    status={r[0]:r[1] for r in rows}
                vals=sorted(latencies)
                result={"attempted":total,"parallelism":concurrency,"success_results":len(latencies),
                        "api_failures":len(errors),"run_status":status,
                        "p50_ms":round(statistics.median(vals),2) if vals else None,
                        "p95_ms":round(vals[min(len(vals)-1,int((len(vals)-1)*.95))],2) if vals else None,
                        "max_ms":round(max(vals),2) if vals else None,
                        "total_batch_ms":round(ms,2),"errors":errors[:6]}
                print("OWNER_REAL_GRAPH_API_SSE "+json.dumps(result,ensure_ascii=False),flush=True)
                assert len(errors)==0 and len(latencies)==total and status.get("completed")==total
if __name__=="__main__":main()
