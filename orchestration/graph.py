"""Small pluggable state graph over the frozen teacher's three-tool registry.

The included nodes are deterministic RULE_DEMO agents. They are real, independently
replaceable nodes, but deliberately do not claim multi-LLM quality or private CoT.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from contextvars import ContextVar
import json
from pathlib import Path
from typing import Any, Callable, Protocol, TypedDict
from uuid import uuid4

from app.runtime import load_harness
from orchestration.evidence_audit import audit_claim, audit_reference, load_clause_index, skeptic_findings
from orchestration.semantics import Claim, extract_observations


@dataclass
class RunState:
    run_id: str
    conversation_id: str
    question: str
    context: dict[str, Any]
    mode: str = "RULE_DEMO"
    route: str = "insufficient_context"
    observations: list[dict[str, Any]] = field(default_factory=list)
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    rbi_results: list[dict[str, Any]] = field(default_factory=list)
    candidates: list[dict[str, Any]] = field(default_factory=list)
    evidence_refs: list[dict[str, Any]] = field(default_factory=list)
    claims: list[dict[str, Any]] = field(default_factory=list)
    disagreements: list[dict[str, Any]] = field(default_factory=list)
    gaps: list[dict[str, Any]] = field(default_factory=list)
    answer: str = ""
    issues: list[str] = field(default_factory=list)


class GraphState(TypedDict):
    """Serializable StateGraph projection of ``RunState``.

    The first migration deliberately remains sequential. No reducer is required
    because a single node owns each update at a time; parallel fan-out must add
    explicit reducers before it is enabled.
    """
    run_id: str
    conversation_id: str
    question: str
    context: dict[str, Any]
    mode: str
    route: str
    observations: list[dict[str, Any]]
    tool_results: list[dict[str, Any]]
    rbi_results: list[dict[str, Any]]
    candidates: list[dict[str, Any]]
    evidence_refs: list[dict[str, Any]]
    claims: list[dict[str, Any]]
    disagreements: list[dict[str, Any]]
    gaps: list[dict[str, Any]]
    answer: str
    issues: list[str]


class AgentNode(Protocol):
    name: str
    def run(self, state: RunState) -> None: ...


EventSink = Callable[[str, str, dict[str, Any]], None]
_UNREVIEWED_RBI_KEYS = {"likelihood", "consequence", "risk_level", "risk_level_unified", "inspection_interval_year"}


def public_tool_result(tool: str, result: dict[str, Any]) -> dict[str, Any]:
    """Copy for SSE only; never mutate the frozen teacher tool's original result."""
    safe = json.loads(json.dumps(result, ensure_ascii=False))
    if tool == "rbi_lookup":
        def strip(value: Any) -> Any:
            if isinstance(value, dict):
                return {key: strip(child) for key, child in value.items() if str(key).lower() not in _UNREVIEWED_RBI_KEYS}
            if isinstance(value, list):
                return [strip(child) for child in value]
            return value
        safe = strip(safe)
    return safe


ROUTED_NODE_NAMES = (
    "supervisor", "evidence_agent", "diagnosis_agent", "rbi_specialist",
    "evidence_auditor", "skeptic", "reporting_agent",
)


class SupervisorAgent:
    name = "supervisor"

    def run(self, state: RunState) -> None:
        state.observations = [x.model_dump(mode="json") for x in extract_observations(state.question + " " + str(state.context.get("field_evidence", "")) + " " + str(state.context.get("operating_condition", "")))]
        if not state.context.get("material") or not state.context.get("medium"):
            state.route = "ask_for_context"
        elif "标准" in state.question or "条款" in state.question:
            state.route = "standard_lookup"
        elif any(x["field"] in {"ph", "iron_ion", "chloride", "h2s"} for x in state.observations) or any(k.lower() in state.question.lower() for k in ("机理", "腐蚀", "损伤", "rbi", "风险", "设备", "铁离子", "氯离子", "硫化氢")):
            state.route = "mechanism_analysis"
        else:
            state.route = "out_of_domain"
        if state.route == "ask_for_context":
            missing = [x for x in ("material", "medium") if not state.context.get(x)]
            state.gaps.append({"field": "operating_context", "question": "请补充材质与介质。", "reason": "Supervisor发现必需工况上下文缺失：" + "、".join(missing), "priority": "high"})


