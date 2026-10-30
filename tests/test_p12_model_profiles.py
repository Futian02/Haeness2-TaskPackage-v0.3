import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend import model_profiles


class _Response:
    def __enter__(self): return self
    def __exit__(self, *_args): return False
    def read(self, _limit):
        return json.dumps({"choices":[{"message":{"content":"OK"}}], "usage":{"prompt_tokens":3,"completion_tokens":1,"total_tokens":4}}).encode()


class P12ModelProfileTests(unittest.TestCase):
    def test_endpoint_rejects_private_and_non_allowlisted_targets(self):
        for value in ("http://api.deepseek.com", "https://127.0.0.1", "file:///etc/passwd", "https://attacker.example"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                model_profiles.validate_endpoint("deepseek", value)

    @unittest.skipUnless(os.name == "nt", "Windows DPAPI is required")
    def test_profile_credential_dpapi_roundtrip_snapshot_and_real_test_contract(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {"AETHERIS_MODEL_STORE": temp}, clear=False), \
                patch("backend.model_profiles.socket.getaddrinfo", return_value=[(2, 1, 6, "", ("8.8.8.8", 443))]):
            profile = model_profiles.save_profile(profile_id=None, provider="deepseek", model="deepseek-chat",
                endpoint="https://api.deepseek.com/v1", api_key="synthetic-test-secret-123")
            pid = profile["id"]
            self.assertNotIn("api_key", profile)
            self.assertEqual(model_profiles.list_profiles()["profiles"][0]["api_key_masked"], "••••••••")
            self.assertTrue(all(b"synthetic-test-secret-123" not in path.read_bytes() for path in Path(temp).iterdir() if path.is_file()))
            model_profiles.activate_profile(pid)
            snap = model_profiles.resolve_snapshot(pid)
            self.assertEqual(snap["model"], "deepseek-chat")
            with patch("backend.model_profiles.urlopen", return_value=_Response()) as call:
                result = model_profiles.test_connection(pid)
            self.assertTrue(result["ok"])
            self.assertEqual(result["usage"]["total_tokens"], 4)
            sent = json.loads(call.call_args.args[0].data.decode())
            self.assertEqual(sent["messages"][0]["content"], "Reply with OK.")
            self.assertNotIn("synthetic-test-secret-123", json.dumps(result))
            self.assertTrue(model_profiles.delete_profile(pid))
            self.assertIsNone(model_profiles.resolve_snapshot(pid))


if __name__ == "__main__":
    unittest.main()
