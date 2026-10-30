"""R2 QA protocol contract oracle; does not start a server or call a provider.

These checks validate the frozen integration fixture used before E/F are ready.
They are explicitly not evidence that the application API or browser passed.
"""
from __future__ import annotations

import copy
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "docs" / "audits" / "evidence" / "r2_qa" / "protocol_mock_contract.json"
CONTRACT_VERSION = "aetheris-r2.0.0"
REQUIRED_BOOLEAN_CAPABILITIES = {
    "runs_create",
    "runs_sse_stream",
    "runs_replay",
    "run_input_snapshot",
    "model_profiles",
    "professional_guidance",
    "file_upload",
    "explicit_web_consent",
    "conversation_history",
    "conversation_memory",
    "sensitive_web_consent_gate",
}
REQUIRED_RUN_FIELDS = {
    "question", "equipment", "equipment_type", "material", "medium",
    "operating_condition", "field_evidence", "mode", "web_mode",
    "web_search_enabled", "allow_sensitive_web_search", "model_profile_id",
}
FORBIDDEN_PUBLIC_KEYS = {
    "api_key", "authorization", "system_prompt", "hidden_reasoning", "raw_sse", "environment",
}


def load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def validate_health(payload: dict, expected_version: str = CONTRACT_VERSION) -> list[str]:
    errors: list[str] = []
    if payload.get("contract_version") != expected_version:
        errors.append("contract_version_mismatch")
    fingerprint = payload.get("build_fingerprint")
    if not isinstance(fingerprint, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", fingerprint):
        errors.append("build_fingerprint_invalid")
    build = payload.get("build")
    if not isinstance(build, dict) or not isinstance(build.get("source_files"), list) or not isinstance(build.get("source_manifest"), dict):
        errors.append("build_manifest_missing")
    elif set(build["source_files"]) != set(build["source_manifest"]):
        errors.append("build_manifest_path_mismatch")
    elif any(not re.fullmatch(r"[0-9a-f]{64}", str(value)) for value in build["source_manifest"].values()):
        errors.append("build_manifest_hash_invalid")
    caps = payload.get("capabilities")
    if not isinstance(caps, dict):
        errors.append("capabilities_missing")
        return errors
    missing = REQUIRED_BOOLEAN_CAPABILITIES.difference(caps)
    if missing:
        errors.append("capabilities_missing:" + ",".join(sorted(missing)))
    for key in REQUIRED_BOOLEAN_CAPABILITIES.intersection(caps):
        if not isinstance(caps[key], bool):
            errors.append(f"capability_not_boolean:{key}")
    if caps.get("teacher_tool_count") != 3:
        errors.append("teacher_tool_count_must_be_3")
    return errors


def public_event_leaks(event: dict) -> set[str]:
    """Recursively find forbidden internal/secret keys in a public event payload."""
    leaks: set[str] = set()
    def visit(value: object) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if str(key).lower() in FORBIDDEN_PUBLIC_KEYS:
                    leaks.add(str(key).lower())
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
    visit(event)
    return leaks


class R2ProtocolMockContractTests(unittest.TestCase):
    def test_fixture_declares_shared_version_capabilities_and_source_fingerprint(self):
        fixture = load_fixture()
        self.assertEqual([], validate_health(fixture))

    def test_health_oracle_catches_legacy_or_partial_backend(self):
        fixture = load_fixture()
        legacy = copy.deepcopy(fixture)
        legacy.pop("contract_version")
        legacy["capabilities"].pop("runs_replay")
        errors = validate_health(legacy)
        self.assertIn("contract_version_mismatch", errors)
        self.assertTrue(any(error.startswith("capabilities_missing:") for error in errors))

    def test_health_oracle_rejects_bad_fingerprint_and_teacher_tool_drift(self):
        fixture = load_fixture()
        fixture["build_fingerprint"] = "not-a-source-hash"
        fixture["capabilities"]["teacher_tool_count"] = 4
        fixture["build"]["source_manifest"].pop("backend/store.py")
        errors = validate_health(fixture)
        self.assertIn("build_fingerprint_invalid", errors)
        self.assertIn("teacher_tool_count_must_be_3", errors)
        self.assertIn("build_manifest_path_mismatch", errors)

    def test_run_fixture_preserves_frontend_input_contract(self):
        fields = set(load_fixture()["run_input_fields"])
        self.assertEqual(REQUIRED_RUN_FIELDS, fields)

    def test_idempotency_contract_reuses_same_run_and_conflicts_on_changed_body(self):
        contract = load_fixture()["run_create"]
        self.assertEqual("Idempotency-Key", contract["idempotency_header"])
        self.assertEqual("same_run_id", contract["repeat_same_key_same_body"])
        self.assertEqual("409_idempotency_conflict", contract["repeat_same_key_different_body"])

    def test_sse_recovery_uses_exclusive_after_sequence_cursor(self):
        contract = load_fixture()["replay"]
        self.assertEqual(["run_id", "sequence"], contract["event_identity"])
        self.assertTrue(contract["after_sequence_is_exclusive"])
        interrupted = [{"run_id": "run-a", "sequence": 1}, {"run_id": "run-a", "sequence": 2}]
        resumed = [{"run_id": "run-a", "sequence": 2}, {"run_id": "run-a", "sequence": 3}]
        unique = {(event["run_id"], event["sequence"]): event for event in interrupted + resumed}
        self.assertEqual([1, 2, 3], sorted(sequence for run, sequence in unique if run == "run-a"))

    def test_replay_contract_deduplicates_by_run_and_sequence_not_payload(self):
        events = [
            {"run_id": "run-a", "sequence": 1, "type": "run_started"},
            {"run_id": "run-a", "sequence": 2, "type": "assistant_delta", "payload": {"text": "候"}},
            {"run_id": "run-a", "sequence": 2, "type": "assistant_delta", "payload": {"text": "候"}},
            {"run_id": "run-b", "sequence": 1, "type": "run_started"},
        ]
        unique = {(event["run_id"], event["sequence"]): event for event in events}
        self.assertEqual(3, len(unique))
        self.assertEqual(2, unique[("run-a", 2)]["sequence"])

    def test_public_event_contract_rejects_secret_raw_sse_and_hidden_reasoning(self):
        event = {
            "run_id": "run-a", "sequence": 4, "type": "tool_completed",
            "payload": {"tool": "standard_clause_search", "api_key": "secret", "trace": {"raw_sse": "data:..."}},
        }
        self.assertEqual({"api_key", "raw_sse"}, public_event_leaks(event))
        safe = {"run_id": "run-a", "sequence": 4, "type": "reference_added", "payload": {"clause_id": "E0"}}
        self.assertEqual(set(), public_event_leaks(safe))

    def test_http_failure_mapping_is_explicit_and_retryable_only_for_backpressure(self):
        classes = load_fixture()["http_error_classes"]
        self.assertEqual("request_contract_error", classes["422"])
        self.assertEqual("backpressure_retryable", classes["429"])
        self.assertEqual("server_or_provider_failure", classes["5xx"])
        self.assertNotEqual(classes["422"], classes["429"])


if __name__ == "__main__":
    unittest.main()
