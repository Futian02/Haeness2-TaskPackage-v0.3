"""Shape-only P6-C review record validator; it does not authenticate humans.

``validate_record(require_verified=True)`` is retained as a legacy *shape* gate.
It only checks that fields look like a verified record. It MUST NOT be used to
authenticate an identity, validate a signature, grant E2/E3, or create Gold.
Production promotion requires a separate, externally backed
``HumanReviewAuthority.verify_attestation`` implementation (see P6C protocol).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol, TypedDict

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "evals" / "p6c_review_schema.json"
TEMPLATE_PATH = ROOT / "evals" / "p6c_review_template.json"
SHA256 = re.compile(r"^[a-fA-F0-9]{64}$")
RFC3339 = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)
RFC3339_PATTERN = r"^\\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\\d|3[01])T([01]\\d|2[0-3]):[0-5]\\d:[0-5]\\d(\\.\\d+)?(Z|[+-]([01]\\d|2[0-3]):[0-5]\\d)$"
REVIEWER_ROLES = {
    "site_data_confirmant", "domain_expert", "standard_extractor",
    "independent_reviewer", "adjudicator", "owner",
}
EXPERT_ROLES = {"domain_expert", "independent_reviewer", "adjudicator"}
RECORD_FIELDS: dict[str, tuple[set[str], set[str]]] = {
    "expert_assessment": (
        {"record_type", "review_id", "reviewer", "claim_id", "source_sha",
         "source_clause_id", "pdf_printed_page", "device_context_hash",
         "assessment_type", "verdict", "justification", "reviewed_at", "status"},
        {"conflict_group_id", "adjudication_ref"},
    ),
    "site_context_confirmation": (
        {"record_type", "confirmation_id", "reviewer", "device_context_hash",
         "confirmed_fields", "unknown_fields", "confirmed_at", "status"}, set(),
    ),
    "extraction_attestation": (
        {"record_type", "attestation_id", "reviewer", "source_sha",
         "source_clause_id", "pdf_printed_page", "quote_sha", "attestation_role",
         "attested_at", "status"}, set(),
    ),
}
REVIEWER_REQUIRED = {
    "reviewer_identity_verified", "reviewer_role", "reviewer_signature_ref"
}
REVIEWER_ALLOWED = REVIEWER_REQUIRED | {"reviewer_identity_ref"}


class AuthorityDecision(TypedDict):
    authenticated: bool
    reason_code: str
    verified_identity_ref: str | None
    signed_payload_sha256: str | None


class HumanReviewAuthority(Protocol):
    """Contract only: implementations must bind to an approved trust service.

    A production adapter must verify the cryptographic signature, trust chain,
    identity status/expiry/revocation, reviewer qualifications, canonical payload
    and source hashes, role authorization, and independent reviewer separation.
    No implementation is supplied by this schema-only package.
    """

    def verify_attestation(
        self, record: dict[str, Any], *, evidence_bundle: dict[str, Any]
    ) -> AuthorityDecision: ...


def _nonblank(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_datetime(value: Any) -> bool:
    """JSON Schema format=date-time parity: RFC3339 timestamp with UTC offset."""
    if not isinstance(value, str) or not RFC3339.fullmatch(value):
        return False
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() is not None


def _require_nonblank(record: dict[str, Any], fields: tuple[str, ...], issues: list[str]) -> None:
    for field in fields:
        if not _nonblank(record.get(field)):
            issues.append(f"{field} must be a non-empty string")


def _check_nullable_string(container: dict[str, Any], field: str, issues: list[str], label: str) -> None:
    value = container.get(field)
    if value is not None and not _nonblank(value):
        issues.append(f"{label} must be null or a non-empty string")


def _check_timestamp(record: dict[str, Any], field: str, issues: list[str], *, required: bool) -> None:
    value = record.get(field)
    if value is None and not required:
        return
    if not _is_datetime(value):
        issues.append(f"{field} must be null or an RFC3339 date-time" if not required else f"{field} must be an RFC3339 date-time")


def validate_record(record: dict[str, Any], *, require_verified: bool = False) -> list[str]:
    """Validate schema-equivalent shape; optional flag checks verified-shaped fields only.

    IMPORTANT: even an empty result with ``require_verified=True`` is not proof
    of human identity/signature/qualification. Only a trusted external authority
    can authenticate and authorize a review. This function never grants E2/E3.
    """
    if not isinstance(record, dict):
        return ["record must be an object"]
    kind = record.get("record_type")
    if kind not in RECORD_FIELDS:
        return ["record_type must identify a supported human record"]
    required, optional = RECORD_FIELDS[kind]
    issues: list[str] = []
    missing = sorted(required - record.keys())
    if missing:
        issues.append("missing required fields: " + ", ".join(missing))
    extra = sorted(record.keys() - required - optional)
    if extra:
        issues.append("additional properties are not allowed: " + ", ".join(extra))

    reviewer = record.get("reviewer")
    if not isinstance(reviewer, dict):
        issues.append("reviewer must be an object")
        reviewer = {}
    missing_reviewer = sorted(REVIEWER_REQUIRED - reviewer.keys())
    if missing_reviewer:
        issues.append("reviewer missing required fields: " + ", ".join(missing_reviewer))
    extra_reviewer = sorted(reviewer.keys() - REVIEWER_ALLOWED)
    if extra_reviewer:
        issues.append("reviewer additional properties are not allowed: " + ", ".join(extra_reviewer))
    if not isinstance(reviewer.get("reviewer_identity_verified"), bool):
        issues.append("reviewer_identity_verified must be a boolean")
    role = reviewer.get("reviewer_role")
    if role not in REVIEWER_ROLES:
        issues.append("reviewer_role is invalid")
    for field in ("reviewer_signature_ref", "reviewer_identity_ref"):
        if field in reviewer:
            _check_nullable_string(reviewer, field, issues, field)

    status = record.get("status")
    if kind == "expert_assessment":
        _require_nonblank(record, ("review_id", "claim_id", "source_clause_id", "justification"), issues)
        if not isinstance(record.get("source_sha"), str) or not SHA256.fullmatch(record["source_sha"]):
            issues.append("source_sha must be a SHA-256 hex digest")
        if not isinstance(record.get("device_context_hash"), str) or not SHA256.fullmatch(record["device_context_hash"]):
            issues.append("device_context_hash must be a SHA-256 hex digest")
        if type(record.get("pdf_printed_page")) is not int or record["pdf_printed_page"] < 1:
            issues.append("pdf_printed_page must be a positive integer")
        if record.get("assessment_type") not in {"E2_source_entailment", "E3_applicability"}:
            issues.append("assessment_type is invalid")
        if record.get("verdict") not in {"supported", "contradicted", "unresolved"}:
            issues.append("verdict is invalid")
        if role not in EXPERT_ROLES:
            issues.append("expert assessment requires a domain expert, independent reviewer, or adjudicator")
        if status not in {"draft", "submitted", "verified", "adjudicated", "rejected"}:
            issues.append("status is invalid")
        for field in ("conflict_group_id", "adjudication_ref"):
            if field in record:
                _check_nullable_string(record, field, issues, field)
        _check_timestamp(record, "reviewed_at", issues, required=status in {"verified", "adjudicated"})
    elif kind == "site_context_confirmation":
        _require_nonblank(record, ("confirmation_id",), issues)
        if role != "site_data_confirmant":
            issues.append("site facts require reviewer_role=site_data_confirmant")
        if not isinstance(record.get("device_context_hash"), str) or not SHA256.fullmatch(record["device_context_hash"]):
            issues.append("device_context_hash must be a SHA-256 hex digest")
        for field in ("confirmed_fields", "unknown_fields"):
            values = record.get(field)
            if not isinstance(values, list) or any(not _nonblank(item) for item in values):
                issues.append(f"{field} must be an array of non-empty strings")
            elif len(values) != len(set(values)):
                issues.append(f"{field} must not contain duplicates")
        if status not in {"draft", "submitted", "verified", "rejected"}:
            issues.append("status is invalid")
        _check_timestamp(record, "confirmed_at", issues, required=status == "verified")
    else:
        _require_nonblank(record, ("attestation_id", "source_clause_id"), issues)
        for field in ("source_sha", "quote_sha"):
            if not isinstance(record.get(field), str) or not SHA256.fullmatch(record[field]):
                issues.append(f"{field} must be a SHA-256 hex digest")
        if type(record.get("pdf_printed_page")) is not int or record["pdf_printed_page"] < 1:
            issues.append("pdf_printed_page must be a positive integer")
        attestation_role = record.get("attestation_role")
        if attestation_role not in {"standard_extractor", "independent_reviewer"}:
            issues.append("attestation_role is invalid")
        if role != attestation_role:
            issues.append("extraction attestation reviewer_role must match attestation_role")
        if status not in {"draft", "submitted", "verified", "rejected"}:
            issues.append("status is invalid")
        _check_timestamp(record, "attested_at", issues, required=status == "verified")

    if status in {"verified", "adjudicated"}:
        if reviewer.get("reviewer_identity_verified") is not True:
            issues.append("verified-shaped record requires reviewer_identity_verified=true")
        signature = reviewer.get("reviewer_signature_ref")
        if not _nonblank(signature):
            issues.append("verified-shaped record requires a non-empty reviewer_signature_ref")
    if require_verified and status not in {"verified", "adjudicated"}:
        issues.append("record is not in a verified terminal review state")
    # This flag is intentionally only structural; no local boolean may authenticate a person.
    return issues


def validate_template() -> list[str]:
    try:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        template = json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"schema/template cannot be loaded: {exc}"]
    errors: list[str] = []
    if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        errors.append("schema draft declaration missing")
    if not template.get("template_only") or not template.get("notice"):
        errors.append("template must be explicitly marked template_only")
    records = template.get("records")
    if not isinstance(records, list) or len(records) != 1:
        errors.append("template must contain exactly one placeholder record")
    else:
        record = records[0]
        if validate_record(record):
            errors.append("placeholder shape failed structural validation: " + "; ".join(validate_record(record)))
        if not validate_record(record, require_verified=True):
            errors.append("placeholder unexpectedly passed the shape-only verified gate")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record", nargs="?", help="JSON file to structurally validate")
    parser.add_argument("--require-verified", action="store_true", help="check verified-shaped fields only; does NOT authenticate identity/signature or grant E2/E3/Gold")
    parser.add_argument("--check-template", action="store_true", help="check schema/template and prove unsigned placeholder is blocked")
    args = parser.parse_args()
    try:
        if args.check_template:
            issues = validate_template()
        elif args.record:
            record = json.loads(Path(args.record).read_text(encoding="utf-8"))
            issues = validate_record(record, require_verified=args.require_verified)
        else:
            parser.error("provide a JSON record or --check-template")
            return 2
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if issues:
        print("INVALID")
        for issue in issues:
            print(f"- {issue}")
        return 1
    print("P6C_SHAPE_VALID_ONLY (not authenticated, not E2/E3, not Gold)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
