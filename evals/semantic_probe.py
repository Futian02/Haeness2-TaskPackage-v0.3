"""Unlabelled natural-language retrieval smoke probe.

Inspect only; do not turn hit rankings into "correct" domain conclusions.
"""
from __future__ import annotations

import json

from app.runtime import load_harness
from knowledge.lexical import SqliteLexicalRetriever

SCENARIOS = [
    {"question": "塔顶水样铁离子升高，pH下降，尚未测厚，可能出现什么损伤机理？", "tag": "narrative_unknown"},
    {"question": "压降增大且结盐迹象明显，怀疑塔顶注水点上游腐蚀", "tag": "phenomenology"},
    {"question": "设备没有测量是否减薄，也不知道是否有裂纹，能直接给RBI风险等级吗？", "tag": "missing_inspection"},
    {"question": "不锈钢设备附近出现沿晶裂纹，涉及氯离子环境", "tag": "ambiguous_material"},
    {"question": "连续发现铁离子浓度偏高但无法确认采样位置", "tag": "weak_evidence"}
]


def main():
    official = load_harness().tool_impl
    fts = SqliteLexicalRetriever()
    try:
        for case in SCENARIOS:
            o = official.standard_clause_search(
                keyword=case["question"], knowledge_type="damage_mechanism", top_k=5
            )
            f = fts.search(case["question"], kind="damage_mechanism", top_k=5)
            print(json.dumps({
                "tag": case["tag"],
                "query": case["question"],
                "official_status": o["status"],
                "official_titles": [
                    {"name": h["title"], "clause_id": h["clause_id"]}
                    for h in (o.get("result") or {}).get("hits", [])
                ],
                "fts_titles": [
                    {"name": h["title"], "clause_id": h["clause_id"]}
                    for h in f
                ],
                "note": "Exploratory unlabelled ranking; not expert-verified evidence",
            }, ensure_ascii=False))
    finally:
        fts.close()


if __name__ == "__main__":
    main()
