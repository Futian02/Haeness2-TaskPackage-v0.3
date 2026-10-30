"""Offline P13 reliability coverage; no live provider or production database."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from fastapi.testclient import TestClient

from backend import api, deepseek
from backend.web_search import SearchError, SearchResponse, WebSource
from backend.store import Store


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self): return self
    def __exit__(self, *_args): return False
    def read(self, *_args): return json.dumps(self.payload).encode("utf-8")


def _provider_response(content="ok", finish_reason="stop"):
    return _Response({"model": "returned-model-v9", "choices": [{
        "finish_reason": finish_reason,
        "message": {"content": content, "reasoning_content": "PRIVATE_REASONING_DO_NOT_STORE"},
    }], "usage": {"prompt_tokens": 123, "completion_tokens": 456, "total_tokens": 579}})


class P13DeepSeekAdapterTests(unittest.TestCase):
    def setUp(self):
        self.profile = {"api_key": "synthetic-test-key-not-real", "base_url": "https://api.deepseek.com",
                       "endpoint": "https://api.deepseek.com/chat/completions", "model": "deepseek-flash",
                       "timeout": 1.0}

    def test_chat_context_and_provider_metadata_are_bounded_and_safe(self):
        history = [{"role": "user", "content": "做个完整HTML自行车SVG"},
                   {"role": "assistant", "content": "先前可见回答"}]
        profile = {**self.profile, "_history": history,
                   "_failed_run_summary": "上次任务未完成，错误类别：provider_timeout"}
        with patch("backend.deepseek.urlopen", return_value=_provider_response()) as call:
            result = deepseek.generate_chat("请继续生成", profile)
        body = json.loads(call.call_args.args[0].data.decode("utf-8"))
        self.assertEqual(body["max_tokens"], 8192)
        self.assertEqual([m["role"] for m in body["messages"]], ["system", "user", "assistant", "system", "user"])
        self.assertIn("做个完整HTML自行车SVG", json.dumps(body, ensure_ascii=False))
        self.assertIn("请继续生成", body["messages"][-1]["content"])
        self.assertEqual(result.finish_reason, "stop")
        self.assertEqual(result.model, "returned-model-v9")
        self.assertEqual(result.usage["total_tokens"], 579)
        self.assertNotIn("PRIVATE_REASONING", result.content)
        self.assertNotIn("synthetic-test-key", json.dumps(body))

    def test_length_and_null_content_become_typed_failures(self):
        with patch("backend.deepseek.urlopen", return_value=_provider_response("部分输出", "length")):
            with self.assertRaises(deepseek.ModelGenerationError) as caught:
                deepseek.generate_chat("生成HTML", self.profile)
        self.assertEqual(caught.exception.code, "output_truncated")
        self.assertEqual(caught.exception.finish_reason, "length")
        with patch("backend.deepseek.urlopen", return_value=_provider_response(None, "stop")):
            with self.assertRaises(deepseek.ModelGenerationError) as caught:
                deepseek.generate_chat("你好", self.profile)
        self.assertEqual(caught.exception.code, "empty_response")

    def test_content_filter_is_typed_and_provider_body_is_never_exposed(self):
        with patch("backend.deepseek.urlopen", return_value=_provider_response(None, "content_filter")):
            with self.assertRaises(deepseek.ModelGenerationError) as caught:
                deepseek.generate_chat("问询", self.profile)
        self.assertEqual(caught.exception.code, "content_filtered")
        # A 429 provider response may contain a secret/echoed prompt; public error stays finite.
        from urllib.error import HTTPError
        err = HTTPError("https://api.deepseek.com", 429, "private-body", {}, None)
        safe = deepseek._provider_error(err)
        self.assertEqual(safe.code, "provider_rate_limited")
        self.assertNotIn("private-body", str(safe))

    def test_output_budget_and_optional_thinking_mode_are_bounded(self):
        with patch.dict(os.environ, {"DEEPSEEK_CHAT_MAX_TOKENS": "999999", "DEEPSEEK_THINKING_MODE": "disabled"}), \
             patch("backend.deepseek.urlopen", return_value=_provider_response()) as call:
            deepseek.generate_chat("生成SVG", self.profile)
        payload = json.loads(call.call_args.args[0].data.decode("utf-8"))
        self.assertEqual(payload["max_tokens"], 16384)
        self.assertEqual(payload["thinking"], {"type": "disabled"})

    def test_addendum_36_protocol_error_shapes_are_typed_and_sanitized(self):
        status_codes = [400, 401, 402, 429, 500] * 6
        expected = {400: "provider_request_error", 401: "provider_auth_error",
                    402: "provider_payment_required", 429: "provider_rate_limited",
                    500: "provider_unavailable"}
        for index, status in enumerate(status_codes):
            raw = f"private-body-{index}-api_key=LEAK_SENTINEL"
            error = HTTPError("https://api.deepseek.com", status, raw, {}, None)
            safe = deepseek._provider_error(error)
            with self.subTest(index=index, status=status):
                self.assertEqual(safe.code, expected[status])
                self.assertNotIn("LEAK_SENTINEL", str(safe))
        for reason in (TimeoutError("secret timeout detail"), OSError("secret disconnect detail"),
                       URLError(TimeoutError("secret url timeout")), URLError("secret network detail")):
            with patch("backend.deepseek.urlopen", side_effect=reason):
                with self.assertRaises(deepseek.ModelGenerationError) as caught:
                    deepseek.generate_chat("普通问题", self.profile)
                self.assertNotIn("secret", str(caught.exception).lower())

    def test_addendum_finish_reason_matrix_and_long_utf8_markdown_output(self):
        cases = [
            ("stop", "visible answer", None), ("length", "partial", "output_truncated"),
            ("content_filter", None, "content_filtered"), ("tool_calls", None, "empty_response"),
            ("insufficient_system_resource", "", "empty_response"), ("aborted", None, "empty_response"),
        ]
        for finish_reason, content, expected_error in cases:
            with self.subTest(finish_reason=finish_reason):
                with patch("backend.deepseek.urlopen", return_value=_provider_response(content, finish_reason)):
                    if expected_error:
                        with self.assertRaises(deepseek.ModelGenerationError) as caught:
                            deepseek.generate_chat("请输出", self.profile)
                        self.assertEqual(caught.exception.code, expected_error)
                    else:
                        result = deepseek.generate_chat("请输出", self.profile)
                        self.assertEqual(result.finish_reason, finish_reason)
        long_code = "```html\n<!-- 中文 -->\n" + ("<svg><text>车轮动画🚲</text></svg>\n" * 8192) + "```"
        with patch("backend.deepseek.urlopen", return_value=_provider_response(long_code, "stop")):
            result = deepseek.generate_chat("生成完整 HTML/SVG 代码", self.profile)
        self.assertTrue(result.content.startswith("```html"))
        self.assertIn("车轮动画🚲", result.content)
        self.assertTrue(result.content.endswith("```"))


class P13ChatHistoryAndFailureTests(unittest.TestCase):
    def test_chat_history_is_same_conversation_and_prior_messages_only(self):
        with tempfile.TemporaryDirectory(prefix="p13-history-") as temp:
            store = Store(Path(temp) / "isolated.sqlite3")
            first = store.create_conversation("first")
            other = store.create_conversation("other")
            store.add_message(first["id"], "user", "first question")
            store.add_message(first["id"], "assistant", "visible first answer")
            store.add_message(other["id"], "user", "cross-chat-secret")
            queued = store.create_run_with_message(first["id"], "current question", {}, "DEEPSEEK", [])
            history, failed = store.chat_history(first["id"], queued["id"])
            self.assertEqual([row["content"] for row in history], ["first question", "visible first answer"])
            self.assertIsNone(failed)
            self.assertNotIn("cross-chat-secret", json.dumps(history))

    def test_three_same_conversation_four_turn_replays_and_two_cross_session_isolation_cases(self):
        with tempfile.TemporaryDirectory(prefix="p13-4turn-3sessions-") as temp:
            isolated = Store(Path(temp) / "isolated.sqlite3")
            profile = {"profile_id": "mock-profile", "provider": "deepseek", "model": "mock-v1",
                       "endpoint": "https://api.deepseek.com/chat/completions", "api_key": "synthetic-not-real", "timeout": 1.0}
            graph_result = {"output": {"status": "general_chat", "conclusion": "聊天完成", "hypotheses": [], "citations": [], "tool_calls": 0}, "review_round": None}
            questions = [
                ["创建 HTML 骑自行车动画 SESSION_ALPHA", "怎么回事？", "请继续生成这段代码", "浏览器 TypeError，请修复并继续"],
                ["解释向量数据库 SESSION_BETA", "继续解释刚才的区别", "再举个例子", "把例子改成 Python"],
                ["写一个 CSS Grid 小示例 SESSION_GAMMA", "换个颜色", "继续补完整页面", "帮我解释刚才的样式"],
            ]
            answers = iter(deepseek.GenerationResult(f"VISIBLE_ANSWER_{i}", 1, "stop", {"total_tokens": 2}, "mock-v1") for i in range(12))
            with patch.dict(os.environ, {"APP_ENV": "development"}), \
                 patch.object(api, "store", isolated), patch.object(api, "graph") as graph, \
                 patch.object(api.model_profiles, "safe_profile", return_value=profile), \
                 patch.object(api.model_profiles, "resolve_snapshot", return_value=profile), \
                 patch.object(deepseek, "generate_chat", side_effect=lambda *_args, **_kwargs: next(answers)) as generate:
                graph.run.return_value = graph_result
                with TestClient(api.app) as client:
                    conversations = [client.post("/api/conversations", json={"title": f"history-{index}"}).json()["id"] for index in range(3)]
                    for cid, turns in zip(conversations, questions):
                        for question in turns:
                            created = client.post(f"/api/conversations/{cid}/runs", json={
                                "question": question, "mode": "DEEPSEEK", "web_mode": "off"}).json()
                            client.get(created["events_url"])
                self.assertEqual(generate.call_count, 12)
                profiles = [call.args[1] for call in generate.call_args_list]
                # Each conversation's 2nd, 3rd and 4th turns receive visible prior turns.
                for group_index, sentinel in enumerate(("SESSION_ALPHA", "SESSION_BETA", "SESSION_GAMMA")):
                    for turn_index in range(1, 4):
                        context = json.dumps(profiles[group_index * 4 + turn_index].get("_history", []), ensure_ascii=False)
                        self.assertIn(sentinel, context)
                # Two directed cross-session checks: other sessions' sentinels never enter history.
                alpha_history = json.dumps(profiles[1].get("_history", []), ensure_ascii=False)
                beta_history = json.dumps(profiles[5].get("_history", []), ensure_ascii=False)
                self.assertNotIn("SESSION_BETA", alpha_history)
                self.assertNotIn("SESSION_ALPHA", beta_history)
                for index in (4, 8):
                    self.assertEqual(profiles[index].get("_history", []), [])

    def test_api_failed_generation_is_persisted_as_safe_error_without_empty_assistant(self):
        with tempfile.TemporaryDirectory(prefix="p13-failed-run-") as temp:
            store = Store(Path(temp) / "isolated.sqlite3")
            profile = {"profile_id": "mock-profile", "provider": "deepseek", "model": "mock-v1",
                       "endpoint": "https://api.deepseek.com/chat/completions", "api_key": "synthetic-not-real",
                       "timeout": 1.0}
            with patch.dict(os.environ, {"APP_ENV": "development"}), \
                 patch.object(api, "store", store), \
                 patch.object(api.model_profiles, "safe_profile", return_value=profile), \
                 patch.object(api.model_profiles, "resolve_snapshot", return_value=profile), \
                 patch.object(deepseek, "generate_chat", side_effect=deepseek.ModelGenerationError("provider_timeout", "private provider body")):
                with TestClient(api.app) as client:
                    cid = client.post("/api/conversations", json={"title": "P13 offline"}).json()["id"]
                    created = client.post(f"/api/conversations/{cid}/runs", json={"question": "你好", "mode": "DEEPSEEK"}).json()
                    client.get(created["events_url"])
                    run = store.run(created["run_id"])
                    events = store.events(created["run_id"])
                    self.assertEqual(run["status"], "failed")
                    self.assertEqual(run["error_code"], "provider_timeout")
                    self.assertEqual([row["role"] for row in store.messages(cid)], ["user"])
                    error = next(event["payload"] for event in events if event["type"] == "error")
                    failed_terminal = [event for event in events if event["type"] == "run_failed"]
                    self.assertEqual(len(failed_terminal), 1)
                    self.assertEqual(failed_terminal[0]["payload"]["code"], "provider_timeout")
                    self.assertEqual(error["code"], "provider_timeout")
                    self.assertIn("重试", error["message"])
                    self.assertNotIn("private provider body", json.dumps(events))

    def test_report_wording_failure_does_not_change_local_graph_conclusion(self):
        # Exercise the adapter boundary: report errors are typed and do not
        # mutate/replace the deterministic graph output object.
        output = {"status": "needs_user_input", "conclusion": "补齐现场工况后再复核", "hypotheses": []}
        profile = {"api_key": "synthetic-test-key", "base_url": "https://api.deepseek.com",
                   "endpoint": "https://api.deepseek.com/chat/completions", "model": "mock",
                   "timeout": 1.0}
        with patch("backend.deepseek.urlopen", side_effect=TimeoutError("raw internal detail")):
            with self.assertRaises(deepseek.ModelGenerationError) as caught:
                deepseek.generate_report("研判", output, {}, profile)
        self.assertEqual(caught.exception.code, "provider_timeout")
        self.assertEqual(output["conclusion"], "补齐现场工况后再复核")

    def test_web_search_auto_mode_is_sourced_and_never_claimed_as_teacher_authority(self):
        with tempfile.TemporaryDirectory(prefix="p13-search-glue-") as temp:
            store = Store(Path(temp) / "isolated.sqlite3")
            profile = {"profile_id": "mock-profile", "provider": "deepseek", "model": "mock-v1",
                       "endpoint": "https://api.deepseek.com/chat/completions", "api_key": "synthetic-not-real",
                       "timeout": 1.0}
            graph_result = {"output": {"status": "general_chat", "conclusion": "请参考最新公开资料。",
                                        "hypotheses": [], "citations": [], "tool_calls": 0}, "review_round": None}
            source = WebSource(title="Official reference", url="https://example.org/ref", retrieved_at="2026-10-29T00:00:00Z",
                               summary="public source summary")
            result = SearchResponse(query="最新 Python 语法", sources=(source,), elapsed_ms=12)
            with patch.dict(os.environ, {"APP_ENV": "development"}), \
                 patch.object(api, "store", store), patch.object(api, "graph") as graph, \
                 patch.object(api.model_profiles, "safe_profile", return_value=profile), \
                 patch.object(api.model_profiles, "resolve_snapshot", return_value=profile), \
                 patch("backend.api.DeepSeekWebSearch.search", return_value=result) as search, \
                 patch.object(deepseek, "generate_chat", return_value=deepseek.GenerationResult("有公开参考。", 12, "stop", {"total_tokens": 4}, "mock-v1")) as generate:
                graph.run.return_value = graph_result
                with TestClient(api.app) as client:
                    cid = client.post("/api/conversations", json={"title": "P13 web"}).json()["id"]
                    created = client.post(f"/api/conversations/{cid}/runs", json={
                        "question": "最新 Python 语法", "mode": "DEEPSEEK", "web_mode": "auto"}).json()
                    snapshot = client.get(f"/api/runs/{created['run_id']}/input").json()
                    client.get(created["events_url"])
                    answer = store.messages(cid)[-1]["content"]
                    events = store.events(created["run_id"])
                search.assert_called_once()
                self.assertEqual(created["web_mode"], "auto")
                self.assertEqual(snapshot["context"]["web_mode"], "auto")
                self.assertTrue(search.call_args.kwargs["enabled"])
                self.assertFalse(search.call_args.kwargs["sensitive"])
                self.assertIn("_web_sources", generate.call_args.args[1])
                self.assertIn("https://example.org/ref", answer)
                self.assertIn("非老师标准条文权威依据", answer)
                event = next(e for e in events if e["type"] == "web_search_completed")
                self.assertEqual(event["payload"]["sources"][0]["retrieved_at"], "2026-10-29T00:00:00Z")

    def test_web_search_stays_off_by_default_and_sensitive_outbound_requires_second_opt_in(self):
        with tempfile.TemporaryDirectory(prefix="p13-search-privacy-") as temp:
            store = Store(Path(temp) / "isolated.sqlite3")
            profile = {"profile_id": "mock-profile", "provider": "deepseek", "model": "mock-v1",
                       "endpoint": "https://api.deepseek.com/chat/completions", "api_key": "synthetic-not-real",
                       "timeout": 1.0}
            graph_result = {"output": {"status": "general_chat", "conclusion": "回答", "hypotheses": [],
                                        "citations": [], "tool_calls": 0}, "review_round": None}
            with patch.dict(os.environ, {"APP_ENV": "development"}), \
                 patch.object(api, "store", store), patch.object(api, "graph") as graph, \
                 patch.object(api.model_profiles, "safe_profile", return_value=profile), \
                 patch.object(api.model_profiles, "resolve_snapshot", return_value=profile), \
                 patch("backend.api.DeepSeekWebSearch.search", side_effect=SearchError("sensitive_data_blocked", "blocked")) as search, \
                 patch.object(deepseek, "generate_chat", return_value=("答复", 3)):
                graph.run.return_value = graph_result
                with TestClient(api.app) as client:
                    cid = client.post("/api/conversations", json={}).json()["id"]
                    run_off = client.post(f"/api/conversations/{cid}/runs", json={
                        "question": "普通问候", "mode": "DEEPSEEK"}).json()
                    client.get(run_off["events_url"])
                    self.assertFalse(search.called)
                    run_blocked = client.post(f"/api/conversations/{cid}/runs", json={
                        "question": "设备腐蚀风险研判", "mode": "DEEPSEEK", "web_search_enabled": True}).json()
                    self.assertEqual(run_blocked["web_mode"], "on")
                    client.get(run_blocked["events_url"])
                    events = store.events(run_blocked["run_id"])
                # Explicit web-on is not the second, sensitive-data consent.
                # Do not even invoke the adapter for a sensitive engineering turn.
                search.assert_not_called()
                blocked = next(e for e in events if e["type"] == "web_search_skipped")
                self.assertEqual(blocked["payload"]["error_code"], "sensitive_data_blocked")
                self.assertIn("没有发出外部请求", blocked["payload"]["source_notice"])

    def test_unrelated_weather_turn_does_not_inherit_device_slots_or_send_them_to_search(self):
        with tempfile.TemporaryDirectory(prefix="p13-no-context-poison-") as temp:
            isolated = Store(Path(temp) / "isolated.sqlite3")
            conv = isolated.create_conversation("engineering then weather")
            previous = isolated.create_run_with_message(conv["id"], "分析本台管道腐蚀", {
                "material": "碳钢", "medium": ["湿硫化氢"], "equipment_type": "管道"}, "RULE_DEMO", [])
            token = "previous-worker"
            self.assertTrue(isolated.claim_run(previous["id"], token))
            self.assertTrue(isolated.finish_run_with_message(previous["id"], token, "工程上下文记录"))
            profile = {"profile_id": "mock-profile", "provider": "deepseek", "model": "mock-v1",
                       "endpoint": "https://api.deepseek.com/chat/completions", "api_key": "synthetic-not-real", "timeout": 1.0}
            graph_result = {"output": {"status": "general_chat", "conclusion": "请提供城市。", "hypotheses": [], "citations": [], "tool_calls": 0}, "review_round": None}
            location_error = SearchError("location_required", "天气查询需要用户明确提供城市；不会推断或上传设备位置")
            with patch.dict(os.environ, {"APP_ENV": "development"}), \
                 patch.object(api, "store", isolated), patch.object(api, "graph") as graph, \
                 patch.object(api.model_profiles, "safe_profile", return_value=profile), \
                 patch.object(api.model_profiles, "resolve_snapshot", return_value=profile), \
                 patch("backend.api.DeepSeekWebSearch.search", side_effect=location_error) as search, \
                 patch.object(deepseek, "generate_chat", return_value=deepseek.GenerationResult("请告诉我城市。", 2, "stop", {}, "mock-v1")):
                graph.run.return_value = graph_result
                with TestClient(api.app) as client:
                    created = client.post(f"/api/conversations/{conv['id']}/runs", json={
                        "question": "今天的天气如何", "mode": "DEEPSEEK", "web_mode": "auto"}).json()
                    client.get(created["events_url"])
                    current = isolated.run(created["run_id"])
                search.assert_called_once()
                self.assertFalse(search.call_args.kwargs["sensitive"])
                self.assertNotEqual(current["context"].get("material"), "碳钢")
                self.assertNotIn("湿硫化氢", json.dumps(current["context"], ensure_ascii=False))
                self.assertEqual(current["context"]["web_mode"], "auto")

    def test_search_http_402_429_timeout_and_location_failures_are_visible_without_silent_success(self):
        for code, message in (("http_402", "联网检索服务返回 HTTP 402"),
                              ("http_429", "联网检索服务返回 HTTP 429"),
                              ("network_error", "联网检索服务暂时不可用"),
                              ("location_required", "天气查询需要用户明确提供城市")):
            with self.subTest(code=code), tempfile.TemporaryDirectory(prefix="p13-search-degrade-") as temp:
                isolated = Store(Path(temp) / "isolated.sqlite3")
                profile = {"profile_id": "mock-profile", "provider": "deepseek", "model": "mock-v1",
                           "endpoint": "https://api.deepseek.com/chat/completions", "api_key": "synthetic-not-real", "timeout": 1.0}
                graph_result = {"output": {"status": "general_chat", "conclusion": "回答", "hypotheses": [], "citations": [], "tool_calls": 0}, "review_round": None}
                with patch.dict(os.environ, {"APP_ENV": "development"}), \
                     patch.object(api, "store", isolated), patch.object(api, "graph") as graph, \
                     patch.object(api.model_profiles, "safe_profile", return_value=profile), \
                     patch.object(api.model_profiles, "resolve_snapshot", return_value=profile), \
                     patch("backend.api.DeepSeekWebSearch.search", side_effect=SearchError(code, message)), \
                     patch.object(deepseek, "generate_chat", return_value=deepseek.GenerationResult("answer without web data", 5, "stop", {"total_tokens": 3}, "mock-v1")):
                    graph.run.return_value = graph_result
                    with TestClient(api.app) as client:
                        cid = client.post("/api/conversations", json={}).json()["id"]
                        created = client.post(f"/api/conversations/{cid}/runs", json={
                            "question": "查询最新公开资料", "mode": "DEEPSEEK", "web_mode": "on"}).json()
                        client.get(created["events_url"])
                        answer = isolated.messages(cid)[-1]["content"]
                        events = isolated.events(created["run_id"])
                        run = isolated.run(created["run_id"])
                self.assertEqual(run["status"], "completed")
                self.assertIn("联网检索状态", answer)
                self.assertIn(message, answer)
                expected_event = "web_search_skipped" if code == "location_required" else "web_search_failed"
                self.assertTrue(any(event["type"] == expected_event for event in events))


if __name__ == "__main__":
    unittest.main()
