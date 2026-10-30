#!/usr/bin/env python3
"""Read-only S3-A source inventory and authored candidate generator.

Reads formal upstream JSONL/enum/PDF/workbook bytes; writes only under
knowledge/applicability/candidates. No OCR, PDF claim, source mutation, or approval.
"""
from __future__ import annotations
import argparse, hashlib, json, re, sys
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[1]
CLAUSES=ROOT/'upstream/05_提交区/clauses.jsonl'
ENUMS=ROOT/'upstream/04_接口文档/enums.json'
PDF=ROOT/'upstream/02_损伤机理参考/GBT30579-2022_承压设备损伤模式识别.pdf'
XLSX=ROOT/'upstream/02_损伤机理参考/条款摘录表_损伤机理.xlsx'
OUT=ROOT/'knowledge/applicability/candidates'
OUTFILES=('source_manifest.jsonl','dm82_field_audit.jsonl','pilot_predicates.jsonl','professional_counterexamples.jsonl','candidate_summary.json')
PILOT=('5.1','5.2','5.5','5.6','5.11','5.14','5.17','5.18','5.19','5.21','5.22','5.23','5.24','6.1','6.7')
EIGHT=('description','morphology','affected_materials','influencing_factors','susceptible_locations','prevention','detection_methods','related_damages')

