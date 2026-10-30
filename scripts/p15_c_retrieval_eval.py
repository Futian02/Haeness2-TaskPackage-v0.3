"""Frozen retrieval probes against the unchanged official three-tool implementation."""
from __future__ import annotations
import argparse, csv, json, sys, importlib.util
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"upstream/05_提交区"))
import tools  # noqa: E402 - intentionally test teacher tools, no edits or adapter

CASES=[
 ("area_a","standard_clause_search","GB/T 26610.5 表2 面积后果 A CA 9.29 平方米","GBT26610.5-2022-表2-a"),
 ("area_b","standard_clause_search","26610.5 最终后果面积 B 9.29 到 92.9 m2","GBT26610.5-2022-表2-b"),
 ("area_c","standard_clause_search","26610.5 表2 C级面积 92.9 279","GBT26610.5-2022-表2-c"),
 ("area_d","standard_clause_search","26610.5 表2 D 279 929 后果面积","GBT26610.5-2022-表2-d"),
 ("area_e","standard_clause_search","26610.5 表2 E CA 大于929面积后果等级","GBT26610.5-2022-表2-e"),
 ("area_table","standard_clause_search","GB/T 26610.5 表2 面积后果等级划分","GBT26610.5-2022-表2-a|GBT26610.5-2022-表2-b|GBT26610.5-2022-表2-c|GBT26610.5-2022-表2-d|GBT26610.5-2022-表2-e"),
 ("econ_table","standard_clause_search","26610.5 热交换器管束经济后果等级 表3","GBT26610.5-2022-5.4"),
 ("consequence_overview","standard_clause_search","失效后果定量分析的目的 潜在失效后果分级","GBT26610.5-2022-5.4"),
 ("likelihood_method","standard_clause_search","失效可能性定量分析方法 GB/T 26610.4 失效概率","GBT26610.4-2022-8.3.2"),
 ("matrix_3","standard_clause_search","26610.3 定性风险矩阵 可能性 后果 风险等级","GBT26610.3-2014-7-a"),
 ("matrix_5e","standard_clause_search","26610.3 风险矩阵 5E 高可能性 E后果","GBT26610.3-2014-7-y"),
 ("matrix_mapping","standard_clause_search","GB/T 26610.3-2014 风险矩阵图1 25格","GBT26610.3-2014-7-a"),
 ("inspection_strategy","standard_clause_search","26610.2 基于风险的检验策略 检验周期","GBT26610.2-2022-8.2"),
 ("rbi_basic","standard_clause_search","GB/T 26610.1 基本要求 实施程序 RBI","__NO_GOLD__"),
 ("dm_523_title","standard_clause_search","30579 5.23 酸性水腐蚀 碱式","GBT30579-2022-5.23"),
 ("dm_523_nh4hs","standard_clause_search","碱式酸性水 硫氢化铵 NH4HS 腐蚀","GBT30579-2022-5.23"),
 ("dm_523_concentration","standard_clause_search","5.23 硫氢化铵 浓度超过2% 紊流区","GBT30579-2022-5.23"),
 ("dm_523_temp_window","standard_clause_search","5.23 49℃ 66℃ NH4HS 气相析出","GBT30579-2022-5.23"),
 ("dm_56_naphthenic","standard_clause_search","30579 5.6 环烷酸腐蚀","GBT30579-2022-5.6"),
 ("dm_56_177_242","standard_clause_search","5.6 177℃ 242℃ 环烷酸 金属腐蚀","GBT30579-2022-5.6"),
 ("dm_56_light_phase","standard_clause_search","环烷酸轻相介质 218℃ 400℃","GBT30579-2022-5.6"),
 ("dm_67_sour","standard_clause_search","30579 6.7 湿硫化氢破坏","GBT30579-2022-6.7"),
 ("dm_67_partial_pressure","standard_clause_search","6.7 湿硫化氢气相分压 0.0003 MPa","GBT30579-2022-6.7"),
 ("dm_67_hic","standard_clause_search","湿硫化氢 氢鼓泡 氢致开裂 HIC","GBT30579-2022-6.7"),
 ("dm_51_hcl","standard_clause_search","30579 5.1 盐酸腐蚀 氯化氢","GBT30579-2022-5.1"),
 ("dm_519_nh4cl","standard_clause_search","30579 5.19 氯化铵腐蚀 NH4Cl","GBT30579-2022-5.19"),
 ("dm_521_sulfidation","standard_clause_search","高温硫化物腐蚀 无氢气环境 5.21","GBT30579-2022-5.21"),
 ("dm_522_h2","standard_clause_search","高温硫化物腐蚀 氢气环境 5.22","GBT30579-2022-5.22"),
 ("dm_611_chloride","standard_clause_search","氯化物应力腐蚀开裂 6.1","GBT30579-2022-6.1"),
 ("dm_511_cui","standard_clause_search","大气腐蚀 有隔热层 5.11 保温层","GBT30579-2022-5.11"),
 ("dm_55_co2","standard_clause_search","二氧化碳腐蚀 5.5 CO2","GBT30579-2022-5.5"),
 ("dm_64_caustic","standard_clause_search","碱应力腐蚀开裂 氢氧化钠 6.4","GBT30579-2022-6.4"),
 ("dm_612_polythionic","standard_clause_search","连多硫酸应力腐蚀开裂 6.12","GBT30579-2022-6.12"),
 ("dm_93_erosion_corrosion","standard_clause_search","9.3 冲蚀 损伤模式","GBT30579-2022-9.3"),
 ("dm_86_erosion","standard_clause_search","8.6 冲刷 与冲蚀区别","GBT30579-2022-8.6"),
 ("dm_528_oxygen","standard_clause_search","含氧工艺水腐蚀 氧气 工艺水","GBT30579-2022-5.28"),
 ("dm_98_graphitization","standard_clause_search","铸铁石墨化腐蚀 9.8 软化水","GBT30579-2022-9.8"),
 ("tsg_period","standard_clause_search","TSG 21 定期检验 周期 安全状况等级","TSG21-2016-8.1.6.1-a"),
 ("tsg_modify","standard_clause_search","TSG 21 2016 第1号修改单 定期检验","__NO_GOLD__"),
 ("cross_material","standard_clause_search","GB/T 150.3 2024 材料设计许用应力","__NO_GOLD__"),
 ("cross_heat_exchanger","standard_clause_search","GB/T 151 热交换器设计制造","__NO_GOLD__"),
 ("cross_pipe","standard_clause_search","GB/T 21447 钢质管道外腐蚀控制","__NO_GOLD__"),
 ("negative_unknown_tool","standard_clause_search","不存在的标准号 9999 测试无依据假条款","__NO_GOLD__"),
 ("negative_fake_api","standard_clause_search","API 581 收费标准条文内容查询","__NO_GOLD__"),
 ("negative_raw_stream","standard_clause_search","原油物流名称不能直接推定腐蚀介质","__NO_GOLD__"),
 ("negative_pressure_type","standard_clause_search","6.7 湿硫化氢 0.0003 MPa 是总操作压力吗","GBT30579-2022-6.7"),
]

