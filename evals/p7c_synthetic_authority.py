"""SYNTHETIC TEST ONLY. Never import from product code or register as an authority.

This memory-only mock exercises the protocol boundary. It performs no cryptography,
identity verification, qualification check, persistence, or Gold creation.
"""
from __future__ import annotations

from typing import Any

from evals.p6c_validate_review import AuthorityDecision

SYNTHETIC_ONLY = True
AUTHORITY_ID = "SYNTHETIC_TEST_ONLY_NOT_A_TRUST_PROVIDER"


class SyntheticMockAuthority:
    """A deliberately non-authenticating mock for unit tests only."""

    synthetic_only = True
    authority_id = AUTHORITY_ID

    def verify_attestation(self, record: dict[str, Any], *, evidence_bundle: dict[str, Any]) -> AuthorityDecision:
        # Tests can exercise request/response plumbing without generating a valid signature.
        if evidence_bundle.get("fixture_marker") != SYNTHETIC_ONLY:
            return {
                "authenticated": False, "reason_code": "SYNTHETIC_FIXTURE_REQUIRED",
                "verified_identity_ref": None, "signed_payload_sha256": None,
            }
        return {
            "authenticated": False, "reason_code": "SYNTHETIC_MOCK_NEVER_AUTHENTICATES",
            "verified_identity_ref": None, "signed_payload_sha256": None,
        }
