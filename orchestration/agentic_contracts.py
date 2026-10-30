"""Strict, serializable contracts for the isolated Aetheris V2 AgentGraph."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictFloat, StrictInt, StrictStr


TeacherToolName = Literal[
    "damage_mechanism_query", "rbi_lookup", "standard_clause_search",
]


class StrictContract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class PlannerRequest(StrictContract):
    run_id: StrictStr = Field(min_length=1, max_length=100)
    thread_id: StrictStr = Field(min_length=1, max_length=100)
    question: StrictStr = Field(max_length=4000)
    facts: dict[str, Any]
    unknowns: list[StrictStr] = Field(max_length=40)
    iteration: StrictInt = Field(ge=0, le=3)
    previous_actions: list[dict[str, Any]] = Field(max_length=8)
    candidate_source_ids: list[StrictStr] = Field(max_length=40)
    candidate_summaries: list[dict[str, Any]] = Field(default_factory=list, max_length=20)
    review_feedback: StrictStr = Field(default="", max_length=2000)
    budget_remaining: dict[str, int]


class ReflectionRequest(StrictContract):
    run_id: StrictStr = Field(min_length=1, max_length=100)
    thread_id: StrictStr = Field(min_length=1, max_length=100)
    question: StrictStr = Field(max_length=4000)
    iteration: StrictInt = Field(ge=0, le=3)
    evidence_summary: list[dict[str, Any]] = Field(max_length=40)
    candidate_summaries: list[dict[str, Any]] = Field(default_factory=list, max_length=20)
    errors: list[StrictStr] = Field(max_length=20)
    unknowns: list[StrictStr] = Field(max_length=40)
    budget_remaining: dict[str, int]


class PlanProposal(StrictContract):
    """Untrusted model action. ``tool_name`` remains str so policy can audit rejection."""
    action: Literal["call_tool", "finish"]
    tool_name: StrictStr = Field(default="", max_length=100)
    query: StrictStr = Field(default="", max_length=600)
    tool_arguments: dict[str, Any] = Field(default_factory=dict)
    investigation_goal: StrictStr = Field(min_length=1, max_length=500)
    evidence_gap: StrictStr = Field(default="", max_length=500)
    public_rationale: StrictStr = Field(min_length=1, max_length=500)
    focus_clause_ids: list[StrictStr] = Field(default_factory=list, max_length=20)


class ReflectProposal(StrictContract):
    continue_investigation: StrictBool
    next_evidence_gap: StrictStr = Field(default="", max_length=500)
    public_rationale: StrictStr = Field(min_length=1, max_length=500)


class ProviderReply(StrictContract):
    payload: dict[str, Any]
    input_tokens: StrictInt = Field(ge=0)
    output_tokens: StrictInt = Field(ge=0)
    latency_ms: float = Field(ge=0)
    provider_name: StrictStr = Field(default="fake", max_length=80)


class StandardSearchArgs(StrictContract):
    keyword: StrictStr = Field(min_length=1, max_length=600)
    knowledge_type: Literal["rbi", "damage_mechanism"] | None = None
    top_k: StrictInt = Field(default=5, ge=1, le=20)


class DamageEvidenceArgs(StrictContract):
    ph: StrictInt | StrictFloat | None = None
    cl_ppm: StrictInt | StrictFloat | None = None
    fe_ppm: StrictInt | StrictFloat | None = None
    h2s_ppm: StrictInt | StrictFloat | None = None
    wall_thinning: StrictBool | None = None
    crack_found: StrictBool | None = None


class DamageQueryArgs(StrictContract):
    material: StrictStr = Field(min_length=1, max_length=100)
    medium: list[StrictStr] = Field(min_length=1, max_length=8)
    temperature_c: float | int | None = None
    equipment_type: StrictStr | None = Field(default=None, max_length=100)
    evidence: DamageEvidenceArgs | None = None


class RbiLookupArgs(StrictContract):
    equipment_type: StrictStr = Field(min_length=1, max_length=100)
    material: StrictStr = Field(min_length=1, max_length=100)
    mechanism: StrictStr | None = Field(default=None, max_length=200)
    medium: list[StrictStr] | None = Field(default=None, max_length=8)
    temperature_c: float | int | None = None
    pressure_mpa: float | int | None = None
    service_years: float | int | None = None


class ReviewFinding(StrictContract):
    role: Literal["auditor", "skeptic"]
    finding: StrictStr = Field(min_length=1, max_length=500)
    source_ids: list[StrictStr] = Field(default_factory=list, max_length=20)
    unresolved: list[StrictStr] = Field(default_factory=list, max_length=30)
    conflict: StrictBool = False