FILTER_PROBES=[
 {"case_id":"523_phase_window_55c","material":"碳钢","medium":["碱式酸性水"],"temperature_c":55,"pressure_mpa":None,"target":"GBT30579-2022-5.23","expected":"hit","basis":"the recorded 49–66 C value is stated as NH4HS gas-phase precipitation window; 55 C is a positive reproduction anchor, not an expert label"},
 {"case_id":"523_phase_window_80c","material":"碳钢","medium":["碱式酸性水"],"temperature_c":80,"pressure_mpa":None,"target":"GBT30579-2022-5.23","expected":"not_hard_excluded_by_local_phase_window","basis":"adversarial; PDF semantic confirmation pending. Check whether local precipitation range was misused as whole mechanism applicability"},
 {"case_id":"56_multi_window_220c","material":"碳钢","medium":["环烷酸"],"temperature_c":220,"pressure_mpa":None,"target":"GBT30579-2022-5.6","expected":"hit","basis":"inside reported 177–242 C general range and overlapping reported light-phase condition"},
 {"case_id":"56_light_phase_250c","material":"碳钢","medium":["环烷酸"],"temperature_c":250,"pressure_mpa":None,"target":"GBT30579-2022-5.6","expected":"review_not_silent_exclude","basis":"adversarial; workbook separately says light phase 218–400 C; PDF field/object mapping unverified"},
 {"case_id":"67_partial_vs_total_pressure","material":"碳钢","medium":["湿硫化氢"],"temperature_c":100,"pressure_mpa":0.0002,"target":"GBT30579-2022-6.7","expected":"must_not_treat_partial_pressure_as_total_pressure_bound","basis":"source wording in current record says gas-phase H2S partial pressure; query input pressure_mpa is total operating pressure"},
]

def invoke(case):
    _, method, query, gold=case
    response=tools.standard_clause_search(query,top_k=20)
    ids=[x.get("clause_id") for x in response.get("result",{}).get("hits",[]) if x.get("clause_id")]
    return response,ids

