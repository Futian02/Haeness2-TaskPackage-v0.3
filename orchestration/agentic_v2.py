"""Isolated, model-led Aetheris V2 investigation candidate (S1-B).

The graph accepts an injected structured planner and exactly the three frozen
teacher tools. It is intentionally not wired into the R9/default runtime.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import dataclass, field
import hashlib
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Annotated, Any, Callable, TypedDict
from uuid import uuid4

from pydantic import ValidationError

from backend.agentic_provider import ScriptedFakePlanner, StructuredPlanner
from orchestration.agentic_contracts import (
    DamageQueryArgs, PlanProposal, PlannerRequest, RbiLookupArgs,
    ReflectProposal, ReflectionRequest, StandardSearchArgs,
)

ROOT = Path(__file__).resolve().parents[1]
CLAUSES_PATH = ROOT / "upstream" / "05_提交区" / "clauses.jsonl"
ENUMS_PATH = ROOT / "upstream" / "04_接口文档" / "enums.json"
TEACHER_TOOLS = ("damage_mechanism_query", "rbi_lookup", "standard_clause_search")
MAX_TOOL_ATTEMPTS = 8
MAX_INVESTIGATIONS = 3
MAX_REVIEW_RETRIES = 2
MAX_PROVIDER_CALLS = 12
MAX_PROVIDER_TOKENS = 12_000
MAX_WALL_SECONDS = 30.0
TOOL_TIMEOUT_SECONDS = 5.0


def _sha(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


def _load_jsonl(path: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                row = json.loads(line)
                if isinstance(row.get("clause_id"), str):
                    rows[row["clause_id"]] = row
    return rows


def _default_registry() -> dict[str, Callable[..., Any]]:
    from app.runtime import load_harness
    registry = load_harness().build_registry()
    names = set(registry.names())
    if names != set(TEACHER_TOOLS):
        raise RuntimeError(f"teacher tool registry mismatch: {sorted(names)}")
    return {name: registry.get(name).func for name in TEACHER_TOOLS}


def _canonical_enum_sets(path: Path) -> dict[str, set[str]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {key: set(raw.get(key, {})) for key in ("material", "medium", "equipment_type")}


class State(TypedDict, total=False):
    run_id: str
    thread_id: str
    subtask_id: str
    question: str
    caller_context: dict[str, Any]
    facts: dict[str, Any]
    unknowns: list[str]
    plan: dict[str, Any]
    policy_decision: str
    reflection_continue: bool
    review_status: str
    iteration: int
    tool_attempts: int
    provider_calls: int
    provider_tokens: int
    provider_call_log: Annotated[list[dict[str, Any]], list.__add__]
    tool_log: Annotated[list[dict[str, Any]], list.__add__]
    evidence: dict[str, dict[str, Any]]
    evidence_summary: list[dict[str, Any]]
    errors: Annotated[list[str], list.__add__]
    events: Annotated[list[dict[str, Any]], list.__add__]
    action_key: str
    action_result: dict[str, Any]
    action_error: str
    candidate_conditions: list[dict[str, Any]]
    auditor: dict[str, Any]
    skeptic: dict[str, Any]
    review_retries: int
    review_feedback: str
    review_conflict: bool
    retry_requested: bool
    review_gate_decision: str
    finish_reason: str
    output: dict[str, Any]
    started_at: float


@dataclass
class ReplayLedger:
    """Thread-safe per-instance replay cache. Cache keys include thread/run IDs."""
    values: dict[tuple[str, str, str], dict[str, Any]] = field(default_factory=dict)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def get_or_execute(self, thread_id: str, run_id: str, digest: str,
                       action: Callable[[], dict[str, Any]]) -> tuple[dict[str, Any], bool]:
        key = (thread_id, run_id, digest)
        with self.lock:
            if key in self.values:
                return self.values[key], True
            result = action()
            self.values[key] = result
            return result, False


class AgenticV2Candidate:
    def __init__(self, *, planner: StructuredPlanner | None = None,
                 tool_registry: dict[str, Callable[..., Any]] | None = None,
                 clause_index: dict[str, dict[str, Any]] | None = None,
                 enum_sets: dict[str, set[str]] | None = None,
                 replay_ledger: ReplayLedger | None = None,
                 auditor: Callable[[State], dict[str, Any]] | None = None,
                 skeptic: Callable[[State], dict[str, Any]] | None = None,
                 tool_timeout_seconds: float = TOOL_TIMEOUT_SECONDS,
                 wall_seconds: float = MAX_WALL_SECONDS,
                 checkpointer: Any | None = None):
        self.planner = planner or ScriptedFakePlanner()
        # Only the frozen on-disk registry is run in a killable subprocess.
        # Injected test doubles keep their explicit in-process isolation.
        self._isolated_teacher_boundary = tool_registry is None
        self.tools = tool_registry if tool_registry is not None else _default_registry()
        if set(self.tools) != set(TEACHER_TOOLS):
            raise ValueError(f"exactly the three frozen tools required: {TEACHER_TOOLS}")
        self.clauses = clause_index if clause_index is not None else _load_jsonl(CLAUSES_PATH)
        self.corpus_sha256 = hashlib.sha256(CLAUSES_PATH.read_bytes()).hexdigest() if clause_index is None else _sha(list(clause_index.values()))
        self.enum_sets = enum_sets if enum_sets is not None else _canonical_enum_sets(ENUMS_PATH)
        self.replay = replay_ledger or ReplayLedger()
        self.auditor_fn = auditor
        self.skeptic_fn = skeptic
        self.tool_timeout_seconds = tool_timeout_seconds
        self.wall_seconds = wall_seconds
        self.checkpointer = checkpointer
        self.graph = self._build()

    def _build(self):
        from langgraph.graph import END, START, StateGraph
        graph = StateGraph(State)
        for name, fn in (("prepare_case", self._prepare), ("model_plan", self._plan),
                         ("policy_validate", self._policy), ("execute_tool", self._execute),
                         ("source_ground", self._ground), ("candidate_conditions", self._conditions),
                         ("reflect", self._reflect), ("review_dispatch", self._review_dispatch),
                         ("auditor", self._auditor),
                         ("skeptic", self._skeptic), ("merge_reviews", self._merge),
                         ("review_gate", self._review_gate), ("claim_gate", self._claim_gate), ("report", self._report)):
            graph.add_node(name, fn)
        graph.add_edge(START, "prepare_case")
        graph.add_edge("prepare_case", "model_plan")
        graph.add_edge("model_plan", "policy_validate")
        graph.add_conditional_edges("policy_validate", self._after_policy,
                                   {"execute_tool": "execute_tool", "review": "review_dispatch", "report": "report"})
        graph.add_edge("execute_tool", "source_ground")
        graph.add_edge("source_ground", "candidate_conditions")
        graph.add_edge("candidate_conditions", "reflect")
        graph.add_conditional_edges("reflect", self._after_reflect,
                                   {"plan": "model_plan", "review": "review_dispatch", "report": "report"})
        graph.add_edge("review_dispatch", "auditor")
        graph.add_edge("review_dispatch", "skeptic")
        graph.add_edge(["auditor", "skeptic"], "merge_reviews")
        graph.add_edge("merge_reviews", "review_gate")
        graph.add_conditional_edges("review_gate", self._after_review,
                                    {"plan": "model_plan", "claim_gate": "claim_gate"})
        graph.add_edge("claim_gate", "report")
        graph.add_edge("report", END)
        return graph.compile(checkpointer=self.checkpointer)

    @staticmethod
    def _evt(s: State, kind: str, node: str, **fields: Any) -> dict[str, Any]:
        fields.setdefault("public_rationale", f"{node}按候选图的可审计职责推进")
        return {"run_id": s["run_id"], "thread_id": s["thread_id"], "kind": kind,
                "node": node, "at_monotonic": round(time.monotonic(), 6), **fields}

    def _prepare(self, s: State) -> dict[str, Any]:
        context = dict(s.get("caller_context") or {})
        facts: dict[str, Any] = {}
        for key in ("material", "medium", "temperature_c", "pressure_mpa", "equipment_type", "service_years", "evidence"):
            value = context.get(key)
            if value is not None and value != "":
                facts[key] = value
        # Only caller-provided facts are observed. Inbound citations/source IDs are ignored.
        unknowns = [f for f in ("material", "medium", "temperature_c", "pressure_mpa", "equipment_type") if f not in facts]
        return {"facts": facts, "unknowns": unknowns, "iteration": 0, "tool_attempts": 0,
                "provider_calls": 0, "provider_tokens": 0, "provider_call_log": [], "tool_log": [],
                "evidence": {}, "evidence_summary": [], "errors": [], "events": [],
                "review_retries": 0, "finish_reason": "", "candidate_conditions": [],
                "events": [self._evt(s, "case_prepared", "prepare_case", public_rationale="保留显式输入，缺失工况设为未知")],
                "started_at": time.monotonic()}

    def _plan(self, s: State) -> dict[str, Any]:
        real_call_limit = getattr(self.planner, "max_calls", None)
        real_call_count = getattr(self.planner, "calls", None)
        provider_exhausted = (
            s["provider_calls"] >= MAX_PROVIDER_CALLS
            or s["provider_tokens"] >= MAX_PROVIDER_TOKENS
            or (isinstance(real_call_limit, int) and isinstance(real_call_count, int)
                and real_call_count >= real_call_limit)
        )
        wall_exhausted = time.monotonic() - s["started_at"] > self.wall_seconds
        if provider_exhausted or wall_exhausted:
            reason = "provider_budget_exhausted" if provider_exhausted else "wall_budget_exhausted"
            return {"plan": {"action":"finish", "tool_name":"", "tool_arguments":{},
                             "query":"", "investigation_goal":"本轮达到有界执行预算",
                             "evidence_gap":"待后续有权限的调查继续", "public_rationale":"本轮预算用尽，保留已取得的来源与未知项。",
                             "focus_clause_ids":[]},
                    "finish_reason": reason, "errors":[reason],
                    "events":[self._evt(s,"execution_budget_reached","model_plan",
                             public_rationale="模型请求或执行时间预算用尽，未再次发送请求")]}
        req = PlannerRequest(run_id=s["run_id"], thread_id=s["thread_id"], question=s["question"], facts=s["facts"],
                             unknowns=s["unknowns"], iteration=s["iteration"],
                             previous_actions=[{"tool": x["tool"], "status": x["status"]} for x in s["tool_log"]],
                             candidate_source_ids=list(s["evidence"]),
                             candidate_summaries=s["candidate_conditions"][:20],
                             review_feedback=s.get("review_feedback", ""),
                             budget_remaining={"tool_attempts": MAX_TOOL_ATTEMPTS-s["tool_attempts"],
                                               "investigations": MAX_INVESTIGATIONS-s["iteration"]})
        try:
            reply = self.planner.plan(req)
            payload = reply.payload
            parsed = PlanProposal.model_validate(payload).model_dump(mode="json")
            meta = {"kind": "plan", "provider": reply.provider_name, "input_tokens": reply.input_tokens,
                    "output_tokens": reply.output_tokens, "latency_ms": reply.latency_ms}
            return {"plan": parsed, "provider_calls": s["provider_calls"]+1,
                    "provider_tokens": s["provider_tokens"]+reply.input_tokens+reply.output_tokens,
                    "provider_call_log": [meta], "events": [self._evt(s, "plan_proposed", "model_plan",
                    public_rationale=parsed["public_rationale"], tool_name=parsed["tool_name"])]}
        except Exception as exc:
            return {"plan": {"action": "finish", "tool_name": "", "tool_arguments": {},
                             "query": "", "investigation_goal": "无法生成有效计划", "evidence_gap": "",
                             "public_rationale": "结构化计划失败，停止本轮工具调用", "focus_clause_ids": []},
                    "provider_calls": s["provider_calls"]+1, "errors": [f"planner error: {type(exc).__name__}: {exc}"],
                    "finish_reason": "planner_error", "events": [self._evt(s, "planner_error", "model_plan", error=str(exc)[:300])]}

    def _policy(self, s: State) -> dict[str, Any]:
        p = s["plan"]
        if p["action"] == "finish":
            return {"finish_reason": s.get("finish_reason") or "planner_finished", "policy_decision": "review"}
        tool = p["tool_name"]
        if tool not in TEACHER_TOOLS:
            return self._reject(s, "tool not in frozen teacher allowlist")
        try:
            if tool == "standard_clause_search":
                args = StandardSearchArgs.model_validate(p["tool_arguments"]).model_dump(exclude_none=True)
            elif tool == "damage_mechanism_query":
                args = DamageQueryArgs.model_validate(p["tool_arguments"]).model_dump(exclude_none=True)
                if "material" not in s["facts"] or "medium" not in s["facts"]:
                    return self._search_route(s, "damage query lacks explicit material or medium; use text retrieval")
                if args.get("material") != s["facts"].get("material") or args.get("medium") != s["facts"].get("medium"):
                    return self._reject(s, "model may not alter material/medium facts")
                if args["material"] not in self.enum_sets["material"] or any(v not in self.enum_sets["medium"] for v in args["medium"]):
                    return self._search_route(s, "noncanonical material/medium; no alias inference, use text retrieval")
                for k in ("temperature_c", "equipment_type", "evidence"):
                    if k in args and args[k] != s["facts"].get(k):
                        return self._reject(s, f"model may not synthesize {k}")
                if args.get("equipment_type") and args["equipment_type"] not in self.enum_sets["equipment_type"]:
                    return self._search_route(s, "noncanonical equipment_type; use text retrieval")
            else:
                args = RbiLookupArgs.model_validate(p["tool_arguments"]).model_dump(exclude_none=True)
                for k in ("material", "equipment_type"):
                    if args.get(k) != s["facts"].get(k) or not args.get(k):
                        return self._search_route(s, f"RBI lookup lacks explicit {k}; use source search and keep grade null")
                if args["material"] not in self.enum_sets["material"] or args["equipment_type"] not in self.enum_sets["equipment_type"]:
                    return self._search_route(s, "noncanonical RBI enum; use text retrieval")
                for k in ("medium", "temperature_c", "pressure_mpa", "service_years"):
                    if k in args and args[k] != s["facts"].get(k):
                        return self._reject(s, f"model may not synthesize {k}")
                # Lookup is observational only. It never yields a released risk grade in this candidate.
            if tool == "standard_clause_search":
                if not p["query"] or args["keyword"] != p["query"]:
                    return self._reject(s, "standard search keyword must equal the model's explicit rewritten query")
                if p["focus_clause_ids"]:
                    return self._reject(s, "model-supplied source IDs are not accepted")
            if s["iteration"] >= MAX_INVESTIGATIONS or s["tool_attempts"] >= MAX_TOOL_ATTEMPTS:
                return {"finish_reason": "tool_budget_exhausted", "policy_decision": "report"}
            digest = _sha({"tool": tool, "args": args})
            return {"action_key": digest, "plan": {**p, "tool_arguments": args},
                    "policy_decision": "execute_tool", "events": [self._evt(s, "policy_allowed", "policy_validate", tool_name=tool)]}
        except (ValidationError, TypeError, ValueError) as exc:
            return self._reject(s, f"tool argument schema rejected: {exc}")

    def _reject(self, s: State, reason: str) -> dict[str, Any]:
        return {"errors": [reason], "finish_reason": "policy_rejected", "policy_decision": "review",
                "events": [self._evt(s, "policy_rejected", "policy_validate", error=reason[:300])]}

    def _search_route(self, s: State, reason: str) -> dict[str, Any]:
        keyword = (s["plan"].get("query") or s["question"]).strip()[:600]
        if not keyword:
            return self._reject(s, f"cannot build safe text search: {reason}")
        args = {"keyword": keyword, "knowledge_type": "damage_mechanism", "top_k": 8}
        p = {**s["plan"], "tool_name": "standard_clause_search", "tool_arguments": args, "query": keyword}
        return {"plan": p, "action_key": _sha({"tool": p["tool_name"], "args": args}),
                "policy_decision": "execute_tool", "events": [self._evt(s, "policy_rerouted_to_search", "policy_validate",
                    reason=reason, tool_name="standard_clause_search", public_rationale="非规范条件转为文本检索，不做枚举猜测或自动归一化") ]}

    @staticmethod
    def _after_policy(s: State) -> str:
        return s.get("policy_decision", "report")

    def _execute(self, s: State) -> dict[str, Any]:
        p = s["plan"]
        tool, args = p["tool_name"], p["tool_arguments"]
        attempts = s["tool_attempts"]
        remaining = MAX_TOOL_ATTEMPTS - attempts
        if hasattr(self.replay, "execute_tool"):
            cached, replayed, extra_attempts = self.replay.execute_tool(
                conversation_id=s["thread_id"], run_id=s["run_id"],
                subtask_id=s.get("subtask_id", "engineering"),
                step_id=f"tool:{s['iteration'] + 1}", tool_name=tool, args=args,
                action=lambda: self._invoke(tool, args, max_attempts=1),
                max_attempts=max(1, min(2, remaining)),
            )
        else:
            cached, replayed = self.replay.get_or_execute(s["thread_id"], s["run_id"], s["action_key"],
                lambda: self._invoke(tool, args, max_attempts=min(2, remaining)))
            extra_attempts = 0 if replayed else int(cached.get("attempts", 1))
        row = {"tool": tool, "arguments": args, "status": cached.get("status", "error"),
               "attempts": extra_attempts, "replayed": replayed, "result": cached.get("envelope"),
               "error": cached.get("error", ""), "action_key": s["action_key"]}
        return {"action_result": cached, "tool_attempts": attempts + extra_attempts,
                # A replay is not a new tool attempt, but it is still an
                # investigation decision and must consume the investigation cap.
                "iteration": s["iteration"] + 1, "tool_log": [row],
                "events": [self._evt(s, "tool_replayed" if replayed else "tool_completed", "execute_tool",
                                     tool_name=tool, status=row["status"], attempts=extra_attempts,
                                     public_tool_summary=f"{tool}: {row['status']}, {extra_attempts} actual attempt(s)",
                                     public_rationale="仅执行通过策略校验的只读教师工具") ]}

    def _invoke(self, tool: str, args: dict[str, Any], *, max_attempts: int = 2) -> dict[str, Any]:
        if self._isolated_teacher_boundary:
            return self._invoke_subprocess(tool, args, max_attempts=max_attempts)
        attempts = 0
        last_error = ""
        while attempts < max_attempts:
            attempts += 1
            pool = ThreadPoolExecutor(max_workers=1)
            future = pool.submit(self.tools[tool], **args)
            try:
                envelope = future.result(timeout=self.tool_timeout_seconds)
                pool.shutdown(wait=False, cancel_futures=True)
                return {"status": "returned", "envelope": envelope, "attempts": attempts}
            except FutureTimeout:
                future.cancel(); pool.shutdown(wait=False, cancel_futures=True)
                last_error = "tool timeout"
            except Exception as exc:
                pool.shutdown(wait=False, cancel_futures=True)
                last_error = f"{type(exc).__name__}: {exc}"
        return {"status": "error", "envelope": None, "attempts": attempts, "error": last_error[:300]}

    def _invoke_subprocess(self, tool: str, args: dict[str, Any], *, max_attempts: int) -> dict[str, Any]:
        """Hard timeout for the frozen read-only teacher tools: kill the child.

        This is distinct from Future.cancel(), which cannot stop a running
        thread. No API keys, provider clients, or editable teacher data are
        passed to the child. Do not use this to execute arbitrary model tools.
        """
        if tool not in TEACHER_TOOLS:
            return {"status": "error", "envelope": None, "attempts": 0, "error": "tool not authorized"}
        payload = json.dumps({"tool": tool, "args": args}, ensure_ascii=False)
        if len(payload.encode("utf-8")) > 16_384:
            return {"status": "error", "envelope": None, "attempts": 0, "error": "tool arguments exceed process input budget"}
        last_error = ""
        # Explicit env allowlist: never inherit model API keys, credentials or
        # arbitrary connector tokens into a read-only teacher-tool subprocess.
        safe_vars = {"SystemRoot", "SYSTEMROOT", "WINDIR", "PATH", "TEMP", "TMP", "PYTHONUTF8", "PYTHONIOENCODING"}
        isolated_env = {name: value for name, value in os.environ.items() if name in safe_vars}
        for attempt in range(1, max_attempts + 1):
            try:
                proc = subprocess.run([sys.executable, "-B", "-m", "orchestration.isolated_teacher_tool"],
                                      input=payload, capture_output=True, text=True,
                                      encoding="utf-8", timeout=self.tool_timeout_seconds,
                                      cwd=str(ROOT), env=isolated_env, check=False)
                if proc.returncode != 0:
                    last_error = f"isolated tool exit code {proc.returncode}"
                    continue
                if len(proc.stdout) > 1_000_000:
                    last_error = "isolated tool output exceeded size limit"
                    continue
                envelope = json.loads(proc.stdout)
                if not isinstance(envelope, dict):
                    last_error = "isolated tool returned a non-object"
                    continue
                return {"status": "returned", "envelope": envelope, "attempts": attempt}
            except subprocess.TimeoutExpired:
                last_error = "isolated tool deadline exceeded; child terminated"
            except (OSError, ValueError, json.JSONDecodeError):
                last_error = "isolated tool protocol failure"
        return {"status": "error", "envelope": None, "attempts": max_attempts, "error": last_error}

    def _ground(self, s: State) -> dict[str, Any]:
        result = s.get("action_result") or {}
        if result.get("status") == "error":
            return {"errors": [f"tool failed: {result.get('error', 'unknown') }"], "evidence_summary": [{"status": "error", "source_ids": []}],
                    "finish_reason": "tool_error"}
        env = result.get("envelope")
        if not isinstance(env, dict) or set(env) != {"status", "in_domain", "result", "source", "message"}:
            return self._ground_error("tool envelope must contain exactly five frozen fields")
        if env["status"] not in {"ok", "out_of_domain", "not_found", "error"} or not isinstance(env["in_domain"], bool) or not isinstance(env["source"], list):
            return self._ground_error("invalid tool envelope field types")
        if env["status"] == "ok" and not env["source"]:
            return self._ground_error("successful tool envelope has empty source")
        if env["status"] == "ok" and not env["in_domain"]:
            return self._ground_error("tool returned status=ok with in_domain=false")
        if env["status"] != "ok":
            return {"evidence_summary": [{"status": env["status"], "source_ids": [],
                                            "message": str(env["message"])[:300]}],
                    "events": [self._evt(s, "tool_no_evidence", "source_ground", status=env["status"])]}
        found: dict[str, dict[str, Any]] = {}
        for src in env["source"]:
            if not isinstance(src, dict):
                return self._ground_error("source entry is not an object")
            cid = src.get("clause_id")
            canonical = self.clauses.get(cid) if isinstance(cid, str) else None
            if not canonical:
                return self._ground_error(f"source ID not in canonical corpus: {cid}")
            checks = {"standard_code": "standard_code", "clause_no": "clause_no", "page": "page"}
            if any(src.get(k) != canonical.get(v) for k, v in checks.items()):
                return self._ground_error(f"source identity mismatch: {cid}")
            record_hash = _sha(canonical)
            for optional_hash in ("source_sha256", "record_sha256"):
                if optional_hash in src and src[optional_hash] != record_hash:
                    return self._ground_error(f"source hash mismatch: {cid}")
            found[cid] = {"source": src, "canonical_record_sha256": record_hash,
                          "source_hash_status": "canonical_record_sha256_calculated",
                          "corpus_sha256": self.corpus_sha256}
        evidence = dict(s["evidence"]); evidence.update(found)
        return {"evidence": evidence,
                "evidence_summary": [{"status": env["status"], "source_ids": list(found),
                                       "message": str(env["message"])[:300]}],
                "events": [self._evt(s, "sources_grounded", "source_ground", source_ids=list(found), corpus_sha256=self.corpus_sha256,
                                     public_rationale="只保留与冻结条款库 ID、标准号、条款号和页码一致的工具来源") ]}

    def _ground_error(self, reason: str) -> dict[str, Any]:
        return {"errors": [reason], "action_result": {"status": "error", "envelope": None, "attempts": 0, "error": reason},
                "evidence_summary": [{"status": "invalid_source", "source_ids": []}], "finish_reason": "source_validation_error"}

    def _conditions(self, s: State) -> dict[str, Any]:
        # Candidate claims are derived only from teacher-returned result data and grounded source IDs.
        env = (s.get("action_result") or {}).get("envelope") or {}
        ids = [cid for cid in (s.get("evidence_summary") or [{}])[-1].get("source_ids", []) if cid in s["evidence"]]
        result = env.get("result") if isinstance(env, dict) else None
        candidates: list[dict[str, Any]] = []
        raw_items = []
        if isinstance(result, dict):
            for key in ("hits", "mechanisms", "candidates", "items"):
                value = result.get(key)
                if isinstance(value, list): raw_items.extend(x for x in value if isinstance(x, dict))
            if result.get("mechanism"):
                raw_items.append(result)
        for item in raw_items:
            if item.get("clause_id"):
                item_ids = [item["clause_id"]] if item["clause_id"] in ids else []
            else:
                # A structured mechanism result may be associated only with the
                # source bundle from the same tool invocation; ambiguous bundles
                # do not create a candidate claim.
                item_ids = ids[:] if len(ids) == 1 else []
            if not item_ids:
                continue
            candidates.append({"label": item.get("title") or item.get("mechanism") or item.get("name") or "来源支持的候选方向",
                               "source_ids": item_ids, "support": [str(item.get("snippet") or item.get("description") or "原始工具命中")[:300]],
                               "contradictions": [], "unknowns": list(s["unknowns"]),
                               "conditions": {"caller_confirmed": s["facts"], "source_applicability": "not independently adjudicated"},
                               "evidence_level": "POSSIBLE", "applicability": "UNKNOWN"})
        return {"candidate_conditions": candidates,
                "events": [self._evt(s, "candidate_conditions_built", "candidate_conditions", count=len(candidates),
                                     public_rationale="仅将本次工具结果与本次已验证来源绑定，设备适用性仍未知")]}

    def _reflect(self, s: State) -> dict[str, Any]:
        if s.get("finish_reason") in {"tool_error", "source_validation_error", "policy_rejected", "planner_error"}:
            return {"reflection_continue": False}
        if s["provider_calls"] >= MAX_PROVIDER_CALLS or s["provider_tokens"] >= MAX_PROVIDER_TOKENS or time.monotonic()-s["started_at"] > self.wall_seconds:
            return {"finish_reason": "provider_or_wall_budget_exhausted", "reflection_continue": False}
        req = ReflectionRequest(run_id=s["run_id"], thread_id=s["thread_id"], question=s["question"],
                                iteration=s["iteration"], evidence_summary=s["evidence_summary"],
                                candidate_summaries=s["candidate_conditions"][:20],
                                errors=s["errors"][-10:], unknowns=s["unknowns"],
                                budget_remaining={"tool_attempts": MAX_TOOL_ATTEMPTS-s["tool_attempts"],
                                                  "investigations": MAX_INVESTIGATIONS-s["iteration"]})
        try:
            reply = self.planner.reflect(req)
            proposal = ReflectProposal.model_validate(reply.payload)
            calls = s["provider_calls"]+1; tokens = s["provider_tokens"]+reply.input_tokens+reply.output_tokens
            eligible = proposal.continue_investigation and s["iteration"] < MAX_INVESTIGATIONS and s["tool_attempts"] < MAX_TOOL_ATTEMPTS and calls < MAX_PROVIDER_CALLS and tokens < MAX_PROVIDER_TOKENS
            return {"provider_calls": calls, "provider_tokens": tokens,
                    "provider_call_log": [{"kind": "reflect", "provider": reply.provider_name, "input_tokens": reply.input_tokens,
                                           "output_tokens": reply.output_tokens, "latency_ms": reply.latency_ms}],
                    "reflection_continue": eligible,
                    "finish_reason": "" if eligible else ("reflection_finished" if not proposal.continue_investigation else "investigation_budget_exhausted"),
                    "events": [self._evt(s, "reflection_decided", "reflect", continue_investigation=eligible,
                                         public_rationale=proposal.public_rationale)]}
        except Exception as exc:
            return {"reflection_continue": False, "finish_reason": "reflection_error", "errors": [f"reflection error: {type(exc).__name__}: {exc}"]}

    @staticmethod
    def _after_reflect(s: State) -> str:
        return "plan" if s.get("reflection_continue") else "review"

    def _review_dispatch(self, s: State) -> dict[str, Any]:
        return {"events": [self._evt(s, "independent_reviews_started", "review_dispatch",
                                      public_rationale="Auditor与Skeptic并行检查来源链和未知条件")]}

    def _auditor(self, s: State) -> dict[str, Any]:
        if self.auditor_fn:
            finding = self.auditor_fn(s)
            return {"auditor": finding, "events": [self._evt(s, "review_completed", "auditor", finding=finding,
                    public_rationale="Auditor核对字段、来源和候选引用的一致性") ]}
        findings = []
        seen = {cid for row in s["evidence_summary"] for cid in row.get("source_ids", [])}
        for c in s["candidate_conditions"]:
            missing = [cid for cid in c["source_ids"] if cid not in seen or cid not in s["evidence"]]
            if missing: findings.append(f"候选引用缺少本轮已验证来源: {missing}")
        finding = {"passed": not findings, "findings": findings, "conflict": False, "retry_requested": False}
        return {"auditor": finding, "events": [self._evt(s, "review_completed", "auditor", finding=finding,
                public_rationale="Auditor核对字段、来源和候选引用的一致性") ]}

    def _skeptic(self, s: State) -> dict[str, Any]:
        if self.skeptic_fn:
            finding = self.skeptic_fn(s)
            return {"skeptic": finding, "events": [self._evt(s, "review_completed", "skeptic", finding=finding,
                    public_rationale="Skeptic检查缺失条件、反例和混淆风险") ]}
        finding = {"passed": False if s["unknowns"] else True,
                             "findings": ["工况未知不等于排除；当前证据不能确认设备适用性"],
                             "unknowns": list(s["unknowns"]),
                             "conflict": False, "retry_requested": False,
                             "distinctions": ["H2S分压与系统压力是不同字段", "材料耐蚀性不能从材质牌号单独推定"]}
        return {"skeptic": finding, "events": [self._evt(s, "review_completed", "skeptic", finding=finding,
                public_rationale="Skeptic检查缺失条件、反例和混淆风险") ]}

    def _merge(self, s: State) -> dict[str, Any]:
        conflict = bool(s["auditor"].get("conflict") or s["skeptic"].get("conflict"))
        requested = bool(s["auditor"].get("retry_requested") or s["skeptic"].get("retry_requested"))
        feedback = "; ".join(str(x) for x in (s["auditor"].get("findings", []) + s["skeptic"].get("findings", [])))[:2000]
        return {"review_conflict": conflict, "retry_requested": requested, "review_feedback": feedback,
                "review_status": "needs_human_review" if conflict or s["unknowns"] or not s["auditor"].get("passed") else "candidate_review"}

    def _review_gate(self, s: State) -> dict[str, Any]:
        can_retry = bool(s.get("retry_requested") and s["review_retries"] < MAX_REVIEW_RETRIES
                         and s["iteration"] < MAX_INVESTIGATIONS and s["tool_attempts"] < MAX_TOOL_ATTEMPTS)
        return {"review_retries": s["review_retries"] + int(can_retry),
                "review_gate_decision": "plan" if can_retry else "claim_gate"}

    @staticmethod
    def _after_review(s: State) -> str:
        return s.get("review_gate_decision", "claim_gate")

    def _claim_gate(self, s: State) -> dict[str, Any]:
        valid = []
        for row in s["candidate_conditions"]:
            if row.get("source_ids") and all(cid in s["evidence"] for cid in row["source_ids"]):
                valid.append(row)
        return {"candidate_conditions": valid, "events": [self._evt(s, "claim_gate_completed", "claim_gate",
                accepted_count=len(valid), rejected_count=len(s["candidate_conditions"])-len(valid),
                public_rationale="只放行具备本次Run来源引用的候选；不输出确认结论") ]}

    def _report(self, s: State) -> dict[str, Any]:
        missing = list(s["unknowns"])
        supplement = {"material": "材质牌号及复层/堆焊层信息", "medium": "腐蚀性组分/水相及局部环境", "temperature_c": "正常、启停及局部温度",
                      "pressure_mpa": "系统压力与必要时H2S分压分别记录", "equipment_type": "设备分类及具体部位"}
        targeted = [supplement[x] for x in missing if x in supplement]
        if any(word in s["question"] for word in ("风险等级", "风险分级", "风险是多少", "RBI")):
            targeted.extend(["失效可能性PoF所需检测/损伤数据", "失效后果CoF所需介质、库存及后果边界",
                             "现有检验记录与适用的风险矩阵版本"])
        if s.get("finish_reason") in {"policy_rejected", "planner_error", "tool_error", "source_validation_error"}:
            status = s["finish_reason"]
        elif s["tool_attempts"] >= MAX_TOOL_ATTEMPTS or s["iteration"] >= MAX_INVESTIGATIONS:
            status = "budget_exhausted"
        elif s.get("finish_reason") in {"provider_or_wall_budget_exhausted", "provider_budget_exhausted", "wall_budget_exhausted"}:
            status = "budget_exhausted"
        elif s.get("candidate_conditions"):
            status = "exploratory"
        elif s["evidence"]:
            status = "source_grounded_no_candidate"
        else:
            status = "unresolved"
        return {"output": {"status": status, "answer_type": "source_grounded_preliminary_investigation",
                            "confirmed_engineering_conclusion": False, "human_review_completed": False,
                            "risk_level": None, "candidates": s.get("candidate_conditions", []),
                            "unknowns": missing, "targeted_supplement": targeted,
                            "citations": [{"clause_id": cid, **meta} for cid, meta in s["evidence"].items()],
                            "errors": list(dict.fromkeys(s["errors"])),
                            "review": {"auditor": s.get("auditor", {}), "skeptic": s.get("skeptic", {}),
                                       "status": s.get("review_status", "not_run"),
                                       "conflict": s.get("review_conflict", False), "retries": s["review_retries"]},
                            "finish_reason": s.get("finish_reason", ""),
                            "budget": {"tool_attempts": s["tool_attempts"], "tool_limit": MAX_TOOL_ATTEMPTS,
                                       "investigations": s["iteration"], "investigation_limit": MAX_INVESTIGATIONS,
                                       "provider_calls": s["provider_calls"], "provider_token_estimate": s["provider_tokens"],
                                       "provider_token_limit": MAX_PROVIDER_TOKENS},
                            "provider_calls": list(s["provider_call_log"]), "tool_calls": list(s["tool_log"]),
                            "events": list(s["events"]), "corpus_sha256": self.corpus_sha256}}

    def run(self, question: str, context: dict[str, Any] | None = None, *, run_id: str | None = None,
            thread_id: str | None = None, subtask_id: str = "engineering",
            recursion_limit: int = 40) -> dict[str, Any]:
        if len(question) > 4000: raise ValueError("question exceeds 4000 characters")
        state: State = {"run_id": run_id or str(uuid4()), "thread_id": thread_id or str(uuid4()),
                        "subtask_id": subtask_id, "question": question, "caller_context": dict(context or {})}
        checkpoint_thread = f"{state['thread_id']}::aetheris-v2::{state['run_id']}"
        config = {"recursion_limit": recursion_limit,
                  "configurable": {"thread_id": checkpoint_thread}}
        # A process restart resumes the last unfinished LangGraph superstep. If
        # the side effect completed before the checkpoint, the SQLite action
        # ledger returns its persisted result rather than invoking the tool twice.
        if self.checkpointer is not None:
            snapshot = self.graph.get_state(config)
            if snapshot and snapshot.next:
                return self.graph.invoke(None, config)
        return self.graph.invoke(state, config)

