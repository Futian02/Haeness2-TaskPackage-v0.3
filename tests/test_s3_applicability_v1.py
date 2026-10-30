from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

from knowledge.applicability.schema_v1 import (
    ApplicabilityRule, ApplicabilityStatus, DeviceFact, FactConfirmation,
    GroupOperator, Origin, Polarity, Predicate, PredicateGroup, Property,
    ReviewState, Role, Scope, SourceRef, SourceVerification, Subject, TruthValue,
)
from orchestration.applicability_v1 import (
    annotate_teacher_candidates, diagnose_applicability, evaluate_ranked_candidates,
    import_s3a_candidate_annotations,
)


PDF_SHA = "a" * 64
JSONL_SHA = "b" * 64


def source(*, verified: bool = False) -> SourceRef:
    if verified:
        return SourceRef(
            source_clause_id="SYNTH-1", source_jsonl_sha256=JSONL_SHA,
            source_pdf_sha256=PDF_SHA, clause_no="synthetic 1.1",
            page_physical=1, verification_status=SourceVerification.HUMAN_PDF_VERIFIED,
        )
    return SourceRef(
        source_clause_id="SYNTH-1", source_jsonl_sha256=JSONL_SHA,
        missing_reason="synthetic fixture; no real standard provenance",
    )


def pred(property: Property, value, *, subject: Subject | None = None,
         relation="eq", unit=None, target="pipe_inner_wall", stage=None,
         scope=Scope.WHOLE_MECHANISM, submechanism_id=None, polarity=Polarity.NECESSARY,
         role=Role.TRIGGER, verified=False, predicate_id="p1") -> Predicate:
    if subject is None:
        subject = {
            Property.MATERIAL_FAMILY: Subject.MATERIAL,
            Property.PROCESS_MEDIUM: Subject.MEDIUM,
            Property.WALL_TEMPERATURE: Subject.TEMPERATURE,
            Property.PROCESS_TEMPERATURE: Subject.TEMPERATURE,
            Property.TOTAL_PRESSURE: Subject.PRESSURE,
            Property.H2S_PARTIAL_PRESSURE: Subject.PRESSURE,
            Property.GAS_SIDE: Subject.PROCESS_ENVIRONMENT,
            Property.FLUE_GAS_PRESENT: Subject.PROCESS_ENVIRONMENT,
            Property.WET_H2S: Subject.CORROSION_CONDITION,
            Property.WET_SERVICE: Subject.CORROSION_CONDITION,
            Property.EQUIPMENT_TYPE: Subject.EQUIPMENT,
            Property.CUSTOM_BOOLEAN: Subject.CORROSION_CONDITION,
        }.get(property, Subject.PROCESS_ENVIRONMENT)
    return Predicate(
        predicate_id=predicate_id, subject=subject, property=property,
        relation=relation, value=value, unit=unit, target_object=target, stage=stage,
        polarity=polarity, role=role, scope=scope, submechanism_id=submechanism_id,
        origin=Origin.HUMAN_SOURCE_VERIFIED if verified else Origin.RULE_EXTRACTED,
        review_state=ReviewState.OWNER_APPROVED if verified else ReviewState.PROPOSED,
        source_support="SUPPORTED" if verified else "WEAK", source=source(verified=verified),
    )


def fact(property: Property, value, *, subject: Subject | None = None, unit=None,
         target="pipe_inner_wall", stage=None, truth: TruthValue | None=None,
         confirmation=FactConfirmation.USER_CONFIRMED) -> DeviceFact:
    if subject is None:
        subject = {
            Property.MATERIAL_FAMILY: Subject.MATERIAL,
            Property.PROCESS_MEDIUM: Subject.MEDIUM,
            Property.WALL_TEMPERATURE: Subject.TEMPERATURE,
            Property.PROCESS_TEMPERATURE: Subject.TEMPERATURE,
            Property.TOTAL_PRESSURE: Subject.PRESSURE,
            Property.H2S_PARTIAL_PRESSURE: Subject.PRESSURE,
            Property.GAS_SIDE: Subject.PROCESS_ENVIRONMENT,
            Property.FLUE_GAS_PRESENT: Subject.PROCESS_ENVIRONMENT,
            Property.WET_H2S: Subject.CORROSION_CONDITION,
            Property.WET_SERVICE: Subject.CORROSION_CONDITION,
            Property.EQUIPMENT_TYPE: Subject.EQUIPMENT,
            Property.CUSTOM_BOOLEAN: Subject.CORROSION_CONDITION,
        }.get(property, Subject.PROCESS_ENVIRONMENT)
    if truth is None:
        truth = (TruthValue.UNKNOWN if value is None else
                 TruthValue.FALSE if isinstance(value, bool) and value is False else TruthValue.TRUE)
    return DeviceFact(subject=subject, property=property, target_object=target,
                      stage=stage, value=value, unit=unit, truth=truth,
                      confirmation=confirmation, evidence_ref="synthetic-fixture")


