"""Read-only SQLite usage aggregates for the P11 local activity dashboard.

All interval endpoints are UTC instants derived from a caller-provided local
UTC offset. Archived conversations remain in history and are counted when
their runs/messages fall inside the requested period.
"""
from __future__ import annotations

import json
from datetime import datetime, time, timedelta, timezone
from typing import Any, Callable, Literal

from fastapi import APIRouter, HTTPException, Query

from backend.store import Store

Period = Literal["today", "7d", "30d"]
_PENDING_STATES = {"needs_user_input", "insufficient_evidence", "unresolved", "review_conflict", "requires_human_review"}
_TOKEN_KEYS = ("prompt_tokens", "completion_tokens", "total_tokens")


def _utc_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds")


def period_bounds(period: Period, tz_offset_minutes: int, now: datetime | None = None) -> tuple[datetime, datetime]:
    """Return [start, end) as UTC datetimes; offset is minutes east of UTC."""
    if period not in {"today", "7d", "30d"}:
        raise ValueError("period must be today, 7d, or 30d")
    if not -720 <= tz_offset_minutes <= 840:
        raise ValueError("tz_offset_minutes must be between -720 and 840")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    offset = timezone(timedelta(minutes=tz_offset_minutes))
    local_now = current.astimezone(offset)
    local_midnight = datetime.combine(local_now.date(), time.min, tzinfo=offset)
    days = {"today": 1, "7d": 7, "30d": 30}[period]
    start = local_midnight - timedelta(days=days - 1)
    end = local_midnight + timedelta(days=1)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


def _run_state(status: str, final_status: str | None) -> str:
    if status == "failed":
        return "failed"
    if status in {"queued", "running"}:
        return "running"
    if status == "completed" and final_status in _PENDING_STATES:
        return "needs_evidence"
    return "success" if status == "completed" else "other"


def _exact_usage(payload_json: str) -> dict[str, int]:
    try:
        usage = json.loads(payload_json).get("usage")
    except (json.JSONDecodeError, AttributeError, TypeError):
        return {}
    if not isinstance(usage, dict):
        return {}
    result = {}
    for key in _TOKEN_KEYS:
        value = usage.get(key)
        # bool is an int subclass but is never a provider token count.
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            result[key] = value
    return result


