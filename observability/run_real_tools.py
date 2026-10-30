from __future__ import annotations

import argparse
import json
import os
from uuid import uuid4

from .bootstrap import bootstrap, traced_call


def main() -> int:
    parser = argparse.ArgumentParser(description="Local Phoenix smoke test using the project's frozen teacher tools")
    parser.add_argument("--backend", choices=("none", "phoenix"), default=os.getenv("TRACE_BACKEND", "none"))
    args = parser.parse_args()
    tracer, provider = bootstrap(args.backend)

    # Read-only call through the existing frozen official registry. Never modify
    # upstream tool files/signatures and never export the tool inputs/results.
    from orchestration.graph import load_harness
    registry = load_harness().build_registry()
    invocations = [
        ("damage_mechanism_query", {"material": "碳钢", "medium": ["湿硫化氢"]}, lambda: registry.get("damage_mechanism_query").func(material="碳钢", medium=["湿硫化氢"])),
        ("standard_clause_search", {"keyword": "湿硫化氢", "top_k": 3}, lambda: registry.get("standard_clause_search").func(keyword="湿硫化氢", top_k=3)),
    ]
    results = traced_call(tracer, str(uuid4()), "evidence_agent", invocations)
    export_flushed = True
    if provider is not None:
        try:
            export_flushed = bool(provider.force_flush(timeout_millis=5000))
        except Exception:
            # Local diagnostics are best-effort and must not change tool results.
            export_flushed = False
    print(json.dumps({"backend": args.backend, "tool_count": len(results), "statuses": [r.get("status") for r in results if isinstance(r, dict)], "export_flushed": export_flushed, "trace_id": "see Phoenix localhost project" if provider else None}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
