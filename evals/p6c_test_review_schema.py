"""Executable contract checks; fixtures are synthetic placeholders, never expert gold."""
from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from evals.p6c_validate_review import ROOT, validate_record, validate_template


def draft_expert_record() -> dict:
    return {
        "record_type": "expert_assessment",
        "review_id": "TEST-ONLY",
        "reviewer": {
            "reviewer_identity_verified": False,
            "reviewer_role": "domain_expert",
            "reviewer_signature_ref": None,
            "reviewer_identity_ref": None,
        },
        "claim_id": "TEST-ONLY",
        "source_sha": "a" * 64,
        "source_clause_id": "TEST-ONLY",
        "pdf_printed_page": 1,
        "device_context_hash": "b" * 64,
        "assessment_type": "E2_source_entailment",
        "verdict": "unresolved",
        "justification": "Synthetic unit-test fixture only; not a judgment.",
        "reviewed_at": None,
        "status": "draft",
        "conflict_group_id": None,
        "adjudication_ref": None,
    }


class P6CReviewContractTests(unittest.TestCase):
    def test_schema_json_and_required_review_fields(self):
        schema = json.loads((ROOT / "evals" / "p6c_review_schema.json").read_text(encoding="utf-8"))
        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(len(schema["oneOf"]), 3)
        required = set(schema["$defs"]["expertAssessment"]["required"])
        self.assertTrue({"review_id", "reviewer", "claim_id", "source_sha", "source_clause_id", "pdf_printed_page", "device_context_hash", "assessment_type", "verdict", "justification", "reviewed_at"}.issubset(required))

    def test_unsigned_draft_is_structurally_accepted_but_never_verified(self):
        record = draft_expert_record()
        self.assertEqual(validate_record(record), [])
        self.assertTrue(validate_record(record, require_verified=True))

    def test_unverified_llm_or_unsigned_record_cannot_pass_gate(self):
        record = draft_expert_record()
        record.update(status="verified", reviewed_at="2026-10-28T12:00:00+08:00")
        self.assertTrue(any("identity" in issue for issue in validate_record(record, require_verified=True)))
        record["reviewer"]["reviewer_identity_verified"] = True
        self.assertTrue(any("signature" in issue for issue in validate_record(record, require_verified=True)))

    def test_user_fact_confirmation_is_distinct_from_expert_assessment(self):
        record = {
            "record_type": "site_context_confirmation",
            "confirmation_id": "TEST-ONLY",
            "reviewer": {"reviewer_identity_verified": False, "reviewer_role": "domain_expert", "reviewer_signature_ref": None, "reviewer_identity_ref": None},
            "device_context_hash": "c" * 64,
            "confirmed_fields": ["material"],
            "unknown_fields": ["temperature"],
            "confirmed_at": None,
            "status": "draft",
        }
        self.assertTrue(any("site_data_confirmant" in issue for issue in validate_record(record)))

    def test_e2_e3_require_expert_roles_and_verdict_is_not_auto_promoted(self):
        record = draft_expert_record()
        record["reviewer"]["reviewer_role"] = "site_data_confirmant"
        self.assertTrue(any("expert" in issue for issue in validate_record(record)))
        record["reviewer"]["reviewer_role"] = "independent_reviewer"
        record["assessment_type"] = "E3_applicability"
        record["verdict"] = "unresolved"
        self.assertEqual(validate_record(record), [])
        self.assertEqual(record["verdict"], "unresolved")

    def test_template_gate_has_no_signed_or_gold_records(self):
        template = json.loads((ROOT / "evals" / "p6c_review_template.json").read_text(encoding="utf-8"))
        self.assertTrue(template["template_only"])
        self.assertTrue(all(r["reviewer"]["reviewer_identity_verified"] is False for r in template["records"]))
        self.assertTrue(all(r["status"] == "draft" for r in template["records"]))
        self.assertEqual(validate_template(), [])


if __name__ == "__main__":
    unittest.main()
