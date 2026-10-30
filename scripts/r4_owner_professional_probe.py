"""Read-only professional-question baseline. No API calls, no production DB.

Execute from project root:
  ./.venv-langgraph/Scripts/python.exe -B -m scripts.r4_owner_professional_probe
Results only contain question, model-free graph answer, status and SOURCE IDs.
"""
from __future__ import annotations
from datetime import datetime,timezone
import json
import time
from pathlib import Path
from backend.context_slots import extract_explicit_context
from orchestration.r9_industrial_candidate import IndustrialCandidate

CASESET=[
 ("P1","概念：什么是应力腐蚀开裂？它需要具备哪些条件？","concept"),
 ("P2","塔顶弯头材质300系列不锈钢，介质碱式酸性水，温度60℃，出现减薄，可能有哪些腐蚀机理？如何区分？","mechanism"),
 ("P3","碳钢换热器处于湿硫化氢介质，工艺温度110℃，局部发现裂纹，如何区分湿H2S相关损伤？","mechanism"),
 ("P4","承压容器壳体受碰撞后有凹陷，何时应暂停使用、需要哪些检验和验收依据？","safety"),
 ("P5","碳钢盐酸管线95℃出现腐蚀，没有烟气侧，为什么不能直接判断是烟气露点腐蚀？","negative"),
 ("P6","300系列不锈钢储罐出现腐蚀裂纹，但介质成分、温度未知，能否直接给出RBI风险等级与检验周期？","rbi"),
 ("P7","GB/T 150.4-2024 中壳体凹陷修理后的验收尺寸限值具体是多少？请引用条款。","standards"),
]
def run():
    graph=IndustrialCandidate()
    result=[]
    for case_id,q,kind in CASESET:
        t=time.perf_counter()
        d=extract_explicit_context(q)
        ctx=d.get("values",{})
        try:
            graph_answer=graph.run(q,ctx,run_id="r4-probe-"+case_id,professional_mode=kind!="concept")
            o=graph_answer["output"]
            row={"case_id":case_id,"kind":kind,"question":q,"context":ctx,"status":o.get("status"),
                 "answer":str(o.get("conclusion") or "")[:1600],
                 "source_ids":sorted({c.get("clause_id") for c in o.get("citations",[]) if isinstance(c,dict) and c.get("clause_id")}),
                 "tool_names":[x.get("tool") for x in o.get("tool_calls",[]) if isinstance(x,dict)],
                 "tool_count":len(o.get("tool_calls") or []),"hypothesis_count":len(o.get("hypotheses") or []),
                 "risk_level":o.get("risk_level"),"latency_ms":round(1000*(time.perf_counter()-t),1)}
        except Exception as e:
            import traceback
            traceback.print_exc(limit=12)
            row={"case_id":case_id,"kind":kind,"question":q,"context":ctx,
                 "status":"PROBE_EXCEPTION","error_type":type(e).__name__,"error_detail":str(e)[:240],
                 "latency_ms":round(1000*(time.perf_counter()-t),1)}
        result.append(row)
        print(json.dumps(row,ensure_ascii=False),flush=True)
    print("R4_PROBE_SUMMARY "+json.dumps({"cases":len(result),"nonempty_sources":sum(bool(r.get("source_ids")) for r in result),
         "tool_calls":sum(r.get("tool_count",0) for r in result),
         "median_latency_ms":sorted(r["latency_ms"] for r in result)[len(result)//2],
         "statuses":{s:sum(r.get("status")==s for r in result) for s in sorted({r.get("status") for r in result})}},ensure_ascii=False))
if __name__=="__main__":run()
