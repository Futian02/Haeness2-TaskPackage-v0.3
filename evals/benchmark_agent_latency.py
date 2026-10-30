"""Read-only rule-Harness latency baseline over three device scenarios.

No LLM calls, no writes, no claims about semantic accuracy.
Run from repository root:
    python -B -m evals.benchmark_agent_latency
"""
from __future__ import annotations

import json
from math import ceil
from statistics import mean, median
from time import perf_counter

from app.runtime import build_task, run_case

CASES = [
    ("HCl", build_task("常压塔", "碳钢", "氯化氢", "操作温度95℃", "塔顶水pH 5.8", "可能是什么损伤机理？")),
    ("wet_H2S", build_task("换热器", "碳钢", "湿硫化氢", "操作温度110℃", "pH 5.8，铁离子4.1mg/L", "如何鉴别？")),
    ("multi_medium", build_task("空冷器", "碳钢", "氯化氢,氯化铵", "操作温度110℃", "未检测是否减薄", "可能是什么损伤机理，能否定级？")),
]


def quantile_ceil(data: list[float], fraction: float) -> float:
    values = sorted(data)
    return values[max(0, min(len(values) - 1, ceil(len(values) * fraction) - 1))]


def bench(repeat: int = 12) -> dict:
    if repeat < 2:
        raise ValueError("repeat must be >= 2")
    report = []
    for name, task in CASES:
        run_case(task, "rule")  # warm importer/cache; exclude from timing
        elapsed = []
        calls = []
        tool_elapsed = []
        evidence_issues = 0
        blocked = 0
        for _ in range(repeat):
            start = perf_counter()
            r = run_case(task, "rule")
            elapsed.append((perf_counter() - start) * 1000)
            steps = r["trace"]["steps"]
            calls.append(len(steps))
            tool_elapsed.append(sum(s["elapsed_ms"] for s in steps))
            evidence_issues += len(r["basis_issues"])
            blocked += sum(1 for s in steps if s["blocked"])
        report.append({
            "case": name,
            "repeat": repeat,
            "min_tool_calls": min(calls),
            "max_tool_calls": max(calls),
            "mean_total_ms": round(mean(elapsed), 2),
            "p50_total_ms": round(median(elapsed), 2),
            "p95_total_ms": round(quantile_ceil(elapsed, .95), 2),
            "mean_reported_tools_ms_int_resolution": round(mean(tool_elapsed), 2),
            "basis_id_presence_issues": evidence_issues,
            "blocked_steps": blocked,
        })
    return {"engine": "RulePlanner (NOT real LLM)", "cases": report,
            "caveat": "Local warm-loop timing, no API/network/UI, no semantics gold labels."}


def main() -> None:
    print(json.dumps(bench(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
