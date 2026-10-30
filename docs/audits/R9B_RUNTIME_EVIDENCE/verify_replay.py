"""Verify the R9-B demo against persisted SQLite/SSE events without retaining payloads."""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:8000"
HERE = Path(__file__).parent


def get(path: str):
    with urllib.request.urlopen(BASE + path, timeout=30) as response:
        return response.read()


summary = json.loads((HERE / "replay_summary.json").read_text(encoding="utf-8"))
run_id = summary["run_id"]
replay = json.loads(get(f"/api/runs/{run_id}/events?after_sequence=0"))
events = replay["events"]
last_sequence = max(event["sequence"] for event in events)
cursor = last_sequence // 2
tail = json.loads(get(f"/api/runs/{run_id}/events?after_sequence={cursor}"))["events"]
sse = get(f"/api/runs/{run_id}/stream?after_sequence=0").decode("utf-8")
sse_events = [json.loads(line[6:]) for line in sse.splitlines() if line.startswith("data: ")]
types = [event["type"] for event in events]
assert len(events) == summary["event_count"]
assert len({(event["run_id"], event["sequence"]) for event in events}) == len(events)
assert all(event["run_id"] == run_id for event in events)
assert [event["sequence"] for event in events] == sorted(event["sequence"] for event in events)
assert all(event["sequence"] > cursor for event in tail)
assert len(sse_events) == len(events)
assert "tool_called" in types and "tool_result" in types and "reference_added" in types

result = {
    "status": "PASS",
    "run_id": run_id,
    "event_count": len(events),
    "sse_event_count": len(sse_events),
    "tail_after_sequence": cursor,
    "tail_event_count": len(tail),
    "last_sequence": last_sequence,
    "tool_call_count": types.count("tool_called"),
    "tool_result_count": types.count("tool_result"),
    "reference_count": types.count("reference_added"),
    "replay_source": "SQLite persisted events + SSE replay endpoint",
}
(HERE / "replay_verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(result, ensure_ascii=False, indent=2))
