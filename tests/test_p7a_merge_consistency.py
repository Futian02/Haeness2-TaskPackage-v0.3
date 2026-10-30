import itertools
import unittest

from orchestration.p6_parallel_audit import (
    AuditFinding, SkepticFinding, merge_findings,
)


class P7AMergeConsistencyTests(unittest.TestCase):
    def audit(self, result, attempt="attempt-1"):
        return AuditFinding("run-1", "claim-1", "clause-1", "evidence_auditor", attempt, result)

    def skeptic(self, result, attempt="attempt-1"):
        return SkepticFinding("run-1", "claim-1", "clause-1", "skeptic", attempt, result)

    def test_same_key_conflict_is_order_invariant_and_fail_closed(self):
        e1 = self.audit({"grade": "E1", "checks": [{"status": "matched"}]})
        e0 = self.audit({"grade": "E0", "checks": [{"status": "missing"}]})
        skeptic = self.skeptic({"verdict": "unresolved"})
        expected = None
        for order in itertools.permutations([e1, e0]):
            merged = merge_findings(list(order), [skeptic])
            if expected is None:
                expected = merged
            self.assertEqual(merged, expected)
        audit_row = next(row for row in expected if row["origin_agent"] == "evidence_auditor")
        self.assertTrue(audit_row["conflict_requires_review"])
        self.assertEqual(audit_row["verification_level"], "E0")
        self.assertEqual(audit_row["result"]["grade"], "E0")
        self.assertEqual(len(audit_row["conflicting_payloads"]), 2)
        self.assertEqual(len(audit_row["result"]["conflict_payload_sha256s"]), 2)
        self.assertTrue(all(len(item["sha256"]) == 64 for item in audit_row["conflicting_payloads"]))

    def test_identical_payload_retry_deduplicates_and_preserves_attempt(self):
        one = self.audit({"grade": "E1", "checks": [{"status": "matched"}]}, "a1")
        duplicate = self.audit({"checks": [{"status": "matched"}], "grade": "E1"}, "a1")
        new_attempt = self.audit({"grade": "E0"}, "a2")
        merged = merge_findings([one, duplicate, new_attempt], [])
        self.assertEqual(len(merged), 2)
        self.assertEqual([row["attempt_id"] for row in merged], ["a1", "a2"])
        self.assertFalse(merged[0]["conflict_requires_review"])

    def test_untrusted_and_future_grades_are_clamped_in_all_projections(self):
        for grade in ("E2", "E3", "L1", "invalid", None):
            with self.subTest(grade=grade):
                row = merge_findings([self.audit({"grade": grade, "verification_level": grade})], [])[0]
                self.assertEqual(row["verification_level"], "E0")
                self.assertEqual(row["result"]["grade"], "E0")
                self.assertEqual(row["result"]["verification_level"], "E0")
                self.assertEqual(row["grade_gate_reason"], "grade_outside_merge_E0_E1_allowlist")

    def test_evidence_auditor_only_accepts_e0_e1(self):
        for grade, expected in (("E0", "E0"), ("E1", "E1")):
            row = merge_findings([self.audit({"grade": grade})], [])[0]
            self.assertEqual(row["verification_level"], expected)

    def test_skeptic_cannot_assign_verification_grade(self):
        row = merge_findings([], [self.skeptic({"grade": "E1", "verdict": "supported"})])[0]
        self.assertEqual(row["verification_level"], "E0")
        self.assertEqual(row["result"]["grade"], "E0")
        self.assertIn("only_evidence_auditor", row["grade_gate_reason"])

    def test_different_attempts_are_independent_rows(self):
        first = self.audit({"grade": "E1"}, "attempt-1")
        second = self.audit({"grade": "E0"}, "attempt-2")
        rows = merge_findings([second, first], [])
        self.assertEqual(len(rows), 2)
        self.assertEqual({row["attempt_id"] for row in rows}, {"attempt-1", "attempt-2"})

    def test_unknown_origin_and_non_json_payload_fail_closed(self):
        invalid_origin = AuditFinding("r", "c", "s", "diagnosis", "a1", {"grade": "E1"})
        with self.assertRaisesRegex(ValueError, "origin_agent"):
            merge_findings([invalid_origin], [])
        invalid_json = self.audit({"grade": "E1", "payload": object()})
        with self.assertRaises((TypeError, ValueError)):
            merge_findings([invalid_json], [])


if __name__ == "__main__":
    unittest.main()
