"""Conservative three-valued applicability evaluator (shadow-only, no model/network calls)."""
from __future__ import annotations

from collections import defaultdict
import json
import math
from pathlib import Path
import statistics
import time
from typing import Any, Iterable, Mapping

from knowledge.applicability.schema_v1 import (
    ApplicabilityResult, ApplicabilityRule, ApplicabilityStatus, DeviceFact,
    FactConfirmation, GroupOperator, Origin, Polarity, Predicate, Property,
    ReviewState, Role, Scope, SourceRef, SourceVerification, Subject, TruthValue,
    hard_exclusion_eligible,
)


def _base_number(value: float, unit: str, prop: Property) -> float:
    value = float(value)
    if prop in (Property.WALL_TEMPERATURE, Property.PROCESS_TEMPERATURE):
        return value - 273.15 if unit == "K" else value
    if prop in (Property.TOTAL_PRESSURE, Property.H2S_PARTIAL_PRESSURE):
        return value * {"Pa": 1e-6, "kPa": 1e-3, "MPa": 1.0,
                        "Pa_partial": 1e-6, "kPa_partial": 1e-3, "MPa_partial": 1.0}[unit]
    return value


def _predicate_value(predicate: Predicate, fact_value: Any, fact_unit: str | None = None) -> TruthValue:
    """Compare a known fact to a predicate; UNKNOWN is never coerced to FALSE."""
    prop = predicate.property
    if predicate.relation.value in ("present", "absent"):
        if not isinstance(fact_value, bool):
            return TruthValue.UNKNOWN
        present = fact_value
        matched = present if predicate.relation.value == "present" else not present
        return TruthValue.TRUE if matched else TruthValue.FALSE

    if prop in (Property.WALL_TEMPERATURE, Property.PROCESS_TEMPERATURE,
                Property.TOTAL_PRESSURE, Property.H2S_PARTIAL_PRESSURE,
                Property.CONCENTRATION, Property.FLOW_VELOCITY, Property.CUSTOM_NUMERIC):
        if isinstance(fact_value, bool) or not isinstance(fact_value, (int, float)):
            return TruthValue.UNKNOWN
        if fact_unit is None:
            return TruthValue.UNKNOWN
        x = _base_number(fact_value, fact_unit, prop)
        unit = predicate.unit or ""
        if predicate.relation.value == "interval":
            lo, hi = (_base_number(v, unit, prop) for v in predicate.value)
            ok = lo <= x <= hi
        else:
            expected = _base_number(predicate.value, unit, prop) if predicate.relation.value != "in" else None
            if predicate.relation.value == "eq":
                ok = x == expected
            elif predicate.relation.value == "ge":
                ok = x >= expected
            elif predicate.relation.value == "le":
                ok = x <= expected
            else:
                return TruthValue.UNKNOWN
        return TruthValue.TRUE if ok else TruthValue.FALSE

    if predicate.relation.value == "eq":
        ok = fact_value == predicate.value
    elif predicate.relation.value == "in":
        values = fact_value if isinstance(fact_value, list) else [fact_value]
        ok = any(v in predicate.value for v in values)
    else:
        return TruthValue.UNKNOWN
    return TruthValue.TRUE if ok else TruthValue.FALSE


def _fact_comparison(predicate: Predicate, fact: DeviceFact) -> TruthValue:
    if fact.truth == TruthValue.UNKNOWN or fact.confirmation == FactConfirmation.UNCONFIRMED:
        return TruthValue.UNKNOWN
    if predicate.property != fact.property or predicate.subject != fact.subject:
        return TruthValue.UNKNOWN
    if predicate.target_object != fact.target_object:
        return TruthValue.UNKNOWN
    if predicate.stage is not None and predicate.stage != fact.stage:
        return TruthValue.UNKNOWN
    if predicate.property in (Property.WALL_TEMPERATURE, Property.PROCESS_TEMPERATURE,
                              Property.TOTAL_PRESSURE, Property.H2S_PARTIAL_PRESSURE,
                              Property.CONCENTRATION, Property.FLOW_VELOCITY, Property.CUSTOM_NUMERIC):
        if fact.unit is None or predicate.unit is None:
            return TruthValue.UNKNOWN
        # Normalize both values but preserve property identity: total and partial
        # pressure are different properties even though both use pressure units.
        punit = predicate.unit
        funit = fact.unit
        try:
            return _predicate_value(predicate, float(fact.value), funit)
        except (TypeError, ValueError, KeyError):
            return TruthValue.UNKNOWN
    return _predicate_value(predicate, fact.value)


