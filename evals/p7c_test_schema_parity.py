"""P7-C parity and authority-boundary tests; every fixture is synthetic/in-memory."""
from __future__ import annotations

import unittest

from evals.p6c_test_review_schema import draft_expert_record
from evals.p6c_validate_review import validate_record
from evals.p7c_schema_parity import SYNTHETIC_LABEL, differential_results, fixtures
from evals.p7c_synthetic_authority import SYNTHETIC_ONLY, SyntheticMockAuthority


class P7CSchemaParityTests(unittest.TestCase):
    def test_at_least_40_synthetic_cases_match_both_validators(self):
        results = differential_results()
        self.assertGreaterEqual(len(results), 40)
        self.assertTrue(all(r["fixture_id"].startswith(SYNTHETIC_LABEL + ":") for r in results))
        self.assertTrue(all(r["parity"] for r in results), [r for r in results if not r["parity"]])
        self.assertFalse(any(r["unexpected_expectation"] for r in results))

    def test_extraction_attestation_role_mismatch_rejected_by_both(self):
        row = next(r for r in differential_results() if r["fixture_id"].endswith(":extraction-role-mismatch"))
        self.assertFalse(row["schema_valid"])
        self.assertFalse(row["stdlib_valid"])

    def test_unsigned_template_remains_shape_valid_but_not_verified_shaped(self):
        record = next(r for n, r, _ in fixtures() if n == "expert-valid-draft")
        self.assertEqual(validate_record(record), [])
        self.assertTrue(validate_record(record, require_verified=True))

    def test_boolean_and_arbitrary_signature_reference_do_not_authenticate(self):
        record = draft_expert_record()
        record["status"] = "verified"
        record["reviewed_at"] = "2026-10-28T12:00:00Z"
        record["reviewer"]["reviewer_identity_verified"] = True
        record["reviewer"]["reviewer_signature_ref"] = "SYNTHETIC_NOT_A_SIGNATURE"
        # This legacy check only evaluates shape and is not an authority decision.
        self.assertEqual(validate_record(record, require_verified=True), [])
        decision = SyntheticMockAuthority().verify_attestation(
            record, evidence_bundle={"fixture_marker": SYNTHETIC_ONLY}
        )
        self.assertFalse(decision["authenticated"])
        self.assertEqual(decision["reason_code"], "SYNTHETIC_MOCK_NEVER_AUTHENTICATES")

    def test_mock_fails_closed_without_explicit_synthetic_fixture(self):
        result = SyntheticMockAuthority().verify_attestation({}, evidence_bundle={})
        self.assertFalse(result["authenticated"])
        self.assertEqual(result["reason_code"], "SYNTHETIC_FIXTURE_REQUIRED")


if __name__ == "__main__":
    unittest.main()
