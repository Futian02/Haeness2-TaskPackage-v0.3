"""Build review-required semantic card candidates from the frozen clause JSONL.

No OCR, standard paraphrase, or teacher-package write is performed. Page printed
numbers come from structured clauses; PDF page indices remain unknown until review.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLAUSES = ROOT / "upstream" / "05_提交区" / "clauses.jsonl"
OUT = ROOT / "knowledge" / "semantic_drafts.jsonl"
CASES = ROOT / "evals" / "semantic_cases.json"

CARDS = [
    ("盐酸腐蚀", ["塔顶水样pH下降", "湿氯化氢", "铁离子升高"]),
    ("氯化铵腐蚀", ["注水点上游结盐", "铵盐沉积", "压降趋势变化"]),
    ("湿硫化氢破坏", ["湿H2S环境", "裂纹/鼓泡待检", "H2S浓度未知"]),
    ("氯化物应力腐蚀开裂", ["氯离子环境", "奥氏体不锈钢", "裂纹未确认"]),
    ("高温氧化", ["高温烟气", "氧化皮", "壁厚待测"]),
    ("微生物腐蚀", ["冷却水系统", "沉积物下局部腐蚀", "微生物检测未做"]),
    ("冷却水腐蚀", ["循环冷却水", "水质变化", "局部减薄待核"]),
    ("胺腐蚀", ["胺液系统", "胺浓度/温度", "腐蚀监测数据缺失"]),
    ("高温硫化物腐蚀(无氢气环境)", ["高温含硫介质", "无氢气环境待确认", "壁厚趋势待查"]),
    ("硝酸盐应力腐蚀开裂", ["硝酸盐介质", "拉应力", "裂纹检查未完成"]),
]

CASES_DATA = [
    ("塔顶水样pH从7降到4.8，铁离子升高，塔顶冷凝水接触含氯化氢介质。", "盐酸腐蚀", ["pH", "iron_ion"], ["wall_thinning", "temperature_c"]),
    ("注水点上游有沉积物且压降逐周增加，介质包含氯化铵；尚未做内窥。", "氯化铵腐蚀", [], ["crystal_location", "wall_thinning"]),
    ("湿H2S管线巡检发现鼓泡迹象，但没有H2S分压与硬度数据。", "湿硫化氢破坏", [], ["h2s_partial_pressure", "hardness"]),
    ("不锈钢换热器氯离子偏高，焊缝区域还未做PT检查。", "氯化物应力腐蚀开裂", [], ["chloride_value", "crack_found"]),
    ("炉管长期高温氧化气氛运行，氧化皮变厚，最近一次测厚结果缺失。", "高温氧化", [], ["temperature_c", "wall_thinning"]),
    ("循环水换热器有黏泥和局部点蚀报告，但没有微生物检测。", "微生物腐蚀", [], ["microbiology_test", "wall_thinning"]),
    ("冷却水氯离子上升、换热器压差变化，现场仅报告水侧局部减薄待确认。", "冷却水腐蚀", [], ["wall_thinning", "water_chemistry"]),
    ("胺液再生系统出现铁离子上升，胺液浓度和温度趋势没有提供。", "胺腐蚀", [], ["amine_concentration", "temperature_c"]),
    ("高温含硫工艺管线有减薄记录，是否存在氢气环境尚不清楚。", "高温硫化物腐蚀(无氢气环境)", [], ["hydrogen_environment", "wall_thinning"]),
    ("硝酸盐清洗后的受拉不锈钢部件未完成表面裂纹检测。", "硝酸盐应力腐蚀开裂", [], ["nitrate_concentration", "crack_found"]),
]


def main() -> None:
    if not CLAUSES.is_file(): raise SystemExit(f"missing upstream source: {CLAUSES}")
    sha = hashlib.sha256(CLAUSES.read_bytes()).hexdigest()
    rows = [json.loads(line) for line in CLAUSES.read_text(encoding="utf-8").splitlines() if line.strip()]
    by_title = {r.get("title"): r for r in rows if r.get("knowledge_type") == "damage_mechanism"}
    drafts = []
    for title, aliases in CARDS:
        source = by_title.get(title)
        if not source: raise SystemExit(f"no exact official clause title: {title}")
        drafts.append({
            "mechanism_id": source["clause_id"], "official_name": title,
            "source_clause_ids": [source["clause_id"]],
            "applicable_conditions": source.get("applicable_conditions", {}),
            "mechanism_eight_fields": source.get("mechanism_detail", {}),
            "term_aliases": aliases, "supporting_evidence": [], "contradictory_evidence": [],
            "missing_facts": ["现场适用性尚未审核"], "discriminator_questions": ["待领域专家审核并补充可证伪鉴别问题"],
            "evidence_level": "E0", "reviewed": False, "review_status": "draft_needs_review",
            "source_file_sha": sha,
            "source": {"doc_sha256": sha, "standard_code": source.get("standard_code"), "clause_no": source.get("clause_no"),
                       "page_printed": source.get("page"), "pdf_page": None, "quote_span": source.get("content_raw"),
                       "extraction_method": "structured_clause_jsonl", "review_status": "draft_needs_review"},
        })
    OUT.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in drafts), encoding="utf-8")
    cases = []
    for query, title, observed, unknown in CASES_DATA:
        source = by_title[title]
        cases.append({"case_id": f"SEM-{len(cases)+1:02d}", "query": query, "candidate_label_draft": title,
                      "candidate_clause_id": source["clause_id"], "observed_fields_draft": observed,
                      "unknown_fields_draft": unknown, "review_status": "draft_needs_review", "gold": False})
    CASES.write_text(json.dumps(cases, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"draft_cards={len(drafts)} semantic_cases={len(cases)} source_sha256={sha}")
    print(f"wrote {OUT.relative_to(ROOT)} and {CASES.relative_to(ROOT)} (all draft_needs_review)")


if __name__ == "__main__": main()