def _fact_key(fact: DeviceFact) -> tuple[Any, ...]:
    return fact.subject, fact.property, fact.target_object, fact.stage


def _fact_index(facts: Iterable[DeviceFact]) -> tuple[dict[tuple[Any, ...], DeviceFact | None], list[str]]:
    grouped: dict[tuple[Any, ...], list[DeviceFact]] = defaultdict(list)
    for fact in facts:
        grouped[_fact_key(fact)].append(fact)
    index: dict[tuple[Any, ...], DeviceFact | None] = {}
    conflicts: list[str] = []
    for key, values in grouped.items():
        confirmed = [x for x in values if x.truth != TruthValue.UNKNOWN and x.confirmation != FactConfirmation.UNCONFIRMED]
        if len({(x.truth, json.dumps(x.value, sort_keys=True, ensure_ascii=False), x.unit)
                for x in confirmed}) > 1:
            index[key] = None
            conflicts.append(f"conflicting confirmed facts for {key[1].value} on {key[2]}")
        elif confirmed:
            index[key] = confirmed[0]
        else:
            index[key] = values[0]
    return index, conflicts


def _scope_applies(predicate: Predicate, rule: ApplicabilityRule) -> bool:
    if predicate.scope == Scope.SPECIFIC_SUBTYPE:
        return bool(rule.submechanism_id and predicate.submechanism_id == rule.submechanism_id)
    return True


def _evaluate_predicate(predicate: Predicate, rule: ApplicabilityRule,
                        facts: Mapping[tuple[Any, ...], DeviceFact | None]) -> TruthValue:
    if not _scope_applies(predicate, rule):
        return TruthValue.UNKNOWN
    key = (predicate.subject, predicate.property, predicate.target_object, predicate.stage)
    fact = facts.get(key)
    if predicate.stage is None:
        candidates = [value for candidate_key, value in facts.items()
                      if candidate_key[:3] == key[:3]]
        if candidates:
            if any(value is None for value in candidates):
                return TruthValue.UNKNOWN
            normalized = {(value.truth, value.value, value.unit) for value in candidates if value is not None}
            if len(normalized) > 1:
                return TruthValue.UNKNOWN
            fact = next((value for value in candidates if value is not None), None)
    if fact is None:
        # A conflict is represented by None; a genuinely missing fact is also unknown.
        return TruthValue.UNKNOWN
    return _fact_comparison(predicate, fact)


def _group_truth(predicate_values: list[TruthValue], operator: GroupOperator) -> TruthValue:
    if operator == GroupOperator.ALL:
        if TruthValue.FALSE in predicate_values:
            return TruthValue.FALSE
        if all(v == TruthValue.TRUE for v in predicate_values):
            return TruthValue.TRUE
        return TruthValue.UNKNOWN
    if TruthValue.TRUE in predicate_values:
        return TruthValue.TRUE
    if all(v == TruthValue.FALSE for v in predicate_values):
        return TruthValue.FALSE
    return TruthValue.UNKNOWN


def _source_ids(rule: ApplicabilityRule) -> tuple[list[str], list[str]]:
    predicates = [p for g in [*rule.necessary_groups, *rule.exclusion_groups] for p in g.predicates]
    predicates.extend(rule.annotations)
    ids = sorted({p.source.source_clause_id for p in predicates if p.source.source_clause_id})
    clauses = sorted({p.source.clause_no for p in predicates if p.source.clause_no})
    return ids, clauses


