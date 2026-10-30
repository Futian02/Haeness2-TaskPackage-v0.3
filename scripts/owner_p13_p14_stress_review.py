"""Independent Owner P13 mixed-outcome SQLite race/replay stress.
Isolated TemporaryDirectory only; no production DB, no provider or web calls.
Run via python -B -m scripts.owner_p13_p14_stress_review
"""
from __future__ import annotations
import json
import statistics
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Lock
from backend.store import Store

def pct(xs,part):
    seq=sorted(xs)
    return round(seq[min(len(seq)-1, int((len(seq)-1)*part))],2)

def run_group(size=120, concurrency=8):
    with tempfile.TemporaryDirectory(prefix=f"owner-mixed-{concurrency}-") as tmp:
        st=Store(Path(tmp)/"test.sqlite")
        cid=st.create_conversation("owner-mixed-stream")["id"]
        timings=[]
        failures=[]
        lock=Lock()
        def one(i):
            start=time.perf_counter()
            try:
                rec=st.create_run_with_message(cid,f"case {i}",{"web_mode":"off","test_only":True},"RULE_DEMO",[])
                rid=rec["id"]
                token=f"worker-{i}"
                if not st.claim_run(rid,token):raise AssertionError("claim rejected")
                if st.claim_run(rid,token+"-stale"):raise AssertionError("duplicate claim accepted")
                st.append_event(rid,"agent_started","supervisor",{"step":i},worker_token=token)
                if i%5==0:
                    if not st.finish_run(rid,token,"failed","synthetic_error"):raise AssertionError("failed finish rejected")
                    want_status="failed"
                    terminal="run_failed"
                else:
                    if not st.finish_run_with_message(rid,token,f"response-{i}",{"case":i}):raise AssertionError("complete finish rejected")
                    want_status="completed"
                    terminal="run_completed"
                events=st.events(rid)
                if [e["sequence"]for e in events]!=[1,2]:raise AssertionError("event seq")
                if events[-1]["type"]!=terminal:raise AssertionError("wrong terminal")
                if [e["sequence"]for e in st.events(rid,after_sequence=1)]!=[2]:raise AssertionError("replay offset")
                if st.run(rid)["status"]!=want_status:raise AssertionError("wrong stored run status")
                try:
                    st.append_event(rid,"run_completed","invalid-worker",{},worker_token=token)
                except PermissionError:
                    pass
                else:raise AssertionError("postterminal append accepted")
                with lock:timings.append((time.perf_counter()-start)*1000)
            except Exception as exc:
                with lock:failures.append({"case":i,"type":type(exc).__name__,"message":str(exc)[:160]})
        start=time.perf_counter()
        with ThreadPoolExecutor(max_workers=concurrency) as pool:list(pool.map(one,range(size)))
        total=(time.perf_counter()-start)*1000
        runs=[]
        total_runs=0
        for offset in range(0,size,100):
            page,total_runs=st.list_runs_by_conversation(cid,limit=min(100,size-offset),offset=offset)
            runs.extend(page)
        messages=st.messages(cid)
        success=sum(r["status"]=="completed" for r in runs)
        fail=sum(r["status"]=="failed" for r in runs)
        correct_messages=sum(m["role"]=="assistant" for m in messages)==success and sum(m["role"]=="user" for m in messages)==size
        terminal_count=sum(len([x for x in st.events(r["id"]) if x["type"] in ("run_failed","run_completed")]) for r in runs)
        result={"concurrency":concurrency,"attempted":size,"stored_runs":total_runs,
                "completed":success,"failed_expected":fail,"test_errors":len(failures),
                "event_terminal_count":terminal_count,"message_counts_ok":correct_messages,
                "p50_ms":pct(timings,.5) if timings else None,
                "p95_ms":pct(timings,.95) if timings else None,
                "max_ms":round(max(timings),2) if timings else None,
                "batch_ms":round(total,2),"throughput_runs_per_s":round(size*1000/total,2),
                "failure_samples":failures[:6]}
        print("OWNER_MIXED_STRESS "+json.dumps(result,ensure_ascii=False),flush=True)
        assert not failures and total_runs==size and success==size-size//5 and fail==size//5 and correct_messages and terminal_count==size
        return result
if __name__=="__main__":
    for c in (4,8,16):run_group(120,c)