def evaluate(out: Path):
    rows=[]; recalled=0; relevant_total=0; rr=[]; positives=0; no_gold_count=0
    formal_records=tools.load_clauses()[0]
    for c in CASES:
        cid,name,q,gold=c
        resp,ids=invoke(c); expected=[] if gold=="__NO_GOLD__" else gold.split("|")
        if expected:
            positives+=1; rank=next((i+1 for i,x in enumerate(ids) if x in expected),None)
            matched=len(set(ids)&set(expected)); recalled+=matched; relevant_total+=len(set(expected)); rr.append(1/rank if rank else 0)
            ok=rank is not None
        else:
            rank=None; ok=""; no_gold_count+=1
        gold_state="FORMAL_CLAUSE_ID_LINKED_UNREVIEWED" if expected and set(expected).issubset(formal_records) else "NO_GOLD_UNJUDGED" if not expected else "GOLD_ID_NOT_IN_ACTIVE_CORPUS"
        rows.append({"case_id":cid,"method":name,"query":q,"expected_clause_ids":"|".join(expected),"query_origin":"SYNTHETIC_UNREVIEWED","gold_evidence_status":gold_state,"expected_exclusion":"no gold judgment; returned content must be manually assessed" if not expected else "none","status":resp.get("status"),"returned_clause_ids":"|".join(ids),"first_gold_rank":rank or "","recall_at_20":(len(set(ids)&set(expected))/len(set(expected))) if expected else "","empty_result":not bool(ids),"note":"retrieval only; not semantic/applicability verification"})
    out.parent.mkdir(parents=True,exist_ok=True)
    with out.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    evidence_counts={state:sum(r["gold_evidence_status"]==state for r in rows) for state in sorted({r["gold_evidence_status"] for r in rows})}
    print(f"cases={len(rows)} judged_positive={positives} retrieved_relevant={recalled}/{relevant_total} micro_recall@20={recalled/relevant_total:.3f} MRR@20={sum(rr)/positives:.3f} no_gold_unjudged={no_gold_count} evidence_states={json.dumps(evidence_counts,ensure_ascii=False)}")
    print(f"report={out}")
    for r in rows:
        if r["recall_at_20"] not in ("",1.0) or (r["empty_result"] and r["expected_clause_ids"]): print("PARTIAL_OR_MISS",r["case_id"],r["recall_at_20"],r["returned_clause_ids"])
    return 0

def evaluate_filters(out:Path):
    rows=[]
    for c in FILTER_PROBES:
        r=tools.damage_mechanism_query(material=c["material"],medium=c["medium"],temperature_c=c["temperature_c"],equipment_type="管道",evidence=None)
        hits=r.get("result",{}).get("mechanisms",[]); excluded=r.get("result",{}).get("excluded",[])
        hit_ids=[x.get("clause_id") for x in hits]; excluded_ids=[x.get("clause_id") for x in excluded]
        target_hit=c["target"] in hit_ids; target_excluded=c["target"] in excluded_ids
        if c["case_id"]=="67_partial_vs_total_pressure": outcome="NOT_TESTABLE_PRESSURE_NOT_TOOL_ARGUMENT"
        else: outcome="PASS" if target_hit else "FAIL_TARGET_NOT_RETRIEVED"
        rows.append({**c,"tool_status":r.get("status"),"target_hit":target_hit,"target_excluded":target_excluded,"probe_outcome":outcome,"returned_mechanism_ids":"|".join(x for x in hit_ids if x),"excluded_ids":"|".join(x for x in excluded_ids if x),"tool_message":r.get("message",""),"query_origin":"SYNTHETIC_UNREVIEWED","gold_evidence_status":"ADVERSARIAL_RULE_PROBE_UNREVIEWED"})
    out.parent.mkdir(parents=True,exist_ok=True)
    with out.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print(f"filter_probes={len(rows)} pass={sum(r['probe_outcome']=='PASS' for r in rows)} fail={sum(r['probe_outcome']=='FAIL_TARGET_NOT_RETRIEVED' for r in rows)} not_testable={sum(r['probe_outcome'].startswith('NOT_TESTABLE') for r in rows)} report={out}")
    for r in rows: print("FILTER",r["case_id"],"status="+str(r["tool_status"]),"hit="+str(r["target_hit"]),"outcome="+r["probe_outcome"])
    return 0

if __name__=="__main__":
    ap=argparse.ArgumentParser(); ap.add_argument("--out",type=Path,default=ROOT/"work/data_staging/p15/C_QA/P15_C_RETRIEVAL_RESULTS.csv"); ap.add_argument("--submit-dir",type=Path,help="optional isolated teacher-tool package directory containing candidate clauses.jsonl"); args=ap.parse_args()
    if args.submit_dir:
        submit=args.submit_dir.resolve();sys.path.insert(0,str(submit))
        spec=importlib.util.spec_from_file_location("p15_candidate_tools",submit/"tools.py");candidate=importlib.util.module_from_spec(spec);assert spec and spec.loader;spec.loader.exec_module(candidate);tools=candidate
        print(f"retrieval_dataset=CANDIDATE_STAGING clauses={submit/'clauses.jsonl'} tools_sha256={__import__('hashlib').sha256((submit/'tools.py').read_bytes()).hexdigest()}")
    else: print(f"retrieval_dataset=OFFICIAL_READ_ONLY clauses={ROOT/'upstream/05_提交区/clauses.jsonl'}")
    evaluate(args.out); raise SystemExit(evaluate_filters(args.out.with_name(args.out.stem+"_CONDITION_FILTER_PROBES.csv")))
