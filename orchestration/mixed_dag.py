"""Bounded, serial, evidence-gated MIXED route executor for the V2 offline candidate."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from backend.execution_ledger import SQLiteExecutionLedger
from backend.intent_router_v2 import IntentSubtask, MainRoute, RouteDecision, TaskKind
from orchestration.agentic_v2 import AgenticV2Candidate, TEACHER_TOOLS

ENGINEERING_KINDS = {
    TaskKind.MECHANISM_EXPLORATION, TaskKind.DEVICE_DIAGNOSIS, TaskKind.RBI_ASSESSMENT,
}
MAX_MIXED_TASKS = 4


class MixedDAGError(ValueError):
    pass


@dataclass
class MockTextProvider:
    """Offline deterministic provider; it has no client, key lookup, or network path."""

    def explain(self, task: IntentSubtask, question: str) -> dict[str, Any]:
        return {"status": "succeeded", "text": f"一般说明子任务：{task.user_goal}。这是离线Mock摘要，不是现场事实。", "sources": []}

    def synthesize(self, question: str, results: list[dict[str, Any]]) -> str:
        lines = ["混合任务摘要（离线Mock；只合并已完成子任务与已核验来源）："]
        for item in results:
            task = item["task"]
            result = item["result"]
            state = item["state"]
            if state != "SUCCEEDED":
                lines.append(f"- {task.id}：{state}，未纳入事实结论。")
                continue
            text = str(result.get("text") or result.get("summary") or result.get("status") or "已完成")
            refs = result.get("source_ids") or []
            lines.append(f"- {task.id}（{task.kind.value}）：{text[:600]}" +
                         (f"；来源：{', '.join(refs[:8])}" if refs else "；无已核验来源"))
        lines.append("任何缺少来源或现场证据的内容均保持为待核事项，不生成风险等级。")
        return "\n".join(lines)


class MixedDAGExecutor:
    """Executes a RouteDecision serially with SQLite state and strict dependency gates."""

    def __init__(self, *, candidate: AgenticV2Candidate, ledger: SQLiteExecutionLedger,
                 standard_tool: Callable[..., Any], text_provider: MockTextProvider | None = None):
        self.candidate = candidate
        self.ledger = ledger
        self.standard_tool = standard_tool
        self.text_provider = text_provider or MockTextProvider()

    @staticmethod
    def _priority(task: IntentSubtask) -> tuple[int, str]:
        if task.kind in ENGINEERING_KINDS or task.task_risk in {"SAFETY_RELEVANT", "HIGH_CONSEQUENCE"}:
            return (0, task.id)
        if task.kind == TaskKind.STANDARD_LOOKUP:
            return (1, task.id)
        if task.kind == TaskKind.GENERAL_EXPLANATION:
            return (2, task.id)
        if task.kind == TaskKind.WRITING_SYNTHESIS:
            return (3, task.id)
        return (4, task.id)

    @classmethod
    def _ordered(cls, decision: RouteDecision) -> list[IntentSubtask]:
        tasks = list(decision.subtasks)
        if decision.primary_route != MainRoute.MIXED:
            raise MixedDAGError("executor requires explicit MIXED route")
        if not 2 <= len(tasks) <= MAX_MIXED_TASKS:
            raise MixedDAGError("mixed route must contain 2..4 subtasks")
        by_id = {task.id: task for task in tasks}
        if len(by_id) != len(tasks):
            raise MixedDAGError("duplicate subtask id")
        for task in tasks:
            if any(dep not in by_id for dep in task.depends_on):
                raise MixedDAGError(f"unknown dependency in {task.id}")
            if task.id in task.depends_on:
                raise MixedDAGError(f"self dependency in {task.id}")
        output: list[IntentSubtask] = []
        done: set[str] = set()
        remaining = set(by_id)
        while remaining:
            ready = [by_id[key] for key in remaining
                     if set(by_id[key].depends_on).issubset(done)]
            if not ready:
                raise MixedDAGError("dependency cycle or non-topological route")
            selected = sorted(ready, key=cls._priority)
            output.extend(selected)
            done.update(task.id for task in selected)
            remaining.difference_update(task.id for task in selected)
        return output

    def _standard_lookup(self, task: IntentSubtask, run_id: str, cid: str) -> dict[str, Any]:
        args = {"keyword": task.user_goal[:600], "top_k": 8}
        def action() -> dict[str, Any]:
            envelope = self.standard_tool(**args)
            return {"status": "returned", "attempts": 1, "envelope": envelope}
        result, replayed, attempts_delta = self.ledger.execute_tool(
            conversation_id=cid, run_id=run_id, subtask_id=task.id, step_id="tool:1",
            tool_name="standard_clause_search", args=args, action=action, max_attempts=2,
        )
        action_record = self.ledger.get_action(run_id=run_id, subtask_id=task.id, step_id="tool:1")
        envelope = result.get("envelope")
        if not isinstance(envelope, dict) or set(envelope) != {"status", "in_domain", "result", "source", "message"}:
            raise MixedDAGError("standard tool returned invalid frozen envelope")
        if envelope["status"] == "ok" and (not envelope["in_domain"] or not envelope["source"]):
            raise MixedDAGError("successful standard lookup must be in-domain with sources")
        source_ids: list[str] = []
        for source in envelope.get("source") or []:
            if not isinstance(source, dict):
                raise MixedDAGError("invalid source object")
            source_id = source.get("clause_id")
            canonical = self.candidate.clauses.get(source_id) if isinstance(source_id, str) else None
            if not canonical:
                raise MixedDAGError("source ID missing from canonical corpus")
            if any(source.get(key) != canonical.get(field) for key, field in
                   (("standard_code", "standard_code"), ("clause_no", "clause_no"), ("page", "page"))):
                raise MixedDAGError("tool source identity mismatch")
            source_ids.append(source_id)
        return {"status": envelope["status"],
                "summary": "标准检索返回了可定位条款；条文适用性与设备结论仍待核。",
                "source_ids": source_ids, "tool": "standard_clause_search",
                "actual_attempts": int(action_record.get("attempt_count") or attempts_delta),
                "replayed": replayed}

    def execute(self, decision: RouteDecision, *, question: str, context: dict[str, Any],
                run_id: str, conversation_id: str,
                on_event: Callable[[dict[str, Any]], None] | None = None) -> dict[str, Any]:
        ordered = self._ordered(decision)
        results: dict[str, dict[str, Any]] = {}
        rows: list[dict[str, Any]] = []
        for task in ordered:
            blocked = [dependency for dependency in task.depends_on
                       if results.get(dependency, {}).get("state") != "SUCCEEDED"]
            if blocked:
                self.ledger.begin_subtask(run_id=run_id, subtask_id=task.id,
                    kind=task.kind.value, goal=task.user_goal, dependencies=task.depends_on)
                result = {"status": "skipped", "blocked_by": blocked, "source_ids": []}
                self.ledger.finish_subtask(run_id=run_id, subtask_id=task.id,
                    state="SKIPPED", result=result, error="dependency_not_succeeded")
                results[task.id] = {"task": task, "state": "SKIPPED", "result": result}
                rows.append(results[task.id])
                if on_event: on_event({"type": "subtask_skipped", "subtask_id": task.id,
                                       "kind": task.kind.value, "blocked_by": blocked})
                continue

            slot = self.ledger.begin_subtask(run_id=run_id, subtask_id=task.id,
                kind=task.kind.value, goal=task.user_goal, dependencies=task.depends_on)
            if slot.get("replayed"):
                result = slot.get("result") or {}
                state = str(slot["state"])
                results[task.id] = {"task": task, "state": state, "result": result}
                rows.append(results[task.id])
                continue
            if on_event: on_event({"type": "subtask_started", "subtask_id": task.id,
                                   "kind": task.kind.value, "dependencies": task.depends_on})
            try:
                if task.kind == TaskKind.GENERAL_EXPLANATION:
                    result = self.text_provider.explain(task, question)
                elif task.kind == TaskKind.STANDARD_LOOKUP:
                    result = self._standard_lookup(task, run_id, conversation_id)
                elif task.kind in ENGINEERING_KINDS:
                    graph_result = self.candidate.run(
                        question + "\n子任务目标：" + task.user_goal, context,
                        run_id=run_id, thread_id=conversation_id, subtask_id=task.id)
                    output = graph_result["output"]
                    tool_calls = output.get("tool_calls") or []
                    if any(not isinstance(call, dict) or call.get("tool") not in TEACHER_TOOLS
                           for call in tool_calls):
                        raise MixedDAGError("candidate attempted a tool outside the frozen allowlist")
                    source_ids = [str(row.get("clause_id")) for row in output.get("citations", [])
                                  if isinstance(row, dict) and row.get("clause_id")]
                    if any(source_id not in self.candidate.clauses for source_id in source_ids):
                        raise MixedDAGError("engineering candidate cited a non-canonical source")
                    result = {"status": output.get("status", "unresolved"),
                              "summary": "来源约束的初步候选；不构成工程确认。",
                              "candidate_count": len(output.get("candidates") or []),
                              "risk_level": None, "source_ids": source_ids,
                              "output": output}
                elif task.kind == TaskKind.CLARIFICATION_REQUIRED:
                    result = {"status": "needs_clarification", "text": task.user_goal, "source_ids": []}
                    self.ledger.finish_subtask(run_id=run_id, subtask_id=task.id, state="DEFERRED",
                                               result=result, error="clarification_required")
                    results[task.id] = {"task": task, "state": "DEFERRED", "result": result}
                    rows.append(results[task.id])
                    continue
                elif task.kind == TaskKind.WRITING_SYNTHESIS:
                    dependencies = [results[key] for key in task.depends_on]
                    result = {"status": "synthesized",
                              "text": self.text_provider.synthesize(question, dependencies),
                              "source_ids": sorted({source for row in dependencies
                                                    for source in (row["result"].get("source_ids") or [])})}
                else:
                    result = {"status": "deferred", "source_ids": [], "reason": "unsupported_subtask"}
                    self.ledger.finish_subtask(run_id=run_id, subtask_id=task.id, state="DEFERRED",
                                               result=result, error="unsupported_subtask")
                    results[task.id] = {"task": task, "state": "DEFERRED", "result": result}
                    rows.append(results[task.id])
                    continue
                source_ids = list(result.get("source_ids") or [])
                if task.kind == TaskKind.WRITING_SYNTHESIS:
                    deps = [results[key] for key in task.depends_on]
                    allowed = {source for row in deps for source in (row["result"].get("source_ids") or [])
                               if row["state"] == "SUCCEEDED"}
                    if not set(source_ids).issubset(allowed):
                        raise MixedDAGError("synthesis referenced evidence outside successful dependencies")
                self.ledger.finish_subtask(run_id=run_id, subtask_id=task.id,
                    state="SUCCEEDED", result=result, source_ids=source_ids)
                results[task.id] = {"task": task, "state": "SUCCEEDED", "result": result}
            except Exception as exc:
                result = {"status": "failed", "reason": type(exc).__name__, "source_ids": []}
                self.ledger.finish_subtask(run_id=run_id, subtask_id=task.id, state="FAILED",
                    result=result, error=f"{type(exc).__name__}: {exc}"[:300])
                results[task.id] = {"task": task, "state": "FAILED", "result": result}
            rows.append(results[task.id])
            task_result = results[task.id]["result"]
            if on_event and task_result.get("tool"):
                on_event({"type": "tool_called", "subtask_id": task.id,
                    "kind": task.kind.value, "tool": task_result["tool"],
                    "tool_name": task_result["tool"],
                    "args": {"keyword": "已记录（具体值不公开）", "top_k": 8},
                    "actual_attempts": task_result.get("actual_attempts", 0),
                    "status": "recorded"})
                on_event({"type": "tool_result", "subtask_id": task.id,
                    "kind": task.kind.value, "tool": task_result["tool"],
                    "tool_name": task_result["tool"],
                    "actual_attempts": task_result.get("actual_attempts", 0),
                    "status": task_result.get("status", "unknown"),
                    "result": {"status": task_result.get("status", "unknown"),
                               "sources": [{"clause_id": sid} for sid in task_result.get("source_ids", [])]},
                    "source_ids": task_result.get("source_ids", [])})
            if on_event: on_event({"type": "subtask_completed", "subtask_id": task.id,
                "kind": task.kind.value, "status": results[task.id]["state"],
                "source_ids": task_result.get("source_ids", [])})

        successful = [row for row in rows if row["state"] == "SUCCEEDED"]
        failed = [row for row in rows if row["state"] in {"FAILED", "SKIPPED", "DEFERRED"}]
        final_text = next((row["result"].get("text") for row in reversed(rows)
                           if row["task"].kind == TaskKind.WRITING_SYNTHESIS
                           and row["state"] == "SUCCEEDED"), None)
        if final_text is None:
            final_text = self.text_provider.synthesize(question, rows)
        return {"status": "partial" if failed and successful else "failed" if failed else "completed",
                "route_execution": "MIXED_DAG_EXECUTED_OFFLINE",
                "final_text": final_text, "tool_calls": sum(
                    1 for row in rows if row["result"].get("tool")),
                "subtasks": [
                    {"id": row["task"].id, "kind": row["task"].kind.value,
                     "depends_on": row["task"].depends_on, "state": row["state"],
                     "source_ids": row["result"].get("source_ids", []),
                     "result": row["result"]} for row in rows],
                "source_ids": sorted({source for row in successful
                                      for source in (row["result"].get("source_ids") or [])})}
