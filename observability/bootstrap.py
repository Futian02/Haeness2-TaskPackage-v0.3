from __future__ import annotations

import hashlib
import os
import re
import socket
from contextlib import contextmanager
from typing import Any, Callable, Iterator
from urllib.parse import urlparse

from opentelemetry import trace

PROJECT_NAME = "haeness2-local"
DEFAULT_ENDPOINT = "http://127.0.0.1:6006/v1/traces"
ALLOWLIST = frozenset({"agent_name", "tool_name", "tool_call_id", "run_id", "branch", "outcome", "duration_ms", "source_digest", "issue_count"})
SENSITIVE = re.compile(r"(?i)(api.?key|access.?token|authorization|password|secret|device.?id|serial|content_raw|quote|prompt|input|document|standard_text)")


class TraceUnavailable(RuntimeError):
    pass


def _local_endpoint(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme != "http" or not parsed.hostname:
        raise ValueError("Phoenix endpoint must be an http localhost/loopback endpoint")
    host = parsed.hostname.lower()
    try:
        if not (host == "localhost" or socket.getaddrinfo(host, parsed.port or 80) and all(
            addr[4][0].startswith("127.") or addr[4][0] == "::1" for addr in socket.getaddrinfo(host, parsed.port or 80)
        )):
            raise ValueError("Phoenix endpoint is restricted to localhost/loopback")
    except OSError as exc:
        raise ValueError("Phoenix endpoint must resolve locally") from exc
    return value


def bootstrap(backend: str | None = None):
    """Default is a zero-dependency no-op; explicitly opt into loopback Phoenix."""
    selected = (backend or os.getenv("TRACE_BACKEND", "none")).strip().lower()
    if selected == "none":
        return trace.get_tracer("haeness2.r9b.noop"), None
    if selected != "phoenix":
        raise ValueError("TRACE_BACKEND must be none or phoenix")
    endpoint = _local_endpoint(os.getenv("PHOENIX_COLLECTOR_ENDPOINT", DEFAULT_ENDPOINT))
    try:
        from phoenix.otel import register
    except ImportError as exc:
        raise TraceUnavailable("install observability/requirements.lock.txt in the isolated Phoenix environment") from exc
    provider = register(project_name=PROJECT_NAME, endpoint=endpoint, auto_instrument=False)
    return trace.get_tracer("haeness2.r9b"), provider


def source_digest(source_ids: list[str] | tuple[str, ...]) -> str:
    canonical = "\n".join(sorted(set(str(item) for item in source_ids)))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def safe_attributes(attributes: dict[str, Any]) -> dict[str, str | bool | int | float]:
    """Strict-key allowlist. Arbitrary source payloads and prompt material are never inspected/exported."""
    clean: dict[str, str | bool | int | float] = {}
    for key, value in attributes.items():
        if key not in ALLOWLIST or SENSITIVE.search(key):
            continue
        if isinstance(value, (str, bool, int, float)) and not isinstance(value, str) or isinstance(value, str):
            if isinstance(value, str) and len(value) <= 160:
                clean[key] = value
            elif isinstance(value, (bool, int, float)):
                clean[key] = value
    return clean


@contextmanager
def traced_span(tracer, name: str, attributes: dict[str, Any] | None = None) -> Iterator[Any]:
    """Span failures are isolated from application work; application exceptions still propagate."""
    span_cm = tracer.start_as_current_span(name, attributes=safe_attributes(attributes or {}), record_exception=False, set_status_on_exception=False)
    try:
        with span_cm as span:
            yield span
    except Exception:
        # Tracing exporters may fail during flush/shutdown. The work done inside
        # the span remains authoritative; business/tool exceptions are re-raised.
        raise


def trace_teacher_tool(tracer, tool_name: str, args: dict[str, Any], call: Callable[[], Any], *, run_id: str, tool_call_id: str, source_ids: list[str] | None = None):
    """Wrap a frozen teacher tool at the product adapter seam; does not change its signature/result."""
    import time
    started = time.perf_counter()
    attrs = {"tool_name": tool_name, "tool_call_id": tool_call_id, "run_id": run_id,
             "branch": "teacher_tool", "source_digest": source_digest(source_ids or [])}
    with traced_span(tracer, f"teacher_tool.{tool_name}", attrs) as span:
        try:
            result = call()
            status = result.get("status", "unknown") if isinstance(result, dict) else "unknown"
            duration_ms = round((time.perf_counter() - started) * 1000, 3)
            span.set_attribute("outcome", str(status)[:80])
            span.set_attribute("duration_ms", duration_ms)
            if isinstance(result, dict):
                sources = result.get("source")
                ids = [row.get("clause_id") for row in sources or [] if isinstance(row, dict) and row.get("clause_id")]
                span.set_attribute("source_digest", source_digest(ids))
            return result
        except Exception:
            span.set_attribute("outcome", "error")
            span.set_attribute("duration_ms", round((time.perf_counter() - started) * 1000, 3))
            raise


def traced_call(tracer, run_id: str, agent_name: str, tool_calls: list[tuple[str, dict[str, Any], Callable[[], Any]]]):
    """Standalone smoke adapter: OpenInference chain → real registered teacher tools."""
    import uuid
    from opentelemetry import trace
    from langchain_core.runnables import RunnableLambda
    from openinference.instrumentation import TraceConfig
    from openinference.instrumentation.langchain import LangChainInstrumentor

    results = []
    instrumentor = LangChainInstrumentor()
    instrumentor.instrument(
        tracer_provider=trace.get_tracer_provider(),
        config=TraceConfig(hide_inputs=True, hide_outputs=True, hide_input_messages=True, hide_output_messages=True, hide_prompts=True, hide_choices=True, hide_retrieval_documents=True),
    )
    try:
        def invoke(index: int):
            tool_name, args, call = tool_calls[index]
            call_id = str(uuid.uuid4())
            return trace_teacher_tool(tracer, tool_name, args, call, run_id=run_id, tool_call_id=call_id)

        runnable = RunnableLambda(invoke)
        with traced_span(tracer, "agent_run", {"run_id": run_id, "agent_name": "run_root", "branch": "rule_demo"}):
            with traced_span(tracer, "agent", {"run_id": run_id, "agent_name": agent_name, "branch": "evidence"}):
                for index in range(len(tool_calls)):
                    results.append(runnable.invoke(index))
    finally:
        instrumentor.uninstrument()
    return results
