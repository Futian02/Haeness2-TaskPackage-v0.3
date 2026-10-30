from __future__ import annotations
import hashlib, json
from collections import Counter
from pathlib import Path
ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
CLAUSES=ROOT/'upstream/05_提交区/clauses.jsonl'
MANIFEST=ROOT/'knowledge/applicability/candidates/source_manifest.jsonl'
DM_AUDIT=ROOT/'knowledge/applicability/candidates/dm82_field_audit.jsonl'
PDFS={
'GB/T 30579-2022':'upstream/02_损伤机理参考/GBT30579-2022_承压设备损伤模式识别.pdf',
'GB/T 26610.2-2022':'upstream/01_RBI标准/GBT26610.2-2022_基于风险的检验策略.pdf',
'GB/T 26610.3-2014':'upstream/01_RBI标准/GBT26610.3-2014_风险的定性分析方法.pdf',
'GB/T 26610.4-2022':'upstream/01_RBI标准/GBT26610.4-2022_失效可能性定量分析方法.pdf',
'GB/T 26610.5-2022':'upstream/01_RBI标准/GBT26610.5-2022_失效后果定量分析方法.pdf',
' TS': 'none',
'TSG 21-2016':'upstream/01_RBI标准/补充规范/TSG21-2016_固定式压力容器安全技术监察规程.pdf'}
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
 return h.hexdigest()
def read(p): return [json.loads(s) for s in Path(p).read_text(encoding='utf-8-sig').splitlines() if s.strip()]
def norm(x): return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def nonempty(v): return not (v is None or v=='' or v==[] or v=={})
def known(v):
 if v is None or v=='': return False
 if isinstance(v,(list,tuple)): return any(x is not None and x!='' for x in v)
 if isinstance(v,dict): return any(known(x) for x in v.values())
 return True