def diagnose_applicability(rule: ApplicabilityRule, facts: Iterable[DeviceFact]) -> ApplicabilityResult:
    """Evaluate one mechanism/submechanism candidate using confirmed typed facts only."""
    start = time.perf_counter()
    fact_index, conflicts = _fact_index(facts)
    support: list[str] = []
    contradictions: list[str] = []
    unknowns: list[str] = list(conflicts)
    priorities: list[str] = []
    annotations: list[str] = []
    possible_hard_exclusion = False
    all_required_true = bool(rule.necessary_groups)
    all_required_source_verified = bool(rule.necessary_groups)
    has_assessable_group = False

    for group in rule.necessary_groups:
        values = [_evaluate_predicate(p, rule, fact_index) for p in group.predicates]
        group_value = _group_truth(values, group.operator)
        applicable = any(_scope_applies(p, rule) for p in group.predicates)
        if applicable:
            has_assessable_group = True
        all_required_true &= group_value == TruthValue.TRUE
        group_verified = all(hard_exclusion_eligible(p) and p.polarity == Polarity.NECESSARY
                             for p in group.predicates)
        all_required_source_verified &= group_verified
        if group_value == TruthValue.TRUE:
            support.append(f"{group.group_id}: necessary condition group satisfied")
        elif group_value == TruthValue.FALSE:
            contradictions.append(f"{group.group_id}: confirmed necessary-condition contradiction")
            per_predicate = [_evaluate_predicate(p, rule, fact_index) for p in group.predicates]
            if group.operator == GroupOperator.ALL:
                possible_hard_exclusion |= any(
                    value == TruthValue.FALSE and hard_exclusion_eligible(p)
                    for p, value in zip(group.predicates, per_predicate)
                )
            else:
                possible_hard_exclusion |= (
                    all(value == TruthValue.FALSE for value in per_predicate)
                    and all(hard_exclusion_eligible(p) for p in group.predicates)
                )
        else:
            labels = [p.property.value for p in group.predicates]
            unknowns.append(f"{group.group_id}: unknown/unconfirmed {', '.join(labels)}")
            priorities.extend(labels)

    exclusion_triggered = False
    unknown_exclusion_condition = False
    for group in rule.exclusion_groups:
        values = [_evaluate_predicate(p, rule, fact_index) for p in group.predicates]
        group_value = _group_truth(values, group.operator)
        if group_value == TruthValue.TRUE:
            contradictions.append(f"{group.group_id}: explicit exclusion condition observed")
            if all(hard_exclusion_eligible(p) for p in group.predicates):
                exclusion_triggered = True
        elif group_value == TruthValue.UNKNOWN:
            unknown_exclusion_condition = True
            unknowns.append(f"{group.group_id}: exclusion condition unknown")
            priorities.extend(p.property.value for p in group.predicates)

    for p in rule.annotations:
        if p.role == Role.PROTECTION or p.polarity == Polarity.PROTECTIVE:
            annotations.append(f"{p.predicate_id}: protective description; never treated as a hard exclusion")
        elif p.polarity == Polarity.SUPPORTING:
            value = _evaluate_predicate(p, rule, fact_index)
            annotations.append(f"{p.predicate_id}: supporting evidence {value.value.lower()} (not a necessary gate)")
        else:
            annotations.append(f"{p.predicate_id}: contextual evidence only")

    if exclusion_triggered or possible_hard_exclusion:
        status = ApplicabilityStatus.EXCLUDED_WITH_CONFIRMED_CONTRADICTION
    elif not rule.necessary_groups or not has_assessable_group:
        status = ApplicabilityStatus.NOT_ASSESSED
        if not rule.necessary_groups:
            unknowns.append("no explicit necessary-condition set is available")
        else:
            unknowns.append("available predicates are scoped to a different/unselected submechanism")
    elif (all_required_true and rule.completeness == "complete" and all_required_source_verified
          and not unknown_exclusion_condition):
        status = ApplicabilityStatus.SUPPORTED_WITH_CONDITIONS
    else:
        status = ApplicabilityStatus.POSSIBLE_NEEDS_EVIDENCE
        if all_required_true and (rule.completeness != "complete" or not all_required_source_verified):
            unknowns.append("conditions are not source-verified/approved as a complete necessary set")
    # Evaluation time is intentionally not exposed in the decision; callers can measure externally.
    _ = time.perf_counter() - start
    source_ids, source_clauses = _source_ids(rule)
    return ApplicabilityResult(
        mechanism_id=rule.mechanism_id, submechanism_id=rule.submechanism_id,
        status=status, support=support, contradictions=contradictions,
        unknowns=unknowns, source_ids=source_ids, source_clauses=source_clauses,
        measurement_priority=sorted(set(priorities)), annotations=annotations,
        risk_level=None, inspection_interval_year=None, observed_damage=None,
    )


