"""Generate synthetic schema-vs-stdlib differential cases (never human evidence)."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from evals.p6c_test_review_schema import draft_expert_record
from evals.p6c_validate_review import ROOT, validate_record

SYNTHETIC_LABEL = "SYNTHETIC_TEST_ONLY_NOT_HUMAN_REVIEW"


def draft_site_record() -> dict[str, Any]:
    return {
        "record_type": "site_context_confirmation", "confirmation_id": "TEST-ONLY-site",
        "reviewer": {"reviewer_identity_verified": False, "reviewer_role": "site_data_confirmant",
                     "reviewer_signature_ref": None, "reviewer_identity_ref": None},
        "device_context_hash": "c" * 64, "confirmed_fields": ["material"],
        "unknown_fields": ["temperature"], "confirmed_at": None, "status": "draft",
    }


def draft_extraction_record() -> dict[str, Any]:
    return {
        "record_type": "extraction_attestation", "attestation_id": "TEST-ONLY-extract",
        "reviewer": {"reviewer_identity_verified": False, "reviewer_role": "standard_extractor",
                     "reviewer_signature_ref": None, "reviewer_identity_ref": None},
        "source_sha": "d" * 64, "source_clause_id": "TEST-ONLY-clause",
        "pdf_printed_page": 1, "quote_sha": "e" * 64,
        "attestation_role": "standard_extractor", "attested_at": None, "status": "draft",
    }


def fixtures() -> list[tuple[str, dict[str, Any], bool]]:
    """Return >40 named cases; expected boolean is included as a guard against vacuous parity."""
    bases = {
        "expert": draft_expert_record(),
        "site": draft_site_record(),
        "extraction": draft_extraction_record(),
    }
    cases: list[tuple[str, dict[str, Any], bool]] = []
    for label, base in bases.items():
        cases.append((f"{label}-valid-draft", deepcopy(base), True))
        required_fields = {
            "expert": ["review_id", "reviewer", "claim_id", "source_sha", "source_clause_id", "pdf_printed_page", "device_context_hash", "assessment_type", "verdict", "justification", "reviewed_at", "status"],
            "site": ["confirmation_id", "reviewer", "device_context_hash", "confirmed_fields", "unknown_fields", "confirmed_at", "status"],
            "extraction": ["attestation_id", "reviewer", "source_sha", "source_clause_id", "pdf_printed_page", "quote_sha", "attestation_role", "attested_at", "status"],
        }[label]
        for field in required_fields:
            changed = deepcopy(base); changed.pop(field)
            cases.append((f"{label}-missing-{field}", changed, False))
        changed = deepcopy(base); changed["extra_field"] = "x"
        cases.append((f"{label}-unknown-field", changed, False))
        changed = deepcopy(base); changed["reviewer"]["extra"] = "x"
        cases.append((f"{label}-reviewer-unknown-field", changed, False))
        changed = deepcopy(base); changed["reviewer"]["reviewer_identity_verified"] = "false"
        cases.append((f"{label}-identity-not-bool", changed, False))
        changed = deepcopy(base); changed["reviewer"]["reviewer_role"] = "not-a-role"
        cases.append((f"{label}-bad-role-enum", changed, False))
        changed = deepcopy(base); changed["reviewer"]["reviewer_signature_ref"] = 4
        cases.append((f"{label}-signature-wrong-type", changed, False))
        changed = deepcopy(base); changed["reviewer"]["reviewer_identity_ref"] = "   "
        cases.append((f"{label}-identity-ref-blank", changed, False))
        changed = deepcopy(base); changed["status"] = "unknown"
        cases.append((f"{label}-status-invalid", changed, False))

    # Per-record semantic constraints.
    for name, field, value in [
        ("expert-bad-source-sha", "source_sha", "g" * 64),
        ("expert-short-context-hash", "device_context_hash", "0" * 63),
        ("expert-page-bool", "pdf_printed_page", True),
        ("expert-page-zero", "pdf_printed_page", 0),
        ("expert-bad-assessment", "assessment_type", "E4"),
        ("expert-bad-verdict", "verdict", "maybe"),
        ("expert-blank-claim", "claim_id", "  "),
        ("expert-bad-timestamp", "reviewed_at", "2026-10-28 12:00:00"),
    ]:
        changed = deepcopy(bases["expert"]); changed[field] = value
        cases.append((name, changed, False))
    changed = deepcopy(bases["expert"]); changed["status"] = "verified"
    cases.append(("expert-verified-missing-auth-shape", changed, False))
    changed = deepcopy(bases["expert"]); changed["status"] = "verified"; changed["reviewed_at"] = "2026-10-28T12:00:00+08:00"
    changed["reviewer"]["reviewer_identity_verified"] = True; changed["reviewer"]["reviewer_signature_ref"] = "SYNTHETIC-ref"
    changed["reviewer"]["reviewer_role"] = "domain_expert"
    cases.append(("expert-verified-shaped-synthetic", changed, True))
    changed = deepcopy(changed)
    changed["reviewer"]["reviewer_role"] = "site_data_confirmant"
    cases.append(("expert-role-not-expert", changed, False))
    changed = deepcopy(bases["expert"]); changed["conflict_group_id"] = "   "
    cases.append(("expert-blank-optional-id", changed, False))

    changed = deepcopy(bases["site"]); changed["reviewer"]["reviewer_role"] = "domain_expert"
    cases.append(("site-wrong-role", changed, False))
    changed = deepcopy(bases["site"]); changed["confirmed_fields"] = ["material", "material"]
    cases.append(("site-duplicate-field", changed, False))
    changed = deepcopy(bases["site"]); changed["unknown_fields"] = [""]
    cases.append(("site-empty-array-item", changed, False))
    changed = deepcopy(bases["site"]); changed["confirmed_at"] = "not-a-date"
    cases.append(("site-bad-optional-date", changed, False))
    changed = deepcopy(bases["site"]); changed["status"] = "verified"
    cases.append(("site-verified-missing-signature", changed, False))
    changed = deepcopy(bases["site"]); changed["status"] = "verified"; changed["confirmed_at"] = "2026-10-28T12:00:00Z"
    changed["reviewer"]["reviewer_identity_verified"] = True; changed["reviewer"]["reviewer_signature_ref"] = "SYNTHETIC-ref"
    cases.append(("site-verified-shaped-synthetic", changed, True))

    changed = deepcopy(bases["extraction"]); changed["attestation_role"] = "independent_reviewer"
    cases.append(("extraction-role-mismatch", changed, False))
    changed = deepcopy(bases["extraction"]); changed["attestation_role"] = "independent_reviewer"; changed["reviewer"]["reviewer_role"] = "independent_reviewer"
    cases.append(("extraction-reviewer-role-matched", changed, True))
    changed = deepcopy(bases["extraction"]); changed["attestation_role"] = "bad-role"
    cases.append(("extraction-role-invalid", changed, False))
    changed = deepcopy(bases["extraction"]); changed["quote_sha"] = "z" * 64
    cases.append(("extraction-bad-quote-sha", changed, False))
    changed = deepcopy(bases["extraction"]); changed["attested_at"] = "2026-10-28T12:00:00"  # no zone
    cases.append(("extraction-naive-date", changed, False))
    changed = deepcopy(bases["extraction"]); changed["status"] = "verified"
    cases.append(("extraction-verified-missing-signature", changed, False))
    changed = deepcopy(bases["extraction"]); changed["status"] = "verified"; changed["attested_at"] = "2026-10-28T12:00:00+00:00"
    changed["reviewer"]["reviewer_identity_verified"] = True; changed["reviewer"]["reviewer_signature_ref"] = "SYNTHETIC-ref"
    cases.append(("extraction-verified-shaped-synthetic", changed, True))

    assert len(cases) >= 40, len(cases)
    return cases


def differential_results() -> list[dict[str, Any]]:
    schema = json.loads((ROOT / "evals" / "p6c_review_schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    output = []
    for name, record, expected in fixtures():
        schema_ok = not list(validator.iter_errors(record))
        stdlib_ok = not validate_record(record)
        output.append({"fixture_id": f"{SYNTHETIC_LABEL}:{name}", "expected_valid": expected,
                       "schema_valid": schema_ok, "stdlib_valid": stdlib_ok,
                       "parity": schema_ok == stdlib_ok,
                       "unexpected_expectation": schema_ok != expected or stdlib_ok != expected})
    return output


def main() -> int:
    results = differential_results()
    mismatches = [r for r in results if not r["parity"]]
    unexpected = [r for r in results if r["unexpected_expectation"]]
    print(f"SYNTHETIC_DIFFERENTIAL_CASES={len(results)} SCHEMA_STDLIB_MISMATCHES={len(mismatches)} EXPECTATION_MISMATCHES={len(unexpected)}")
    for row in mismatches + unexpected:
        print(json.dumps(row, ensure_ascii=False))
    if mismatches or unexpected:
        return 1
    print("PASS: parity only; no identity, signature, expert review, or Gold was authenticated/created")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