def sha(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def canonical(d:Any)->str:return json.dumps(d,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def jline(d):return canonical(d)+'\n'
def load_rows():return [json.loads(x) for x in CLAUSES.read_text(encoding='utf-8-sig').splitlines() if x.strip()]
def text_blob(r):
 c=r.get('applicable_conditions') or {}; m=r.get('mechanism_detail') or {}
 return ' '.join([str(c.get('other','')), ' '.join(map(str,m.get('influencing_factors',[]) or [])), ' '.join(map(str,m.get('morphology',[]) or [])), ' '.join(map(str,m.get('affected_materials',[]) or []))])
def excerpt(text,needle=None,limit=220):
 if needle:
  i=text.lower().find(needle.lower())
  if i>=0:return text[max(0,i-65):min(len(text),i+len(needle)+100)].strip()[:limit]
 return text[:limit].strip()
def build():
 raw=CLAUSES.read_bytes(); rows=[r for r in load_rows() if r.get('knowledge_type')=='damage_mechanism']
 rows.sort(key=lambda r:(r.get('clause_no',''),r.get('clause_id','')))
 enums=json.loads(ENUMS.read_text(encoding='utf-8-sig'))
 ids=[r['clause_no'] for r in rows]
 if len(rows)!=82 or len(set(ids))!=82:raise ValueError(f'expected 82 unique mechanisms; found {len(rows)} / {len(set(ids))}')
 record_sha={r['clause_id']:sha(canonical(r).encode('utf-8')) for r in rows}
 pdfsha=sha(PDF.read_bytes()); xlsxsha=sha(XLSX.read_bytes())
 source_sha=sha(raw)
 man=[]; audit=[]; predicates=[]
 for r in rows:
  cid=r['clause_id']; no=r['clause_no']; page=r.get('page'); cond=r.get('applicable_conditions') or {}; detail=r.get('mechanism_detail') or {}
  m={'clause_id':cid,'clause_no':no,'title':r.get('title'),'standard_code':r.get('standard_code'),'standard_title':r.get('standard_name'),'jsonl_path':str(CLAUSES.relative_to(ROOT)).replace('\\','/'),'jsonl_sha256':source_sha,'record_sha256':record_sha[cid],'pdf_path':str(PDF.relative_to(ROOT)).replace('\\','/'),'pdf_sha256':pdfsha,'pdf_printed_page':page,'pdf_physical_page_index_candidate':(page+5 if isinstance(page,int) else None),'page_mapping':'AUTO_OFFSET_PLUS_5; cross-checked on sample pages only, not page-by-page verified','locator_status':'NEEDS_PDF_CHECK','review_state':'NEEDS_PDF_CHECK','human_reviewed':False}
  man.append(m)
  vals={k:cond.get(k) for k in ('material','medium','equipment_type','temperature_c','pressure_mpa','other')}
  issues=[]
  for k in ('material','medium','equipment_type'):
   v=vals[k]
   if not v:issues.append({'field':k,'class':'NOT_MENTIONED_OR_EMPTY','detail':'official structured field empty'})
   elif k in enums and isinstance(v,list):
    outside=[x for x in v if x not in enums[k]]
    if outside:issues.append({'field':k,'class':'SOURCE_VALUE_OUTSIDE_ENUM','values':outside})
  blob=text_blob(r)
  for term,issue in [('壁温','OBJECT_SCOPE_AMBIGUITY'),('金属温度','OBJECT_SCOPE_AMBIGUITY'),('分压','PRESSURE_BASIS_DISTINCTION'),('保护膜','ROLE_OR_POLARITY_MIX'),('耐腐蚀性','ROLE_OR_POLARITY_MIX'),('易腐蚀','ROLE_OR_POLARITY_MIX'),('49℃','LOCAL_SUBMECHANISM_CONDITION'),('66℃','LOCAL_SUBMECHANISM_CONDITION'),('露点','SUBMECHANISM_OR_SIDE_SCOPE')]:
   if term in blob:issues.append({'field':'narrative','class':issue,'matched_term':term,'source_excerpt':excerpt(blob,term,180),'excerpt_scope':'short local excerpt; verify against PDF'})
  if not cond.get('temperature_c') or all(x is None for x in cond.get('temperature_c',[])):issues.append({'field':'temperature_c','class':'NOT_STATED_IN_STRUCTURED_RANGE'})
  if not cond.get('pressure_mpa') or all(x is None for x in cond.get('pressure_mpa',[])):issues.append({'field':'pressure_mpa','class':'NOT_STATED_IN_STRUCTURED_RANGE'})
  if r.get('verified_by') in (None,''):issues.append({'field':'verified_by','class':'NO_FORMAL_VERIFIER_VALUE'})
  audit.append({'clause_id':cid,'clause_no':no,'title':r.get('title'),'source_sha256':source_sha,'record_sha256':record_sha[cid],'field_values':vals,'eight_narrative_fields_nonempty':{k:bool(detail.get(k)) for k in EIGHT},'issues':issues,'evidence_locator':{'jsonl_path':m['jsonl_path'],'record_key':'clause_id','page_printed':page,'pdf_physical_page_index_candidate':m['pdf_physical_page_index_candidate'],'status':'NEEDS_PDF_CHECK'},'review_state':'SOURCE_INVENTORY_ONLY_NO_EXPERT_REVIEW'})
  if no in PILOT:
   base={'clause_id':cid,'clause_no':no,'title':r.get('title'),'source_sha256':source_sha,'record_sha256':record_sha[cid]}
   # Structured values stay descriptive candidates; target/scope are explicitly unresolved.
   for field,prop,unit in [('medium','process_medium',None),('material','material',None),('equipment_type','equipment_type',None)]:
    for val in cond.get(field) or []:
     predicates.append({**base,'property':prop,'operator':'in','value':val,'unit':unit,'target_object':'equipment/process context (candidate; exact component unresolved)','role':('exposure_medium_candidate' if field=='medium' else 'susceptibility_or_resistance_role_unresolved' if field=='material' else 'equipment_context_candidate'),'polarity':'candidate_support_or_scope_only','scope':'clause_scope_unverified','origin':'STRUCTURED_SOURCE_FIELD','source_excerpt_locator':{'jsonl_path':m['jsonl_path'],'clause_id':cid,'field':'applicable_conditions.'+field,'pdf_printed_page':page,'pdf_page_index_candidate':m['pdf_physical_page_index_candidate'],'review_state':'NEEDS_PDF_CHECK'},'source_excerpt':str(val),'review_state':'PROPOSED_NEEDS_PDF_CHECK','human_reviewed':False})
   for field in ('temperature_c','pressure_mpa'):
    v=cond.get(field)
    if isinstance(v,list) and any(x is not None for x in v):
     predicates.append({**base,'property':'temperature' if field=='temperature_c' else 'pressure','operator':'interval','value':v,'unit':'°C' if field=='temperature_c' else 'MPa','target_object':'scope unresolved (fluid / wall / local phase / system basis must be checked)','role':'condition_scope_candidate','polarity':'candidate_only','scope':'NOT_GLOBAL_UNLESS_PDF_CONFIRMS','origin':'STRUCTURED_SOURCE_FIELD','source_excerpt_locator':{'jsonl_path':m['jsonl_path'],'clause_id':cid,'field':'applicable_conditions.'+field,'pdf_printed_page':page,'pdf_page_index_candidate':m['pdf_physical_page_index_candidate'],'review_state':'NEEDS_PDF_CHECK'},'source_excerpt':canonical(v),'review_state':'PROPOSED_SCOPE_UNRESOLVED','human_reviewed':False})
   predicates += special_candidates(r,m,base)
 # at least 3 authored cases per pilot, all explicitly synthetic, not gold labels.
 cases=make_cases({r['clause_no']:r for r in rows if r['clause_no'] in PILOT},source_sha,record_sha)
 summary={'status':'CANDIDATE_RESEARCH_ONLY','source_rows_scanned':len(rows),'unique_mechanisms':len(set(ids)),'pilot_clause_nos':list(PILOT),'pilot_count':len([x for x in rows if x['clause_no'] in PILOT]),'candidate_predicate_count':len(predicates),'reliable_approved_predicate_count':0,'source_manifest_count':len(man),'field_audit_count':len(audit),'authored_counterexample_count':len(cases),'source_jsonl_sha256':source_sha,'source_pdf_sha256':pdfsha,'source_workbook_sha256':xlsxsha,'enum_json_sha256':sha(ENUMS.read_bytes()),'human_reviewed_count':0,'expert_gold_labels':0,'l1_l4_risk_outputs':0,'all_pdfs_page_verified':False}
 out={'source_manifest.jsonl':[jline(x) for x in man],'dm82_field_audit.jsonl':[jline(x) for x in audit],'pilot_predicates.jsonl':[jline(x) for x in predicates],'professional_counterexamples.jsonl':[jline(x) for x in cases],'candidate_summary.json':[canonical(summary)+'\n']}
 validate(out,summary,rows,cases)
 return out,summary

def special_candidates(r,m,base):
 no=r['clause_no']; blob=text_blob(r); out=[]
 def add(prop,op,val,unit,obj,role,scope,needle,origin='SOURCE_TEXT_RULE_CANDIDATE'):
  out.append({**base,'property':prop,'operator':op,'value':val,'unit':unit,'target_object':obj,'role':role,'polarity':'candidate_only','scope':scope,'origin':origin,'source_excerpt_locator':{'jsonl_path':m['jsonl_path'],'clause_id':m['clause_id'],'field':'content_raw / mechanism_detail / applicable_conditions.other','pdf_printed_page':m['pdf_printed_page'],'pdf_page_index_candidate':m['pdf_physical_page_index_candidate'],'review_state':'NEEDS_PDF_CHECK'},'source_excerpt':excerpt(blob,needle),'review_state':'PROPOSED_NEEDS_PDF_CHECK','human_reviewed':False})
 if no=='5.6':
  add('temperature_c','interval',[177,427],'°C','naphthenic-acid-exposed process metal; global scope unverified','general_mechanism_range_candidate','general mechanism vs local phase unresolved','177℃～427℃')
  add('temperature_c','interval',[218,400],'°C','light naphthenic-acid phase / more common zone','subscope_prevalence_candidate','light phase local/common range, not whole mechanism','218℃～400℃')
  add('temperature_c','conflicts_with',[177,242],'°C','official JSONL applicable_conditions.temperature_c','source_representation_conflict','must resolve against PDF; retain both source facts','temperature_c')
 if no=='5.18':
  add('side','equals','flue_gas / combustion gas side',None,'gas-side wall / condensate location','side_scope_gate','requires combustion/flue gas evidence','烟气')
  add('wall_temperature','below','local acid dew point','°C','metal wall at flue-gas condensate location','local_condensation_trigger','not transferable to ordinary acid process piping','露点')
  add('dewpoint_reference','conditional_values','H2SO4 ~138; HCl ~54','°C','flue-gas composition dependent dewpoint','reference_threshold_candidate','composition-dependent; not universal threshold','138')
 if no=='5.19':
  add('condition','contains','NH4Cl salt deposition / hygroscopic deliquescent salt',None,'salt deposit and local aqueous film','salt_deposit_local_condition','may occur under conditions not reducible to ordinary acid dewpoint','NH4Cl')
 if no=='5.22':
  add('gas_partial_pressure_H2S','greater_than',0.0003,'MPa','H2S gas-phase partial pressure','mode_trigger_candidate','not system total pressure; mode-specific','分压')
 if no=='5.23':
  add('temperature_c','interval',[49,66],'°C','NH4HS gas precipitation zone / local phase transition','local_submechanism_condition','not global corrosion applicability interval','49℃～66℃')
  add('mass_fraction_NH4HS','greater_than',2,'%','NH4HS-containing aqueous medium at turbulent/local high-rate zones','severity_modifier_candidate','source links concentration and flow/location; not universal threshold','超过2%')
 if no=='6.1':
  add('metal_temperature','greater_than_or_equal',38,'°C','susceptible metal under chloride aqueous exposure and tensile stress','susceptibility_condition_candidate','metal temperature; conjunction with chloride and tensile stress; source check required','38℃')
  add('stress_state','requires','tensile stress',None,'susceptible material','necessary_factor_candidate','conjunctive condition; not a medium property','拉伸应力')
 if no=='6.7':
  add('gas_partial_pressure_H2S','greater_than',0.0003,'MPa','wet H2S gas-phase partial pressure','mode_trigger_candidate','do not map to system pressure; verify mode and standard locator','0.0003 MPa')
  add('water_presence','requires',True,None,'process environment contacting susceptible steel','wet_environment_gate','wet H2S vs dry high-temperature sulfide distinction','水')
 if no=='5.11':
  add('metal_surface_temperature','interval',[100,121],'°C','insulated metal surface / local corrosion zone','local_susceptibility_window_candidate','not universal atmospheric corrosion range','100℃～121℃')
 if no=='5.14':
  add('organism_survival_temperature','interval',[-17,113],'°C','microorganism survival, not necessarily metal corrosion rate','biological_survival_context','survival range is not whole-mechanism corrosion limit','-17℃～113℃')
 if no=='5.17':
  add('environment','requires','fuel/combustion ash containing corrosive constituents (e.g. S/Na/K/V)',None,'combustion-side deposits / tube surface','side_and_deposit_gate','not ordinary process-side acid pipe','烟气')
 if no=='5.21':
  add('hydrogen_presence','equals',False,None,'high-temperature sulfidation exposure context','mechanism_discriminator_candidate','contrast with H2-accelerated mechanism; PDF check required','无氢')
 return out

def make_cases(pilot,source_sha,record_sha):
 cases=[]
 common={
 '5.1':('acid condensate with local HCl concentration, carbon steel exposed','fluid is alkaline water with no chloride/HCl evidence','ordinary HCl process pipe is not automatically flue-gas dew-point corrosion'),
 '5.2':('sulfuric-acid-containing stream with concentration and temperature documented','acid identity known but concentration and phase absent','dilute sulfuric-acid line cannot be classified from HCl dewpoint rule'),
 '5.5':('wet CO2 and water contact carbon steel with corrosion evidence','CO2 reported but water phase unknown','dry CO2 service is not sufficient evidence for aqueous carbonic corrosion'),
 '5.6':('naphthenic-acid process in stated elevated-temperature range; light phase identified','temperature known but acid composition/phase missing','temperature 200C alone without naphthenic acid does not establish mechanism'),
 '5.11':('external insulated carbon-steel surface with wetting and atmospheric exposure','insulation present but water ingress/cyclic wetness unknown','hot internal process fluid does not establish external CUI'),
 '5.14':('water system with biofilm/stagnation and microbial evidence','stagnant water but no microbiological evidence','sterile clean water with no biofilm evidence is not MIC proof'),
 '5.17':('combustion/fuel ash deposits containing corrosive species on hot-side surface','hot equipment but fuel/ash composition unknown','ordinary liquid process-side acid line without combustion ash is not fuel-ash corrosion'),
 '5.18':('combustion flue gas and wall temperature below composition-dependent acid dewpoint','acidic service but no combustion/flue-gas side evidence','ordinary HCl process piping at 95C is not automatically flue-gas dewpoint corrosion'),
 '5.19':('NH4Cl salt deposition with hygroscopic wetting on surface','ammonia/chloride present but salt deposition not established','aqueous HCl without ammonium chloride salt deposition is not NH4Cl under-deposit corrosion'),
 '5.21':('high-temperature sulfide exposure without hydrogen in process context','sulfide present but temperature regime and hydrogen status unknown','wet low-temperature sour water is not automatically high-temperature sulfidation'),
 '5.22':('high-temperature sulfide with hydrogen; H2 partial pressure separately recorded','total pressure recorded but H2 partial pressure absent','system total pressure alone cannot satisfy H2 partial-pressure condition'),
 '5.23':('alkaline sour water with NH4HS, concentration and local turbulent zone documented','49-66C fluid noted but NH4HS phase, concentration, and flow location unknown','49-66C alone does not imply whole-mechanism applicability or gas precipitation'),
 '5.24':('acidic sour water with H2S and pH context documented','H2S present but pH unavailable to distinguish acid/alkaline sour water','alkaline NH4HS aqueous stream must not be relabeled acidic sour water'),
 '6.1':('chloride aqueous exposure, tensile stress, susceptible stainless material, metal temperature documented','chloride present but stress state/metal temperature unknown','fluid temperature cannot substitute for metal temperature; carbon steel not automatically chloride SCC susceptible'),
 '6.7':('wet H2S aqueous exposure and mode-specific H2S gas partial pressure recorded','system pressure recorded, H2S partial pressure or wetness missing','dry high-temperature sulfide without water is not wet-H2S cracking'),
 }
 for no in PILOT:
  r=pilot[no]; group=common[no]
  for kind,label,claim in [('support','SUPPORT_CANDIDATE',group[0]),('unknown','UNKNOWN_MISSING_CONDITION',group[1]),('false_positive','COUNTEREXAMPLE_DO_NOT_MATCH',group[2])]:
   cases.append({'case_id':f'S3A-{no.replace(".","_")}-{kind}','clause_id':r['clause_id'],'clause_no':no,'mechanism_title':r['title'],'case_kind':kind,'scenario':claim,'expected_candidate_behavior':label,'missing_or_disambiguating_fields':{'support':['source-matched exposure and target','mode-specific conditions'], 'unknown':['identify exact missing fields; return UNKNOWN not false'], 'false_positive':['do not transfer neighboring mechanism/role or local threshold']}[kind],'case_origin':'AUTHOR_SYNTHETIC','gold_status':'AUTHOR_SYNTHETIC_PENDING_REVIEW','expert_gold':False,'human_reviewed':False,'source_sha256':source_sha,'record_sha256':record_sha[r['clause_id']],'risk_level_output_forbidden':True})
 # Extra focused cross-cutting adversarial cases to ensure >=30 and exercise distinctions.
 extras=[('6.7','system total pressure 10 MPa, H2S partial pressure absent; wetness known','system total pressure must not be substituted for H2S partial pressure'),('6.7','H2S partial pressure known, water presence absent','missing wetness must remain UNKNOWN for wet-H2S modes'),('6.1','fluid 60C but metal wall 30C; chloride and stress documented','fluid temperature is not a verified metal temperature'),('5.18','wall 150C on an ordinary acid process line, no combustion gas','dewpoint mechanism needs flue-gas-side scope'),('5.18','flue gas confirmed but SO3/HCl composition and dewpoint absent','do not assert fixed dewpoint from generic temperature'),('5.23','NH4HS mass fraction 3%, but location low-flow and deposit status unknown','concentration alone does not prove turbulent erosion/local condition'),('5.1','carbon steel and HCl present, but alkaline neutralized bulk liquid pH 8','do not apply low-pH condensate condition without matching phase'),('5.24','pH 5.5 and H2S water evidence, temperature missing','classify missing temperature as UNKNOWN, not reject'),('5.22','H2S partial pressure 0.0004MPa but no high-temperature sulfide exposure','one trigger alone does not satisfy combined mode scope'),('5.21','high-temperature sulfide plus hydrogen documented','possible competing 5.22 mode; do not keep “no H2” discriminator'),('5.17','combustion-side ash, but alloy protective role mentioned','protective material mention does not equal susceptible material'),('5.14','temperature within microorganism survival range but no water/biofilm','survival range alone does not prove MIC'),('5.6','official structured interval [177,242], narrative general 177-427 and light phase 218-400','retain conflict and scope labels; do not silently choose'),('5.11','insulated surface at 110C but no wetting/atmospheric exposure','local susceptibility window alone is insufficient'),('5.19','NH4Cl detected in dry deposit with no moisture evidence','salt presence does not by itself establish aqueous corrosion'),('5.2','sulfuric acid 90% vs dilute; line material and temperature differ','do not assume monotonic/general universal concentration rule')]
 for i,(no,scenario,behavior) in enumerate(extras,1):
  r=pilot[no]; cases.append({'case_id':f'S3A-X{i:02d}','clause_id':r['clause_id'],'clause_no':no,'mechanism_title':r['title'],'case_kind':'cross_cutting_adversarial','scenario':scenario,'expected_candidate_behavior':behavior,'case_origin':'AUTHOR_SYNTHETIC','gold_status':'AUTHOR_SYNTHETIC_PENDING_REVIEW','expert_gold':False,'human_reviewed':False,'source_sha256':source_sha,'record_sha256':record_sha[r['clause_id']],'risk_level_output_forbidden':True})
 return cases

def validate(out,summary,rows,cases):
 for name,lines in out.items():
  if name.endswith('.jsonl'):
   parsed=[json.loads(x) for x in lines]
   assert len(parsed)==len(lines)
 assert summary['source_rows_scanned']==82 and summary['source_manifest_count']==82 and summary['field_audit_count']==82
 assert summary['pilot_count']==15 and summary['authored_counterexample_count']>=30
 assert len(cases)>=30 and all(c['expert_gold'] is False and c['human_reviewed'] is False for c in cases)
 assert all(p.get('review_state','').startswith('PROPOSED') and not p.get('human_reviewed') for p in map(json.loads,out['pilot_predicates.jsonl']))
 assert len([r for r in rows if r['clause_no'] in PILOT])==15
 assert summary['reliable_approved_predicate_count']==0 and summary['l1_l4_risk_outputs']==0

def self_test():
 a,s=build(); b,t=build(); assert a==b and s==t,'repeat generation changed output'
 for name,lines in a.items():
  if name.endswith('.jsonl'): [json.loads(x) for x in lines]
 assert len(a['professional_counterexamples.jsonl'])>=30
 # Specific invariants: no total-pressure proxy; local thresholds not global; competing roles retained.
 p=[json.loads(x) for x in a['pilot_predicates.jsonl']]
 assert any(x['clause_no']=='6.7' and x['property']=='gas_partial_pressure_H2S' for x in p)
 assert any(x['clause_no']=='5.23' and x['property']=='temperature_c' and x['scope']=='not global corrosion applicability interval' for x in p)
 assert any(x['clause_no']=='5.6' and x['operator']=='conflicts_with' for x in p)
 print(f'PASS repeat-determinism outputs={len(a)} source_rows=82 pilot=15 predicates={len(p)} authored_cases={len(a["professional_counterexamples.jsonl"])} human_gold=0')

def write_outputs():
 out,summary=build(); OUT.mkdir(parents=True,exist_ok=True)
 for name,lines in out.items(): (OUT/name).write_text(''.join(lines),encoding='utf-8',newline='\n')
 print(canonical(summary))

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--self-test',action='store_true'); ap.add_argument('--write',action='store_true'); ap.add_argument('--check',action='store_true'); args=ap.parse_args()
 if args.self_test:self_test()
 if args.write:write_outputs()
 if args.check or not (args.self_test or args.write):
  out,s=build(); print('CHECK PASS',canonical(s))
if __name__=='__main__':main()


