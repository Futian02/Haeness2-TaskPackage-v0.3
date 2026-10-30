"""Synthetic-only timing/behavior comparison for the isolated P6-A graph."""
from __future__ import annotations

import copy
import json
import statistics
import time
from pathlib import Path

from orchestration.evidence_audit import audit_claim, skeptic_findings
from orchestration.p6_parallel_audit import merge_findings, run_parallel_audit
from tests.test_p6a_parallel_evidence import snapshot


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, int((len(ordered) * p + 0.999999) - 1)))]


def sequential(snapshot_data: dict) -> dict:
    state = type("State", (), {})()
    state.context = snapshot_data["context"]
    state.observations = snapshot_data["observations"]
    state.tool_results = snapshot_data["tool_results"]
    state.claims = snapshot_data["claims"]
    audits, skeptics = [], []
    for claim in state.claims:
        audited = audit_claim(claim, state, snapshot_data["clause_index"]).model_dump(mode="json")
        for cid in claim["source_clause_ids"]:
            from orchestration.p6_parallel_audit import AuditFinding
            audits.append(AuditFinding(snapshot_data["run_id"], claim["claim_id"], cid,
                                       "evidence_auditor", snapshot_data["attempt_id"], audited))
    for finding in skeptic_findings(state, snapshot_data["clause_index"]):
        claim = next(item for item in state.claims if item["claim_id"] == finding["claim_id"])
        for cid in claim["source_clause_ids"]:
            from orchestration.p6_parallel_audit import SkepticFinding
            skeptics.append(SkepticFinding(snapshot_data["run_id"], claim["claim_id"], cid,
                                           "skeptic", snapshot_data["attempt_id"], finding))
    return merge_findings(audits, skeptics)


def main() -> int:
    cases = [snapshot(case_id) for case_id in range(20)]
    parallel_ms: list[float] = []
    sequential_ms: list[float] = []
    tool_count_parallel = tool_count_sequential = 0
    duplicate_source_reads = 0
    illegal_grade_count = 0
    for case in cases:
        frozen = copy.deepcopy(case)
        t0 = time.perf_counter()
        p = run_parallel_audit(case)
        parallel_ms.append((time.perf_counter() - t0) * 1000)
        t0 = time.perf_counter()
        s = sequential(case)
        sequential_ms.append((time.perf_counter() - t0) * 1000)
        if p["merged_findings"] != s:
            raise AssertionError(f"branch order mismatch for {case['run_id']}")
        if case != frozen:
            raise AssertionError("parallel audit mutated its immutable input snapshot")
        tool_count_parallel += len(case["tool_results"])
        tool_count_sequential += len(case["tool_results"])
        source_ids = [source.get("clause_id") for call in case["tool_results"]
                      for source in ((call.get("result") or {}).get("source") or [])]
        duplicate_source_reads += len(source_ids) - len(set(source_ids))
        illegal_grade_count += sum(row["verification_level"] not in {"E0", "E1"}
                                   for row in p["merged_findings"])

    result = {
        "status": "READY_FOR_OWNER_REVIEW",
        "mode": "RULE_DEMO synthetic fixture; not multi-LLM and not expert gold",
        "cases": len(cases), "runs_per_mode": len(cases),
        "parallel_ms": {"p50": round(statistics.median(parallel_ms), 3),
                         "p95": round(percentile(parallel_ms, .95), 3)},
        "sequential_ms": {"p50": round(statistics.median(sequential_ms), 3),
                           "p95": round(percentile(sequential_ms, .95), 3)},
        "tool_calls_per_mode_total": {"parallel": tool_count_parallel, "sequential": tool_count_sequential},
        "duplicate_source_reads": duplicate_source_reads,
        "illegal_risk_grade_or_level_count": illegal_grade_count,
        "expert_accuracy": None,
        "interpretation": "Latency includes graph compile/invoke for parallel and direct sequential helper execution; not an apples-to-apples production benchmark.",
        "nonclaims": ["no professional accuracy claim", "no E2/E3 adjudication", "no teacher side-effecting tool call"]
    }
    output = Path(__file__).resolve().parents[1] / "docs" / "audits" / "P6A_PARALLEL_EVIDENCE.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("P6A_SYNTHETIC_COMPARISON_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
