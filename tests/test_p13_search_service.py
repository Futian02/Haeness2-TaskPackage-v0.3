from __future__ import annotations

import unittest

from backend.web_search import CallBudget, DeepSeekWebSearch, SearchError, should_search


class FakeTransport:
    def __init__(self, response=None, error=None):
        self.response = response or {"results": []}
        self.error = error
        self.calls = []

    def __call__(self, url, *, api_key, payload, timeout):
        self.calls.append((url, api_key, payload, timeout))
        if self.error:
            raise self.error
        return self.response


class P13SearchServiceTests(unittest.TestCase):
    def test_addendum_web_mode_matrix_and_twenty_mock_search_cases(self):
        policy_cases = [
            ("off", "latest Python version", False, False),
            ("auto", "你好", False, False), ("auto", "写一首秋天的诗", False, False),
            ("auto", "解释一下什么是图灵机", False, False),
            ("auto", "最新 Python 版本", False, True), ("auto", "北京今天的天气", False, True),
            ("auto", "今天的天气", False, True), ("auto", "最新政策公告", False, True),
            ("auto", "最新的设备风险等级", True, False),
            ("on", "你好", False, False), ("on", "写个故事", False, False),
            ("on", "最新 DeepSeek 文档", False, True), ("on", "给我查一下当前公开汇率", False, True),
            ("on", "设备台账与腐蚀工况", True, True),
        ]
        for mode, query, sensitive, expected in policy_cases:
            with self.subTest(mode=mode, query=query):
                self.assertEqual(should_search(mode, query, sensitive=sensitive), expected)

        transport = FakeTransport({"results": [{"title": "Public source", "url": "https://example.org/item", "snippet": "s"}]})
        client = DeepSeekWebSearch("mock-key", transport=transport)
        for index in range(20):
            response = client.search(f"public test topic {index}", enabled=True, budget=CallBudget(max_calls=1))
            self.assertEqual(len(response.sources), 1)
        self.assertEqual(len(transport.calls), 20)
        self.assertTrue(all(call[0].endswith("/v1/tools/search") for call in transport.calls))

    def test_opt_in_is_off_by_default_and_sensitive_data_needs_second_opt_in(self):
        transport = FakeTransport()
        client = DeepSeekWebSearch("test-secret", transport=transport)
        with self.assertRaisesRegex(SearchError, "联网未启用") as disabled:
            client.search("public news")
        self.assertEqual(disabled.exception.code, "opt_in_required")
        with self.assertRaisesRegex(SearchError, "敏感工程") as sensitive:
            client.search("my pressure vessel corrosion data", enabled=True, sensitive=True)
        self.assertEqual(sensitive.exception.code, "sensitive_data_blocked")
        self.assertEqual(transport.calls, [])

    def test_search_records_source_metadata_and_uses_official_search_endpoint(self):
        transport = FakeTransport({"results": [
            {"title": "Reference", "url": "https://example.org/source", "snippet": "short", "summary": "summary", "date": "2026-10-28T00:00:00Z", "site_name": "Example", "authority": 3},
            {"title": "Credentials", "url": "https://user:pass@example.org/private"},
            {"title": "Bad scheme", "url": "javascript:alert(1)"},
        ]})
        client = DeepSeekWebSearch("secret", transport=transport)
        result = client.search("public topic", enabled=True, count=50)
        self.assertEqual(len(result.sources), 1)
        source = result.sources[0]
        self.assertEqual(source.title, "Reference")
        self.assertEqual(source.url, "https://example.org/source")
        self.assertTrue(source.retrieved_at.endswith("Z"))
        self.assertEqual(source.source_scope, "external_web_not_teacher_standard_authority")
        self.assertIn("不是老师标准条文权威", result.source_notice)
        self.assertEqual(transport.calls[0][0], "https://api.deepseek.com/v1/tools/search")
        self.assertEqual(transport.calls[0][1], "secret")
        self.assertEqual(transport.calls[0][2], {"query": "public topic", "count": 5, "need_content": False})
        self.assertLessEqual(transport.calls[0][3], 10)

    def test_weather_search_requires_explicit_city_without_location_inference(self):
        transport = FakeTransport()
        client = DeepSeekWebSearch("secret", transport=transport)
        with self.assertRaises(SearchError) as missing:
            client.search("今天的天气如何", enabled=True)
        self.assertEqual(missing.exception.code, "location_required")
        self.assertEqual(transport.calls, [])
        client.search("北京今天天气如何", enabled=True)
        client.search("Weather in Boston today", enabled=True)
        self.assertEqual(len(transport.calls), 2)

    def test_query_validation_and_budget_are_bounded_before_io(self):
        transport = FakeTransport()
        client = DeepSeekWebSearch("secret", transport=transport)
        for value in ("", " " * 5, "x" * 129):
            with self.subTest(value=value[:10]), self.assertRaises(SearchError) as invalid:
                client.search(value, enabled=True)
            self.assertEqual(invalid.exception.code, "invalid_query")
        budget = CallBudget(max_calls=1, timeout_seconds=1)
        client.search("one", enabled=True, budget=budget)
        with self.assertRaises(SearchError) as exhausted:
            client.search("two", enabled=True, budget=budget)
        self.assertEqual(exhausted.exception.code, "budget_exhausted")
        self.assertEqual(len(transport.calls), 1)

    def test_fetch_requires_opt_in_valid_url_and_returns_cited_metadata(self):
        transport = FakeTransport({"title": "Fetched title", "content": "Readable page body"})
        client = DeepSeekWebSearch("secret", transport=transport)
        with self.assertRaises(SearchError):
            client.fetch("file:///etc/passwd", enabled=True)
        with self.assertRaises(SearchError):
            client.fetch("http://127.0.0.1/admin", enabled=True)
        with self.assertRaises(SearchError):
            client.fetch("http://metadata.google.internal/", enabled=True)
        self.assertEqual(transport.calls, [])
        source = client.fetch("https://example.org/article", enabled=True)
        self.assertEqual(transport.calls[0][0], "https://api.deepseek.com/v1/tools/fetch")
        self.assertEqual(transport.calls[0][2], {"url": "https://example.org/article"})
        self.assertEqual(source.title, "Fetched title")
        self.assertEqual(source.summary, "Readable page body")
        self.assertTrue(source.retrieved_at.endswith("Z"))

    def test_provider_exception_is_sanitized(self):
        transport = FakeTransport(error=RuntimeError("secret-key and private query leaked"))
        client = DeepSeekWebSearch("secret", transport=transport)
        with self.assertRaises(SearchError) as failure:
            client.search("safe public topic", enabled=True)
        self.assertEqual(failure.exception.code, "provider_error")
        self.assertNotIn("secret-key", str(failure.exception))
        self.assertNotIn("private query", str(failure.exception))

    def test_endpoint_is_pinned_to_official_https_host(self):
        for url in ("http://api.deepseek.com", "https://attacker.example", "https://user:pw@api.deepseek.com"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                DeepSeekWebSearch("secret", base_url=url, transport=FakeTransport())


if __name__ == "__main__":
    unittest.main()
