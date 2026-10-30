import random
import time
import unittest

from langgraph.errors import InvalidUpdateError
from langgraph.graph import END, START, StateGraph
from typing import TypedDict

from orchestration.p6_parallel_audit import (
    AuditFinding, ParallelAuditState, SkepticFinding, _audit_branch, _merge_node,
    _skeptic_branch, merge_findings, run_parallel_audit,
)


def snapshot(case: int = 0):
    cid = f"SYNTH-CLAUSE-{case}"
    canonical = {"clause_id": cid, "standard_code": "SYNTH-STD", "clause_no": str(case + 1),
                 "page": case + 1, "version": "fixture-1", "content_raw": "synthetic fixture only",
                 "applicable_conditions": {}}
    source = {key: canonical[key] for key in ("clause_id", "standard_code", "clause_no", "page", "version")}
    if case % 5 == 1:
        source.pop("page")  # missing source metadata must remain E0
    if case % 5 == 2:
        canonical = dict(canonical, content_raw="")  # missing canonical text must remain E0
    obs = [{"field": "wall_thinning", "raw_span": "not measured", "normalized_value": None,
            "observation_state": "unknown"}]
    if case % 3 == 0:
        obs += [{"field": "temperature", "raw_span": "unknown", "normalized_value": None,
                 "observation_state": "unknown"}]
    claim = {"claim_id": f"run-{case}-claim-1", "kind": "engineering_hypothesis",
             "text": "synthetic unreviewed hypothesis", "source_clause_ids": [cid],
             "observation_ids": ["obs-wall_thinning"], "assumptions": []}
    if case % 7 == 0:
        claim["kind"] = "risk_level"  # risk claim gate must cap at E0
    return {"run_id": f"run-{case}", "attempt_id": "attempt-1", "context": {},
            "observations": obs,
            "tool_results": [{"tool": "standard_clause_search", "args": {},
                              "result": {"status": "ok", "source": [source]}}],
            "claims": [claim], "clause_index": {cid: canonical}}


class _BadState(TypedDict):
    values: list[str]


class P6AParallelEvidenceTests(unittest.TestCase):
    def test_unreduced_parallel_write_fails_with_expected_langgraph_error(self):
        builder = StateGraph(_BadState)
        builder.add_node("a", lambda _s: {"values": ["a"]})
        builder.add_node("b", lambda _s: {"values": ["b"]})
        builder.add_edge(START, "a")
        builder.add_edge(START, "b")
        builder.add_edge("a", END)
        builder.add_edge("b", END)
        with self.assertRaises(InvalidUpdateError):
            builder.compile().invoke({"values": []})

    def test_fifteen_plus_synthetic_cases_keep_evidence_unknowns_and_grade_caps(self):
        for case_id in range(20):
            with self.subTest(case=case_id):
                result = run_parallel_audit(snapshot(case_id))
                self.assertEqual(len(result["audit_updates"]), 1)
                self.assertEqual(len(result["skeptic_updates"]), 1)
                self.assertEqual(len(result["merged_findings"]), 2)
                self.assertEqual({row["origin_agent"] for row in result["merged_findings"]},
                                 {"evidence_auditor", "skeptic"})
                self.assertTrue(all(row["review_status"] == "requires_human_review"
                                    for row in result["merged_findings"]))
                audit = next(row for row in result["merged_findings"] if row["origin_agent"] == "evidence_auditor")
                self.assertIn(audit["verification_level"], {"E0", "E1"})
                if case_id % 7 == 0 or case_id % 5 in {1, 2}:
                    self.assertEqual(audit["verification_level"], "E0")

    def test_merge_is_order_invariant_and_keeps_supporting_and_counter_views(self):
        base = snapshot(3)
        outputs = []
        for seed in range(10):
            result = run_parallel_audit(base)
            audits = list(result["audit_updates"])
            skeptics = list(result["skeptic_updates"])
            random.Random(seed).shuffle(audits)
            random.Random(seed + 30).shuffle(skeptics)
            outputs.append(merge_findings(audits, skeptics))
        self.assertTrue(all(value == outputs[0] for value in outputs))
        self.assertEqual({row["origin_agent"] for row in outputs[0]}, {"evidence_auditor", "skeptic"})

    def test_randomized_parallel_completion_order_has_identical_merge(self):
        expected = run_parallel_audit(snapshot(4))["merged_findings"]
        for seed in range(10):
            delay_audit = random.Random(seed).random() * .006
            delay_skeptic = random.Random(seed + 17).random() * .006
            builder = StateGraph(ParallelAuditState)
            def audit(state):
                time.sleep(delay_audit)
                return _audit_branch(state)
            def skeptic(state):
                time.sleep(delay_skeptic)
                return _skeptic_branch(state)
            builder.add_node("evidence_auditor", audit)
            builder.add_node("skeptic", skeptic)
            builder.add_node("merge", _merge_node)
            builder.add_edge(START, "evidence_auditor")
            builder.add_edge(START, "skeptic")
            builder.add_edge(["evidence_auditor", "skeptic"], "merge")
            builder.add_edge("merge", END)
            data = {**snapshot(4), "audit_updates": [], "skeptic_updates": [], "merged_findings": []}
            result = builder.compile().invoke(data)
            self.assertEqual(result["merged_findings"], expected)

    def test_merge_deduplicates_retry_but_preserves_distinct_attempts(self):
        finding = AuditFinding("r", "c", "s", "evidence_auditor", "a1", {"grade": "E1"})
        retry_duplicate = AuditFinding("r", "c", "s", "evidence_auditor", "a1", {"grade": "E0"})
        next_attempt = AuditFinding("r", "c", "s", "evidence_auditor", "a2", {"grade": "E0"})
        skeptic = SkepticFinding("r", "c", "s", "skeptic", "a1", {"verdict": "unresolved"})
        merged = merge_findings([finding, retry_duplicate, next_attempt], [skeptic])
        self.assertEqual(len(merged), 3)
        self.assertEqual(sum(row["origin_agent"] == "evidence_auditor" for row in merged), 2)
        # Same-attempt contradictory payloads stay visible and conservatively
        # clamp to E0; do not let a legacy test promote the E1 side.
        self.assertEqual(merged[0]["verification_level"], "E0")
        self.assertTrue(merged[0]["conflict_requires_review"])
        self.assertEqual(len(merged[0]["conflicting_payloads"]), 2)

    def test_conflicting_review_views_are_not_collapsed_to_best_grade(self):
        audit = AuditFinding("r", "c", "s", "evidence_auditor", "attempt-1",
                             {"grade": "E1", "verdict": "unresolved", "checks": [{"status": "matched"}]})
        counter = SkepticFinding("r", "c", "s", "skeptic", "attempt-1",
                                 {"verdict": "contradicted", "finding": "field condition missing"})
        merged = merge_findings([audit], [counter])
        self.assertEqual(len(merged), 2)
        self.assertEqual({item["origin_agent"] for item in merged}, {"evidence_auditor", "skeptic"})
        self.assertEqual(next(item for item in merged if item["origin_agent"] == "skeptic")["verification_level"], "E0")
        self.assertTrue(all(item["review_status"] == "requires_human_review" for item in merged))

    def test_missing_snapshot_fields_fail_closed(self):
        data = snapshot()
        data.pop("clause_index")
        with self.assertRaisesRegex(ValueError, "clause_index"):
            run_parallel_audit(data)


if __name__ == "__main__":
    unittest.main()