def get_usage_stats(store: Store, period: Period = "today", tz_offset_minutes: int = 0,
                    now: datetime | None = None) -> dict[str, Any]:
    start, end = period_bounds(period, tz_offset_minutes, now)
    start_iso, end_iso = _utc_iso(start), _utc_iso(end)
    offset_modifier = f"{'+' if tz_offset_minutes >= 0 else ''}{tz_offset_minutes} minutes"

    with store.session() as con:
        run_rows = con.execute(
            """SELECT r.id, r.conversation_id, r.status, r.mode, r.started_at, r.ended_at,
                      (SELECT e.payload_json FROM agent_events e
                       WHERE e.run_id=r.id AND e.type='run_completed'
                       ORDER BY e.sequence DESC LIMIT 1) AS terminal_payload,
                      (SELECT e.payload_json FROM agent_events e
                       WHERE e.run_id=r.id AND e.type='phase_started'
                         AND json_extract(e.payload_json, '$.phase')='route'
                       ORDER BY e.sequence LIMIT 1) AS route_payload
               FROM runs r WHERE r.started_at >= ? AND r.started_at < ?
               ORDER BY r.started_at, r.id""",
            (start_iso, end_iso),
        ).fetchall()
        message_row = con.execute(
            """SELECT COUNT(*) AS all_messages,
                      SUM(CASE WHEN role='user' THEN 1 ELSE 0 END) AS sent_messages
               FROM messages WHERE created_at >= ? AND created_at < ?""",
            (start_iso, end_iso),
        ).fetchone()
        tool_calls = con.execute(
            """SELECT COUNT(*) FROM tool_calls
               WHERE created_at >= ? AND created_at < ?""", (start_iso, end_iso)
        ).fetchone()[0]
        model_requests = con.execute(
            """SELECT COUNT(*) FROM agent_events
               WHERE created_at >= ? AND created_at < ? AND type='llm_started'""",
            (start_iso, end_iso),
        ).fetchone()[0]
        usage_rows = con.execute(
            """SELECT payload_json FROM agent_events
               WHERE created_at >= ? AND created_at < ? AND type='llm_completed'""",
            (start_iso, end_iso),
        ).fetchall()
        mode_rows = con.execute(
            """SELECT mode, COUNT(*) AS count FROM runs
               WHERE started_at >= ? AND started_at < ? GROUP BY mode ORDER BY mode""",
            (start_iso, end_iso),
        ).fetchall()
        hour_rows = con.execute(
            """SELECT CAST(strftime('%H', started_at, ?) AS INTEGER) AS hour, COUNT(*) AS count
               FROM runs WHERE started_at >= ? AND started_at < ?
               GROUP BY hour ORDER BY hour""", (offset_modifier, start_iso, end_iso),
        ).fetchall()

    task_counts: dict[str, int] = {}
    status_counts = {"success": 0, "needs_evidence": 0, "failed": 0, "running": 0, "other": 0}
    durations: list[float] = []
    for row in run_rows:
        try:
            terminal = json.loads(row["terminal_payload"] or "{}").get("status")
        except (json.JSONDecodeError, TypeError):
            terminal = None
        state = _run_state(str(row["status"]), terminal)
        status_counts[state] += 1
        try:
            route_payload = json.loads(row["route_payload"] or "{}")
            rationale = str(route_payload.get("public_rationale") or "")
            category = rationale.removeprefix("route=") if rationale.startswith("route=") else "unknown"
        except (json.JSONDecodeError, TypeError):
            category = "unknown"
        task_counts[category or "unknown"] = task_counts.get(category or "unknown", 0) + 1
        if row["ended_at"]:
            try:
                begin = datetime.fromisoformat(row["started_at"])
                finish = datetime.fromisoformat(row["ended_at"])
                durations.append(max(0.0, (finish - begin).total_seconds() * 1000))
            except (TypeError, ValueError):
                pass

    token_sums = {key: 0 for key in _TOKEN_KEYS}
    token_seen = {key: False for key in _TOKEN_KEYS}
    for row in usage_rows:
        for key, value in _exact_usage(row["payload_json"]).items():
            token_sums[key] += value
            token_seen[key] = True
    tokens = {key: token_sums[key] if token_seen[key] else None for key in _TOKEN_KEYS}
    conversation_count = len({row["conversation_id"] for row in run_rows})
    return {
        "period": period,
        "timezone_offset_minutes": tz_offset_minutes,
        "range": {"start_utc": start_iso, "end_utc_exclusive": end_iso},
        "generated_at_utc": _utc_iso(datetime.now(timezone.utc)),
        "archive_policy": "included",
        "counts": {
            "conversations": conversation_count,
            "messages_sent": int(message_row["sent_messages"] or 0),
            "messages_total": int(message_row["all_messages"] or 0),
            "runs": len(run_rows),
            "model_calls": int(model_requests),
            "tool_calls": int(tool_calls),
            "average_run_ms": round(sum(durations) / len(durations), 1) if durations else None,
        },
        "token_usage": {"availability": "recorded" if any(token_seen.values()) else "not_recorded", **tokens},
        "status_distribution": status_counts,
        "task_distribution": [{"key": key, "count": value} for key, value in sorted(task_counts.items())],
        "mode_distribution": [{"key": str(row["mode"]), "count": int(row["count"])} for row in mode_rows],
        "hourly_runs": [{"hour": int(row["hour"]), "count": int(row["count"])} for row in hour_rows if row["hour"] is not None],
    }


def create_usage_router(store_provider: Callable[[], Store]) -> APIRouter:
    """Create an isolated router; the main app owner injects its existing Store."""
    router = APIRouter()

    @router.get("/api/stats")
    def stats(period: str = Query("today", pattern="^(today|7d|30d)$"),
              tz_offset: int = Query(0, ge=-720, le=840)):
        try:
            return get_usage_stats(store_provider(), period, tz_offset)  # type: ignore[arg-type]
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    return router