class EvidenceAgent:
    """Calls the actual frozen teacher tools; never registers a product tool."""
    name = "evidence_agent"

    def run(self, state: RunState) -> None:
        h = load_harness()
        registry = h.build_registry()
        temp = next((o["normalized_value"] for o in state.observations if o["field"] == "temperature"), None)
        evidence: dict[str, Any] = {}
        for observation in state.observations:
            key = {"iron_ion": "fe_ppm", "chloride": "cl_ppm", "h2s": "h2s_ppm", "ph": "ph"}.get(observation["field"])
            if key and isinstance(observation.get("normalized_value"), (int, float)):
                evidence[key] = observation["normalized_value"]
            if observation["field"] in {"wall_thinning", "crack_found"} and observation["observation_state"] != "unknown":
                evidence[observation["field"]] = observation["normalized_value"]
        dm_args: dict[str, Any] = {"material": state.context["material"], "medium": state.context["medium"]}
        if temp is not None: dm_args["temperature_c"] = temp
        if state.context.get("equipment_type"): dm_args["equipment_type"] = state.context["equipment_type"]
        if evidence: dm_args["evidence"] = evidence
        if state.route == "standard_lookup":
            self._call(registry, "standard_clause_search", {"keyword": state.question, "top_k": 5}, state)
        else:
            self._call(registry, "damage_mechanism_query", dm_args, state)
            self._call(registry, "standard_clause_search", {"keyword": state.question, "knowledge_type": "damage_mechanism", "top_k": 5}, state)

    @staticmethod
    def _call(registry: Any, name: str, args: dict[str, Any], state: RunState) -> None:
        spec = registry.get(name)
        if spec is None:
            state.issues.append(f"官方工具注册表缺少冻结工具 {name}")
            return
        result = spec.func(**args)
        record = {"tool": name, "args": args, "result": result}
        state.tool_results.append(record)
        for source in result.get("source", []) if isinstance(result, dict) else []:
            if isinstance(source, dict) and source.get("clause_id"):
                state.evidence_refs.append({**source, "verification_level": "E0", "review_status": "draft_needs_review"})
        if name == "damage_mechanism_query" and isinstance(result, dict):
            state.candidates = result.get("result", {}).get("mechanisms", []) or []
        if name == "rbi_lookup" and isinstance(result, dict):
            state.rbi_results.append(result)


class DiagnosisAgent:
    name = "diagnosis_agent"

    def run(self, state: RunState) -> None:
        if state.route in {"ask_for_context", "out_of_domain", "standard_lookup"}:
            return
        present = {o["field"] for o in state.observations}
        if "wall_thinning" not in present:
            state.gaps.append({"field": "wall_thinning", "question": "是否已完成定点/扫查测厚？", "reason": "未测厚应保持 unknown，不能解释为无减薄。", "priority": "high"})
        if not any(o["field"] == "h2s" for o in state.observations) and any("硫化氢" in str(x) for x in state.context.get("medium", [])):
            state.gaps.append({"field": "h2s_concentration", "question": "请补充水相/气相 H2S 浓度或分压及采样时间。", "reason": "介质存在不等于现场浓度已知。", "priority": "high"})
        if not state.candidates:
            state.gaps.append({"field": "mechanism_candidates", "question": "补充装置部位、材质牌号、温压和现场检测信息。", "reason": "当前检索未形成可核证候选。", "priority": "high"})
        existing = {claim.get("claim_id") for claim in state.claims}
        for index, candidate in enumerate(state.candidates):
            name = str(candidate.get("name", "未命名候选"))
            cited = candidate.get("clause_id")
            source_ids = [str(cited)] if cited else [str(ref["clause_id"]) for ref in state.evidence_refs if ref.get("clause_id")]
            claim_id = f"{state.run_id}-mechanism-{index + 1}"
            if claim_id in existing:
                continue
            claim = Claim(
                claim_id=claim_id,
                kind="engineering_hypothesis",
                text=f"工具候选机理：{name}（待独立核证，不代表设备已发生该损伤）",
                source_clause_ids=list(dict.fromkeys(source_ids)),
                observation_ids=[f"obs-{item['field']}" for item in state.observations],
                assumptions=["官方工具返回仅说明候选匹配；需核对条款蕴含及设备适用性"],
            )
            state.claims.append(claim.model_dump(mode="json"))


