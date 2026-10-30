"""Opt-in, bounded web search as an application-side resource.

This module is deliberately independent from the teacher's three-tool contract.
It does not run unless a caller explicitly opts in. Sensitive engineering queries
are rejected unless a second, explicit outbound-data opt-in is supplied.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import ipaddress
import json
import os
import re
import time
from typing import Any, Callable, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


class SearchError(RuntimeError):
    """Sanitized, stable error; never carries provider response bodies/secrets."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class JsonTransport(Protocol):
    def __call__(self, url: str, *, api_key: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]: ...


def _urllib_post_json(url: str, *, api_key: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    request = Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read(1_000_001)
    except HTTPError as exc:
        raise SearchError(f"http_{exc.code}", f"联网检索服务返回 HTTP {exc.code}") from None
    except (URLError, TimeoutError, OSError):
        raise SearchError("network_error", "联网检索服务暂时不可用") from None
    if len(raw) > 1_000_000:
        raise SearchError("response_too_large", "联网检索响应超出大小限制")
    try:
        result = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise SearchError("invalid_response", "联网检索服务响应格式无效") from None
    if not isinstance(result, dict):
        raise SearchError("invalid_response", "联网检索服务响应格式无效")
    return result


@dataclass(frozen=True)
class WebSource:
    title: str
    url: str
    retrieved_at: str
    snippet: str = ""
    summary: str = ""
    published_at: str | None = None
    site_name: str | None = None
    authority: int | None = None
    # This is an attribution boundary, not a source-validation claim.
    source_scope: str = "external_web_not_teacher_standard_authority"


@dataclass(frozen=True)
class SearchResponse:
    query: str
    sources: tuple[WebSource, ...]
    elapsed_ms: int
    provider: str = "deepseek_search_fetch"
    source_notice: str = "外部网络资料仅作参考，不是老师标准条文权威依据。"


@dataclass
class CallBudget:
    """Per-operation budget, intentionally capped to one paid request by default."""

    max_calls: int = 1
    timeout_seconds: float = 8.0
    calls_used: int = 0
    started_at: float = field(default_factory=time.monotonic)

    def __post_init__(self) -> None:
        self.max_calls = max(0, min(int(self.max_calls), 2))
        self.timeout_seconds = max(1.0, min(float(self.timeout_seconds), 20.0))

    def take(self) -> float:
        if self.calls_used >= self.max_calls:
            raise SearchError("budget_exhausted", "本轮联网调用预算已用完")
        remaining = self.timeout_seconds - (time.monotonic() - self.started_at)
        if remaining <= 0:
            raise SearchError("time_budget_exhausted", "本轮联网时间预算已用完")
        self.calls_used += 1
        return max(1.0, min(remaining, 10.0))


class DeepSeekWebSearch:
    """Thin adapter over DeepSeek's raw Search/Fetch JSON endpoints.

    The transport is injectable for offline tests. The default endpoint is pinned
    to the official host so a misconfigured URL cannot receive the bearer key.
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = "https://api.deepseek.com",
        transport: JsonTransport | None = None,
    ) -> None:
        parsed = urlparse(base_url)
        if parsed.scheme != "https" or parsed.hostname != "api.deepseek.com" or parsed.username or parsed.password:
            raise ValueError("Search endpoint must use official https://api.deepseek.com host")
        self.base_url = "https://api.deepseek.com"
        self.api_key = (api_key if api_key is not None else os.getenv("DEEPSEEK_API_KEY", "")).strip()
        self._transport = transport or _urllib_post_json

    def search(
        self,
        query: str,
        *,
        enabled: bool = False,
        sensitive: bool = False,
        allow_sensitive_outbound: bool = False,
        count: int = 5,
        budget: CallBudget | None = None,
    ) -> SearchResponse:
        self._authorize(enabled, sensitive, allow_sensitive_outbound)
        query = self._validate_query(query)
        if _needs_location(query):
            raise SearchError("location_required", "天气查询需要用户明确提供城市；不会推断或上传设备位置")
        count = max(1, min(int(count), 5))
        budget = budget or CallBudget()
        timeout = budget.take()
        payload = {"query": query, "count": count, "need_content": False}
        response = self._call("/v1/tools/search", payload, timeout)
        results = response.get("results")
        if not isinstance(results, list):
            raise SearchError("invalid_response", "联网检索服务响应格式无效")
        retrieved_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        sources: list[WebSource] = []
        for item in results[:count]:
            if not isinstance(item, dict):
                continue
            url = _valid_http_url(item.get("url"))
            if not url:
                continue
            sources.append(WebSource(
                title=_short_text(item.get("title"), 300) or url,
                url=url,
                retrieved_at=retrieved_at,
                snippet=_short_text(item.get("snippet"), 800),
                summary=_short_text(item.get("summary"), 2000),
                published_at=_short_text(item.get("date"), 80) or None,
                site_name=_short_text(item.get("site_name"), 160) or None,
                authority=_int_or_none(item.get("authority"), low=-1, high=4),
            ))
        return SearchResponse(query=query, sources=tuple(sources), elapsed_ms=round((time.monotonic() - budget.started_at) * 1000))

    def fetch(
        self,
        url: str,
        *,
        enabled: bool = False,
        sensitive: bool = False,
        allow_sensitive_outbound: bool = False,
        budget: CallBudget | None = None,
    ) -> WebSource:
        self._authorize(enabled, sensitive, allow_sensitive_outbound)
        normalized = _valid_http_url(url)
        if not normalized or len(normalized) > 8192:
            raise SearchError("invalid_url", "待抓取链接必须是有效 HTTP(S) URL")
        budget = budget or CallBudget()
        response = self._call("/v1/tools/fetch", {"url": normalized}, budget.take())
        retrieved_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        return WebSource(
            title=_short_text(response.get("title"), 300) or normalized,
            url=normalized,
            retrieved_at=retrieved_at,
            summary=_short_text(response.get("content"), 5000),
        )

    def _authorize(self, enabled: bool, sensitive: bool, allow_sensitive_outbound: bool) -> None:
        if not enabled:
            raise SearchError("opt_in_required", "联网未启用；默认保持离线")
        if sensitive and not allow_sensitive_outbound:
            raise SearchError("sensitive_data_blocked", "检测到敏感工程查询；需单独明确允许向外部搜索发送")
        if not self.api_key:
            raise SearchError("not_configured", "联网检索服务未配置")

    @staticmethod
    def _validate_query(query: str) -> str:
        if not isinstance(query, str):
            raise SearchError("invalid_query", "搜索词无效")
        query = query.strip()
        if not query or len(query) > 128:
            raise SearchError("invalid_query", "搜索词需为 1–128 个字符")
        return query

    def _call(self, path: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        try:
            result = self._transport(self.base_url + path, api_key=self.api_key, payload=payload, timeout=timeout)
        except SearchError:
            raise
        except Exception:
            # Do not leak exception strings; adapters may include request details.
            raise SearchError("provider_error", "联网检索服务调用失败") from None
        if not isinstance(result, dict):
            raise SearchError("invalid_response", "联网检索服务响应格式无效")
        return result


def _short_text(value: Any, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()[:limit]


def _int_or_none(value: Any, low: int, high: int) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        return None
    return value


def _valid_http_url(value: Any) -> str | None:
    if not isinstance(value, str) or len(value) > 8192:
        return None
    parsed = urlparse(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        return None
    host = parsed.hostname.rstrip(".").lower()
    if host in {"localhost", "localhost.localdomain"} or host.endswith((".local", ".internal", ".localhost")):
        return None
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        return None
    return value.strip()


def _needs_location(query: str) -> bool:
    """Weather search needs an explicit city; never infer location from IP/device."""
    weather_match = re.search(r"天气|气温|降雨|下雨|weather|temperature|forecast", query, re.IGNORECASE)
    if not weather_match:
        return False
    if re.search(r"(?:在|位于|城市|地区|地点)\s*[：:]?\s*[\u3400-\u9fffA-Za-z0-9·-]{2,20}", query):
        return False
    if re.search(r"\b(?:in|at)\s+[A-Za-z][A-Za-z .'-]{1,40}", query, re.IGNORECASE):
        return False
    # Chinese city names often appear as a prefix (e.g. 北京今天天气). Remove
    # generic temporal/deictic words first so “今天的天气” is not mistaken for a city.
    prefix = query[:weather_match.start()].strip()
    prefix = re.sub(r"(?:今天|明天|昨日|昨天|现在|当前|本地|这里|那边|当地|的|今天的|明天的)+$", "", prefix)
    if re.search(r"[\u3400-\u9fff]{2,8}$", prefix) or re.search(r"[A-Za-z][A-Za-z .'-]{1,40}$", prefix):
        return False
    return True


_AUTO_SEARCH_PATTERNS = re.compile(
    r"最新|最近|当前|现在|今天|明天|本周|本月|今年|实时|新闻|天气|气温|降雨|价格|报价|汇率|"
    r"政策|公告|发布|版本|官网|官方文档|发布时间|上市|更新|查一下|搜索一下|联网查|"
    r"latest|current|today|tomorrow|this week|this month|real[- ]time|news|weather|price|"
    r"exchange rate|policy|release|version|official docs|search for",
    re.IGNORECASE,
)
_LOW_VALUE_SEARCH_PATTERNS = re.compile(
    r"^(?:你好|您好|嗨|哈喽|hello|hi|hey|谢谢|多谢|晚安|早上好|晚上好|再见|拜拜|"
    r"写一首|写个故事|创作|给我一个笑话|解释一下什么是|什么是|定义一下|"
    r"帮我写(?:一个|一段|一首|个)?(?:html|svg|代码|程序|诗|故事))",
    re.IGNORECASE,
)


def should_search(mode: str, query: str, *, sensitive: bool = False) -> bool:
    """Cheap policy gate for off/auto/on; no network or location inference here.

    ``on`` means prefer an external lookup when it adds public context, not
    blindly search greetings, creative prompts, or explicit industrial cases.
    Sensitive cases are still recorded as skipped and never reach transport
    unless a separate per-run confirmation is passed to ``search``.
    """
    selected = mode if mode in {"off", "auto", "on"} else "auto"
    text = (query or "").strip()
    if selected == "off" or not text or _LOW_VALUE_SEARCH_PATTERNS.match(text):
        return False
    if sensitive and selected == "auto":
        return False
    if selected == "auto":
        return bool(_AUTO_SEARCH_PATTERNS.search(text))
    return True

