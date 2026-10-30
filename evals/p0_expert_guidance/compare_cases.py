"""Offline P0 paired reproduction; uses official read-only teacher tools, no network/model calls."""
from __future__ import annotations
import json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from backend.context_slots import extract_explicit_context
from backend.professional_answers import deterministic_draft,render_professional_response,source_catalog_from_run
from orchestration.r9_industrial_candidate import IndustrialCandidate

CASES=[
("A","设备：塔顶碱液管线弯头，材质：300系列不锈钢，介质：[碱式酸性水]，温度：60°C，问题：该减薄属于哪类腐蚀？", "请补充材质与介质后再检索。待补充：material medium"),
("B","设备发生壳体磕碰损伤，什么情况需要停机维修？验收判定标准是什么？", "未取得可追溯出处；无法形成受证据支持的结论。"),
]
def main():
 graph=IndustrialCandidate(); results=[]
 for label,question,before in CASES:
  parsed=extract_explicit_context(question); context={**parsed['values'],'_context_sources':parsed['sources'],'_context_raw_values':parsed.get('raw_values',{}),
    '_context_unknown_enums':parsed.get('unknown_enum_values',{}),'_context_field_details':parsed.get('field_details',{}),'raw_medium':parsed.get('raw_values',{}).get('medium')}
  run=graph.run(question,context,professional_mode=True)
  output=run['output']; catalog=source_catalog_from_run(output.get('citations',[]),run.get('tool_calls',[]),graph.clause_index,question=question,context=context)
  known=[{'field':k,'value':context.get(k),'label':{'equipment':'设备/部位','equipment_type':'设备类型','material':'用户陈述材质','medium':'用户陈述介质','temperature_c':'用户陈述温度'}.get(k,k),
    'provenance':parsed['sources'].get(k,'provided_context'),'measurement_confirmed':False} for k in ('equipment','equipment_type','material','medium','temperature_c') if context.get(k) not in (None,'',[])]
  response=render_professional_response(deterministic_draft(question,context,catalog),known,catalog)
  results.append({'case':label,'question':question,'before_owner_reproduced_answer':before,'after_candidate_main_answer':response,
   'context_snapshot':context,'query_variants':run.get('query_variants',[]),'tool_calls':[{'tool':c['tool'],'args':c['args'],'status':c['status'],'source_ids':c['source_ids'],'duration_ms':c['duration_ms']} for c in run.get('tool_calls',[])],
   'source_catalog':list(catalog.values()),'risk_level':output.get('risk_level'),'human_source_verified':False,'model_provider_called':False})
 out={'mode':'offline_REAL_TEACHER_TOOLS_deterministic_response','source':'upstream/05_提交区/clauses.jsonl','cases':results}
 dest=ROOT/'evals/p0_expert_guidance/comparison.json';dest.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
 print(json.dumps({'cases':len(results),'A_tools':len(results[0]['tool_calls']),'A_sources':len(results[0]['source_catalog']),'B_tools':len(results[1]['tool_calls']),'B_sources':len(results[1]['source_catalog']),'B_answer_chars':len(results[1]['after_candidate_main_answer']),'output':str(dest)},ensure_ascii=False))
if __name__=='__main__':main()