class RbiSpecialistAgent:
    """Invoke the frozen RBI tool only after explicit operating factors are present."""
    name = "rbi_specialist"

    def run(self, state: RunState) -> None:
        if state.route != "mechanism_analysis":
            return
        values = {o["field"]: o.get("normalized_value") for o in state.observations}
        required = ["temperature", "pressure", "service_years"]
        missing = [name for name in required if not isinstance(values.get(name), (int, float))]
        if not state.candidates:
            missing.append("confirmed_mechanism")
        if missing:
            state.gaps.append({"field": "rbi_inputs", "question": "暂不请求 RBI 判级；需补充：" + "、".join(missing),
                               "reason": "避免在关键现场因子缺失时输出风险等级或周期。", "priority": "high"})
            return
        args = {"equipment_type": state.context.get("equipment_type"), "material": state.context.get("material"),
                "mechanism": state.candidates[0].get("name"), "medium": state.context.get("medium"),
                "temperature_c": values["temperature"], "pressure_mpa": values["pressure"], "service_years": values["service_years"]}
        EvidenceAgent._call(load_harness().build_registry(), "rbi_lookup", args, state)
        # Preserve the legacy tool call, but never publish its risk grade without
        # independently reviewed likelihood and consequence evidence.
        if not isinstance(state.context.get("likelihood_evidence"), dict) or not isinstance(state.context.get("consequence_evidence"), dict):
            state.gaps.append({"field": "rbi_level_evidence", "question": "RBI风险级别暂不展示；需独立提供并复核失效可能性、后果依据及适用性。",
                               "reason": "本轮工具查询不能替代失效可能性/后果证据，也不能据工具输出直接形成L1-L4。", "priority": "high"})


class EvidenceAuditorAgent:
    name = "evidence_auditor"

    def run(self, state: RunState) -> None:
        clause_file = Path(__file__).resolve().parents[1] / "upstream" / "05_提交区" / "clauses.jsonl"
        index = load_clause_index(clause_file)
        returned = {source.get("clause_id") for call in state.tool_results if call.get("tool") == "standard_clause_search"
                    for source in (call["result"].get("source") or []) if isinstance(source, dict)}
        state.evidence_refs = [audit_reference(ref, state, index) for ref in state.evidence_refs]
        for ref in state.evidence_refs:
            if ref.get("verification_level") != "E1":
                state.issues.append(f"引用ID {ref.get('clause_id')}来源/元数据/原文未完整核验；保持E0/partial")
        for candidate in state.candidates:
            cid = candidate.get("clause_id")
            if cid and cid not in returned:
                state.issues.append(f"候选 {candidate.get('name')} 的 {cid} 未见本轮工具 source，证据级别维持 E0")
        for call in state.tool_results:
            ret = call["result"]
            if ret.get("status") == "ok" and not ret.get("source"):
                state.issues.append(f"工具 {call['tool']} 返回 status=ok 但 source 为空")
        if state.claims:
            state.claims = [audit_claim(claim, state, index).model_dump(mode="json") for claim in state.claims]


class SkepticAgent:
    """Independent RULE_DEMO check over raw observations and tool sources."""
    name = "skeptic"

    def run(self, state: RunState) -> None:
        state.disagreements = skeptic_findings(state)
        by_id = {item["claim_id"]: item for item in state.disagreements}
        for claim in state.claims:
            finding = by_id.get(claim["claim_id"])
            if not finding:
                continue
            claim["independent_validation"] = {
                "mode": "RULE_DEMO",
                "reviewer_role": self.name,
                "result": finding["verdict"],
                "finding_id": finding["disagreement_id"],
                "basis_observation_ids": finding["basis_observation_ids"],
                "basis_source_clause_ids": finding["basis_source_clause_ids"],
                "review_scope": finding.get("review_scope", "lexical_only_no_semantic_entailment"),
                "independent_retrieval": finding.get("independent_retrieval", []),
            }
            claim["verdict"] = finding["verdict"]
            claim["review_status"] = "requires_human_review"