def rule(*groups: PredicateGroup, mechanism="SYNTH-1", submechanism=None,
         complete=True, exclusions=(), annotations=()) -> ApplicabilityRule:
    return ApplicabilityRule(
        mechanism_id=mechanism, submechanism_id=submechanism,
        completeness="complete" if complete else "incomplete",
        necessary_groups=list(groups), exclusion_groups=list(exclusions),
        annotations=list(annotations),
    )


def group(*predicates: Predicate, operator=GroupOperator.ALL, group_id="g1") -> PredicateGroup:
    return PredicateGroup(group_id=group_id, operator=operator, predicates=list(predicates))


class ApplicabilityV1Tests(unittest.TestCase):
    def test_01_schema_version_and_three_valued_unknown(self):
        x = DeviceFact(subject=Subject.MEDIUM, property=Property.PROCESS_MEDIUM,
                       target_object="process_stream", value=None, truth=TruthValue.UNKNOWN)
        self.assertEqual(x.truth, TruthValue.UNKNOWN)
        self.assertEqual(rule().schema_version, "1.0")

    def test_02_unknown_cannot_carry_default_zero(self):
        with self.assertRaises(ValidationError):
            DeviceFact(subject=Subject.TEMPERATURE, property=Property.WALL_TEMPERATURE,
                       target_object="pipe_inner_wall", value=0, unit="degC",
                       truth=TruthValue.UNKNOWN)

    def test_03_confirmed_fact_requires_confirmation(self):
        with self.assertRaises(ValidationError):
            fact(Property.PROCESS_MEDIUM, "hydrochloric acid",
                 confirmation=FactConfirmation.UNCONFIRMED)

    def test_04_generic_temp_property_is_rejected(self):
        with self.assertRaises(ValidationError):
            pred(Property.CUSTOM_NUMERIC, 90, unit="degC")

    def test_05_total_pressure_and_partial_pressure_are_distinct(self):
        r = rule(group(pred(Property.H2S_PARTIAL_PRESSURE, 0.0003,
                            relation="ge", unit="MPa_partial", target="process_stream")))
        result = diagnose_applicability(r, [fact(Property.TOTAL_PRESSURE, 1.0,
                                                 unit="MPa", target="process_stream")])
        self.assertEqual(result.status, ApplicabilityStatus.POSSIBLE_NEEDS_EVIDENCE)
        self.assertIn("h2s_partial_pressure", " ".join(result.measurement_priority))

    def test_06_partial_pressure_unit_cannot_be_total_pressure_unit(self):
        with self.assertRaises(ValidationError):
            pred(Property.H2S_PARTIAL_PRESSURE, 0.1, relation="ge", unit="MPa")

    def test_07_wall_temperature_not_process_temperature(self):
        r = rule(group(pred(Property.WALL_TEMPERATURE, 80, relation="ge",
                            unit="degC", target="pipe_inner_wall")))
        result = diagnose_applicability(r, [fact(Property.PROCESS_TEMPERATURE, 100,
                                                 unit="degC", target="process_stream")])
        self.assertEqual(result.status, ApplicabilityStatus.POSSIBLE_NEEDS_EVIDENCE)

    def test_08_temperature_unit_conversion_celsius_kelvin(self):
        r = rule(group(pred(Property.WALL_TEMPERATURE, 100, relation="ge",
                            unit="degC", target="pipe_inner_wall", verified=True)))
        result = diagnose_applicability(r, [fact(Property.WALL_TEMPERATURE, 373.15,
                                                 unit="K", target="pipe_inner_wall")])
        self.assertEqual(result.status, ApplicabilityStatus.SUPPORTED_WITH_CONDITIONS)

    def test_09_pressure_unit_conversion_pa_mpa(self):
        r = rule(group(pred(Property.TOTAL_PRESSURE, 0.2, relation="ge",
                            unit="MPa", target="vessel_shell", verified=True)))
        result = diagnose_applicability(r, [fact(Property.TOTAL_PRESSURE, 250000,
                                                 unit="Pa", target="vessel_shell")])
        self.assertEqual(result.status, ApplicabilityStatus.SUPPORTED_WITH_CONDITIONS)

    def test_10_material_confirmed_mismatch_only_excludes_with_verified_source(self):
        r = rule(group(pred(Property.MATERIAL_FAMILY, "carbon_steel",
                            subject=Subject.MATERIAL, target="pipe_wall", verified=True)))
        result = diagnose_applicability(r, [fact(Property.MATERIAL_FAMILY, "stainless_steel",
                                                 subject=Subject.MATERIAL, target="pipe_wall")])
        self.assertEqual(result.status, ApplicabilityStatus.EXCLUDED_WITH_CONFIRMED_CONTRADICTION)

    def test_11_material_mismatch_unverified_never_hard_excludes(self):
        r = rule(group(pred(Property.MATERIAL_FAMILY, "carbon_steel",
                            subject=Subject.MATERIAL, target="pipe_wall")))
        result = diagnose_applicability(r, [fact(Property.MATERIAL_FAMILY, "stainless_steel",
                                                 subject=Subject.MATERIAL, target="pipe_wall")])
        self.assertEqual(result.status, ApplicabilityStatus.POSSIBLE_NEEDS_EVIDENCE)

    def test_12_protective_material_annotation_does_not_exclude(self):
        protection = pred(Property.MATERIAL_FAMILY, "high_alloy",
                          subject=Subject.MATERIAL, target="pipe_wall",
                          polarity=Polarity.PROTECTIVE, role=Role.PROTECTION)
        r = rule(group(pred(Property.PROCESS_MEDIUM, "acid", subject=Subject.MEDIUM,
                            target="process_stream", verified=True)),
                 annotations=[protection])
        result = diagnose_applicability(r, [
            fact(Property.PROCESS_MEDIUM, "acid", subject=Subject.MEDIUM, target="process_stream"),
            fact(Property.MATERIAL_FAMILY, "high_alloy", subject=Subject.MATERIAL, target="pipe_wall"),
        ])
        self.assertEqual(result.status, ApplicabilityStatus.SUPPORTED_WITH_CONDITIONS)
        self.assertIn("never treated as a hard exclusion", result.annotations[0])

    def test_13_protective_role_cannot_be_a_hard_negative(self):
        with self.assertRaises(ValidationError):
            pred(Property.MATERIAL_FAMILY, "high_alloy", subject=Subject.MATERIAL,
                 polarity=Polarity.EXCLUDING, role=Role.PROTECTION)

    def test_14_unconfirmed_fact_is_unknown_not_false(self):
        r = rule(group(pred(Property.PROCESS_MEDIUM, "acid", subject=Subject.MEDIUM,
                            target="process_stream", verified=True)))
        result = diagnose_applicability(r, [fact(Property.PROCESS_MEDIUM, None,
                                                 subject=Subject.MEDIUM, target="process_stream",
                                                 truth=TruthValue.UNKNOWN,
                                                 confirmation=FactConfirmation.UNCONFIRMED)])
        self.assertEqual(result.status, ApplicabilityStatus.POSSIBLE_NEEDS_EVIDENCE)

    def test_15_unknown_does_not_exclude(self):
        r = rule(group(pred(Property.FLUE_GAS_PRESENT, True, relation="eq",
                            target="exchanger_gas_side", verified=True)))
        result = diagnose_applicability(r, [fact(Property.FLUE_GAS_PRESENT, None,
                                                 target="exchanger_gas_side", truth=TruthValue.UNKNOWN,
                                                 confirmation=FactConfirmation.UNCONFIRMED)])
        self.assertEqual(result.status, ApplicabilityStatus.POSSIBLE_NEEDS_EVIDENCE)

    def test_16_wrong_target_side_is_unknown_not_false(self):
        r = rule(group(pred(Property.GAS_SIDE, True, relation="eq",
                            target="exchanger_gas_side", verified=True)))
        result = diagnose_applicability(r, [fact(Property.GAS_SIDE, False,
                                                 target="exchanger_process_side")])
        self.assertEqual(result.status, ApplicabilityStatus.POSSIBLE_NEEDS_EVIDENCE)

    def test_17_operating_phase_mismatch_is_unknown(self):
        r = rule(group(pred(Property.WET_SERVICE, True, relation="eq",
                            target="process_stream", stage="startup", verified=True)))
        result = diagnose_applicability(r, [fact(Property.WET_SERVICE, False,
                                                 target="process_stream", stage="normal")])
        self.assertEqual(result.status, ApplicabilityStatus.POSSIBLE_NEEDS_EVIDENCE)

    def test_18_stage_unspecified_uses_unique_phase_fact(self):
        r = rule(group(pred(Property.WET_SERVICE, True, relation="eq",
                            target="process_stream", verified=True)))
        result = diagnose_applicability(r, [fact(Property.WET_SERVICE, True,
                                                 target="process_stream", stage="normal")])
        self.assertEqual(result.status, ApplicabilityStatus.SUPPORTED_WITH_CONDITIONS)

    def test_19_multiple_phase_conflict_becomes_unknown(self):
        r = rule(group(pred(Property.WET_SERVICE, True, relation="eq",
                            target="process_stream", verified=True)))
        result = diagnose_applicability(r, [
            fact(Property.WET_SERVICE, True, target="process_stream", stage="startup"),
            fact(Property.WET_SERVICE, False, target="process_stream", stage="normal"),
        ])
        self.assertEqual(result.status, ApplicabilityStatus.POSSIBLE_NEEDS_EVIDENCE)

    def test_20_local_subtype_does_not_exclude_whole_mechanism(self):
        p = pred(Property.WALL_TEMPERATURE, 100, relation="ge", unit="degC",
                 target="pipe_inner_wall", scope=Scope.SPECIFIC_SUBTYPE,
                 submechanism_id="subtype-hot", verified=True)
        r = rule(group(p), mechanism="SYNTH-ROOT")
        result = diagnose_applicability(r, [fact(Property.WALL_TEMPERATURE, 20,
                                                 unit="degC", target="pipe_inner_wall")])
        self.assertEqual(result.status, ApplicabilityStatus.NOT_ASSESSED)
        self.assertEqual(result.mechanism_id, "SYNTH-ROOT")

    def test_21_matching_local_subtype_can_be_excluded(self):
        p = pred(Property.WALL_TEMPERATURE, 100, relation="ge", unit="degC",
                 target="pipe_inner_wall", scope=Scope.SPECIFIC_SUBTYPE,
                 submechanism_id="subtype-hot", verified=True)
        r = rule(group(p), mechanism="SYNTH-ROOT", submechanism="subtype-hot")
        result = diagnose_applicability(r, [fact(Property.WALL_TEMPERATURE, 20,
                                                 unit="degC", target="pipe_inner_wall")])
        self.assertEqual(result.status, ApplicabilityStatus.EXCLUDED_WITH_CONFIRMED_CONTRADICTION)
        self.assertEqual(result.submechanism_id, "subtype-hot")

    def test_22_all_group_false_on_one_confirmed_necessary_condition(self):
        r = rule(group(
            pred(Property.PROCESS_MEDIUM, "acid", subject=Subject.MEDIUM,
                 target="process_stream", verified=True, predicate_id="medium"),
            pred(Property.FLUE_GAS_PRESENT, True, target="gas_side",
                 verified=True, predicate_id="gas"),
            operator=GroupOperator.ALL,
        ))
        result = diagnose_applicability(r, [
            fact(Property.PROCESS_MEDIUM, "water", subject=Subject.MEDIUM, target="process_stream"),
            fact(Property.FLUE_GAS_PRESENT, True, target="gas_side"),
        ])
        self.assertEqual(result.status, ApplicabilityStatus.EXCLUDED_WITH_CONFIRMED_CONTRADICTION)

    def test_23_any_group_requires_all_alternatives_false_to_exclude(self):
        r = rule(group(
            pred(Property.PROCESS_MEDIUM, "acid", subject=Subject.MEDIUM,
                 target="process_stream", verified=True, predicate_id="a"),
            pred(Property.PROCESS_MEDIUM, "alkali", subject=Subject.MEDIUM,
                 target="process_stream", verified=True, predicate_id="b"),
            operator=GroupOperator.ANY,
        ))
        result = diagnose_applicability(r, [fact(Property.PROCESS_MEDIUM, "water",
                                                 subject=Subject.MEDIUM, target="process_stream")])
        self.assertEqual(result.status, ApplicabilityStatus.EXCLUDED_WITH_CONFIRMED_CONTRADICTION)

    def test_24_any_group_unknown_alternative_prevents_exclusion(self):
        r = rule(group(
            pred(Property.PROCESS_MEDIUM, "acid", subject=Subject.MEDIUM,
                 target="process_stream", verified=True, predicate_id="a"),
            pred(Property.PROCESS_MEDIUM, "alkali", subject=Subject.MEDIUM,
                 target="process_stream", verified=True, predicate_id="b"),
            operator=GroupOperator.ANY,
        ))
        result = diagnose_applicability(r, [fact(Property.PROCESS_MEDIUM, None,
                                                 subject=Subject.MEDIUM, target="process_stream",
                                                 truth=TruthValue.UNKNOWN,
                                                 confirmation=FactConfirmation.UNCONFIRMED)])
        self.assertEqual(result.status, ApplicabilityStatus.POSSIBLE_NEEDS_EVIDENCE)

    def test_25_incomplete_necessary_set_never_supports(self):
        r = rule(group(pred(Property.PROCESS_MEDIUM, "acid", subject=Subject.MEDIUM,
                            target="process_stream", verified=True)), complete=False)
        result = diagnose_applicability(r, [fact(Property.PROCESS_MEDIUM, "acid",
                                                 subject=Subject.MEDIUM, target="process_stream")])
        self.assertEqual(result.status, ApplicabilityStatus.POSSIBLE_NEEDS_EVIDENCE)

    def test_26_full_verified_necessary_set_supports_only_conditions(self):
        r = rule(group(pred(Property.PROCESS_MEDIUM, "acid", subject=Subject.MEDIUM,
                            target="process_stream", verified=True)))
        result = diagnose_applicability(r, [fact(Property.PROCESS_MEDIUM, "acid",
                                                 subject=Subject.MEDIUM, target="process_stream")])
        self.assertEqual(result.status, ApplicabilityStatus.SUPPORTED_WITH_CONDITIONS)
        self.assertIsNone(result.risk_level)
        self.assertIsNone(result.inspection_interval_year)
        self.assertIsNone(result.observed_damage)

    def test_27_auto_candidate_source_cannot_hard_exclude(self):
        r = rule(group(pred(Property.PROCESS_MEDIUM, "acid", subject=Subject.MEDIUM,
                            target="process_stream", verified=False)))
        result = diagnose_applicability(r, [fact(Property.PROCESS_MEDIUM, "water",
                                                 subject=Subject.MEDIUM, target="process_stream")])
        self.assertNotEqual(result.status, ApplicabilityStatus.EXCLUDED_WITH_CONFIRMED_CONTRADICTION)

    def test_28_missing_pdf_hash_cannot_be_labeled_verified(self):
        with self.assertRaises(ValidationError):
            SourceRef(source_clause_id="SYNTH", verification_status=SourceVerification.HUMAN_PDF_VERIFIED,
                      clause_no="1.1", page_physical=1)

    def test_29_wrong_unit_for_pressure_is_rejected(self):
        with self.assertRaises(ValidationError):
            pred(Property.TOTAL_PRESSURE, 0.1, relation="ge", unit="MPa_partial")

    def test_30_numeric_unknown_has_no_zero_default(self):
        r = rule(group(pred(Property.TOTAL_PRESSURE, 0.2, relation="ge",
                            unit="MPa", target="vessel_shell", verified=True)))
        result = diagnose_applicability(r, [])
        self.assertEqual(result.status, ApplicabilityStatus.POSSIBLE_NEEDS_EVIDENCE)

    def test_31_boolean_presence_relation(self):
        r = rule(group(pred(Property.FLUE_GAS_PRESENT, None, relation="present",
                            target="furnace_gas_side", verified=True)))
        yes = diagnose_applicability(r, [fact(Property.FLUE_GAS_PRESENT, True,
                                              target="furnace_gas_side")])
        no = diagnose_applicability(r, [fact(Property.FLUE_GAS_PRESENT, False,
                                             target="furnace_gas_side")])
        self.assertEqual(yes.status, ApplicabilityStatus.SUPPORTED_WITH_CONDITIONS)
        self.assertEqual(no.status, ApplicabilityStatus.EXCLUDED_WITH_CONFIRMED_CONTRADICTION)

    def test_32_interval_boundaries_inclusive(self):
        r = rule(group(pred(Property.WALL_TEMPERATURE, [50, 100], relation="interval",
                            unit="degC", target="pipe_wall", verified=True)))
        for val in (50, 75, 100):
            with self.subTest(val=val):
                self.assertEqual(diagnose_applicability(
                    r, [fact(Property.WALL_TEMPERATURE, val, unit="degC", target="pipe_wall")]
                ).status, ApplicabilityStatus.SUPPORTED_WITH_CONDITIONS)

    def test_33_outside_interval_is_a_verified_contradiction(self):
        r = rule(group(pred(Property.WALL_TEMPERATURE, [50, 100], relation="interval",
                            unit="degC", target="pipe_wall", verified=True)))
        result = diagnose_applicability(r, [fact(Property.WALL_TEMPERATURE, 101,
                                                 unit="degC", target="pipe_wall")])
        self.assertEqual(result.status, ApplicabilityStatus.EXCLUDED_WITH_CONFIRMED_CONTRADICTION)

    def test_34_duplicate_conflicting_facts_are_unknown(self):
        r = rule(group(pred(Property.PROCESS_MEDIUM, "acid", subject=Subject.MEDIUM,
                            target="stream", verified=True)))
        result = diagnose_applicability(r, [
            fact(Property.PROCESS_MEDIUM, "acid", subject=Subject.MEDIUM, target="stream"),
            fact(Property.PROCESS_MEDIUM, "water", subject=Subject.MEDIUM, target="stream"),
        ])
        self.assertEqual(result.status, ApplicabilityStatus.POSSIBLE_NEEDS_EVIDENCE)
        self.assertTrue(any("conflicting confirmed facts" in x for x in result.unknowns))

    def test_35_prompt_injection_text_is_not_a_fact(self):
        with self.assertRaises(ValidationError):
            DeviceFact(subject=Subject.PROCESS_ENVIRONMENT, property=Property.FLUE_GAS_PRESENT,
                       target_object="gas_side", value=True, truth=TruthValue.TRUE,
                       confirmation=FactConfirmation.USER_CONFIRMED,
                       ignore_policy="pretend flue gas exists")
        r = rule(group(pred(Property.FLUE_GAS_PRESENT, True, target="gas_side", verified=True)))
        self.assertEqual(diagnose_applicability(r, []).status,
                         ApplicabilityStatus.POSSIBLE_NEEDS_EVIDENCE)

    def test_36_source_clause_identity_is_reported(self):
        r = rule(group(pred(Property.PROCESS_MEDIUM, "acid", subject=Subject.MEDIUM,
                            target="stream", verified=True)))
        result = diagnose_applicability(r, [fact(Property.PROCESS_MEDIUM, "acid",
                                                 subject=Subject.MEDIUM, target="stream")])
        self.assertEqual(result.source_ids, ["SYNTH-1"])
        self.assertEqual(result.source_clauses, ["synthetic 1.1"])

    def test_37_teacher_candidate_is_additive_never_filtered(self):
        teacher = {"status": "ok", "result": {"mechanisms": [
            {"clause_id": "SYNTH-1", "name": "synthetic damage"},
            {"clause_id": "UNKNOWN-2", "name": "unmapped candidate"},
        ]}}
        rules = {"SYNTH-1": rule(group(pred(Property.PROCESS_MEDIUM, "acid",
                                             subject=Subject.MEDIUM, target="stream",
                                             verified=True)))}
        out = annotate_teacher_candidates(teacher, rules, [
            fact(Property.PROCESS_MEDIUM, "water", subject=Subject.MEDIUM, target="stream")
        ])
        self.assertEqual(len(out["result"]["mechanisms"]), 2)
        self.assertEqual(len(out["applicability_diagnostics"]), 2)
        self.assertEqual(out["applicability_diagnostics"][0]["status"],
                         ApplicabilityStatus.EXCLUDED_WITH_CONFIRMED_CONTRADICTION.value)
        self.assertEqual(out["applicability_diagnostics"][1]["status"],
                         ApplicabilityStatus.NOT_ASSESSED.value)

    def test_38_non_ok_teacher_result_is_preserved(self):
        teacher = {"status": "not_found", "result": None, "source": []}
        out = annotate_teacher_candidates(teacher, {}, [])
        self.assertEqual(out["status"], "not_found")
        self.assertEqual(out["applicability_diagnostics"], [])

    def test_39_metrics_are_marked_human_gold_pending(self):
        r = rule(group(pred(Property.PROCESS_MEDIUM, "acid", subject=Subject.MEDIUM,
                            target="stream", verified=True)))
        out = evaluate_ranked_candidates(["SYNTH-1"], {"SYNTH-1": r},
                                         [fact(Property.PROCESS_MEDIUM, "acid",
                                               subject=Subject.MEDIUM, target="stream")],
                                         {"SYNTH-1"}, {"SYNTH-1": TruthValue.UNKNOWN}, k=1)
        self.assertEqual(out["gold_state"], "HUMAN_GOLD_PENDING")
        self.assertGreaterEqual(out["p50_ms"], 0.0)
        self.assertGreaterEqual(out["p95_ms"], 0.0)
        self.assertEqual(out["critical_hazard_recall_at_k"], 1.0)

    def test_40_bad_top_k_is_rejected(self):
        with self.assertRaises(ValueError):
            evaluate_ranked_candidates([], {}, [], set(), {}, k=0)

    def test_41_medium_outside_teacher_enum_can_be_explicitly_assessed(self):
        r = rule(group(pred(Property.PROCESS_MEDIUM, "sulfuric acid",
                            subject=Subject.MEDIUM, target="process_stream", verified=True)))
        out = diagnose_applicability(r, [fact(Property.PROCESS_MEDIUM, "sulfuric acid",
                                              subject=Subject.MEDIUM, target="process_stream")])
        self.assertEqual(out.status, ApplicabilityStatus.SUPPORTED_WITH_CONDITIONS)

    def test_42_environment_side_must_match_exactly(self):
        r = rule(group(pred(Property.FLUE_GAS_PRESENT, True, target="furnace_gas_side",
                            verified=True)))
        out = diagnose_applicability(r, [fact(Property.FLUE_GAS_PRESENT, True,
                                              target="process_stream")])
        self.assertEqual(out.status, ApplicabilityStatus.POSSIBLE_NEEDS_EVIDENCE)

    def test_43_h2s_partial_pressure_boundary(self):
        r = rule(group(pred(Property.H2S_PARTIAL_PRESSURE, 0.0003, relation="ge",
                            unit="MPa_partial", target="gas_phase", verified=True)))
        out = diagnose_applicability(r, [fact(Property.H2S_PARTIAL_PRESSURE, 0.3,
                                              unit="kPa_partial", target="gas_phase")])
        self.assertEqual(out.status, ApplicabilityStatus.SUPPORTED_WITH_CONDITIONS)

    def test_44_total_pressure_does_not_satisfy_h2s_partial_pressure(self):
        r = rule(group(pred(Property.H2S_PARTIAL_PRESSURE, 0.0003, relation="ge",
                            unit="MPa_partial", target="gas_phase", verified=True)))
        out = diagnose_applicability(r, [fact(Property.TOTAL_PRESSURE, 1.0,
                                              unit="MPa", target="gas_phase")])
        self.assertEqual(out.status, ApplicabilityStatus.POSSIBLE_NEEDS_EVIDENCE)

    def test_45_supporting_evidence_never_becomes_necessary_gate(self):
        annotation = pred(Property.WET_H2S, True, relation="eq", target="stream",
                          polarity=Polarity.SUPPORTING, role=Role.DISAMBIGUATOR)
        r = rule(group(pred(Property.PROCESS_MEDIUM, "water", subject=Subject.MEDIUM,
                            target="stream", verified=True)), annotations=[annotation])
        out = diagnose_applicability(r, [fact(Property.PROCESS_MEDIUM, "water",
                                              subject=Subject.MEDIUM, target="stream")])
        self.assertEqual(out.status, ApplicabilityStatus.SUPPORTED_WITH_CONDITIONS)
        self.assertTrue(out.annotations)

    def test_46_source_missing_reason_retained_as_unknown_metadata(self):
        s = SourceRef(source_clause_id="SYNTH-X", missing_reason="synthetic only")
        self.assertEqual(s.missing_reason, "synthetic only")

    def test_47_eq_relation_for_numeric(self):
        r = rule(group(pred(Property.WALL_TEMPERATURE, 95, relation="eq",
                            unit="degC", target="wall", verified=True)))
        self.assertEqual(diagnose_applicability(
            r, [fact(Property.WALL_TEMPERATURE, 95, unit="degC", target="wall")]
        ).status, ApplicabilityStatus.SUPPORTED_WITH_CONDITIONS)

    def test_48_ge_relation_for_numeric(self):
        r = rule(group(pred(Property.TOTAL_PRESSURE, 2, relation="ge",
                            unit="MPa", target="shell", verified=True)))
        out = diagnose_applicability(r, [fact(Property.TOTAL_PRESSURE, 1,
                                               unit="MPa", target="shell")])
        self.assertEqual(out.status, ApplicabilityStatus.EXCLUDED_WITH_CONFIRMED_CONTRADICTION)

    def test_49_open_ended_missing_fact_reports_measurement_priority(self):
        r = rule(group(pred(Property.H2S_PARTIAL_PRESSURE, 0.0003, relation="ge",
                            unit="MPa_partial", target="gas_phase", verified=True)))
        out = diagnose_applicability(r, [])
        self.assertIn("h2s_partial_pressure", out.measurement_priority)

    def test_50_all_predicates_in_or_group_must_be_verified_before_exclusion(self):
        a = pred(Property.PROCESS_MEDIUM, "acid", subject=Subject.MEDIUM,
                 target="stream", verified=True, predicate_id="a")
        b = pred(Property.PROCESS_MEDIUM, "alkali", subject=Subject.MEDIUM,
                 target="stream", verified=False, predicate_id="b")
        r = rule(group(a, b, operator=GroupOperator.ANY))
        out = diagnose_applicability(r, [fact(Property.PROCESS_MEDIUM, "water",
                                              subject=Subject.MEDIUM, target="stream")])
        self.assertNotEqual(out.status, ApplicabilityStatus.EXCLUDED_WITH_CONFIRMED_CONTRADICTION)

    def test_51_fact_property_mismatch_is_unknown(self):
        r = rule(group(pred(Property.WALL_TEMPERATURE, 50, relation="ge",
                            unit="degC", target="wall", verified=True)))
        out = diagnose_applicability(r, [fact(Property.PROCESS_TEMPERATURE, 100,
                                              unit="degC", target="wall")])
        self.assertEqual(out.status, ApplicabilityStatus.POSSIBLE_NEEDS_EVIDENCE)

    def test_52_s3a_candidate_import_is_annotation_only_and_quarantines_ambiguous_fields(self):
        rows = [
            {
                "clause_id": "S3A-1", "clause_no": "5.1", "property": "material",
                "value": "stainless steel", "source_sha256": JSONL_SHA,
                "record_sha256": "c" * 64, "role": "susceptibility_or_resistance_role_unresolved",
                "polarity": "candidate_support_or_scope_only",
                "review_state": "PROPOSED_NEEDS_PDF_CHECK",
                "source_excerpt_locator": {"field": "applicable_conditions.material"},
            },
            {
                "clause_id": "S3A-1", "clause_no": "5.1", "property": "wall_temperature",
                "value": 120, "unit": "degC", "source_sha256": JSONL_SHA,
                "role": "condition_scope_candidate",
            },
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "pilot.jsonl"
            path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
            imported = import_s3a_candidate_annotations(path)
        self.assertEqual(imported["accepted_annotation_count"], 1)
        self.assertEqual(imported["clause_count"], 1)
        self.assertEqual(len(imported["quarantined"]), 1)
        imported_rule = imported["rules_by_clause_id"]["S3A-1"]
        self.assertEqual(imported_rule.necessary_groups, [])
        self.assertEqual(imported_rule.annotations[0].polarity, Polarity.CONTEXTUAL)
        self.assertEqual(imported_rule.annotations[0].role, Role.CONTEXT)
        diagnostic = diagnose_applicability(imported_rule, [
            fact(Property.MATERIAL_FAMILY, "carbon steel", subject=Subject.MATERIAL,
                 target="candidate_context_unresolved")
        ])
        self.assertEqual(diagnostic.status, ApplicabilityStatus.NOT_ASSESSED)

    def test_53_unknown_exclusion_discriminator_prevents_supported_status(self):
        required = group(pred(Property.PROCESS_MEDIUM, "acid", subject=Subject.MEDIUM,
                              target="process_stream", verified=True))
        exclusion = group(pred(Property.FLUE_GAS_PRESENT, True, target="gas_side",
                               polarity=Polarity.EXCLUDING, role=Role.DISAMBIGUATOR,
                               verified=True, predicate_id="exclusion"),
                          group_id="disambiguator")
        r = rule(required, exclusions=[exclusion])
        out = diagnose_applicability(r, [
            fact(Property.PROCESS_MEDIUM, "acid", subject=Subject.MEDIUM,
                 target="process_stream"),
        ])
        self.assertEqual(out.status, ApplicabilityStatus.POSSIBLE_NEEDS_EVIDENCE)
        self.assertTrue(any("exclusion condition unknown" in item for item in out.unknowns))

    def test_54_unsupported_fact_truth_does_not_become_exclusion(self):
        r = rule(group(pred(Property.PROCESS_MEDIUM, "acid", subject=Subject.MEDIUM,
                            target="stream", verified=True)))
        out = diagnose_applicability(r, [fact(Property.PROCESS_MEDIUM, None,
                                              subject=Subject.MEDIUM, target="stream",
                                              truth=TruthValue.UNKNOWN,
                                              confirmation=FactConfirmation.UNCONFIRMED)])
        self.assertNotEqual(out.status, ApplicabilityStatus.EXCLUDED_WITH_CONFIRMED_CONTRADICTION)


if __name__ == "__main__":
    unittest.main()
