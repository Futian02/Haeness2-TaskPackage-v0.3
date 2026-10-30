from __future__ import annotations

import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend import api, model_profiles
from backend.store import Store


class R2ApiContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="aetheris-r2-api-")
        self.old_store = api.store
        api.store = Store(Path(self.temp.name) / "isolated.sqlite3")
        self.client = TestClient(api.app)
        self.safe_profile = patch.object(model_profiles, "safe_profile", return_value=None)
        self.safe_profile.start()
        self.addCleanup(self.safe_profile.stop)
        self.addCleanup(self.client.close)
        self.addCleanup(self._restore_store)

    def _restore_store(self):
        api.store = self.old_store
        self.temp.cleanup()

    def _conversation(self):
        response = self.client.post("/api/conversations", json={"title": "R2 isolated"})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["id"]

    def test_health_contract_and_response_headers_identify_loaded_backend(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["contract_version"], "aetheris-r2.0.0")
        self.assertRegex(body["build_fingerprint"], r"^sha256:[0-9a-f]{64}$")
        self.assertEqual(body["build"]["source_files"], sorted(body["build"]["source_files"]))
        self.assertTrue({"runs_create", "runs_sse_stream", "runs_replay", "run_input_snapshot",
                         "model_profiles", "professional_guidance", "file_upload", "explicit_web_consent",
                         "conversation_history", "conversation_memory", "sensitive_web_consent_gate",
                         "teacher_tool_count", "run_idempotency_key"}.issubset(body["capabilities"]))
        self.assertEqual(body["capabilities"]["teacher_tool_count"], 3)
        self.assertEqual(response.headers["x-aetheris-contract-version"], body["contract_version"])
        self.assertEqual(response.headers["x-aetheris-build-fingerprint"], body["build_fingerprint"])
        self.assertNotIn("api_key", response.text.lower())

    def test_run_post_header_key_replays_same_run_without_duplicate_messages(self):
        cid = self._conversation()
        headers = {"Idempotency-Key": "r2-repeat-question-0001"}
        payload = {"question": "你好", "mode": "RULE_DEMO", "web_mode": "off"}
        first = self.client.post(f"/api/conversations/{cid}/runs", json=payload, headers=headers)
        second = self.client.post(f"/api/conversations/{cid}/runs", json=payload, headers=headers)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(first.json()["run_id"], second.json()["run_id"])
        self.assertFalse(first.json()["idempotency_replayed"])
        self.assertTrue(second.json()["idempotency_replayed"])
        self.assertEqual(self.client.get(f"/api/conversations/{cid}/runs").json()["total"], 1)
        self.assertEqual(len(api.store.messages(cid)), 1)

    def test_concurrent_same_key_is_atomic_and_cross_conversation_keys_are_scoped(self):
        cid_a, cid_b = self._conversation(), self._conversation()
        payload = {"question": "设备问题的隔离请求", "mode": "RULE_DEMO", "web_mode": "off"}
        headers = {"Idempotency-Key": "r2-concurrent-run-0001"}

        def post(cid):
            return self.client.post(f"/api/conversations/{cid}/runs", json=payload, headers=headers)

        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(post, [cid_a, cid_a]))
        self.assertTrue(all(item.status_code == 200 for item in responses), [item.text for item in responses])
        self.assertEqual(len({item.json()["run_id"] for item in responses}), 1)
        self.assertEqual(self.client.get(f"/api/conversations/{cid_a}/runs").json()["total"], 1)
        other = post(cid_b)
        self.assertEqual(other.status_code, 200, other.text)
        self.assertNotEqual(other.json()["run_id"], responses[0].json()["run_id"])

    def test_key_reuse_with_different_request_is_explicit_conflict(self):
        cid = self._conversation()
        headers = {"Idempotency-Key": "r2-conflict-question-0001"}
        first = self.client.post(f"/api/conversations/{cid}/runs", json={"question": "你好"}, headers=headers)
        conflicting = self.client.post(f"/api/conversations/{cid}/runs", json={"question": "再问一个问题"}, headers=headers)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(conflicting.status_code, 409, conflicting.text)
        self.assertEqual(conflicting.json()["detail"]["code"], "IDEMPOTENCY_KEY_REUSED")
        self.assertEqual(self.client.get(f"/api/conversations/{cid}/runs").json()["total"], 1)

    def test_run_accepts_legacy_problem_device_aliases(self):
        cid = self._conversation()
        response = self.client.post(f"/api/conversations/{cid}/runs", json={
            "problem": "你好，请解释设备概念",
            "device": "塔顶弯头",
            "mode": "RULE_DEMO",
            "web_mode": "off",
        })
        self.assertEqual(response.status_code, 200, response.text)
        snapshot = self.client.get(f"/api/runs/{response.json()['run_id']}/input").json()
        self.assertEqual(snapshot["question"], "你好，请解释设备概念")
        self.assertEqual(snapshot["context"]["equipment"], "塔顶弯头")


if __name__ == "__main__":
    unittest.main()