def annotate_teacher_candidates(
    teacher_result: Mapping[str, Any],
    rules_by_clause_id: Mapping[str, ApplicabilityRule],
    facts: Iterable[DeviceFact],
) -> dict[str, Any]:
    """Return an additive shadow annotation; official teacher candidates are never filtered."""
    cloned = dict(teacher_result)
    result = teacher_result.get("result")
    if not isinstance(result, dict):
        cloned["applicability_diagnostics"] = []
        return cloned
    mechanisms = result.get("mechanisms")
    if not isinstance(mechanisms, list):
        cloned["applicability_diagnostics"] = []
        return cloned
    facts_snapshot = list(facts)
    diagnostics: list[dict[str, Any]] = []
    for candidate in mechanisms:
        if not isinstance(candidate, dict):
            continue
        clause_id = candidate.get("clause_id")
        rule = rules_by_clause_id.get(clause_id) if isinstance(clause_id, str) else None
        if rule is None:
            diagnostics.append({
                "clause_id": clause_id,
                "status": ApplicabilityStatus.NOT_ASSESSED.value,
                "unknowns": ["no S3-A applicability rule supplied"],
                "risk_level": None,
            })
            continue
        diagnostic = diagnose_applicability(rule, facts_snapshot)
        diagnostics.append(diagnostic.model_dump(mode="json"))
    cloned["applicability_diagnostics"] = diagnostics
    return cloned


def import_s3a_candidate_annotations(path: str | Path) -> dict[str, Any]:
    """Load S3-A JSONL as non-operative annotations; quarantine ambiguous semantics.

    This deliberately does not translate S3-A's candidate-only role/polarity to
    necessary/excluding predicates. Pending PDF review and unresolved material
    susceptibility/protection cannot create a hard rule.
    """
    candidate_property_map = {
        "material": (Subject.MATERIAL, Property.MATERIAL_FAMILY),
        "process_medium": (Subject.MEDIUM, Property.PROCESS_MEDIUM),
        "equipment_type": (Subject.EQUIPMENT, Property.EQUIPMENT_TYPE),
    }
    rules: dict[str, dict[str, Any]] = {}
    quarantined: list[dict[str, Any]] = []
    accepted = 0
    for line_number, raw_line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        if not raw_line.strip():
            continue
        try:
            row = json.loads(raw_line)
            clause_id = row.get("clause_id")
            prop_name = row.get("property")
            value = row.get("value")
            if not isinstance(clause_id, str):
                raise ValueError("missing clause_id")
            mapped = candidate_property_map.get(prop_name)
            if mapped is None:
                quarantined.append({
                    "line": line_number, "clause_id": clause_id,
                    "property": prop_name, "role": row.get("role"),
                    "reason": "property/object semantics require explicit S3-B schema review",
                })
                continue
            if not isinstance(value, str) or not value:
                quarantined.append({
                    "line": line_number, "clause_id": clause_id,
                    "property": prop_name, "role": row.get("role"),
                    "reason": "mapped candidate must have a non-empty scalar string value",
                })
                continue
            subject, property_type = mapped
            source_hash = row.get("source_sha256")
            locator = row.get("source_excerpt_locator")
            clause_no = row.get("clause_no")
            predicate = Predicate(
                predicate_id=f"s3a-line-{line_number}-{str(row.get('record_sha256', 'candidate'))[:12]}",
                subject=subject, property=property_type, relation="eq", value=value,
                target_object="candidate_context_unresolved",
                polarity=Polarity.CONTEXTUAL, role=Role.CONTEXT,
                origin=Origin.RULE_EXTRACTED, review_state=ReviewState.PROPOSED,
                source_support="NOT_VERIFIED",
                source=SourceRef(
                    source_clause_id=clause_id,
                    source_jsonl_sha256=source_hash,
                    clause_no=clause_no if isinstance(clause_no, str) else None,
                    text_span_ref=(locator.get("field") if isinstance(locator, dict)
                                   and isinstance(locator.get("field"), str) else None),
                    verification_status=SourceVerification.CLAUSE_JSONL_ONLY,
                    missing_reason="S3-A source/PDF locator and role remain candidate-only; annotation cannot gate eligibility",
                ),
                confidence_note="S3-A candidate annotation only; not a necessary condition",
            )
            bucket = rules.setdefault(clause_id, {
                "mechanism_id": clause_id, "completeness": "incomplete",
                "necessary_groups": [], "exclusion_groups": [], "annotations": [],
            })
            bucket["annotations"].append(predicate)
            accepted += 1
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            quarantined.append({
                "line": line_number, "clause_id": None, "property": None,
                "role": None, "reason": f"invalid candidate row: {type(exc).__name__}",
            })
    typed_rules = {cid: ApplicabilityRule(**fields) for cid, fields in rules.items()}
    return {
        "rules_by_clause_id": typed_rules,
        "accepted_annotation_count": accepted,
        "clause_count": len(typed_rules),
        "quarantined": quarantined,
        "status": "ANNOTATIONS_ONLY",
    }


