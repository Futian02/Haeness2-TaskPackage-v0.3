"""Versioned, provenance-aware schema for shadow applicability candidates.

This package is an additive self-owned knowledge layer. It does not alter the
frozen teacher tools, their data, RBI grades, or inspection intervals.
"""
from __future__ import annotations

from enum import Enum
import hashlib
import math
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, validate_assignment=True)


class TruthValue(str, Enum):
    TRUE = "TRUE"
    FALSE = "FALSE"
    UNKNOWN = "UNKNOWN"


class Subject(str, Enum):
    MATERIAL = "material"
    MEDIUM = "medium"
    PROCESS_ENVIRONMENT = "process_environment"
    EQUIPMENT = "equipment"
    CORROSION_CONDITION = "corrosion_condition"
    TEMPERATURE = "temperature"
    PRESSURE = "pressure"
    CONCENTRATION = "concentration"
    FLOW = "flow"


class Property(str, Enum):
    MATERIAL_FAMILY = "material_family"
    PROCESS_MEDIUM = "process_medium"
    GAS_SIDE = "gas_side"
    WET_H2S = "wet_h2s"
    FLUE_GAS_PRESENT = "flue_gas_present"
    WALL_TEMPERATURE = "wall_temperature"
    PROCESS_TEMPERATURE = "process_temperature"
    TOTAL_PRESSURE = "total_pressure"
    H2S_PARTIAL_PRESSURE = "h2s_partial_pressure"
    CONCENTRATION = "concentration"
    FLOW_VELOCITY = "flow_velocity"
    EQUIPMENT_TYPE = "equipment_type"
    WET_SERVICE = "wet_service"
    DEPOSIT_PRESENT = "deposit_present"
    OXYGEN_PRESENT = "oxygen_present"
    CUSTOM_ENUM = "custom_enum"
    CUSTOM_NUMERIC = "custom_numeric"
    CUSTOM_BOOLEAN = "custom_boolean"


class Relation(str, Enum):
    EQ = "eq"
    IN = "in"
    GE = "ge"
    LE = "le"
    INTERVAL = "interval"
    PRESENT = "present"
    ABSENT = "absent"


class Polarity(str, Enum):
    NECESSARY = "necessary"
    SUPPORTING = "supporting"
    EXCLUDING = "excluding"
    PROTECTIVE = "protective"
    CONTEXTUAL = "contextual"


class Role(str, Enum):
    TRIGGER = "trigger"
    SUSCEPTIBILITY = "susceptibility"
    PROTECTION = "protection"
    BYPRODUCT = "byproduct"
    EXAMPLE = "example"
    DISAMBIGUATOR = "disambiguator"
    CONTEXT = "context"


class Scope(str, Enum):
    WHOLE_MECHANISM = "whole_mechanism"
    SPECIFIC_SUBTYPE = "specific_subtype"
    OPERATING_PHASE = "operating_phase"


class Origin(str, Enum):
    RULE_EXTRACTED = "RULE_EXTRACTED"
    LLM_CANDIDATE = "LLM_CANDIDATE"
    OCR_CANDIDATE = "OCR_CANDIDATE"
    OWNER_TECH_REVIEW = "OWNER_TECH_REVIEW"
    HUMAN_SOURCE_VERIFIED = "HUMAN_SOURCE_VERIFIED"


class ReviewState(str, Enum):
    PROPOSED = "PROPOSED"
    NEEDS_PDF_CHECK = "NEEDS_PDF_CHECK"
    CHECKED_SOURCE = "CHECKED_SOURCE"
    OWNER_APPROVED = "OWNER_APPROVED"


class SourceVerification(str, Enum):
    NOT_VERIFIED = "NOT_VERIFIED"
    CLAUSE_JSONL_ONLY = "CLAUSE_JSONL_ONLY"
    HUMAN_PDF_VERIFIED = "HUMAN_PDF_VERIFIED"


class GroupOperator(str, Enum):
    ALL = "all"
    ANY = "any"


class FactConfirmation(str, Enum):
    UNCONFIRMED = "unconfirmed"
    USER_CONFIRMED = "user_confirmed"
    MEASURED = "measured"


class SourceRef(StrictModel):
    source_clause_id: str = Field(min_length=1, max_length=200)
    source_jsonl_sha256: str | None = None
    source_pdf_sha256: str | None = None
    clause_no: str | None = None
    page_physical: int | None = Field(default=None, ge=1)
    page_printed: str | None = None
    text_span_ref: str | None = None
    verification_status: SourceVerification = SourceVerification.NOT_VERIFIED
    missing_reason: str | None = None

    @field_validator("source_jsonl_sha256", "source_pdf_sha256")
    @classmethod
    def valid_sha256(cls, value: str | None) -> str | None:
        if value is not None and (len(value) != 64 or any(c not in "0123456789abcdef" for c in value.lower())):
            raise ValueError("sha256 must be 64 hexadecimal characters")
        return value.lower() if value else None

    @model_validator(mode="after")
    def verified_pdf_is_complete(self):
        if self.verification_status == SourceVerification.HUMAN_PDF_VERIFIED:
            if not self.source_pdf_sha256 or self.page_physical is None or not self.clause_no:
                raise ValueError("HUMAN_PDF_VERIFIED requires PDF SHA-256, physical page, and clause number")
        return self


