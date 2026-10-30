from __future__ import annotations

import json
import unittest
from pathlib import Path

from orchestration.evidence_audit import (
    audit_claim, audit_reference, canonical_record_sha256, independent_retrieve, skeptic_findings,
)
from orchestration.graph import RunState
from orchestration.semantics import Claim


class P4BClaimVerifierTests(unittest.TestCase):
    CID = "GBT-X-2026-7"

    def canonical(self, **updates):
        row = {"clause_id": self.CID, "standard_code": "GB/T X-2026", "clause_no": "7", "page": 12,
               "version": "2026.1", "title": "盐酸介质腐蚀条件", "content_raw": "盐酸介质条件下检查腐蚀。",
               "applicable_conditions": {"material": ["碳钢"], "medium": ["盐酸"]}}
        row.update(updates)
        return {self.CID: row}

    def source(self, **updates):
        value = {"clause_id": self.CID, "standard_code": "GB/T X-2026", "clause_no": "7", "page": 12}
        value.update(updates)
        return value

    def state(self, *, source=None, context=None, observations=None, question="盐酸介质腐蚀"):
        calls = [] if source is None else [{"tool": "standard_clause_search", "result": {"source": [source]}}]
        return RunState("p4b-test", "c", question, context or {}, tool_results=calls,
                        observations=observations or [])

    def claim(self, cid=None, kind="engineering_hypothesis"):
        return Claim(claim_id="c1", kind=kind, text="工具候选待核", source_clause_ids=[cid or self.CID]).model_dump(mode="json")

    def test_metadata_four_states_never_promote_missing_or_unknown(self):
        canonical = self.canonical()
        for changed, expected in [({"drop_page": True}, "missing"), ({"page": None}, "unknown"), ({"page": 99}, "mismatch"), ({"page": 12}, "matched")]:
            with self.subTest(changed=changed):
                source = self.source(**{k: v for k, v in changed.items() if k != "drop_page"})
                if changed.get("drop_page"):
                    source.pop("page")
                result = audit_claim(self.claim(), self.state(source=source), canonical)
                check = next(x for x in result.checks if x["check"] == "metadata:page")
                self.assertEqual(check["status"], expected)
                self.assertEqual(result.grade == "E1", expected == "matched")

    def test_each_required_metadata_field_missing_is_not_matched(self):
        for key in ("standard_code", "clause_no", "page"):
            source = self.source()
            source.pop(key)
            result = audit_claim(self.claim(), self.state(source=source), self.canonical())
            self.assertEqual(next(x for x in result.checks if x["check"] == f"metadata:{key}")["status"], "missing")
            self.assertEqual(result.grade, "E0")

    def test_wrong_standard_id_wrong_clause_and_wrong_page_fail_e0(self):
        for key, value in (("standard_code", "GB/T FAKE"), ("clause_no", "99"), ("page", 99)):
            result = audit_claim(self.claim(), self.state(source=self.source(**{key: value})), self.canonical())
            self.assertEqual(next(x for x in result.checks if x["check"] == f"metadata:{key}")["status"], "mismatch")
            self.assertEqual(result.grade, "E0")

    def test_unknown_source_value_and_version_conflict_are_fail_closed(self):
        source = self.source(page="")
        result = audit_claim(self.claim(), self.state(source=source), self.canonical())
        self.assertEqual(next(x for x in result.checks if x["check"] == "metadata:page")["status"], "unknown")
        self.assertEqual(result.grade, "E0")
        result = audit_claim(self.claim(), self.state(source=self.source(version="2025.0")), self.canonical())
        self.assertEqual(next(x for x in result.checks if x["check"] == "metadata:version")["status"], "mismatch")
        self.assertEqual(result.grade, "E0")

    def test_canonical_quote_hash_page_and_run_source_are_bound(self):
        index = self.canonical()
        result = audit_claim(self.claim(), self.state(source=self.source()), index)
        entry = result.canonical_evidence[0]
        self.assertEqual(entry["content_raw"], index[self.CID]["content_raw"])
        self.assertEqual(entry["canonical_record_sha256"], canonical_record_sha256(index[self.CID]))
        self.assertEqual(entry["printed_page"], 12)
        self.assertEqual(entry["tool_source"]["clause_id"], self.CID)
        self.assertEqual(result.grade, "E1")

    def test_unknown_official_id_and_empty_canonical_quote_are_e0(self):
        result = audit_claim(self.claim("FAKE-ID"), self.state(source=self.source()), self.canonical())
        self.assertEqual(result.grade, "E0")
        index = self.canonical(content_raw="  ")
        result = audit_claim(self.claim(), self.state(source=self.source()), index)
        self.assertEqual(result.grade, "E0")
        self.assertIn("canonical_content", {x["check"] for x in result.checks})

    def test_claim_classification_is_four_way_and_legacy_names_normalize(self):
        for kind in ("source_fact", "engineering_hypothesis", "equipment_diagnosis", "risk_level"):
            self.assertEqual(Claim(claim_id="x", kind=kind, text="x").kind, kind)
        self.assertEqual(Claim(claim_id="x", kind="mechanism_candidate", text="x").kind, "engineering_hypothesis")
        with self.assertRaises(ValueError):
            Claim(claim_id="x", kind="arbitrary", text="x")

    def test_risk_claim_is_never_supported_by_source_membership_alone(self):
        result = audit_claim(self.claim(kind="risk_level"), self.state(source=self.source()), self.canonical())
        self.assertEqual((result.grade, result.verdict, result.review_status), ("E0", "unresolved", "requires_human_review"))
        self.assertIn("risk_claim_gate", {x["check"] for x in result.checks})

    def test_mixed_media_and_multiple_mutually_exclusive_values_not_any_match(self):
        state = self.state(source=self.source(), context={"medium": ["盐酸", "水"], "material": ["碳钢", "不锈钢"]})
        result = audit_claim(self.claim(), state, self.canonical())
        statuses = {x["check"]: x["status"] for x in result.checks if x["check"].startswith("condition:")}
        self.assertEqual(statuses["condition:medium"], "not_sufficient")
        self.assertEqual(statuses["condition:material"], "not_sufficient")

    def test_fully_in_scope_multivalue_is_matched_but_not_semantic_proof(self):
        index = self.canonical(applicable_conditions={"medium": ["盐酸", "稀盐酸"]})
        state = self.state(source=self.source(), context={"medium": ["盐酸", "稀盐酸"]})
        result = audit_claim(self.claim(), state, index)
        condition = next(x for x in result.checks if x["check"] == "condition:medium")
        self.assertEqual(condition["status"], "matched")
        self.assertEqual((result.verdict, result.review_status), ("unresolved", "requires_human_review"))

    def test_unknown_temperature_is_not_evidence_of_in_range(self):
        index = self.canonical(applicable_conditions={"temperature_c": [0, 100]})
        observation = {"field": "temperature", "observation_state": "unknown", "normalized_value": None}
        result = audit_claim(self.claim(), self.state(source=self.source(), observations=[observation]), index)
        self.assertEqual(next(x for x in result.checks if x["check"] == "condition:temperature")["status"], "unknown")

    def test_false_observation_is_distinct_from_unknown(self):
        state = self.state(observations=[{"field": "wall_thinning", "observation_state": "observed_false", "normalized_value": False}])
        state.claims = [self.claim()]
        finding = skeptic_findings(state)[0]
        self.assertNotIn("wall_thinning", finding["finding"])
        unknown = self.state(observations=[{"field": "wall_thinning", "observation_state": "unknown", "normalized_value": None}])
        unknown.claims = [self.claim()]
        self.assertIn("unknown不能作为无减薄或有减薄", skeptic_findings(unknown)[0]["finding"])

    def test_skeptic_reloads_canonical_quote_and_runs_independent_second_search(self):
        index = self.canonical()
        state = self.state(source=self.source(), context={"medium": "盐酸", "material": "碳钢"}, question="盐酸 碳钢")
        alternate = {"clause_id": "ALT-1", "title": "盐酸检验", "content_raw": "盐酸环境检验条件", "page": 5,
                     "applicable_conditions": {"medium": ["盐酸"]}}
        state.claims = [self.claim()]
        # Retrieval can be injected deterministically in unit tests; production uses the local canonical index.
        retrieved = independent_retrieve(state.observations, state.context, {**index, "ALT-1": alternate})
        self.assertIn("ALT-1", {x["clause_id"] for x in retrieved})
        finding = skeptic_findings(state, {**index, "ALT-1": alternate})[0]
        self.assertTrue(finding["source_recheck"])
        self.assertEqual(finding["source_recheck"][0]["quote_sha256"], __import__("hashlib").sha256(index[self.CID]["content_raw"].encode()).hexdigest())
        self.assertEqual(finding["review_scope"], "lexical_only_no_semantic_entailment")

    def test_reference_is_e0_when_metadata_incomplete(self):
        index = self.canonical()
        ref = audit_reference(self.source(page=None), self.state(source=self.source(page=None)), index)
        self.assertEqual((ref["verification_level"], ref["provenance_status"]), ("E0", "partial"))

    def test_twenty_existing_synthetic_scenarios_are_unreviewed_not_gold(self):
        path = Path(__file__).resolve().parents[1] / "evals" / "p3b_unreviewed_scenarios.jsonl"
        cases = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertEqual(len(cases), 20)
        self.assertTrue(all(case["review_status"] == "unreviewed" and case["expert_label"] is None for case in cases))

    def test_all_negative_cross_source_fixture_cases_are_executable(self):
        path = Path(__file__).resolve().parents[1] / "evals" / "p4b_negative_cases.jsonl"
        cases = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertGreaterEqual(len(cases), 10)
        index = self.canonical(applicable_conditions={"medium": ["盐酸"], "temperature_c": [0, 100]})
        for case in cases:
            with self.subTest(case=case["case_id"]):
                mutation = case["mutation"]
                source = self.source()
                canonical = {self.CID: dict(index[self.CID])}
                cid = self.CID
                context = {"medium": "盐酸"}
                observations = []
                kind = "engineering_hypothesis"
                if "drop" in mutation:
                    source.pop(mutation["drop"])
                if "set" in mutation:
                    source.update(mutation["set"])
                if mutation.get("set_id"):
                    cid = mutation["set_id"]
                    source["clause_id"] = cid
                if "source" in mutation and mutation.get("source") is None:
                    source_list = []
                else:
                    source_list = [source]
                if mutation.get("empty_quote"):
                    canonical[self.CID]["content_raw"] = ""
                if mutation.get("claim_kind"):
                    kind = mutation["claim_kind"]
                if mutation.get("context"):
                    context.update(mutation["context"])
                if mutation.get("temperature_unknown"):
                    observations.append({"field": "temperature", "observation_state": "unknown", "normalized_value": None})
                state = self.state(context=context, observations=observations)
                state.tool_results = [{"tool": "standard_clause_search", "result": {"source": source_list}}]
                claim = self.claim(cid, kind=kind)
                result = audit_claim(claim, state, canonical)
                if case["expected"].startswith("E0"):
                    self.assertEqual(result.grade, "E0")
                if case["expected"] == "condition_not_sufficient":
                    self.assertEqual(next(x for x in result.checks if x["check"] == "condition:medium")["status"], "not_sufficient")
                if case["expected"] == "condition_unknown":
                    self.assertEqual(next(x for x in result.checks if x["check"] == "condition:temperature")["status"], "unknown")
                if case["expected"] == "false_distinct":
                    self.assertEqual(result.verdict, "unresolved")


if __name__ == "__main__":
    unittest.main()