def evaluate_ranked_candidates(
    ranked_clause_ids: list[str],
    rules_by_clause_id: Mapping[str, ApplicabilityRule],
    facts: Iterable[DeviceFact],
    relevant_critical_clause_ids: set[str],
    gold_labels: Mapping[str, TruthValue],
    k: int = 5,
) -> dict[str, Any]:
    """Small adapter for later owner-reviewed evals; reports no metric without a denominator."""
    if k < 1:
        raise ValueError("k must be positive")
    facts_snapshot = list(facts)
    predictions: dict[str, ApplicabilityStatus] = {}
    latencies_ms: list[float] = []
    for cid, rule in rules_by_clause_id.items():
        started = time.perf_counter()
        predictions[cid] = diagnose_applicability(rule, facts_snapshot).status
        latencies_ms.append((time.perf_counter() - started) * 1000.0)
    top_k = ranked_clause_ids[:k]
    recalled = len(set(top_k) & relevant_critical_clause_ids)
    false_exclusions = sum(
        predictions.get(cid) == ApplicabilityStatus.EXCLUDED_WITH_CONFIRMED_CONTRADICTION
        for cid in relevant_critical_clause_ids
    )
    known = {cid: label for cid, label in gold_labels.items() if label != TruthValue.UNKNOWN}
    unknown_total = sum(label == TruthValue.UNKNOWN for label in gold_labels.values())
    unknown_correct = sum(
        predictions.get(cid) in (ApplicabilityStatus.POSSIBLE_NEEDS_EVIDENCE,
                                 ApplicabilityStatus.NOT_ASSESSED)
        for cid, label in gold_labels.items() if label == TruthValue.UNKNOWN
    )
    unsupported = sum(
        predictions.get(cid) == ApplicabilityStatus.SUPPORTED_WITH_CONDITIONS
        and label == TruthValue.FALSE
        for cid, label in known.items()
    )
    ordered_latencies = sorted(latencies_ms)
    p50_ms = statistics.median(ordered_latencies) if ordered_latencies else None
    p95_ms = ordered_latencies[max(0, math.ceil(0.95 * len(ordered_latencies)) - 1)] if ordered_latencies else None
    return {
        "k": k,
        "critical_hazard_recall_at_k": recalled / len(relevant_critical_clause_ids) if relevant_critical_clause_ids else None,
        "critical_hazard_relevant_denominator": len(relevant_critical_clause_ids),
        "false_exclusion_rate": false_exclusions / len(relevant_critical_clause_ids) if relevant_critical_clause_ids else None,
        "false_exclusion_denominator": len(relevant_critical_clause_ids),
        "unknown_calibration": {
            "unassessed_or_possible": unknown_correct,
            "unknown_gold_denominator": unknown_total,
            "rate": unknown_correct / unknown_total if unknown_total else None,
        },
        "unsupported_assertion_rate": unsupported / len(known) if known else None,
        "known_gold_denominator": len(known),
        "p50_ms": p50_ms,
        "p95_ms": p95_ms,
        "latency_note": "local evaluator wall-time per rule; report with fixed corpus and hardware",
        "gold_state": "HUMAN_GOLD_PENDING",
        "predictions": {cid: value.value for cid, value in predictions.items()},
    }
