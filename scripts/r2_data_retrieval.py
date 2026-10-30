"""Build and exercise a read-only, derived R2 retrieval index.

The canonical teacher JSONL is opened read-only. Derived files contain source
identifiers and pointers only, not copied standard paragraphs. Query results are
retrieval candidates; they never assert engineering applicability.

Usage (from the project root):
  python -B scripts/r2_data_retrieval.py build
  python -B scripts/r2_data_retrieval.py audit --limit 64
  python -B scripts/r2_data_retrieval.py self-test
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from statistics import mean
from time import perf_counter
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SOURCE = ROOT / "upstream" / "05_提交区" / "clauses.jsonl"
OUT = ROOT / "knowledge" / "retrieval" / "r2_candidate_v1"
SOURCE_SHA_EXPECTED = "a8151797ba15a6a7452dd83aaec9fab4c0a815724ca45062eb1e2bac7b4d49ef"

# Alias expansions are query rewrites only. They are not canonical synonyms,
# source evidence, or applicability rules.
ALIASES: dict[str, list[str]] = {
    "壳体磕碰损伤": ["机械损伤", "表面缺陷", "局部变形", "容器损伤"],
    "壳体磕碰": ["机械损伤", "表面缺陷", "局部变形"],
    "磕碰": ["机械损伤", "表面缺陷", "凹陷", "局部变形"],
    "碰撞损伤": ["机械损伤", "表面缺陷", "局部变形"],
    "撞击": ["机械损伤", "表面缺陷", "局部变形"],
    "湿h2s": ["湿硫化氢", "硫化物应力腐蚀开裂", "氢致开裂"],
    "湿硫化氢气相分压": ["湿硫化氢", "硫化氢分压", "气相分压"],
    "h2s分压": ["湿硫化氢", "硫化氢分压", "气相分压"],
    "总压力": ["系统压力"],
    "酸雾": ["酸露点腐蚀", "烟气露点腐蚀", "硫酸露点腐蚀"],
    "烟气侧": ["烟气露点腐蚀", "酸露点腐蚀", "硫酸露点腐蚀"],
}

# Query-specific hard negative: the word “碰撞” appears in the explanation of
# neutron/particle collisions, not mechanical damage to an equipment shell.
HARD_NEGATIVES = {
    ("shell_impact", "GBT30579-2022-7.11"):
        "词面碰撞命中的是辐照粒子与晶格原子碰撞；语义对象不是壳体机械磕碰",
    ("hcl_not_flue", "GBT30579-2022-5.18"):
        "查询明确限定非烟气侧；5.18标题为烟气露点腐蚀，存在介质/位置语义冲突，应保留作负例而非适用候选",
}

SCENARIOS = {
    "acid_water_60_80": ["300系列不锈钢 碱式酸性水 60℃", "300系列不锈钢 碱式酸性水 80℃"],
    "shell_impact": ["壳体磕碰损伤 停机维修 验收", "压力容器壳体凹陷 机械损伤 表面缺陷检测"],
    "hcl_not_flue": ["碳钢 95℃ 盐酸腐蚀 非烟气侧", "盐酸腐蚀 碳钢 95℃"],
    "wet_h2s_partial_pressure": ["湿H2S 硫化氢分压 碳钢", "湿硫化氢气相分压 系统总压力 区分"],
    "acid_mist_flue": ["酸雾 烟气侧 酸露点腐蚀", "烟气露点腐蚀 硫酸露点"],
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_rows(path: Path = SOURCE) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(path)
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def source_scope(row: dict[str, Any]) -> list[dict[str, Any]]:
    """Small structured scope notes, machine-projected and unreviewed."""
    cid = row["clause_id"]
    if cid == "GBT30579-2022-5.23":
        return [{
            "subject": "NH4HS气相析出/局部沉积相关条件",
            "field": "temperature_c",
            "value": [49, 66],
            "unit": "°C",
            "source_role": "local_scope_window",
            "polarity": "supporting_subcondition_not_global_necessary_condition",
            "scope_note": "不作为酸性水腐蚀整个机理的全局必要温区；60/80℃均不得据此单独硬排除",
            "review_state": "UNREVIEWED_MACHINE_PROJECTION",
        }]
    if cid == "GBT30579-2022-5.6":
        return [{
            "subject": "环烷酸腐蚀描述中的温度条件",
            "field": "temperature_c",
            "value": [177, 242],
            "unit": "°C",
            "source_role": "source_stated_range",
            "polarity": "candidate_condition",
            "scope_note": "轻相介质另有218–400°C描述；不合并为一个阈值",
            "review_state": "UNREVIEWED_MACHINE_PROJECTION",
        }, {
            "subject": "环烷酸腐蚀轻相介质常见温区",
            "field": "temperature_c",
            "value": [218, 400],
            "unit": "°C",
            "source_role": "subtype_or_phase_specific_range",
            "polarity": "candidate_condition",
            "scope_note": "与177–242°C描述分开保留，具体条件待专业复核",
            "review_state": "UNREVIEWED_MACHINE_PROJECTION",
        }]
    if cid == "GBT30579-2022-6.7":
        return [{
            "subject": "湿硫化氢气相分压",
            "field": "h2s_partial_pressure_mpa",
            "value": {"operator": ">", "threshold": 0.0003},
            "unit": "MPa",
            "source_role": "source_stated_partial_pressure_condition",
            "polarity": "candidate_condition",
            "scope_note": "变量是H2S气相分压，不是设备系统总压力；两者不可互换",
            "review_state": "UNREVIEWED_MACHINE_PROJECTION",
        }, {
            "subject": "湿硫化物应力腐蚀开裂子型温度描述",
            "field": "temperature_c",
            "value": {"operator": "<", "threshold": 82},
            "unit": "°C",
            "source_role": "submechanism_specific_range",
            "polarity": "candidate_condition",
            "scope_note": "不能扩展到同条款列举的所有损伤形式",
            "review_state": "UNREVIEWED_MACHINE_PROJECTION",
        }, {
            "subject": "湿硫化氢氢鼓泡/氢致开裂/应力导向氢致开裂子型温度描述",
            "field": "temperature_c",
            "value": {"operator": "range_from_room_temperature_to", "threshold": 150},
            "unit": "°C",
            "source_role": "submechanism_specific_range",
            "polarity": "candidate_condition",
            "scope_note": "原记录另称有时更高；不把150°C误用于全部子型",
            "review_state": "UNREVIEWED_MACHINE_PROJECTION",
        }]
    if cid in {"TSG21-2016-8.5.8", "TSG21-2016-8.3.6"}:
        return [{
            "subject": "TSG条款对象/条件",
            "field": "applicability_scope",
            "value": row.get("applicable_conditions", {}).get("other", ""),
            "unit": None,
            "source_role": "source_extracted_scope",
            "polarity": "conditional_candidate",
            "scope_note": "检索到相关条款不等于已核实设备适用；8.5.8涉及已发现裂纹，8.3.6为表面缺陷检测规定",
            "review_state": "UNREVIEWED_MACHINE_PROJECTION",
        }]
    return []


def build_index(rows: list[dict[str, Any]], source_digest: str) -> list[dict[str, Any]]:
    result = []
    for line_no, row in enumerate(rows, start=1):
        result.append({
            "clause_id": row["clause_id"],
            "standard_code": row.get("standard_code"),
            "clause_no": row.get("clause_no"),
            "printed_page": row.get("page"),
            "pdf_page_index": None,
            "source_hash": source_digest,
            "excerpt_ref": f"upstream/05_提交区/clauses.jsonl#L{line_no}",
            "knowledge_type": row.get("knowledge_type"),
            "title": row.get("title", ""),
            "scenario_tags": scenario_tags(row),
            "contextual_predicates": source_scope(row),
            "review_state": "SOURCE_RECORD_PRESENT_HUMAN_APPLICABILITY_UNREVIEWED",
            "semantic_relevance": "UNKNOWN_UNTIL_QUERY_REVIEW",
            "applicability": "UNKNOWN_UNTIL_CASE_REVIEW",
        })
    return result


def scenario_tags(row: dict[str, Any]) -> list[str]:
    cid = row.get("clause_id", "")
    tags: set[str] = set()
    if cid == "GBT30579-2022-5.23": tags.update(["acid_water", "alkaline_acid_water", "nh4hs"])
    if cid == "GBT30579-2022-5.6": tags.add("naphthenic_acid")
    if cid == "GBT30579-2022-6.7": tags.update(["wet_h2s", "h2s_partial_pressure"])
    if cid == "TSG21-2016-8.5.8": tags.update(["mechanical_damage", "environmental_cracking", "pressure_vessel"])
    if cid == "TSG21-2016-8.3.6": tags.update(["surface_defect", "mechanical_damage", "inspection_method"])
    title = row.get("title", "")
    if "露点" in title or "硫酸" in title or "烟气" in title: tags.add("dew_point_corrosion")
    return sorted(tags)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(x, ensure_ascii=False, sort_keys=True) + "\n" for x in rows), encoding="utf-8")


def build() -> dict[str, Any]:
    digest = sha256(SOURCE)
    rows = read_rows()
    if digest.lower() != SOURCE_SHA_EXPECTED:
        raise RuntimeError(f"Frozen source hash changed: {digest}; expected {SOURCE_SHA_EXPECTED}")
    if len(rows) != 554 or Counter(r["knowledge_type"] for r in rows) != Counter({"rbi": 472, "damage_mechanism": 82}):
        raise RuntimeError("Unexpected source row count/type distribution")
    index = build_index(rows, digest)
    write_jsonl(OUT / "clauses.jsonl", index)
    (OUT / "term_aliases.json").write_text(json.dumps({"version": "r2_candidate_v1", "authority": "query_rewrite_only", "aliases": ALIASES}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT / "hard_negatives.json").write_text(json.dumps({"version": "r2_candidate_v1", "cases": [{"scenario": k[0], "clause_id": k[1], "classification": "NEGATIVE_SEMANTIC_MATCH", "reason": v} for k, v in HARD_NEGATIVES.items()]}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "index_version": "r2_candidate_v1",
        "built_from": "upstream/05_提交区/clauses.jsonl",
        "source_sha256": digest,
        "source_rows": len(rows),
        "knowledge_type_counts": dict(Counter(r["knowledge_type"] for r in rows)),
        "derived_rows": len(index),
        "full_standard_text_copied": False,
        "pdf_page_index": "null where source JSONL does not supply physical PDF page index",
        "human_reviewed": False,
        "applicability_authority": "none; all candidates remain UNKNOWN until case-specific review",
        "teacher_tool_added": False,
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    matrix = coverage_matrix()
    (OUT / "coverage_matrix.json").write_text(json.dumps(matrix, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def coverage_matrix() -> dict[str, Any]:
    return {
        "classification": "SOURCE_COVERAGE_NOT_APPLICABILITY_OR_GOLD",
        "rows": [
            {"task": "concept explanation", "source_ids": ["GBT30579-2022-5.23", "GBT30579-2022-5.6", "GBT30579-2022-6.7"], "coverage": "partial; damage-mechanism source records exist", "applicability": "UNKNOWN"},
            {"task": "acid-water mechanism", "source_ids": ["GBT30579-2022-5.23"], "coverage": "source record available", "applicability": "UNKNOWN; 49–66°C is local NH4HS condition, not global mechanism gate"},
            {"task": "shell impact / mechanical damage", "source_ids": ["TSG21-2016-8.5.8", "TSG21-2016-8.3.6"], "coverage": "related retrieval available", "applicability": "UNKNOWN; 8.5.8 has cracked-container scope; not a general dent acceptance rule"},
            {"task": "inspection method", "source_ids": ["TSG21-2016-8.3.6"], "coverage": "conditional source record available", "applicability": "UNKNOWN until device/material/scope checked"},
            {"task": "repair / acceptance / stop-return-to-service", "source_ids": ["TSG21-2016-8.5.8"], "coverage": "narrow conditional clause only", "applicability": "UNKNOWN; no general dent depth limit or universal acceptance threshold inferred"},
            {"task": "RBI risk and inspection interval", "source_ids": [], "coverage": "source-dependent; this index does not calculate risk", "applicability": "UNKNOWN absent required inputs and validated method"},
            {"task": "HCl 95°C non-flue-side", "source_ids": ["GBT30579-2022-5.1"], "coverage": "related mechanism source available", "applicability": "UNKNOWN; do not substitute flue-gas dew-point mechanism"},
            {"task": "wet H2S pressure", "source_ids": ["GBT30579-2022-6.7"], "coverage": "source record and explicit H2S partial-pressure field", "applicability": "UNKNOWN; partial pressure not total system pressure"},
            {"task": "acid mist / flue side", "source_ids": ["GBT30579-2022-5.18"], "coverage": "smoke/flue-gas dew-point mechanism source record available", "applicability": "UNKNOWN; not a substitute for HCl process-side corrosion"},
        ],
    }


class CandidateIndex:
    """Read-only in-memory FTS index built directly from frozen JSONL."""

    def __init__(self, rows: list[dict[str, Any]]):
        self.con = sqlite3.connect(":memory:")
        self.con.row_factory = sqlite3.Row
        self.con.execute("CREATE VIRTUAL TABLE docs USING fts5(title,body,clause_id UNINDEXED,kind UNINDEXED,standard UNINDEXED,page UNINDEXED, tokenize='trigram')")
        self.rows = {r["clause_id"]: r for r in rows}
        self.con.executemany("INSERT INTO docs VALUES(?,?,?,?,?,?)", [(r.get("title", ""), r.get("content_raw", ""), r["clause_id"], r["knowledge_type"], r.get("standard_code", ""), r.get("page")) for r in rows])

    @staticmethod
    def _query(q: str) -> str:
        # Phrase quoting prevents FTS operators in user text from becoming syntax.
        phrases = [x for x in re.split(r"[\s，。；,;:：/]+", q.strip()) if len(x) >= 3]
        return " OR ".join('"' + x.replace('"', '""') + '"' for x in phrases)

    def search_one(self, query: str, top_k: int = 10) -> list[dict[str, Any]]:
        expr = self._query(query)
        if not expr:
            return []
        rows = self.con.execute("SELECT clause_id,title,kind,standard,page,-bm25(docs,6.0,1.0) AS score FROM docs WHERE docs MATCH ? ORDER BY bm25(docs,6.0,1.0),clause_id LIMIT ?", (expr, top_k)).fetchall()
        return [dict(x) for x in rows]

    def search(self, query: str, top_k: int = 8, scenario: str | None = None) -> list[dict[str, Any]]:
        expanded = expand_query(query)
        combined: dict[str, dict[str, Any]] = {}
        for q in [query, *expanded]:
            for hit in self.search_one(q, max(top_k * 2, 12)):
                old = combined.get(hit["clause_id"])
                if old is None or hit["score"] > old["score"]:
                    combined[hit["clause_id"]] = hit | {"matched_by": q}
        hits = list(combined.values())
        for hit in hits:
            hit["source_record_present"] = True
            negative = classify_semantic_relevance(hit["clause_id"], scenario)
            hit["semantic_relevance"] = negative[0]
            hit["applicability"] = "UNKNOWN"
            hit["negative_reason"] = negative[1]
        # Prefer explicit semantic negatives at the bottom; keep them visible for
        # auditing rather than silently representing them as true relevant hits.
        hits.sort(key=lambda h: (h["semantic_relevance"] == "NEGATIVE_SEMANTIC_MATCH", -h["score"], h["clause_id"]))
        return hits[:top_k]

    def close(self) -> None:
        self.con.close()


def expand_query(query: str) -> list[str]:
    lowered = query.lower()
    out: list[str] = []
    # Longest phrase first; expansions never override original query.
    for key in sorted(ALIASES, key=len, reverse=True):
        if key.lower() in lowered:
            out.extend(ALIASES[key])
    return list(dict.fromkeys(out))


def classify_semantic_relevance(clause_id: str, scenario: str | None) -> tuple[str, str | None]:
    reason = HARD_NEGATIVES.get((scenario or "", clause_id))
    if reason:
        return "NEGATIVE_SEMANTIC_MATCH", reason
    return "RELATED_RETRIEVAL_ONLY", None


def load_frozen_queries() -> list[dict[str, Any]]:
    # Existing synthetic fixtures are frozen regression inputs, not human gold.
    paths = [ROOT / "evals" / "p0_expert_guidance" / "cases.jsonl", ROOT / "evals" / "v2b_professional_cases.jsonl"]
    out = []
    for path in paths:
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip(): continue
            case = json.loads(line)
            q = case.get("question")
            if q:
                out.append({"case_id": case.get("case_id"), "query": q, "fixture_source": path.relative_to(ROOT).as_posix(), "gold": False})
    # Stable de-duplication by text; retain first provenance.
    seen: set[str] = set(); unique = []
    for case in out:
        if case["query"] not in seen:
            seen.add(case["query"]); unique.append(case)
    return unique


def audit(limit: int = 64) -> dict[str, Any]:
    frozen = load_frozen_queries()[:limit]
    if len(frozen) < 50:
        raise RuntimeError(f"Need >=50 frozen existing queries, found {len(frozen)}")
    rows = read_rows()
    # Existing baseline implementation is immutable and only used in memory.
    from knowledge.lexical import SqliteLexicalRetriever
    old = SqliteLexicalRetriever(SOURCE)
    records = []
    old_nonempty = new_nonempty = 0
    start_init = perf_counter(); new = CandidateIndex(rows); build_ms = (perf_counter() - start_init) * 1000
    for case in frozen:
        t = perf_counter(); old_hits = old.search(case["query"], top_k=5); old_ms = (perf_counter() - t) * 1000
        t = perf_counter(); new_hits = new.search(case["query"], top_k=5); new_ms = (perf_counter() - t) * 1000
        old_ids = [h["clause_id"] for h in old_hits]; new_ids = [h["clause_id"] for h in new_hits]
        old_nonempty += bool(old_ids); new_nonempty += bool(new_ids)
        records.append({"case_id": case["case_id"], "fixture_source": case["fixture_source"], "query": case["query"], "old_top5": old_ids, "new_top5": new_ids,
                        "old_nonempty": bool(old_ids), "new_nonempty": bool(new_ids), "old_latency_ms": round(old_ms, 4), "new_latency_ms": round(new_ms, 4),
                        "gold": False, "correctness_score": None})
    # Focused critical checks ensure query expansion reaches source-bearing
    # candidates and that a lexical false positive is explicitly declassified.
    critical = []
    for scenario, queries in SCENARIOS.items():
        for query in queries:
            hits = new.search(query, scenario=scenario)
            critical.append({"scenario": scenario, "query": query, "top_ids": [h["clause_id"] for h in hits],
                             "semantic_relevance": {h["clause_id"]: h["semantic_relevance"] for h in hits},
                             "applicability": "UNKNOWN", "query_expansion": expand_query(query)})
    old.close(); new.close()
    result = {
        "summary": {"frozen_existing_queries": len(frozen), "human_gold_queries": 0, "source": "AUTHOR_SYNTHETIC regression fixtures; frozen on disk", "old_baseline": "knowledge.lexical.SqliteLexicalRetriever", "new_candidate": "R2 alias-expanded in-memory FTS5", "old_nonempty_retrieval": old_nonempty, "new_nonempty_retrieval": new_nonempty, "old_nonempty_rate": round(old_nonempty / len(frozen), 4), "new_nonempty_rate": round(new_nonempty / len(frozen), 4), "candidate_index_init_ms": round(build_ms, 3), "precision": None, "recall_at_k": None, "mrr": None, "latency_claim": "synthetic local timing only; no warmup/paired significance"},
        "frozen_cases": records,
        "critical_scenarios": critical,
        "source_sha256": sha256(SOURCE),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "retrieval_audit.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def self_test() -> list[str]:
    rows = read_rows(); digest = sha256(SOURCE)
    idx_rows = build_index(rows, digest)
    assert len(rows) == 554 and sum(r["knowledge_type"] == "damage_mechanism" for r in rows) == 82
    c = CandidateIndex(rows)
    try:
        acid60 = c.search("300系列不锈钢 碱式酸性水 60℃")
        acid80 = c.search("300系列不锈钢 碱式酸性水 80℃")
        assert "GBT30579-2022-5.23" in [x["clause_id"] for x in acid60]
        assert "GBT30579-2022-5.23" in [x["clause_id"] for x in acid80]
        shell = c.search("壳体磕碰损伤", scenario="shell_impact")
        by_id = {x["clause_id"]: x for x in shell}
        assert "TSG21-2016-8.5.8" in by_id and "TSG21-2016-8.3.6" in by_id
        assert classify_semantic_relevance("GBT30579-2022-7.11", "shell_impact")[0] == "NEGATIVE_SEMANTIC_MATCH"
        hcl = {x["clause_id"]: x for x in c.search("碳钢 95℃ 盐酸腐蚀 非烟气侧", scenario="hcl_not_flue", top_k=12)}
        assert hcl["GBT30579-2022-5.1"]["semantic_relevance"] == "RELATED_RETRIEVAL_ONLY"
        assert classify_semantic_relevance("GBT30579-2022-5.18", "hcl_not_flue")[0] == "NEGATIVE_SEMANTIC_MATCH"
        h2s = c.search("湿H2S分压")
        assert "GBT30579-2022-6.7" in [x["clause_id"] for x in h2s]
        assert all(x["applicability"] == "UNKNOWN" for x in shell + acid60 + acid80)
    finally:
        c.close()
    assert next(x for x in idx_rows if x["clause_id"] == "GBT30579-2022-5.23")["contextual_predicates"][0]["polarity"] == "supporting_subcondition_not_global_necessary_condition"
    return ["554/472+82 source integrity", "acid water 60C retains 5.23 candidate", "acid water 80C retains 5.23 candidate", "shell impact maps to TSG 8.5.8 and 8.3.6", "radiation embrittlement hard negative rule", "HCl non-flue query separates 5.1 from 5.18 negative", "H2S partial pressure maps to 6.7", "all retrieval candidates retain applicability UNKNOWN", "5.23 local scope predicate is not global exclusion"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["build", "audit", "self-test"])
    parser.add_argument("--limit", type=int, default=64)
    args = parser.parse_args()
    if args.action == "build":
        print(json.dumps(build(), ensure_ascii=False, indent=2))
    elif args.action == "audit":
        print(json.dumps(audit(args.limit)["summary"], ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"checks": self_test(), "status": "PASS"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