class ReportingAgent:
    name = "reporting_agent"

    def run(self, state: RunState) -> None:
        if state.route == "out_of_domain":
            state.answer = "当前问题不在设备风险研判范围内；可输入设备/材质/介质、现场现象，或提出标准条款查询。"
            return
        if state.route == "ask_for_context":
            state.answer = "目前工况上下文不足，暂不调用工具。" + "；".join(gap["question"] for gap in state.gaps)
            return
        names = [str(x.get("name", "未命名候选")) for x in state.candidates]
        lines = ["执行模式：RULE_DEMO（确定性节点，不是多LLM结果）。"]
        lines.append("候选机理：" + ("、".join(names) if names else "当前工具结果未返回候选；不据此判定设备安全。"))
        if state.evidence_refs:
            lines.append("本轮实际检索出处：" + "；".join(f"{x.get('standard_code','')} {x.get('clause_no','')} ({x.get('clause_id')}, p.{x.get('page','?')})" for x in state.evidence_refs[:8]))
        if state.gaps:
            lines.append("待补现场信息：" + "；".join(x["question"] for x in state.gaps))
        if state.rbi_results:
            lines.append("RBI判级未展示：当前缺少独立失效可能性/后果证据或适用性复核；工具返回不作为结论。")
        if state.claims:
            lines.append("可审查声明：" + "；".join(
                f"{claim['claim_id']}={claim['verdict']}/{claim['grade']}/{claim['review_status']}"
                for claim in state.claims
            ))
        if state.disagreements:
            lines.append("Skeptic独立复核：" + "；".join(x["finding"] for x in state.disagreements[:5]))
        lines.append("证据级别：E1=官方条款ID存在且来自本轮工具返回；E2原文蕴含、E3工况适用性尚未人工复核。未核验前不把候选等同于设备定论。")
        if state.issues: lines.append("审计提示：" + "；".join(state.issues))
        state.answer = "\n".join(lines)


