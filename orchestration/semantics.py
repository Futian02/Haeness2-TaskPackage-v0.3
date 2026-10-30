"""Engineering observation schemas and conservative normalization helpers."""
from __future__ import annotations

import re
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ObservationState(str, Enum):
    observed_true = "observed_true"
    observed_false = "observed_false"
    unknown = "unknown"
    not_applicable = "not_applicable"


class EngineeringObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: str
    raw_span: str
    value: bool | float | str | None = None
    unit: str | None = None
    normalized_value: bool | float | str | None = None
    normalized_unit: str | None = None
    observation_state: ObservationState = ObservationState.unknown
    sampled_at: str | None = None
    aliases: list[str] = Field(default_factory=list)


class EvidenceLink(BaseModel):
    model_config = ConfigDict(extra="forbid")
    clause_id: str
    standard_code: str | None = None
    clause_no: str | None = None
    printed_page: int | None = None
    pdf_page: int | None = None
    quote_span: str | None = None
    extraction_method: str = "structured_clause_jsonl"
    review_status: str = "draft_needs_review"
    doc_sha256: str | None = None


class Hypothesis(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hypothesis_id: str
    label: str
    supporting_evidence: list[str] = Field(default_factory=list)
    conflicting_evidence: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    source_clause_ids: list[str] = Field(default_factory=list)
    disposition: str = "candidate"
    review_status: str = "draft_needs_review"


class InformationGap(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: str
    question: str
    reason: str
    priority: str = "normal"


class Claim(BaseModel):
    """Auditable conclusion candidate; machine provenance is not entailment."""
    model_config = ConfigDict(extra="forbid")
    claim_id: str
    kind: Literal["source_fact", "engineering_hypothesis", "equipment_diagnosis", "risk_level"] = "engineering_hypothesis"
    text: str
    source_clause_ids: list[str] = Field(default_factory=list)
    observation_ids: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    verdict: Literal["supported", "unsupported", "contradicted", "unresolved"] = "unresolved"
    grade: Literal["E0", "E1", "E2", "E3"] = "E0"
    review_status: Literal["draft_needs_review", "machine_checked", "requires_human_review", "human_verified"] = "draft_needs_review"
    checks: list[dict[str, Any]] = Field(default_factory=list)
    independent_validation: dict[str, Any] | None = None
    provenance_status: Literal["verified", "partial", "failed", "unknown"] = "unknown"
    canonical_evidence: list[dict[str, Any]] = Field(default_factory=list)

    @field_validator("kind", mode="before")
    @classmethod
    def normalize_legacy_claim_kind(cls, value: Any) -> Any:
        aliases = {"mechanism_candidate": "engineering_hypothesis", "diagnosis": "equipment_diagnosis",
                   "fact": "source_fact", "risk": "risk_level"}
        if isinstance(value, str):
            return aliases.get(value, value)
        return value


ALIASES: dict[str, tuple[str, str]] = {
    "铁离子": ("iron_ion", "mg/L"), "铁": ("iron_ion", "mg/L"), "fe": ("iron_ion", "mg/L"),
    "ph": ("ph", "pH"), "酸碱度": ("ph", "pH"), "氯离子": ("chloride", "mg/L"), "cl": ("chloride", "mg/L"),
    "硫化氢": ("h2s", "ppm"), "壁厚减薄": ("wall_thinning", "boolean"), "减薄": ("wall_thinning", "boolean"),
    "裂纹": ("crack_found", "boolean"), "温度": ("temperature", "°C"), "压力": ("pressure", "MPa"),
    "投用年限": ("service_years", "year"), "已投用": ("service_years", "year"),
}


def resolve_alias(term: str) -> tuple[str, str] | None:
    """Case-insensitive product alias map; never mutates official enum vocabularies."""
    key = term.strip().lower()
    return ALIASES.get(key)

_NUMERIC = re.compile(r"(?P<num>-?\d+(?:\.\d+)?)\s*(?P<unit>mg\s*/\s*l|ppm|mpa|kpa|bar|℃|°c|°f|年|years?)?", re.I)


def normalize_measurement(value: float, unit: str | None, field: str) -> tuple[float, str]:
    """Normalize only unambiguous units; dilute aqueous mg/L↔ppm uses 1:1 approximation."""
    u = (unit or "").strip().lower().replace(" ", "")
    if field == "temperature":
        if u in {"°f", "f"}:
            return round((value - 32) * 5 / 9, 6), "°C"
        return value, "°C"
    if field == "pressure":
        factors = {"kpa": 0.001, "bar": 0.1, "mpa": 1.0, "": 1.0}
        if u not in factors:
            raise ValueError(f"不支持压力单位: {unit}")
        return value * factors[u], "MPa"
    if field in {"iron_ion", "chloride"}:
        if u in {"ppm", "mg/l", ""}:
            return value, "mg/L"
        raise ValueError(f"不支持浓度单位: {unit}")
    if field == "service_years":
        if u in {"年", "year", "years", ""}:
            return value, "year"
        raise ValueError(f"不支持年限单位: {unit}")
    if field == "ph":
        return value, "pH"
    return value, unit or ""


def extract_observations(text: str) -> list[EngineeringObservation]:
    """Small deterministic parser: preserve raw spans and represent missing evidence as unknown."""
    result: list[EngineeringObservation] = []
    specs = [
        ("ph", r"(?:p\s*h|酸碱度)\s*(?:为|=|:)?\s*(-?\d+(?:\.\d+)?)", "pH"),
        ("iron_ion", r"(?:铁离子|铁|Fe)\s*(?:为|=|:)?\s*(-?\d+(?:\.\d+)?)\s*(mg\s*/\s*l|ppm)?", "mg/L"),
        ("chloride", r"(?:氯离子|Cl)\s*(?:为|=|:)?\s*(-?\d+(?:\.\d+)?)\s*(mg\s*/\s*l|ppm)?", "mg/L"),
        ("h2s", r"(?:硫化氢|H2S)\s*(?:为|=|:)?\s*(-?\d+(?:\.\d+)?)\s*(ppm)?", "ppm"),
        ("temperature", r"(?:操作)?温度\s*(?:为|=|:)?\s*(-?\d+(?:\.\d+)?)\s*(℃|°C|°F)?", "°C"),
        ("pressure", r"压力\s*(?:为|=|:)?\s*(-?\d+(?:\.\d+)?)\s*(MPa|kPa|bar)?", "MPa"),
        ("service_years", r"(?:已)?投用\s*(-?\d+(?:\.\d+)?)\s*(年|years?)?", "year"),
    ]
    lowered = text.lower()
    for field, pattern, default_unit in specs:
        match = re.search(pattern, text, re.I)
        if match:
            raw = match.group(0)
            number = float(match.group(1))
            unit = match.group(2) if len(match.groups()) > 1 else default_unit
            normalized, normalized_unit = normalize_measurement(number, unit or default_unit, field)
            result.append(EngineeringObservation(field=field, raw_span=raw, value=number, unit=unit or default_unit,
                                                 normalized_value=normalized, normalized_unit=normalized_unit,
                                                 observation_state=ObservationState.observed_true))
    qualitative = [
        ("ph", ("pH下降", "pH值下降", "酸度升高", "pH偏低"), "decreasing", "pH"),
        ("iron_ion", ("铁离子升高", "铁离子增加", "铁含量升高"), "increasing", "mg/L"),
        ("chloride", ("氯离子偏高", "氯离子升高", "氯含量升高"), "high", "mg/L"),
        ("h2s", ("湿H2S", "湿硫化氢", "含硫化氢"), None, "ppm"),
        ("temperature", ("高温",), "high", "°C"),
    ]
    already = {o.field for o in result}
    for field, phrases, value, unit in qualitative:
        found = next((p for p in phrases if p.lower() in lowered), None)
        if found and field not in already:
            result.append(EngineeringObservation(field=field, raw_span=found, value=value, unit=unit,
                                                 normalized_value=value, normalized_unit=unit,
                                                 observation_state=ObservationState.unknown if value is None else ObservationState.observed_true))
            already.add(field)
    bool_patterns = [
        ("wall_thinning", ("未做测厚", "还没测厚", "尚未测厚", "未测厚"), None),
        ("wall_thinning", ("未发现减薄", "没有减薄", "无减薄"), False),
        ("wall_thinning", ("发现减薄", "存在减薄", "有减薄"), True),
        ("crack_found", ("未发现裂纹", "没有裂纹", "无裂纹"), False),
        ("crack_found", ("发现裂纹", "存在裂纹", "有裂纹"), True),
    ]
    for field, phrases, value in bool_patterns:
        found = next((p for p in phrases if p.lower() in lowered), None)
        if found:
            state = ObservationState.unknown if value is None else (ObservationState.observed_true if value else ObservationState.observed_false)
            result.append(EngineeringObservation(field=field, raw_span=found, value=value, normalized_value=value,
                                                 unit="boolean", normalized_unit="boolean", observation_state=state))
            break
    return result
