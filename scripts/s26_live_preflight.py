"""At-most-ten real DeepSeek structured Planner preflight; never auto-retries."""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from backend.model_profiles import safe_profile
from backend.real_agentic_provider import LiveStructuredPlanner
from orchestration.agentic_contracts import PlannerRequest

DATA = ROOT / "evals" / "s26" / "synthetic_cases.jsonl"
MAX_TOTAL_TOKENS = 50000
OUTPUT_CAP = 700
MAX_CALLS = 10
RATE_SECONDS = 1.1
RESERVE_TOKENS_PER_CALL = 4200  # conservative 3,500 input + 700 output
MAX_GATE0_REQUESTS = 30
STATE_PATH = ROOT / "evals" / "s26" / "preflight_budget_state.json"


def read_cases():
    return [json.loads(x) for x in DATA.read_text(encoding="utf-8").splitlines() if x.strip()]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=int, default=10, choices=range(1, 11))
    ap.add_argument("--start-index", type=int, default=0, choices=range(0, 10), help="zero-based corpus offset; use to resume a bounded preflight")
    ap.add_argument("--output", default="live_preflight.jsonl")
    args = ap.parse_args()
    profile = safe_profile()
    if not profile or not str(profile.get("endpoint", "")).startswith("https://"):
        print(json.dumps({"status": "NO_APPROVED_HTTPS_PROFILE"}))
        return 2
    cases = read_cases()[args.start_index:args.start_index + args.cases]
    if STATE_PATH.exists():
        budget_state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    else:
        accounting = json.loads((ROOT / "evals" / "s26" / "preflight_accounting.json").read_text(encoding="utf-8"))
        budget_state = {
            "requests_attempted": int(accounting["real_supplier_requests_attempted"]),
            "conservative_tokens_reserved": int(accounting["conservative_total_token_upper_bound"]),
            "source": "initialized_from_preflight_accounting.json",
        }
    if budget_state["requests_attempted"] + len(cases) > MAX_GATE0_REQUESTS or \
       budget_state["conservative_tokens_reserved"] + len(cases) * RESERVE_TOKENS_PER_CALL > MAX_TOTAL_TOKENS:
        print(json.dumps({"status": "GLOBAL_PREFLIGHT_BUDGET_STOP", "requests_attempted": budget_state["requests_attempted"],
                          "tokens_reserved": budget_state["conservative_tokens_reserved"],
                          "requested_cases": len(cases), "max_gate0_requests": MAX_GATE0_REQUESTS,
                          "max_total_tokens": MAX_TOTAL_TOKENS}, ensure_ascii=False))
        return 3
    run_id = "s26-preflight-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rows = []
    total_tokens = 0
    # Provider API implementation currently caps one adapter at six calls.
    # A second explicitly bounded adapter is used only for cases 7-10.
    planner = LiveStructuredPlanner(max_calls=min(6, len(cases)), max_output_tokens=OUTPUT_CAP, timeout_seconds=30)
    last = 0.0
    for index, case in enumerate(cases):
        if index == 6:
            planner = LiveStructuredPlanner(max_calls=min(6, len(cases)-6), max_output_tokens=OUTPUT_CAP, timeout_seconds=30)
        wait = RATE_SECONDS - (time.monotonic() - last)
        if wait > 0:
            time.sleep(wait)
        # Reserve before sending so an exception/process interruption still consumes the hard budget.
        budget_state["requests_attempted"] += 1
        budget_state["conservative_tokens_reserved"] += RESERVE_TOKENS_PER_CALL
        budget_state["last_case_id"] = case["case_id"]
        STATE_PATH.write_text(json.dumps(budget_state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        request = PlannerRequest(
            run_id=run_id, thread_id="synthetic-preflight", question=case["question"], facts=case["facts"],
            unknowns=case["unknowns"], iteration=0, previous_actions=[], candidate_source_ids=[],
            budget_remaining={"tool_attempts": 8, "investigations": 3},
        )
        started = time.perf_counter()
        try:
            reply = planner.plan(request)
            last = time.monotonic()
            payload = reply.payload
            used = reply.input_tokens + reply.output_tokens
            if total_tokens + used > MAX_TOTAL_TOKENS:
                raise RuntimeError("total token preflight budget reached after response; stop")
            total_tokens += used
            plan = payload
            row = {
                "run_id": run_id, "case_id": case["case_id"], "requested_route": case["gold_route"],
                "provider": profile.get("provider"), "model": profile.get("model"),
                "finish_reason": "stop", "usage": {"input_tokens": reply.input_tokens, "output_tokens": reply.output_tokens},
                "prompt_hash": case["prompt_sha256"],
                "response_hash": hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
                "parsed_native": True, "fail_reason": None,
                "model_tool": plan.get("tool_name"), "model_action": plan.get("action"),
                "model_arguments": plan.get("tool_arguments", {}),
                "tool_arguments_hash": hashlib.sha256(json.dumps(plan.get("tool_arguments", {}), ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
                "policy_accept": None, "source_ids": [], "latency_ms": round(reply.latency_ms),
                "fallback_used": False,
            }
        except Exception as exc:
            # Never retry/repair or count fallback. Only preserve sanitized failure class.
            last = time.monotonic()
            record = planner.request_log[-1] if planner.request_log else {}
            row = {
                "run_id": run_id, "case_id": case["case_id"], "requested_route": case["gold_route"],
                "provider": profile.get("provider"), "model": profile.get("model"),
                "finish_reason": None, "usage": record.get("usage", {}),
                "prompt_hash": case["prompt_sha256"], "response_hash": None,
                "parsed_native": False, "fail_reason": type(exc).__name__,
                "provider_status": record.get("status"), "provider_error_class": record.get("error_class"),
                "http_status": record.get("http_status"),
                "model_tool": None, "policy_accept": None, "source_ids": [],
                "latency_ms": round((time.perf_counter()-started)*1000), "fallback_used": False,
            }
            rows.append(row)
            continue
        rows.append(row)
        if total_tokens >= MAX_TOTAL_TOKENS:
            break
    output_path = ROOT / "evals" / "s26" / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    usage = [r["usage"] for r in rows if r.get("usage")]
    input_tokens = sum(int(x.get("input_tokens", 0)) for x in usage)
    output_tokens = sum(int(x.get("output_tokens", 0)) for x in usage)
    unmetered_failures = sum(r.get("parsed_native") is False for r in rows)
    # Failed calls have no usage in the current adapter's failure log. Reserve a deliberately loose
    # upper bound of 3,500 input + 700 output tokens for each such request.
    reserved_tokens = unmetered_failures * 4200
    # Conservative peak price for deepseek-flash: input cache miss $0.30/M, output $1.20/M.
    estimated_peak_usd = (input_tokens + unmetered_failures * 3500) * 0.30 / 1_000_000 + (output_tokens + unmetered_failures * 700) * 1.20 / 1_000_000
    parsed = sum(r.get("parsed_native") is True for r in rows)
    print(json.dumps({
        "run_id": run_id, "status": "PREFLIGHT_DONE" if len(rows) == args.cases else "PREFLIGHT_STOPPED",
        "requests_attempted": len(rows), "native_parsed": parsed, "fallback_success_counted": 0,
        "input_tokens": input_tokens, "output_tokens": output_tokens, "total_tokens": input_tokens+output_tokens,
        "unmetered_failed_calls": unmetered_failures, "reserved_tokens_for_failed_calls": reserved_tokens,
        "estimated_cost_usd_peak_bound": round(estimated_peak_usd, 8), "budget_tokens": MAX_TOTAL_TOKENS,
        "cumulative_budget_state": budget_state,
        "output_cap_each": OUTPUT_CAP, "timeout_seconds": 30, "rate_interval_seconds": RATE_SECONDS,
        "artifact": str(output_path), "start_index": args.start_index, "no_raw_prompts_or_keys_logged": True,
    }, ensure_ascii=False))
    return 0 if parsed == len(rows) and len(rows) == args.cases else 1


if __name__ == "__main__":
    raise SystemExit(main())