class AgentGraph:
    """Six-node LangGraph StateGraph behind the stable R1 API/event contract."""
    def __init__(self, nodes: list[AgentNode] | None = None, checkpoint_path: str | Path | None = None):
        self.nodes: dict[str, AgentNode] = {}
        self.order: list[str] = []
        defaults = [SupervisorAgent(), EvidenceAgent(), DiagnosisAgent(), RbiSpecialistAgent(), EvidenceAuditorAgent(), SkepticAgent(), ReportingAgent()]
        for node in defaults if nodes is None else nodes:
            self.add_node(node)
        self.validate_routes()
        self._event_sink: ContextVar[EventSink] = ContextVar("agent_graph_event_sink", default=lambda *_args: None)
        self.checkpoint_path = Path(checkpoint_path) if checkpoint_path else Path(__file__).resolve().parents[1] / "data" / "langgraph_checkpoints.sqlite3"
        self.state_graph = self._build_state_graph()

    def add_node(self, node: AgentNode, after: str | None = None) -> None:
        if node.name in self.nodes: raise ValueError(f"duplicate node: {node.name}")
        self.nodes[node.name] = node
        if after is not None:
            if after not in self.order: raise ValueError(f"unknown predecessor node: {after}")
            self.order.insert(self.order.index(after) + 1, node.name)
        elif "reporting_agent" in self.order:
            self.order.insert(self.order.index("reporting_agent"), node.name)
        else:
            self.order.append(node.name)
        # Preserve R1's public extension API: a node may be inserted after graph
        # construction, so rebuild the StateGraph topology immediately.
        if hasattr(self, "state_graph"):
            self.state_graph = self._build_state_graph()

    def validate_routes(self) -> None:
        """Fail at graph construction, not midway through an API run, if schedule and registry drift."""
        missing = [name for name in ROUTED_NODE_NAMES if name not in self.nodes]
        unordered = [name for name in self.nodes if name not in self.order]
        dangling = [name for name in self.order if name not in self.nodes]
        if missing or unordered or dangling:
            raise ValueError(f"AgentGraph route/registry mismatch: missing={missing}, unordered={unordered}, dangling={dangling}")

    @staticmethod
    def _as_graph_state(state: RunState) -> GraphState:
        return {
            "run_id": state.run_id, "conversation_id": state.conversation_id,
            "question": state.question, "context": state.context, "mode": state.mode,
            "route": state.route, "observations": state.observations,
            "tool_results": state.tool_results, "rbi_results": state.rbi_results,
            "candidates": state.candidates, "evidence_refs": state.evidence_refs,
            "claims": state.claims, "disagreements": state.disagreements,
            "gaps": state.gaps, "answer": state.answer, "issues": state.issues,
        }

    @staticmethod
    def _as_run_state(state: GraphState) -> RunState:
        return RunState(**{key: state[key] for key in RunState.__dataclass_fields__})

    def _build_state_graph(self):
        # Import lazily so tools that only inspect schemas don't import LangGraph;
        # execution happens in the isolated, pinned P2 environment.
        from langgraph.graph import END, START, StateGraph

        builder = StateGraph(GraphState)
        for name in self.order:
            node = self.nodes[name]

            def execute(state: GraphState, *, _name=name, _node=node) -> GraphState:
                current = self._as_run_state(state)
                event = self._event_sink.get()
                event("agent_started", _name, {"route": current.route if _name != "supervisor" else "classify"})
                before_tools = len(current.tool_results)
                before_refs = len(current.evidence_refs)
                before_claims = {item["claim_id"]: item for item in current.claims}
                before_disagreements = {item["disagreement_id"] for item in current.disagreements}
                _node.run(current)
                for call in current.tool_results[before_tools:]:
                    event("tool_called", _name, {"tool": call["tool"], "args": call["args"]})
                    result = call["result"]
                    if call["tool"] == "rbi_lookup":
                        # Keep the historical event envelope; mask unreviewed
                        # likelihood/consequence/risk fields from this run's SSE.
                        result = public_tool_result(call["tool"], result)
                    event("tool_result", _name, {"tool": call["tool"], "result": result})
                for ref in current.evidence_refs[before_refs:]:
                    event("reference_added", _name, ref)
                for claim in current.claims:
                    old = before_claims.get(claim["claim_id"])
                    if old is None:
                        event("claim_added", _name, claim)
                    elif old != claim:
                        event("claim_checked", _name, claim)
                    if claim.get("review_status") == "requires_human_review" and (old is None or old.get("review_status") != "requires_human_review"):
                        event("requires_human_review", _name, claim)
                for finding in current.disagreements:
                    if finding["disagreement_id"] not in before_disagreements:
                        kind = "contradiction_found" if finding["verdict"] == "contradicted" else "requires_human_review"
                        event(kind, _name, finding)
                event("decision_summary", _name, self._public_summary(current, _name))
                event("agent_completed", _name, {"status": "completed"})
                return self._as_graph_state(current)

            builder.add_node(name, execute)

        builder.add_edge(START, self.order[0])
        # A conditional edge is the only outgoing edge on each node. It takes the
        # route from graph state (the closure below is bound per node invocation).
        for name in self.order:
            def dispatch(state: GraphState, *, _name=name):
                route = state["route"]
                index = self.order.index(_name)
                for candidate in self.order[index + 1:]:
                    if route in {"ask_for_context", "out_of_domain"} and candidate in {"evidence_agent", "diagnosis_agent", "rbi_specialist"}:
                        continue
                    return candidate
                return END
            targets = {candidate: candidate for candidate in self.order}
            targets[END] = END
            builder.add_conditional_edges(name, dispatch, targets)
        return builder

    def run(self, state: RunState, emit: EventSink) -> RunState:
        self.validate_routes()
        emit("run_started", "supervisor", {"mode": state.mode, "schema_version": 1})
        # Bind a run-local event sink while LangGraph drives conditional edges.
        token = self._event_sink.set(emit)
        try:
            from langgraph.checkpoint.sqlite import SqliteSaver
            self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
            with SqliteSaver.from_conn_string(str(self.checkpoint_path)) as checkpointer:
                graph = self.state_graph.compile(checkpointer=checkpointer)
                final = graph.invoke(self._as_graph_state(state), {"configurable": {"thread_id": state.run_id}})
                del graph
            for key, value in final.items():
                if key in RunState.__dataclass_fields__:
                    setattr(state, key, value)
        finally:
            self._event_sink.reset(token)
        best = "E1" if any(ref.get("verification_level") == "E1" for ref in state.evidence_refs) else "E0"
        emit("verification", "evidence_auditor", {"issues": state.issues, "evidence_count": len(state.evidence_refs), "level": best})
        emit("token_delta", "reporting_agent", {"text": state.answer})
        emit("run_completed", "supervisor", {"status": "completed", "mode": state.mode})
        return state

    @staticmethod
    def _public_summary(state: RunState, agent: str) -> dict[str, Any]:
        return {"agent": agent, "route": state.route, "observation_count": len(state.observations),
                "candidate_count": len(state.candidates), "claim_count": len(state.claims), "disagreement_count": len(state.disagreements),
                "gap_count": len(state.gaps), "evidence_count": len(state.evidence_refs),
                "rbi_called": bool(state.rbi_results)}
