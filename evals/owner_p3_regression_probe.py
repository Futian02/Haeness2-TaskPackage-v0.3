"""Owner independent P3 gap probe; uses only temporary files and in-memory mocks.
Does not modify production application, original PDF/XLSX or saved sessions.
Run with isolated .venv-langgraph: python -B -m evals.owner_p3_regression_probe
"""
from __future__ import annotations
import asyncio
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch

from backend.store import Store
from orchestration.evidence_audit import audit_claim
from orchestration.graph import RunState
from orchestration.semantics import Claim


def probe_missing_metadata():
    cid = "GBT-X-2026-7"
    canonical = {cid: {
        "clause_id": cid, "standard_code": "GB/T X-2026", "clause_no": "7",
        "page": 12, "applicable_conditions": {},
    }}
    tool = [{"tool": "standard_clause_search", "result": {"source": [
        {"clause_id": cid, "standard_code": "GB/T X-2026", "clause_no": "7"},
    ]}}]
    state = RunState("test", "c", "q", {"material": "碳钢", "medium": ["氯化氢"]}, tool_results=tool)
    claim = Claim(claim_id="c1", kind="mechanism_candidate", text="unreviewed candidate",
                  source_clause_ids=[cid]).model_dump(mode="json")
    out = audit_claim(claim, state, canonical)
    check = [x for x in out.checks if x.get("check") == "metadata:page"][0]
    print("CASE metadata_page_omitted", "grade=", out.grade, "reported=", check["status"],
          "expected_stronger_check=missing_not_matched")
    assert check["status"] == "missing" and out.grade == "E0", "missing page must fail closed"


def probe_duplicate_run_start():
    import backend.api as api
    with tempfile.TemporaryDirectory(prefix="owner-p3-probe-") as tmp:
        store = Store(Path(tmp) / "test.sqlite")
        conv = store.create_conversation("race test")
        run = store.create_run(conv["id"], "a", {"material": "碳钢", "medium": ["水"]}, "RULE_DEMO")
        executions: list[str] = []
        lock = threading.Lock()

        class FakeGraph:
            def run(self, state, emit):
                with lock:
                    executions.append(state.run_id)
                state.answer = "test answer"

        with patch.object(api, "store", store), patch.object(api, "graph", FakeGraph()):
            # Both responses are constructed while the one real run is still QUEUED.
            # StreamingResponse defers the status transition until its body is consumed.
            response1 = api.stream_run(run["id"])
            response2 = api.stream_run(run["id"])

            async def consume(resp):
                async for chunk in resp.body_iterator:
                    pass

            async def go():
                await asyncio.gather(consume(response1), consume(response2))
            asyncio.run(go())
        rows = store.messages(conv["id"])
        print("CASE same_run_two_stream_requests", "graph_executions=", len(executions),
              "assistant_messages=", len(rows), "run_id=", run["id"][:8])
        assert len(executions) == 1, "same run must be executed only once"
        assert len(rows) == 1, "same run must create a single assistant message"


def probe_default_facts_and_quote_source():
    from backend.api import RunIn
    from app.runtime import load_harness
    implicit = RunIn(question="请判断设备风险").model_dump()
    print("CASE bare_request_injected_context", {key: implicit[key] for key in ("material", "medium", "equipment_type")})
    assert implicit["material"] is None and implicit["medium"] == [] and implicit["equipment_type"] is None, "no fabricated equipment facts"
    source = load_harness().build_registry().get("standard_clause_search").func(keyword="盐酸腐蚀", top_k=2)["source"]
    fields = sorted(source[0]) if source else []
    print("CASE teacher_source_schema", fields, "contains_quote=", "content_raw" in fields)
    assert source and "content_raw" not in fields


def main():
    probe_missing_metadata()
    probe_duplicate_run_start()
    probe_default_facts_and_quote_source()
    print("OWNER_P4_REGRESSION_PROBE_PASS: all three former defects remain fixed; frozen teacher source schema unchanged")

if __name__ == "__main__":
    main()
