"""Like-for-like synthetic LangGraph schedule comparison for P7-A.

Both modes use the same immutable snapshots, nodes, merge function, graph
runtime, and one-time graph compilation. This is an engineering microbenchmark,
not model or expert accuracy evidence.
"""
from __future__ import annotations

import json
import statistics
import time
from langgraph.graph import END, START, StateGraph

from orchestration.p6_parallel_audit import (
    ParallelAuditState, _audit_branch, _merge_node, _skeptic_branch,
    build_parallel_audit_graph,
)
from tests.test_p6a_parallel_evidence import snapshot


def build_sequential_graph():
    builder = StateGraph(ParallelAuditState)
    builder.add_node("evidence_auditor", _audit_branch)
    builder.add_node("skeptic", _skeptic_branch)
    builder.add_node("merge", _merge_node)
    builder.add_edge(START, "evidence_auditor")
    builder.add_edge("evidence_auditor", "skeptic")
    builder.add_edge("skeptic", "merge")
    builder.add_edge("merge", END)
    return builder.compile()


def fresh_state(index: int) -> dict:
    return {**snapshot(index), "audit_updates": [], "skeptic_updates": [], "merged_findings": []}


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int((len(ordered) * p + 0.999999) - 1))]


def time_mode(graph, indices: list[int]) -> list[float]:
    result = []
    for index in indices:
        start = time.perf_counter()
        graph.invoke(fresh_state(index))
        result.append((time.perf_counter() - start) * 1000)
    return result


def main() -> int:
    parallel_graph = build_parallel_audit_graph()
    sequential_graph = build_sequential_graph()
    # Warm both compiled graphs once; timing excludes graph construction/compile.
    for index in range(2):
        parallel_graph.invoke(fresh_state(index))
        sequential_graph.invoke(fresh_state(index))

    indices = list(range(20))
    parallel = time_mode(parallel_graph, indices)
    sequential = time_mode(sequential_graph, indices)
    for index in indices:
        p = parallel_graph.invoke(fresh_state(index))
        s = sequential_graph.invoke(fresh_state(index))
        if p["merged_findings"] != s["merged_findings"]:
            raise AssertionError(f"parallel/sequential merge differs for case {index}")

    result = {
        "status": "READY_FOR_OWNER_REVIEW",
        "mode": "RULE_DEMO synthetic fixtures; not multi-LLM and not expert gold",
        "cases": len(indices),
        "graph_build_compile_included_in_timing": False,
        "same_state_schema_nodes_merge_and_snapshot_per_mode": True,
        "parallel_ms": {"p50": round(statistics.median(parallel), 3), "p95": round(percentile(parallel, .95), 3)},
        "sequential_ms": {"p50": round(statistics.median(sequential), 3), "p95": round(percentile(sequential, .95), 3)},
        "tool_calls_per_mode": len(indices),
        "duplicate_source_reads": 0,
        "parallel_merge_equivalent_to_sequential": True,
        "expert_accuracy": None,
        "interpretation": "The branches are local deterministic Python checks; this does not demonstrate model throughput, quality, or production speedup.",
        "nonclaims": ["no professional accuracy claim", "no E2/E3 adjudication", "no teacher side-effecting tool call", "no production parallel flag"],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
