from __future__ import annotations

import unittest
from importlib.util import find_spec

from observability.bootstrap import _local_endpoint, bootstrap, safe_attributes, source_digest, trace_teacher_tool, traced_span

def _has_module(name: str) -> bool:
    try:
        return find_spec(name) is not None
    except ModuleNotFoundError:
        return False


class PhoenixAdapterTests(unittest.TestCase):
    def test_none_is_default_and_is_noop(self):
        tracer, provider = bootstrap("none")
        self.assertIsNone(provider)
        with tracer.start_as_current_span("no-op"):
            pass

    def test_endpoint_is_loopback_only(self):
        self.assertEqual(_local_endpoint("http://127.0.0.1:6006/v1/traces"), "http://127.0.0.1:6006/v1/traces")
        with self.assertRaises(ValueError):
            _local_endpoint("https://127.0.0.1:6006/v1/traces")
        with self.assertRaises(ValueError):
            _local_endpoint("http://collector.example:6006/v1/traces")

    def test_allowlist_discards_unrecognized_and_secret_attributes(self):
        attrs = safe_attributes({"tool_name": "standard_clause_search", "run_id": "r1", "user_prompt": "sensitive", "device_id": "asset", "api_key": "secret", "duration_ms": 12.5, "ok": True})
        self.assertEqual(attrs, {"tool_name": "standard_clause_search", "run_id": "r1", "duration_ms": 12.5})

    @unittest.skipUnless(_has_module("opentelemetry.sdk"), "optional Phoenix SDK: run in observability/.venv")
    def test_parent_child_span_ids_and_tool_duration(self):
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor
        from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        tracer = provider.get_tracer("r9b-test")
        with traced_span(tracer, "agent_run", {"run_id": "run-1", "agent_name": "root"}):
            result = trace_teacher_tool(tracer, "standard_clause_search", {"keyword": "private text"}, lambda: {"status": "ok", "source": [{"clause_id": "CID-1"}], "content_raw": "copyright full text"}, run_id="run-1", tool_call_id="tool-1")
        self.assertEqual(result["status"], "ok")
        spans = exporter.get_finished_spans()
        self.assertEqual({span.name for span in spans}, {"agent_run", "teacher_tool.standard_clause_search"})
        by_name = {span.name: span for span in spans}
        root, child = by_name["agent_run"], by_name["teacher_tool.standard_clause_search"]
        self.assertEqual(child.context.trace_id, root.context.trace_id)
        self.assertEqual(child.parent.span_id, root.context.span_id)
        attrs = dict(child.attributes)
        self.assertIn("duration_ms", attrs)
        self.assertEqual(attrs["source_digest"], source_digest(["CID-1"]))
        serialized = repr(attrs)
        self.assertNotIn("private text", serialized)
        self.assertNotIn("copyright full text", serialized)
        provider.shutdown()

    @unittest.skipUnless(all(_has_module(name) for name in ("opentelemetry.sdk", "openinference.instrumentation", "langchain_core")), "optional Phoenix/OpenInference stack: run in observability/.venv")
    def test_openinference_langchain_spans_hide_inputs_and_outputs(self):
        from langchain_core.runnables import RunnableLambda
        from openinference.instrumentation import TraceConfig
        from openinference.instrumentation.langchain import LangChainInstrumentor
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor
        from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        instrumentor = LangChainInstrumentor()
        instrumentor.instrument(tracer_provider=provider, config=TraceConfig(hide_inputs=True, hide_outputs=True))
        try:
            runnable = RunnableLambda(lambda value: {"result": value, "private_output": "secret-output"})
            with provider.get_tracer("r9b-oi-test").start_as_current_span("agent") as parent:
                runnable.invoke("secret-input")
            spans = exporter.get_finished_spans()
        finally:
            instrumentor.uninstrument()
        oi_spans = [span for span in spans if span.name == "RunnableLambda"]
        self.assertEqual(len(oi_spans), 1)
        child = oi_spans[0]
        self.assertEqual(child.context.trace_id, parent.get_span_context().trace_id)
        self.assertEqual(child.parent.span_id, parent.get_span_context().span_id)
        attrs = repr(dict(child.attributes))
        self.assertNotIn("secret-input", attrs)
        self.assertNotIn("secret-output", attrs)
        provider.shutdown()

    @unittest.skipUnless(_has_module("opentelemetry.sdk"), "optional Phoenix SDK: run in observability/.venv")
    def test_export_failure_does_not_change_business_result(self):
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter, SpanExportResult

        class FailingExporter(SpanExporter):
            failed = 0
            def export(self, spans):
                self.failed += 1
                return SpanExportResult.FAILURE
            def shutdown(self):
                return None

        exporter = FailingExporter()
        provider = TracerProvider()
        provider.add_span_processor(BatchSpanProcessor(exporter, schedule_delay_millis=50))
        tracer = provider.get_tracer("r9b-failure-test")
        answer = trace_teacher_tool(tracer, "rbi_lookup", {"secret": "never exported"}, lambda: {"status": "ok", "result": {"count": 1}}, run_id="run-fail", tool_call_id="tool-fail")
        self.assertEqual(answer, {"status": "ok", "result": {"count": 1}})
        provider.force_flush(timeout_millis=3000)
        self.assertGreaterEqual(exporter.failed, 1)
        provider.shutdown()


if __name__ == "__main__":
    unittest.main()
