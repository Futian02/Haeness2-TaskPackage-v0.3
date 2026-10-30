import json
import os
import unittest
from unittest.mock import patch

from backend import deepseek


class _Response:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, _limit):
        return json.dumps({"choices": [{"message": {"content": "仅依据已有证据整理的回答"}}]}).encode()


class DeepSeekAdapterTests(unittest.TestCase):
    def test_report_request_is_bounded_and_excludes_attachments_and_quotes(self):
        with patch.dict(os.environ, {
            "DEEPSEEK_API_KEY": "test-secret-not-for-output",
            "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
            "DEEPSEEK_MODEL": "deepseek-flash",
        }, clear=False), patch("backend.deepseek.urlopen", return_value=_Response()) as call:
            text, elapsed = deepseek.generate_report(
                "请研判", {"status": "unresolved", "conclusion": "来源不足", "citations": [
                    {"clause_id": "c1", "content_raw": "完整条款原文不得外发", "page": 12}],
                    "hypotheses": [], "unknowns": ["壁厚"]},
                {"material": "碳钢", "medium": ["氯化氢"], "attachment_text": "不得上传"},
            )
        self.assertEqual(text, "仅依据已有证据整理的回答")
        self.assertGreaterEqual(elapsed, 0)
        request = call.call_args.args[0]
        body = json.loads(request.data.decode())
        serialized = json.dumps(body, ensure_ascii=False)
        self.assertNotIn("test-secret-not-for-output", serialized)
        self.assertNotIn("完整条款原文不得外发", serialized)
        self.assertNotIn("不得上传", serialized)
        self.assertEqual(body["model"], "deepseek-flash")
        self.assertEqual(request.full_url, "https://api.deepseek.com/chat/completions")

    def test_requires_secret_and_https_endpoint(self):
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "", "DEEPSEEK_BASE_URL": "http://localhost"}, clear=False):
            self.assertFalse(deepseek.is_configured())


if __name__ == "__main__":
    unittest.main()
