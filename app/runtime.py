"""Read-only compatibility adapter around the official Haeness2 Harness.

No teacher-specified schema, tool name, argument name or return payload is changed.
This module deliberately does NOT claim that RulePlanner is a real LLM agent.
"""
from __future__ import annotations

import importlib
import os
from pathlib import Path
import sys
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = Path(os.environ.get("HAENESS_UPSTREAM", str(ROOT / "upstream"))).resolve()
MAX_INPUT_CHARS = 4000


def split_medium(text: str) -> list[str]:
    """Convert UI comma-delimited media to the official list[str] parameter."""
    normalized = str(text or "").replace("，", ",").replace("、", ",")
    result = [v.strip() for v in normalized.split(",") if v.strip()]
    if not result:
        raise ValueError("至少输入一个介质，名称应与官方 enums.json 一致")
    return result


def build_task(
    equipment: str, material: str, medium: str, operating_condition: str,
    field_evidence: str, question: str,
) -> dict[str, Any]:
    fields = {
        "equipment": str(equipment or "").strip(),
        "material": str(material or "").strip(),
        "operating_condition": str(operating_condition or "").strip(),
        "field_evidence": str(field_evidence or "").strip(),
        "question": str(question or "").strip(),
    }
    if any(len(v) > MAX_INPUT_CHARS for v in fields.values()):
        raise ValueError("输入字段过长")
    if not fields["equipment"] or not fields["material"] or not fields["question"]:
        raise ValueError("设备、材质、问题不可为空")
    return {**fields, "medium": split_medium(medium)}


def load_harness():
    """Only import the original module under upstream/05_提交区."""
    directory = UPSTREAM / "05_提交区"
    module_file = directory / "harness.py"
    data_file = directory / "clauses.jsonl"
    if not module_file.is_file() or not data_file.is_file():
        raise FileNotFoundError(
            "未找到上游项目的 Harness / 标准条款库。先按根目录 README 的 PowerShell 命令克隆至 upstream/。"
        )
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))
    # Reject accidental imports from a different project named harness.
    existing = sys.modules.get("harness")
    if existing is not None and Path(existing.__file__).resolve() != module_file.resolve():
        raise RuntimeError("检测到其他项目的同名 harness 模块，拒绝混用")
    module = importlib.import_module("harness")
    if Path(module.__file__).resolve() != module_file.resolve():
        raise RuntimeError("Harness 模块路径不匹配")
    return module


def check_trace_sources(trace: dict[str, Any]) -> list[str]:
    """Deterministically check that all declared basis IDs were returned by tools.

    This is a *necessary*, not sufficient, condition for factual support.
    """
    seen: set[str] = set()
    for step in trace.get("steps", []):
        for source in (step.get("result") or {}).get("source") or []:
            if isinstance(source, dict) and isinstance(source.get("clause_id"), str):
                seen.add(source["clause_id"])
    basis = ((trace.get("final_answer") or {}).get("basis") or [])
    return [f"结论引用条款 {cid} 未出现在本次工具返回中" for cid in basis if cid not in seen]


def run_case(task: dict[str, Any], mode: str = "rule") -> dict[str, Any]:
    if mode not in {"rule", "llm"}:
        raise ValueError("mode 只能是 rule 或 llm")
    hmod = load_harness()
    registry = hmod.build_registry()
    planner = hmod.RulePlanner()
    if mode == "llm":
        planner = hmod.build_llm_planner(registry)
        if planner is None:
            raise RuntimeError("未开启 HARNESS_LLM=1；LLM 模式不能伪装为规则模式")
    harness = hmod.Harness(registry)
    start = time.perf_counter()
    trajectory = harness.run(
        traj_id="UI-DEMO", task_input=task, planner=planner,
        annotator="ui-demo", checked=False,
    )
    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    trace = trajectory.to_dict()
    issues = check_trace_sources(trace)
    parse_stats = None
    if mode == "llm":
        parse_stats = {
            "parsed_ok": planner.parsed_ok,
            "parsed_fail": planner.parsed_fail,
            "raw_parse_success_rate": planner.parse_success_rate,
            "fallback_occurred": planner.parsed_fail > 0,
        }
    return {
        "mode": mode,
        "duration_ms": duration_ms,
        "trace": trace,
        "basis_issues": issues,
        "parse_stats": parse_stats,
    }