class Predicate(StrictModel):
    predicate_id: str = Field(min_length=1, max_length=160)
    subject: Subject
    property: Property
    relation: Relation
    value: Any = None
    unit: str | None = None
    target_object: str = Field(min_length=1, max_length=120)
    stage: str | None = None
    polarity: Polarity
    role: Role
    scope: Scope = Scope.WHOLE_MECHANISM
    submechanism_id: str | None = None
    origin: Origin
    review_state: ReviewState
    source_support: Literal["SUPPORTED", "WEAK", "NOT_VERIFIED"] = "NOT_VERIFIED"
    source: SourceRef
    confidence_note: str | None = None

    @model_validator(mode="after")
    def validate_semantics_and_value(self):
        expected_subjects = {
            Property.MATERIAL_FAMILY: {Subject.MATERIAL},
            Property.PROCESS_MEDIUM: {Subject.MEDIUM},
            Property.GAS_SIDE: {Subject.PROCESS_ENVIRONMENT},
            Property.FLUE_GAS_PRESENT: {Subject.PROCESS_ENVIRONMENT},
            Property.WET_H2S: {Subject.CORROSION_CONDITION},
            Property.WET_SERVICE: {Subject.CORROSION_CONDITION},
            Property.DEPOSIT_PRESENT: {Subject.CORROSION_CONDITION},
            Property.OXYGEN_PRESENT: {Subject.PROCESS_ENVIRONMENT},
            Property.WALL_TEMPERATURE: {Subject.TEMPERATURE},
            Property.PROCESS_TEMPERATURE: {Subject.TEMPERATURE},
            Property.TOTAL_PRESSURE: {Subject.PRESSURE},
            Property.H2S_PARTIAL_PRESSURE: {Subject.PRESSURE},
            Property.EQUIPMENT_TYPE: {Subject.EQUIPMENT},
            Property.CONCENTRATION: {Subject.CONCENTRATION},
            Property.FLOW_VELOCITY: {Subject.FLOW},
        }
        if self.property in expected_subjects and self.subject not in expected_subjects[self.property]:
            raise ValueError(f"{self.property.value} requires subject in {[s.value for s in expected_subjects[self.property]]}")
        if self.scope == Scope.SPECIFIC_SUBTYPE and not self.submechanism_id:
            raise ValueError("specific_subtype scope requires submechanism_id")
        if self.scope == Scope.OPERATING_PHASE and not self.stage:
            raise ValueError("operating_phase scope requires an explicit stage")
        if self.scope != Scope.SPECIFIC_SUBTYPE and self.submechanism_id is not None:
            raise ValueError("submechanism_id is only valid for specific_subtype scope")
        if self.polarity == Polarity.PROTECTIVE or self.role == Role.PROTECTION:
            if self.polarity in (Polarity.NECESSARY, Polarity.EXCLUDING):
                raise ValueError("protective descriptions cannot be necessary or exclusion conditions")
        if self.polarity == Polarity.NECESSARY and self.role not in (Role.TRIGGER, Role.SUSCEPTIBILITY, Role.DISAMBIGUATOR):
            raise ValueError("necessary predicates must describe a trigger, susceptibility, or disambiguator")
        if self.polarity == Polarity.EXCLUDING and self.role not in (Role.TRIGGER, Role.SUSCEPTIBILITY, Role.DISAMBIGUATOR):
            raise ValueError("exclusion predicates cannot be protective/context-only descriptions")

        numeric = self.property in {
            Property.WALL_TEMPERATURE, Property.PROCESS_TEMPERATURE, Property.TOTAL_PRESSURE,
            Property.H2S_PARTIAL_PRESSURE, Property.CONCENTRATION, Property.FLOW_VELOCITY,
            Property.CUSTOM_NUMERIC,
        }
        boolean = self.property in {
            Property.GAS_SIDE, Property.WET_H2S, Property.FLUE_GAS_PRESENT, Property.WET_SERVICE,
            Property.DEPOSIT_PRESENT, Property.OXYGEN_PRESENT, Property.CUSTOM_BOOLEAN,
        }
        if numeric:
            if self.unit not in _ALLOWED_UNITS[self.property]:
                raise ValueError(f"{self.property.value} requires explicit compatible unit")
            _validate_numeric_relation(self.relation, self.value)
        elif boolean:
            if self.unit is not None:
                raise ValueError(f"{self.property.value} does not accept a unit")
            if self.relation not in (Relation.PRESENT, Relation.ABSENT, Relation.EQ):
                raise ValueError("boolean property supports present/absent/eq")
            if self.relation == Relation.EQ and not isinstance(self.value, bool):
                raise ValueError("boolean eq requires a boolean value")
            if self.relation in (Relation.PRESENT, Relation.ABSENT) and self.value not in (None, True):
                raise ValueError("present/absent relation does not take an arbitrary value")
        else:
            if self.unit is not None:
                raise ValueError(f"{self.property.value} does not accept a unit")
            if self.relation not in (Relation.EQ, Relation.IN):
                raise ValueError("categorical property supports eq/in only")
            if self.relation == Relation.EQ and (not isinstance(self.value, str) or not self.value):
                raise ValueError("categorical eq requires non-empty string")
            if self.relation == Relation.IN and (not isinstance(self.value, list) or not self.value
                                                  or any(not isinstance(v, str) or not v for v in self.value)):
                raise ValueError("categorical in requires non-empty string list")
        return self


