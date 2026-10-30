"""Same-snapshot smoke comparison: frozen R1 graph vs isolated R9-A candidate.

This is a one-machine engineering probe, not a gold evaluation or a quality claim.
The old graph checkpoint is kept under the OS temp directory, never project data/.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics
import tempfile
import time
from uuid import uuid4

from orchestration.graph import AgentGraph, RunState
from orchestration.r9_industrial_candidate import IndustrialCandidate

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "evals" / "r9a_cases.jsonl"


def _load_cases() -> list[dict]:
    return [json.loads(line) for line in CASES.read_text(encoding="utf-8").splitlines() if line.strip()]


def _old_graph(case: dict) -> dict:
    run_id = f"r9a-old-{uuid4()}"
    context = dict(case["context"])
    context.setdefault("field_evidence", "")
    context.setdefault("operating_condition", "")
    context.setdefault("question", case["question"])
    state = RunState(run_id=run_id, conversation_id="r9a-comparison", question=case["question"], context=context)
    checkpoint = Path(tempfile.gettempdir()) / f"{run_id}.sqlite3"
    graph = AgentGraph(checkpoint_path=checkpoint)
    events = []
    started = time.perf_counter()
    final = graph.run(state, lambda event, node, payload: events.append({"event": event, "node": node}))
    elapsed = round((time.perf_counter() - started) * 1000, 3)
    try:
        checkpoint.unlink(missing_ok=True)
    except OSError:
        pass
    return {"path": "frozen_R1_seven_role_sequence", "latency_ms": elapsed,
            "tool_calls": len(final.tool_results), "citation_count": len(final.evidence_refs),
            "review_status": [item.get("review_status") for item in final.claims],
            "source_ids": sorted({str(ref.get("clause_id")) for ref in final.evidence_refs if ref.get("clause_id")}),
            "events": events, "route": final.route, "answer_prefix": final.answer[:100]}


def _candidate(case: dict) -> dict:
    graph = IndustrialCandidate()
    final = graph.run(case["question"], case["context"])
    out = final["output"]
    return {"path": "R9A_candidate", "latency_ms": final["elapsed_ms"],
            "tool_calls": len(final["tool_calls"]), "citation_count": len(final["citations"]),
            "review_status": [row.get("review_status") for row in final["review_rows"]],
            "route": final["task_kind"], "status": out["status"],
            "verification_level": out["verification_level"],
            "risk_level": out["risk_level"], "human_signed": out["human_signed"],
            "iterations": final["investigate_iteration"],
            "query_variants": final["query_variants"],
            "source_ids": sorted({str(row.get("clause_id")) for row in final["citations"] if row.get("clause_id")}),
            "gate_decisions": final["gate_decisions"],
            "events": [{"event": row["event"], "phase": row["phase"], "iteration": row["iteration"]} for row in final["events"]]}


def run(output: Path) -> dict:
    records = []
    for case in _load_cases():
        before = _old_graph(case)
        after = _candidate(case)
        records.append({"case_id": case["case_id"], "purpose": case["purpose"],
                        "same_input_snapshot": True, "baseline": before, "candidate": after})
    latencies = [item["candidate"]["latency_ms"] for item in records]
    summary = {"status": "RULE_DEMO_EXPERIMENT_NOT_GOLD", "cases": len(records),
               "candidate_latency_ms": {"min": min(latencies), "median": statistics.median(latencies),
                                        "max": max(latencies)},
               "records": records}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "evals" / "r9a_comparison.json")
    args = parser.parse_args()
    print(json.dumps(run(args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
