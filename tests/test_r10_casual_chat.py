"""Focused offline tests. Never contact the configured live provider."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from backend import api, deepseek
from backend.store import Store
from orchestration.intent import classify_intent
from orchestration.r9_industrial_candidate import IndustrialCandidate


class _FakeModelResponse:
    def __enter__(self): return self
    def __exit__(self, *_args): return False
    def read(self, *_args):
        return json.dumps({"choices": [{"message": {"content": "你好！当然可以聊天。"}}]}).encode()


class CasualChatRoutingTests(unittest.TestCase):
    def test_intent_uses_sane_domains(self):
        self.assertEqual(classify_intent("你好"), "general_chat")
        self.assertEqual(classify_intent("你是什么模型"), "general_chat")
        self.assertEqual(classify_intent("你可以干什么"), "general_chat")
        self.assertEqual(classify_intent("帮我写一首关于秋天的诗"), "general_chat")
        self.assertEqual(classify_intent("GB/T 26610.3 第4.1条是什么"), "standard_lookup")
        self.assertEqual(classify_intent("GB/T 26610.3-2014 风险等级的确定 标准条款"), "standard_lookup")
        self.assertEqual(classify_intent("请依据标准判断这台设备的风险等级"), "deterministic_rbi_grade")
        self.assertEqual(classify_intent("分析碳钢管道硫化氢腐蚀机理"), "hypothesis_exploration")

    def test_general_has_no_engineering_tool_calls(self):
        result = IndustrialCandidate().run("你好", {})
        self.assertEqual(result["output"]["status"], "general_chat")
        self.assertEqual(result["output"]["tool_calls"], 0)
        self.assertFalse(result["output"]["citations"])
        self.assertNotIn("材质与介质", result["output"]["conclusion"])

    def test_provider_general_request_is_not_a_risk_prompt(self):
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY":"offline-fake", "DEEPSEEK_BASE_URL":"https://api.deepseek.com", "DEEPSEEK_MODEL":"mock-model"}):
            with patch("backend.deepseek.urlopen", return_value=_FakeModelResponse()) as request:
                answer, ms = deepseek.generate_chat("你是什么模型")
        self.assertIn("你好", answer)
        self.assertGreaterEqual(ms, 0)
        payload = json.loads(request.call_args.args[0].data.decode("utf-8"))
        self.assertEqual(payload["messages"][-1]["content"], "你是什么模型")
        self.assertNotIn("deterministic_result", json.dumps(payload))
        self.assertNotIn("材质与介质后再检索", json.dumps(payload, ensure_ascii=False))

    def test_api_chat_uses_mock_deepseek_without_tool_or_duplicate_report(self):
        with tempfile.TemporaryDirectory(prefix="aether-chat-tests-") as root:
            store = Store(Path(root) / "chat.sqlite3")
            with patch.dict(os.environ, {"APP_ENV": "development"}), \
                 patch.object(api, "store", store), \
                 patch.object(deepseek, "is_configured", return_value=True), \
                 patch.object(deepseek, "settings", return_value={"model":"offline-mock"}), \
                 patch.object(deepseek, "generate_chat", return_value=("你好，我是 Aether，很高兴见到你！", 42)) as model:
                with TestClient(api.app) as client:
                    cid = client.post("/api/conversations", json={"title":"测试普通聊天"}).json()["id"]
                    run = client.post(f"/api/conversations/{cid}/runs",
                                      json={"question":"你好", "mode":"DEEPSEEK"})
                    self.assertEqual(run.status_code, 200, run.text)
                    events = client.get(run.json()["events_url"])
                    self.assertEqual(events.status_code, 200)
                    messages = store.messages(cid)
                    self.assertEqual(len(messages), 2)
                    answer = messages[-1]["content"]
                    self.assertEqual(answer, "你好，我是 Aether，很高兴见到你！")
                    self.assertNotIn("本地确定性研判", answer)
                    self.assertNotIn("needs_user_input", answer)
                    with store.session() as con:
                        tool_count = con.execute("SELECT COUNT(*) FROM tool_calls WHERE run_id=?", (run.json()["run_id"],)).fetchone()[0]
                    self.assertEqual(tool_count, 0)
                    model.assert_called_once_with("你好")


if __name__ == "__main__":
    unittest.main()
