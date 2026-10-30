"""Injectable structured-planner boundary for the S1-B candidate.

This module intentionally contains no network client, key loading, billing,
or fallback-to-real-provider behavior. S2 may inject an authorized provider
implementing ``StructuredPlanner``; S1 uses deterministic fake responses.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import time
from typing import Any, Protocol

from orchestration.agentic_contracts import (
    PlannerRequest, ProviderReply, ReflectionRequest,
)


class StructuredPlanner(Protocol):
    def plan(self, request: PlannerRequest) -> ProviderReply: ...
    def reflect(self, request: ReflectionRequest) -> ProviderReply: ...


def _estimate_tokens(value: Any) -> int:
    """Conservative fixture estimate only; never reported as real model usage."""
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return max(1, (len(raw) + 2) // 3)


@dataclass
class ScriptedFakePlanner:
    """Fake structured model: consumes scripted plan/reflect payloads in order."""
    plans: list[Any] = field(default_factory=list)
    reflections: list[Any] = field(default_factory=list)
    calls: list[dict[str, Any]] = field(default_factory=list)
    default_plan: Any | None = None
    default_reflection: Any | None = None

    def plan(self, request: PlannerRequest) -> ProviderReply:
        started = time.perf_counter()
        self.calls.append({"kind": "plan", "run_id": request.run_id,
                           "thread_id": request.thread_id, "iteration": request.iteration})
        index = sum(row["kind"] == "plan" for row in self.calls) - 1
        payload = self.plans[index] if index < len(self.plans) else self.default_plan
        if payload is None:
            payload = default_fake_plan(request)
        return ProviderReply(
            payload=payload,
            input_tokens=_estimate_tokens(request.model_dump(mode="json")),
            output_tokens=_estimate_tokens(payload),
            latency_ms=(time.perf_counter() - started) * 1000,
            provider_name="scripted_fake",
        )

    def reflect(self, request: ReflectionRequest) -> ProviderReply:
        started = time.perf_counter()
        self.calls.append({"kind": "reflect", "run_id": request.run_id,
                           "thread_id": request.thread_id, "iteration": request.iteration})
        index = sum(row["kind"] == "reflect" for row in self.calls) - 1
        payload = self.reflections[index] if index < len(self.reflections) else self.default_reflection
        if payload is None:
            payload = default_fake_reflection(request)
        return ProviderReply(
            payload=payload,
            input_tokens=_estimate_tokens(request.model_dump(mode="json")),
            output_tokens=_estimate_tokens(payload),
            latency_ms=(time.perf_counter() - started) * 1000,
            provider_name="scripted_fake",
        )


def default_fake_plan(request: PlannerRequest) -> dict[str, Any]:
    """Deterministic offline fake that exercises a model-selected investigation.

    This is a test double, not a production intent router. The graph still
    validates and authorizes every proposed tool and parameter independently.
    """
    facts = request.facts
    query = request.question.strip() or "承压设备损伤机理 适用条件"
    has_material = bool(facts.get("material"))
    has_medium = bool(facts.get("medium"))
    requested_risk = any(token in request.question for token in ("风险等级", "风险分级", "RBI"))
    if has_material and has_medium and requested_risk and facts.get("equipment_type"):
        tool = "rbi_lookup"
        args = {
            "equipment_type": facts.get("equipment_type"),
            "material": facts.get("material"),
            "medium": facts.get("medium"),
            "temperature_c": facts.get("temperature_c"),
            "pressure_mpa": facts.get("pressure_mpa"),
            "service_years": facts.get("service_years"),
        }
        args = {key: value for key, value in args.items() if value is not None}
        gap = "机理适用性及完整PoF/CoF资料"
    elif has_material and has_medium:
        tool = "damage_mechanism_query"
        args = {"material": facts["material"], "medium": facts["medium"]}
        for key in ("temperature_c", "equipment_type", "evidence"):
            if facts.get(key) is not None:
                args[key] = facts[key]
        gap = "机理区分所需的现场条件"
    else:
        tool = "standard_clause_search"
        args = {"keyword": query, "knowledge_type": "damage_mechanism", "top_k": 8}
        gap = "材料/介质/温压及设备局部环境的确认值"
    return {
        "action": "call_tool", "tool_name": tool, "query": query,
        "tool_arguments": args,
        "investigation_goal": "依据本地标准来源形成可追溯的初步调查方向",
        "evidence_gap": gap,
        "public_rationale": "按当前已确认输入选择一个只读教师工具；缺失条件保持未知。",
        "focus_clause_ids": [],
    }


def default_fake_reflection(request: ReflectionRequest) -> dict[str, Any]:
    has_source = any(row.get("source_ids") for row in request.evidence_summary)
    can_continue = request.iteration < 2 and request.budget_remaining.get("tool_attempts", 0) > 0
    # One standard query can seed directions; a second action may seek a more
    # discriminating source. Empty/error results also permit a bounded rewrite.
    return {
        "continue_investigation": bool(can_continue and (has_source or request.errors)),
        "next_evidence_gap": request.unknowns[0] if request.unknowns else "交叉检索适用条件与反证",
        "public_rationale": "对照已取得来源与未知现场条件后，决定是否进行下一次有预算的补充检索。",
    }