class PredicateGroup(StrictModel):
    group_id: str = Field(min_length=1, max_length=160)
    operator: GroupOperator
    predicates: list[Predicate] = Field(min_length=1, max_length=32)

    @model_validator(mode="after")
    def same_polarity(self):
        polarities = {p.polarity for p in self.predicates}
        if len(polarities) != 1 or next(iter(polarities)) not in (Polarity.NECESSARY, Polarity.EXCLUDING):
            raise ValueError("condition group requires uniformly necessary or excluding predicates")
        return self


class ApplicabilityRule(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    mechanism_id: str = Field(min_length=1, max_length=200)
    submechanism_id: str | None = None
    completeness: Literal["complete", "incomplete"] = "incomplete"
    necessary_groups: list[PredicateGroup] = Field(default_factory=list, max_length=64)
    exclusion_groups: list[PredicateGroup] = Field(default_factory=list, max_length=64)
    annotations: list[Predicate] = Field(default_factory=list, max_length=64)

    @model_validator(mode="after")
    def groups_are_well_placed(self):
        if any(p.polarity != Polarity.NECESSARY for g in self.necessary_groups for p in g.predicates):
            raise ValueError("necessary_groups may contain necessary predicates only")
        if any(p.polarity != Polarity.EXCLUDING for g in self.exclusion_groups for p in g.predicates):
            raise ValueError("exclusion_groups may contain excluding predicates only")
        if any(p.polarity in (Polarity.NECESSARY, Polarity.EXCLUDING) for p in self.annotations):
            raise ValueError("annotations must be supporting/protective/contextual")
        return self


class DeviceFact(StrictModel):
    subject: Subject
    property: Property
    target_object: str = Field(min_length=1, max_length=120)
    stage: str | None = None
    value: Any = None
    unit: str | None = None
    truth: TruthValue = TruthValue.UNKNOWN
    confirmation: FactConfirmation = FactConfirmation.UNCONFIRMED
    evidence_ref: str | None = None

    @model_validator(mode="after")
    def unknown_never_becomes_false_by_default(self):
        expected_subjects = {
            Property.MATERIAL_FAMILY: {Subject.MATERIAL},
            Property.PROCESS_MEDIUM: {Subject.MEDIUM},
            Property.GAS_SIDE: {Subject.PROCESS_ENVIRONMENT},
            Property.FLUE_GAS_PRESENT: {Subject.PROCESS_ENVIRONMENT},
            Property.WET_H2S: {Subject.CORROSION_CONDITION},
            Property.WET_SERVICE: {Subject.CORROSION_CONDITION},
            Property.DEPOSIT_PRESENT: {Subject.CORROSION_CONDITION},
            Property.OXYGEN_PRESENT: {Subject.PROCESS_ENVIRONMENT},
            Property.WALL_TEMPERATURE: {Subject.TEMPERATURE},
            Property.PROCESS_TEMPERATURE: {Subject.TEMPERATURE},
            Property.TOTAL_PRESSURE: {Subject.PRESSURE},
            Property.H2S_PARTIAL_PRESSURE: {Subject.PRESSURE},
            Property.EQUIPMENT_TYPE: {Subject.EQUIPMENT},
            Property.CONCENTRATION: {Subject.CONCENTRATION},
            Property.FLOW_VELOCITY: {Subject.FLOW},
        }
        if self.property in expected_subjects and self.subject not in expected_subjects[self.property]:
            raise ValueError(f"{self.property.value} fact has incompatible subject")
        if self.truth == TruthValue.UNKNOWN and self.value is not None:
            raise ValueError("UNKNOWN facts must use value=null")
        if self.truth != TruthValue.UNKNOWN and self.confirmation == FactConfirmation.UNCONFIRMED:
            raise ValueError("TRUE/FALSE facts require user confirmation or measurement")
        if self.truth == TruthValue.TRUE and self.value is None:
            raise ValueError("TRUE facts require an explicit value")
        if self.truth == TruthValue.FALSE and self.value is None:
            raise ValueError("FALSE facts require an explicit observed value")
        numeric = self.property in _ALLOWED_UNITS
        boolean = self.property in {
            Property.GAS_SIDE, Property.WET_H2S, Property.FLUE_GAS_PRESENT, Property.WET_SERVICE,
            Property.DEPOSIT_PRESENT, Property.OXYGEN_PRESENT, Property.CUSTOM_BOOLEAN,
        }
        if self.truth == TruthValue.FALSE and (not boolean or self.value is not False):
            raise ValueError("FALSE facts must be an explicit false boolean observation")
        if boolean and self.truth == TruthValue.TRUE and self.value is not True:
            raise ValueError("TRUE boolean facts must carry value=true; false observations use truth=FALSE")
        if numeric:
            if self.unit not in _ALLOWED_UNITS[self.property]:
                raise ValueError(f"{self.property.value} fact requires explicit compatible unit")
            if self.value is not None and (isinstance(self.value, bool) or not isinstance(self.value, (int, float)) or not math.isfinite(float(self.value))):
                raise ValueError("numeric fact value must be finite number")
        else:
            if self.unit is not None:
                raise ValueError(f"{self.property.value} fact does not accept a unit")
            if self.value is not None and not isinstance(self.value, (str, bool, list)):
                raise ValueError("categorical/boolean fact must be a string, boolean, list, or null")
        return self


class ApplicabilityStatus(str, Enum):
    SUPPORTED_WITH_CONDITIONS = "SUPPORTED_WITH_CONDITIONS"
    POSSIBLE_NEEDS_EVIDENCE = "POSSIBLE_NEEDS_EVIDENCE"
    EXCLUDED_WITH_CONFIRMED_CONTRADICTION = "EXCLUDED_WITH_CONFIRMED_CONTRADICTION"
    NOT_ASSESSED = "NOT_ASSESSED"


class ApplicabilityResult(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    mechanism_id: str
    submechanism_id: str | None = None
    status: ApplicabilityStatus
    support: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    source_clauses: list[str] = Field(default_factory=list)
    measurement_priority: list[str] = Field(default_factory=list)
    annotations: list[str] = Field(default_factory=list)
    risk_level: Literal[None] = None
    inspection_interval_year: Literal[None] = None
    observed_damage: Literal[None] = None


_ALLOWED_UNITS = {
    Property.WALL_TEMPERATURE: {"degC", "K"},
    Property.PROCESS_TEMPERATURE: {"degC", "K"},
    Property.TOTAL_PRESSURE: {"MPa", "kPa", "Pa"},
    Property.H2S_PARTIAL_PRESSURE: {"MPa_partial", "kPa_partial", "Pa_partial"},
    Property.CONCENTRATION: {"ppm", "mg/L", "mol%"},
    Property.FLOW_VELOCITY: {"m/s"},
    # Generic numeric fields deliberately exclude temperature/pressure units;
    # those require object-specific typed properties above.
    Property.CUSTOM_NUMERIC: {"1", "ppm", "mg/L", "mol%", "m/s"},
}


def _validate_numeric_relation(relation: Relation, value: Any) -> None:
    def numeric(x: Any) -> bool:
        return not isinstance(x, bool) and isinstance(x, (int, float)) and math.isfinite(float(x))
    if relation in (Relation.EQ, Relation.GE, Relation.LE) and not numeric(value):
        raise ValueError("numeric relation requires a finite number")
    if relation == Relation.INTERVAL and (not isinstance(value, list) or len(value) != 2
                                            or not all(numeric(x) for x in value) or value[0] > value[1]):
        raise ValueError("interval requires an ordered [lower, upper] numeric pair")
    if relation in (Relation.PRESENT, Relation.ABSENT, Relation.IN):
        raise ValueError("numeric property does not support this relation")


def hard_exclusion_eligible(predicate: Predicate) -> bool:
    source = predicate.source
    return (
        predicate.polarity in (Polarity.NECESSARY, Polarity.EXCLUDING)
        and predicate.role in (Role.TRIGGER, Role.SUSCEPTIBILITY, Role.DISAMBIGUATOR)
        and predicate.origin == Origin.HUMAN_SOURCE_VERIFIED
        and predicate.review_state == ReviewState.OWNER_APPROVED
        and predicate.source_support == "SUPPORTED"
        and source.verification_status == SourceVerification.HUMAN_PDF_VERIFIED
        and bool(source.source_pdf_sha256 and source.source_jsonl_sha256
                 and source.page_physical and source.clause_no)
    )
