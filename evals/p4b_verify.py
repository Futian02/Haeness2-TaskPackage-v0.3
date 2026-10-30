"""Rule-behavior probe for P4B. Synthetic cases are not expert gold labels."""
from __future__ import annotations

import json
from pathlib import Path
from orchestration.evidence_audit import audit_claim, load_clause_index
from orchestration.graph import RunState

ROOT = Path(__file__).resolve().parents[1]


def percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int((len(ordered) - 1) * pct))] if ordered else 0.0


def main() -> None:
    index = load_clause_index()
    canonical = next(iter(index.values()), None)
    if not canonical:
        raise SystemExit("FAIL: canonical clauses.jsonl unavailable/empty")
    cid = canonical["clause_id"]
    source = {key: canonical.get(key) for key in ("clause_id", "standard_code", "clause_no", "page")}
    scenarios = [json.loads(line) for line in (ROOT / "evals" / "p3b_unreviewed_scenarios.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    samples: list[float] = []
    for case in scenarios:
        state = RunState(case["case_id"], "synthetic", case["question"], case.get("context", {}),
                         observations=[{
                             "field": item["field"], "raw_span": str(item.get("value", "")),
                             "normalized_value": item.get("value"), "observation_state": item.get("observation_state", "observed_true"),
                         } for item in case.get("observations", [])],
                         tool_results=[{"tool": "standard_clause_search", "result": {"source": [source]}}])
        claim = {"claim_id": case["case_id"], "kind": "engineering_hypothesis", "text": "synthetic rule check",
                 "source_clause_ids": [cid]}
        import time
        start = time.perf_counter()
        result = audit_claim(claim, state, index)
        samples.append((time.perf_counter() - start) * 1000)
        # This asserts only safe rule behavior on each scenario's own context and
        # observation payload, not expert correctness or standard entailment.
        assert result.verdict == "unresolved" and result.review_status == "requires_human_review"
    negatives = [json.loads(line) for line in (ROOT / "evals" / "p4b_negative_cases.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    print(json.dumps({
        "status": "RULE_BEHAVIOR_PASS_NOT_EXPERT_GOLD",
        "existing_synthetic_unreviewed_cases": len(scenarios),
        "negative_cross_source_cases": len(negatives),
        "all_existing_cases_remain_unresolved_for_human_review": True,
        "tool_call_count_per_fixture_case": 1,
        "p50_audit_ms": round(percentile(samples, 0.50), 3),
        "p95_audit_ms": round(percentile(samples, 0.95), 3),
        "canonical_clause_count": len(index),
        "human_review_ratio": 1.0,
        "event_persistence": "covered by tests/test_p4b_claim_verifier.py graph/store integration inherited P3B",
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
