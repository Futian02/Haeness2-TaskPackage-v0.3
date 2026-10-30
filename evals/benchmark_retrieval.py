"""Read-only retrieval comparison with separated initialization and warm queries.

Run: python -B -m evals.benchmark_retrieval
Only exact-name sanity cases; no evidence of semantic/RAG robustness.
"""
from __future__ import annotations

import json
from pathlib import Path
from statistics import mean
from time import perf_counter

from app.runtime import load_harness
from knowledge.lexical import SqliteLexicalRetriever

HERE = Path(__file__).resolve().parent


def scores(case: dict, ids: list[str]) -> tuple[float, float]:
    relevant = set(case["relevant"])
    recall = 1.0 if relevant.intersection(ids) else 0.0
    rr = next((1.0 / i for i, cid in enumerate(ids, 1) if cid in relevant), 0.0)
    return recall, rr


def p95(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[max(0, (95 * len(ordered) + 99) // 100 - 1)]


def timed(call, repeat=30):
    # Every arm is warmed, so lazy clause loading does not skew its comparison.
    answer = call()
    times: list[float] = []
    for _ in range(repeat):
        start = perf_counter()
        answer = call()
        times.append((perf_counter() - start) * 1000)
    return answer, times


def run() -> dict:
    cases = json.loads((HERE / "retrieval_gold.json").read_text(encoding="utf-8"))
    start = perf_counter()
    hmod = load_harness()
    hmod.tool_impl.load_clauses()
    official_init_ms = (perf_counter() - start) * 1000
    start = perf_counter()
    retriever = SqliteLexicalRetriever()
    fts_init_ms = (perf_counter() - start) * 1000
    results = []
    try:
        for case in cases:
            args = {"keyword": case["query"], "knowledge_type": case["kind"], "top_k": 5}
            official, o_times = timed(lambda: hmod.tool_impl.standard_clause_search(**args))
            fts, f_times = timed(lambda: retriever.search(case["query"], kind=case["kind"]))
            if official.get("status") not in ("ok", "not_found"):
                raise RuntimeError(f"Official query failed: {official}")
            official_ids = [hit["clause_id"] for hit in (official.get("result") or {}).get("hits") or []]
            fts_ids = [hit["clause_id"] for hit in fts]
            o_r, o_rr = scores(case, official_ids)
            f_r, f_rr = scores(case, fts_ids)
            results.append({
                "query": case["query"], "expected": case["relevant"],
                "official_top5": official_ids, "fts5_top5": fts_ids,
                "official_hit": o_r, "fts5_hit": f_r,
                "official_rr": o_rr, "fts5_rr": f_rr,
                "official_warm_mean_ms": round(mean(o_times), 4),
                "fts5_warm_mean_ms": round(mean(f_times), 4),
                "official_warm_p95_ms": round(p95(o_times), 4),
                "fts5_warm_p95_ms": round(p95(f_times), 4),
            })
    finally:
        retriever.close()
    return {
        "summary": {
            "cases": len(results), "repeats_per_case": 30,
            "corpus_clauses": 554,
            "official_initialization_ms": round(official_init_ms, 3),
            "fts5_index_build_ms": round(fts_init_ms, 3),
            "official_recall_at_5": round(mean(x["official_hit"] for x in results), 4),
            "fts5_recall_at_5": round(mean(x["fts5_hit"] for x in results), 4),
            "official_mrr_at_5": round(mean(x["official_rr"] for x in results), 4),
            "fts5_mrr_at_5": round(mean(x["fts5_rr"] for x in results), 4),
            "official_warm_mean_ms": round(mean(x["official_warm_mean_ms"] for x in results), 4),
            "fts5_warm_mean_ms": round(mean(x["fts5_warm_mean_ms"] for x in results), 4),
            "note": "Only 8 exact technical terms: neither semantic nor risk/safety validation. No network/LLM latency included.",
        },
        "cases": results,
    }


def main():
    print(json.dumps(run(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
