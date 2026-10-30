"""Subprocess boundary for the three read-only teacher tools.

Launch exclusively from the V2 executor's policy-validated invocation path.
No additional tools, model keys or external model clients are available here.
The parent enforces subprocess timeout and kills the worker on expiry.
"""
from __future__ import annotations

import json
import sys
from app.runtime import load_harness

ALLOWED = frozenset({"damage_mechanism_query", "rbi_lookup", "standard_clause_search"})
MAX_BYTES = 16384


def main() -> int:
    raw = sys.stdin.buffer.read(MAX_BYTES + 1)
    if not raw or len(raw) > MAX_BYTES:
        return 2
    try:
        request = json.loads(raw.decode("utf-8"))
        tool = request["tool"]
        args = request["args"]
        if tool not in ALLOWED or not isinstance(args, dict):
            return 2
        registry = load_harness().build_registry()
        if set(registry.names()) != ALLOWED:
            return 3
        response = registry.get(tool).func(**args)
        if not isinstance(response, dict):
            return 3
        sys.stdout.write(json.dumps(response, ensure_ascii=False, separators=(",", ":"), default=str))
        return 0
    except Exception:
        # Never echo tool input, source excerpts or stack traces to stdout.
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