def main():
 rows=read(CLAUSES); mans={r['clause_id']:r for r in read(MANIFEST)}; dm={r['clause_id']:r for r in read(DM_AUDIT)}
 srcsha=sha(CLAUSES); frozen='a8151797ba15a6a7452dd83aaec9fab4c0a815724ca45062eb1e2bac7b4d49ef'
 if len(rows)!=554 or len({r.get('clause_id') for r in rows})!=554: raise SystemExit('formal row count or IDs invalid')
 if srcsha!=frozen: raise SystemExit(f'frozen source hash mismatch {srcsha}')
 pdfhash={s:sha(ROOT/p) for s,p in PDFS.items() if s!=' TS' and (ROOT/p).is_file()}
 audit=[]; blank=0
 for i,r in enumerate(rows,1):
  std=r.get('standard_code','UNKNOWN'); rel=PDFS.get(std); m=mans.get(r['clause_id']); conditions=r.get('applicable_conditions') or {}
  verified=nonempty(r.get('verified_by')); blank+=not verified
  audit.append({'ordinal_in_frozen_jsonl':i,'clause_id':r['clause_id'],'knowledge_type':r.get('knowledge_type'),'standard_code':std,'standard_title':r.get('standard_name'),'version':r.get('version'),'title':r.get('title'),'source_jsonl':'upstream/05_提交区/clauses.jsonl','source_jsonl_sha256':srcsha,'source_record_sha256':hashlib.sha256(norm(r).encode()).hexdigest(),'source_pdf_path':rel,'source_pdf_sha256':pdfhash.get(std),'printed_page_candidate':(m or {}).get('pdf_printed_page',r.get('page')),'printed_page_status':(m or {}).get('locator_status','JSONL_PAGE_FIELD_UNVERIFIED'),'pdf_physical_page_index_candidate':(m or {}).get('pdf_physical_page_index_candidate'),'pdf_page_locator_status':'MANIFEST_CANDIDATE_NOT_PAGE_BY_PAGE_VERIFIED' if m else 'SOURCE_PDF_PRESENT_ROW_TO_PDF_PAGE_UNVERIFIED','source_record_present':True,'condition_field_keys_present':{k:nonempty(v) for k,v in conditions.items()},'verified_by_present':verified,'evidence_grade':'E0_MACHINE_INVENTORY_ONLY','human_review_state':'NOT_VERIFIED','dm_field_audit_issue_count':len((dm.get(r['clause_id']) or {}).get('issues') or [])})
 out=OUT/'record_source_audit.jsonl'; out.write_text(''.join(json.dumps(x,ensure_ascii=False,sort_keys=True)+'\n' for x in audit),encoding='utf-8')
 critical=[]
 for cid,issue,interpretation in [
 ('GBT30579-2022-5.23','60/80 C + 300-series stainless + alkaline sour water','The structured 49–66 C interval appears in the applicable_conditions record and its other text links it to NH4HS gas-phase precipitation. It is a local/submechanism predicate, not a necessary condition for all acid-water corrosion. 60 C is only a candidate if that local condition and other prerequisites are established; 80 C outside the bounded interval does not exclude the overall mechanism. Both scenarios remain UNKNOWN for actual applicability.'),
 ('GBT30579-2022-5.6','naphthenic acid scope and temperature fields','The structured 177–242 C interval is distinct from a 218–400 C light-phase factor in influencing_factors. Keep the field roles separate; do not flatten the latter into a global necessary temperature range. Source page/content remain machine-inventory only.'),
 ('GBT30579-2022-6.7','wet H2S partial pressure and submechanisms','The record puts an H2S gas partial-pressure threshold in free text while structured pressure_mpa is null. Total system pressure is not interchangeable with H2S partial pressure. Aggregate temperature ranges and submechanism-specific boundaries must stay scoped; no individual equipment applicability is established.')]:
  r=next(x for x in rows if x['clause_id']==cid); cond=r.get('applicable_conditions') or {}; m=mans.get(cid)
  critical.append({'clause_id':cid,'query_family':issue,'temperature_c_record':cond.get('temperature_c'),'pressure_mpa_record':cond.get('pressure_mpa'),'material_record':cond.get('material'),'medium_record':cond.get('medium'),'printed_page_candidate':(m or {}).get('pdf_printed_page',r.get('page')),'pdf_physical_page_index_candidate':(m or {}).get('pdf_physical_page_index_candidate'),'source_record_sha256':hashlib.sha256(norm(r).encode()).hexdigest(),'source_pdf_path':PDFS.get(r.get('standard_code')),'source_pdf_sha256':pdfhash.get(r.get('standard_code')),'source_availability':'FORMAL_JSONL_RECORD_AND_SOURCE_PDF_PRESENT','semantic_relevance':'MACHINE_IDENTIFIED_CANDIDATE_ONLY','applicability':'UNKNOWN_PENDING_SOURCE_AND_EXPERT_REVIEW','visual_pdf_review':'NOT_PERFORMED','literal_excerpt_included':False,'interpretation_boundary':interpretation})
 (OUT/'critical_mechanism_scope_review.json').write_text(json.dumps(critical,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 counts=Counter(r.get('standard_code','UNKNOWN') for r in rows); types=Counter(r.get('knowledge_type','UNKNOWN') for r in rows); ckeys=Counter(); cnknown=Counter(); efields=Counter()
 for r in rows:
  c=r.get('applicable_conditions') or {}
  for k,v in c.items(): ckeys[k]+=nonempty(v); cnknown[k]+=known(v)
  for k,v in (r.get('mechanism_detail') or {}).items(): efields[k]+=known(v)
 summary={'audit_version':'r2-a1-source-audit-v1','source_jsonl':'upstream/05_提交区/clauses.jsonl','source_jsonl_sha256':srcsha,'source_manifest_sha256':sha(MANIFEST),'dm82_field_audit_sha256':sha(DM_AUDIT),'source_rows':len(rows),'unique_clause_ids':len({r['clause_id'] for r in rows}),'by_standard_code':dict(sorted(counts.items())),'by_knowledge_type':dict(sorted(types.items())),'verified_by_blank_count':blank,'pdf_files_found':sorted(PDFS[s] for s in pdfhash),'pdf_hashes_by_standard':pdfhash,'locator_status_counts':dict(Counter(x['pdf_page_locator_status'] for x in audit)),'human_verified_rows':0,'independent_human_gold':0,'exact_pdf_page_verified_rows':0,'condition_field_key_present_count':dict(sorted(ckeys.items())),'condition_field_known_value_count':dict(sorted(cnknown.items())),'mechanism_detail_nonempty_field_counts':dict(sorted(efields.items())),'interpretation':'Machine inventory and field presence only. No claim of PDF transcription accuracy, expert applicability, or citation precision.'}
 (OUT/'audit_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 if sha(CLAUSES)!=srcsha: raise SystemExit('formal source changed during audit')
 check=read(out)
 if len(check)!=554 or len({r['clause_id'] for r in check})!=554: raise SystemExit('generated output integrity failure')
 print(json.dumps({'rows':len(check),'source_sha256':srcsha,'unique_ids':len({r['clause_id'] for r in check}),'verified_by_blank':blank,'pdfs_found':len(pdfhash),'by_standard':dict(counts),'knowledge_type':dict(types)},ensure_ascii=False))
if __name__=='__main__': main()
