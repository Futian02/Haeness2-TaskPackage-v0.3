"""R9-A isolated industrial diagnosis graph candidate (RULE_DEMO by default).

This module is not wired into ``orchestration.graph.AgentGraph`` or any API.
It keeps the teacher tool registry at exactly three entries and fails closed on
missing field evidence, tool failures, unsupported risk grades, and review conflict.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import re
import time
from typing import Any, Callable, TypedDict
from uuid import uuid4

from orchestration.p6_parallel_audit import (
    AuditFinding, SkepticFinding, merge_findings,
)
from orchestration.intent import classify_intent, rule_chat_reply
from backend.professional_answers import classify_professional_intent, plan_teacher_queries

TEACHER_TOOLS = (
    "damage_mechanism_query", "rbi_lookup", "standard_clause_search",
)
MAX_INVESTIGATIONS = 3
MAX_REVIEW_RETRIES = 2
MAX_TOOL_CALLS = 8

_CONCEPT_ASK = re.compile(r"^(?:请问|想问|帮我)?(?:什么是|何为|解释(?:一下)?|介绍(?:一下)?|讲讲|说明(?:一下)?)")
_CONCEPT_SCC = re.compile(r"(?:应力腐蚀开裂|应力腐蚀裂纹|stress\s*corrosion\s*cracking|\bSCC\b)", re.I)
_DEVICE_HAZARD = re.compile(r"渗漏|泄漏|冒烟|异响|振动异常|超温|超压|裂纹|开裂|变形|凹陷|磕碰|碰撞|减薄|腐蚀|损伤|失效")
_DEVICE_WORD = re.compile(r"设备|管道|容器|弯头|壳体|焊缝|换热器|反应釜|储罐|泵|阀门|法兰")
_MIXED_CUE = re.compile(r"同时|并且|另外|以及|还要|还需|并.*(?:查询|检索|解释|分析)")
_QUERY_SYNONYMS = (
    (("磕碰", "碰撞", "撞击"), ("机械损伤 冲击 凹陷")),
    (("验收", "复机", "维修"), ("缺陷检测 修理后复检 评定原则")),
    (("应力腐蚀开裂", "SCC", "stress corrosion cracking"), ("拉应力 敏感材料 腐蚀环境 裂纹")),
    (("湿H2S", "湿硫化氢", "湿H₂S", "氢致开裂"), ("氢致开裂 硫化物应力腐蚀 氢鼓泡")),
    (("HCl", "氯化氢", "盐酸"), ("氯化物腐蚀 盐酸腐蚀 酸露点区分")),
    (("减薄", "局部腐蚀"), ("测厚分布 流速湍流 沉积下腐蚀")),
    (("碱式酸性水", "酸性水"), ("NH4HS 水相 关键组分 流速")),
)


class CandidateState(TypedDict, total=False):
    run_id: str
    question: str
    context: dict[str, Any]
    mode: str
    task_kind: str
    phase: str
    investigate_iteration: int
    review_round: int
    review_retry_count: int
    retry_query: str
    tool_budget: int
    tool_calls: list[dict[str, Any]]
    tool_call_keys: list[str]
    evidence_keys: list[str]
    citations: list[dict[str, Any]]
    hypotheses: list[dict[str, Any]]
    unknowns: list[str]
    gate_decisions: list[dict[str, Any]]
    auditor_findings: list[dict[str, Any]]
    skeptic_findings: list[dict[str, Any]]
    review_rows: list[dict[str, Any]]
    disagreements: list[dict[str, Any]]
    output: dict[str, Any]
    events: list[dict[str, Any]]
    query_variants: list[str]
    professional_queries: list[str]
    professional_plan: list[dict[str, Any]]
    professional_mode: bool
    professional_intent: str
    last_iteration_gain: int


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _event(state: CandidateState, name: str, phase: str, **fields: Any) -> dict[str, Any]:
    row = {
        "event": name, "phase": phase, "iteration": state.get("investigate_iteration", 0),
        "step_id": f"{state.get('run_id', 'run')}:{phase}:{len(state.get('events', [])) + 1}",
        "parent_step_id": None, "public_rationale": "", "retry_reason": "",
        "source_ids": [], "duration_ms": 0.0, **fields,
    }
    return row


def _default_registry() -> dict[str, Callable[..., dict[str, Any]]]:
    from app.runtime import load_harness

    registry = load_harness().build_registry()
    names = set(registry.names())
    if names != set(TEACHER_TOOLS):
        raise RuntimeError(f"teacher registry drift: expected {TEACHER_TOOLS}, got {sorted(names)}")
    return {name: registry.get(name).func for name in TEACHER_TOOLS}


def _is_standard_lookup(question: str) -> bool:
    return any(token in question for token in ("标准", "条款", "页码", "标准号"))


def _requires_wall_thickness(question: str) -> bool:
    """Require thickness only for thickness confirmation or an explicit RBI grade request."""
    return any(token in question for token in ("确认是否存在壁厚减薄", "是否存在壁厚减薄", "确认减薄", "是否减薄", "判断减薄", "风险等级", "风险分级", "RBI等级", "RBI风险"))


def _standard_relevance(question: str, source: dict[str, Any], canonical: dict[str, Any]) -> tuple[bool, str]:
    """Small deterministic code/clause/keyword gate; never treats a hit as semantic proof."""
    code_match = re.search(r"(?:GB\s*/?\s*T|TSG)\s*[0-9A-Za-z.]+(?:\s*[-—]\s*\d{4})?", question, re.I)
    standard = str(canonical.get("standard_code") or source.get("standard_code") or "")
    if code_match:
        requested_digits = "".join(re.findall(r"\d+", code_match.group(0)))
        actual_digits = "".join(re.findall(r"\d+", standard))
        if requested_digits and (not actual_digits or not actual_digits.startswith(requested_digits)):
            return False, "requested_standard_mismatch"
    query = re.sub(r"(?:GB\s*/?\s*T|TSG)\s*[0-9A-Za-z.]+(?:\s*[-—]\s*\d{4})?", " ", question, flags=re.I)
    clause_match = re.search(r"第?\s*(\d+(?:\.\d+)+)\s*条?", query)
    clause_no = str(canonical.get("clause_no") or source.get("clause_no") or "")
    if clause_match:
        return (clause_no == clause_match.group(1), "requested_clause_match" if clause_no == clause_match.group(1) else "requested_clause_mismatch")

    query = re.sub(r"标准|条款|标准号|查询|检索|请问|请查找|帮我|是什么|有哪些|如何|适用|第\s*\d+(?:\.\d+)+\s*条?", " ", query)
    query = re.sub(r"\s+", "", query).lower()
    terms = set(re.findall(r"[a-z0-9]{2,}", query))
    terms.update(query[i:i + 2] for i in range(max(0, len(query) - 1)) if re.search(r"[\u4e00-\u9fff]", query[i:i + 2]))
    terms -= {"什么", "如何", "哪些", "以及", "设备", "可能", "情况", "查询", "问题", "规定", "要求"}
    haystack = " ".join(str(canonical.get(key) or source.get(key) or "") for key in ("title", "content_raw", "clause_no", "standard_code")).lower()
    if not terms:
        return False, "query_has_no_specific_topic"
    return (any(term in haystack for term in terms), "topic_match" if any(term in haystack for term in terms) else "topic_mismatch")


def _query_variant(question: str, iteration: int) -> str:
    """RULE_DEMO query rewrite: deterministic, minimal, and inspectable."""
    text = re.sub(r"\s+", " ", question).strip()
    if iteration == 0:
        return text
    for token in ("请问", "帮我", "设备", "情况", "可能是什么", "如何处理"):
        text = text.replace(token, " ")
    text = re.sub(r"[，,。！？?；;]+", " ", text)
    return re.sub(r"\s+", " ", text).strip() or "设备损伤机理 标准条款"


def _expand_query_terms(question: str) -> list[str]:
    """Small multi-domain controlled vocabulary; expansions are retrieval hints, not facts."""
    q=str(question or "")
    expansions=[]
    for terms, expansion in _QUERY_SYNONYMS:
        if any(term.lower() in q.lower() for term in terms):
            expansions.append(str(expansion))
    return list(dict.fromkeys(expansions))


def _scc_concept_answer() -> str:
    """General concept explanation; deliberately independent of equipment evidence."""
    return ("应力腐蚀开裂（SCC）是材料在**拉应力**与特定腐蚀环境共同作用下发生的脆性或准脆性开裂。通常需要三类条件同时具备："
            "①足以驱动裂纹的拉应力（可来自载荷、残余应力或冷作）；②对该环境敏感的材料/组织状态；③能促发该材料开裂的介质环境。"
            "裂纹可从表面或局部应力集中处萌生并扩展，宏观塑性变形可能不明显；具体裂纹形态、方向和速率取决于材料—环境—应力组合。"
            "排查时应分别核实材料牌号/热处理与焊接残余应力、介质组成和温度、裂纹位置与走向，并用适合的无损检测确认；仅有腐蚀介质或仅有应力都不足以确诊SCC。"
            "这是一般机理解释，不是对某台设备的诊断或安全许可。")


def _source_relation(question: str, source: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Conservative lexical/anchor rerank metadata; never upgrades applicability to true."""
    context = context or {}
    media = context.get("medium") or context.get("raw_medium") or []
    media = media if isinstance(media, list) else [media]
    q=(str(question or "")+" "+" ".join(str(item) for item in media if item)+" "+" ".join(_expand_query_terms(question))).lower()
    text=" ".join(str(source.get(k) or "") for k in ("title","content_raw","snippet","standard_code")).lower()
    if re.search(r"碱式酸性水|酸性水",q) and re.search(r"酸性水腐蚀|碱式酸性水|硫氢化铵|nh4hs",text,re.I):
        return {"relation":"topic_overlap_candidate","score":1.0,"reason_code":"acid_water_scope_anchor_match",
                "may_support_claim":False,"applicability":"UNKNOWN"}
    impact_query=bool(re.search(r"磕碰|碰撞|撞击|机械损伤|壳体.{0,4}损伤",q,re.I))
    if impact_query:
        # Query-specific lexical anchors from the frozen TSG 21 clauses. This
        # is a transparent allowlist for candidate ranking, not a semantic model
        # and not an applicability determination.
        # Component-specific collisions can mention "mechanical damage" but
        # do not define shell acceptance (e.g. refractory lining or rupture
        # disc installation). Keep them cited, never promote them.
        title_text=str(source.get("title") or "").lower()
        if re.search(r"耐火材料退化|爆破片检验|再热裂纹|螺柱检验",title_text):
            return {"relation":"low_relevance_candidate","score":0.0,"reason_code":"impact_query_component_scope_mismatch",
                    "may_support_claim":False,"applicability":"UNKNOWN"}
        pressure_vessel_scope=bool(re.search(r"压力容器",text))
        impact_clause=bool(re.search(r"机械损伤|机械碰撞|机械冲击",text) and
                           re.search(r"环境开裂|表面缺陷检测|机械损伤现象",text))
        repair_assessment=bool(re.search(r"安全状况等级",text) and
                               re.search(r"修理结果|改造或者修理|检验结果综合评定",text))
        if pressure_vessel_scope and (impact_clause or repair_assessment):
            return {"relation":"topic_overlap_candidate","score":1.0,"reason_code":"impact_scope_anchor_match",
                    "may_support_claim":False,"applicability":"UNKNOWN"}
        if re.search(r"检验周期",text):
            return {"relation":"low_relevance_candidate","score":0.0,"reason_code":"impact_query_known_collision_family",
                    "may_support_claim":False,"applicability":"UNKNOWN"}
    qchars=re.sub(r"\s+", "", q)
    # Contrasting process families are labeled as likely relation mismatch, not deleted.
    hcl_query = re.search(r"(?<![a-z0-9])hcl(?![a-z0-9])|氯化氢|盐酸",q,re.I)
    h2s_query = re.search(r"湿\s*h2s|湿硫化氢|湿h₂s|(?<![a-z0-9])h2s(?![a-z0-9])|h₂s|氢致开裂",q,re.I)
    # Known collision topics seen in local retrieval: a lexical token such as
    # "硫"/"腐蚀" must not make sulfuric-acid, soil, irradiation, overheating,
    # or combustion mechanisms look like HCl / wet-H2S mechanism evidence.
    # This remains a soft candidate label; inspection-method clauses are not
    # discarded merely because the mechanism family differs.
    pairs=[
        (hcl_query, re.search(r"烟气|烟道|高含氧气体|燃烧.{0,6}爆炸|硫酸腐蚀|硫酸露点|土壤腐蚀|辐照脆化|过热",text), "HCl_vs_non_HCl_mechanism_family"),
        (h2s_query, re.search(r"燃灰|烟气|高含氧气体|燃烧.{0,6}爆炸|微生物腐蚀|硫酸露点|硫酸腐蚀|土壤腐蚀|辐照脆化|过热",text), "wet_h2s_vs_other_corrosion_family"),
    ]
    for query_match, source_match, reason in pairs:
        if query_match and source_match:
            return {"relation":"low_relevance_candidate","score":0.0,"reason_code":reason,
                    "may_support_claim":False,"applicability":"UNKNOWN"}
    source_text=" ".join(str(source.get(k) or "") for k in ("title","content_raw","snippet"))
    if not source_text.strip():
        return {"relation":"relation_unverified","score":None,"reason_code":"no_source_semantics_available",
                "may_support_claim":False,"applicability":"UNKNOWN"}
    latin=set(re.findall(r"[a-z0-9]{2,}",q))
    latin_src=set(re.findall(r"[a-z0-9]{2,}",text))
    zhq={qchars[i:i+2] for i in range(max(0,len(qchars)-1)) if re.search(r"[\u4e00-\u9fff]",qchars[i:i+2])}
    zhs={text[i:i+2] for i in range(max(0,len(text)-1)) if re.search(r"[\u4e00-\u9fff]",text[i:i+2])}
    stop={"设备","材料","问题","可能","分析","如何","属于","什么","情况","相关","进行","当前","依据","条件","标准","条款","腐蚀","损伤"}
    zhq={x for x in zhq if x not in stop}; zhs={x for x in zhs if x not in stop}
    denom=max(1,len(latin|zhq)); overlap=len((latin&latin_src)|(zhq&zhs)); score=overlap/denom
    if score>=0.2:
        relation,reason="topic_overlap_candidate","lexical_topic_overlap_only"
    elif score>0:
        relation,reason="weak_relation_candidate","weak_lexical_overlap"
    elif not overlap:
        relation,reason="relation_unverified","insufficient_query_or_source_terms"
    else:
        relation,reason="unrelated_candidate","no_topic_overlap"
    return {"relation":relation,"score":round(score,3) if score is not None else None,"reason_code":reason,
            "may_support_claim":False,"applicability":"UNKNOWN"}


def route_task(state: CandidateState) -> dict[str, Any]:
    question = state.get("question", "")
    context = state.get("context", {})
    intent = classify_intent(question, context)
    q_compact=re.sub(r"\s+", "", question or "")
    has_device_issue=bool(_DEVICE_HAZARD.search(q_compact) and (_DEVICE_WORD.search(q_compact) or context.get("equipment") or context.get("equipment_type")))
    asks_concept=bool(_CONCEPT_ASK.search(q_compact))
    # Explicit concept asks (not about this unit) must remain useful without
    # requesting material/medium. Device hazards in a greeting are engineering,
    # not small talk.
    if asks_concept and _CONCEPT_SCC.search(q_compact) and not has_device_issue:
        kind="concept"
    elif asks_concept and has_device_issue and _MIXED_CUE.search(q_compact):
        kind="mixed_investigation"
    elif has_device_issue and intent=="general_chat":
        kind="hypothesis_exploration"
    elif intent == "general_chat" and re.search(r"湿\s*h2s|湿硫化氢|湿h₂s|氢致开裂|腐蚀机理|损伤机理", q_compact, re.I):
        kind="hypothesis_exploration"
    else:
        kind = ""
    # The legacy coarse router may label a short maintenance/standards prompt
    # as general chat when no equipment fields are present. A validated,
    # bounded professional plan is explicit engineering intent: preserve it
    # as an investigation instead of skipping the teacher tools entirely.
    professional_intents = classify_professional_intent(question) if state.get("professional_mode") else []
    if not kind and intent == "general_chat" and any(name in professional_intents for name in (
            "MaintenanceSafety", "StandardsLookup", "RBIGrade", "MechanismExploration", "DeviceInvestigation")):
        intent = "hypothesis_exploration"
    if kind:
        pass
    elif intent in {"general_chat", "context_conflict", "standard_lookup", "hypothesis_exploration",
                  "device_diagnosis", "deterministic_rbi_grade"}:
        kind = intent
    else:  # Unknown or incomplete engineering requests remain bounded exploration.
        kind = "hypothesis_exploration"
    missing = []
    if kind in {"hypothesis_exploration", "device_diagnosis", "deterministic_rbi_grade", "mixed_investigation"}:
        if not context.get("material"):
            missing.append("material")
        if not context.get("medium"):
            missing.append("medium")
    if kind == "deterministic_rbi_grade":
        for field_name in ("equipment_type", "pressure_mpa", "service_years"):
            if context.get(field_name) is None:
                missing.append(field_name)
    # A mechanism question with no valid material/medium is an exploration,
    # not a failed device diagnosis. Search only official local clauses.
    if kind == "device_diagnosis" and (not context.get("material") or not context.get("medium")):
        kind = "hypothesis_exploration"
    professional_intent = ",".join(classify_professional_intent(question)) if state.get("professional_mode") else ""
    professional_plan=state.get("professional_plan") or []
    professional_queries=([str(row.get("query","")) for row in professional_plan]
                          if professional_plan else
        (_focused_queries(state, question)[:MAX_INVESTIGATIONS]
                           if state.get("professional_mode") and kind not in {"general_chat", "context_conflict", "concept"} else []))
    unknown_enums = context.get("_context_unknown_enums") or {}
    for field_name, raw_values in unknown_enums.items():
        for value in raw_values if isinstance(raw_values, list) else [raw_values]:
            missing.append(f"unmapped_{field_name}:{value}")
    return {
        "task_kind": kind, "phase": "route",
        "unknowns": list(dict.fromkeys([*state.get("unknowns", []), *missing])),
        "professional_intent": professional_intent,
        "professional_queries": professional_queries,
        "professional_plan": professional_plan,
        "events": [*state.get("events", []), _event(state, "phase_started", "route", public_rationale=f"route={kind}")],
    }


def evidence_gate(state: CandidateState) -> dict[str, Any]:
    """Pure control decision. Provenance counts as E0/E1 only, never semantic proof."""
    kind = state.get("task_kind")
    iteration = state.get("investigate_iteration", 0)
    budget = state.get("tool_budget", MAX_TOOL_CALLS)
    citations = state.get("citations", [])
    measured = state.get("context", {}).get("evidence", {})
    missing_measurement = kind in {"diagnosis", "device_diagnosis"} and _requires_wall_thickness(state.get("question", "")) and "wall_thinning" not in measured
    if kind == "missing_context":
        action, reason = "ask_user", "required_material_or_medium_missing"
    elif kind == "deterministic_rbi_grade" and state.get("unknowns"):
        action, reason = "ask_user", "risk_grade_inputs_missing"
    elif budget <= 0:
        action, reason = "report", "tool_budget_exhausted"
    elif state.get("professional_mode") and iteration < len(state.get("professional_queries", [])):
        action, reason = "investigate", "bounded_professional_query_variants_remaining"
    elif state.get("last_iteration_gain", 0) == 0 and iteration > 1:
        action, reason = "abstain", "zero_information_gain"
    elif not citations and iteration < MAX_INVESTIGATIONS:
        action, reason = "investigate", "retrieval_has_no_traceable_source"
    elif missing_measurement:
        action, reason = "ask_user", "field_measurement_required"
    elif kind in {"diagnosis", "device_diagnosis"}:
        action, reason = "review", "grounded_hypothesis_requires_independent_review"
    else:
        action, reason = "report", "source_traceable_standard_lookup"
    decision = {
        "next_action": action, "reason_codes": [reason],
        "missing_fields": ["wall_thinning"] if missing_measurement else [],
        "new_evidence_count": state.get("last_iteration_gain", 0),
        "budget_remaining": budget,
    }
    return {"phase": "evidence_gate", "gate_decisions": [*state.get("gate_decisions", []), decision],
            "events": [*state.get("events", []), _event(state, "evidence_gate", "evidence_gate", public_rationale=reason)]}


def _tool_args(name: str, state: CandidateState, query: str) -> dict[str, Any]:
    context = state.get("context", {})
    if name == "standard_clause_search":
        return {"keyword": query, "top_k": 5}
    if name == "damage_mechanism_query":
        args: dict[str, Any] = {"material": context["material"], "medium": context["medium"]}
        for field_name in ("equipment_type", "temperature_c"):
            if context.get(field_name) is not None:
                args[field_name] = context[field_name]
        evidence = context.get("evidence")
        if evidence:
            args["evidence"] = evidence
        return args
    if name == "rbi_lookup":
        args = {"equipment_type": context["equipment_type"], "material": context["material"]}
        for field_name in ("mechanism", "medium", "temperature_c", "pressure_mpa", "service_years"):
            if context.get(field_name) is not None:
                args[field_name] = context[field_name]
        return args
    raise ValueError(f"not a teacher tool: {name}")


def _selected_tools(state: CandidateState) -> list[str]:
    kind = state.get("task_kind")
    if kind == "standard_lookup":
        return ["standard_clause_search"]
    if kind == "hypothesis_exploration":
        return ["standard_clause_search"]
    if kind == "mixed_investigation":
        return ["standard_clause_search"]
    if kind == "mixed_investigation":
        return ["standard_clause_search"]
    if kind == "deterministic_rbi_grade":
        context = state.get("context", {})
        required = ("equipment_type", "material", "pressure_mpa", "service_years")
        return ["rbi_lookup", "standard_clause_search"] if all(context.get(key) is not None for key in required) else []
    if kind not in {"diagnosis", "device_diagnosis"}:
        return []
    # RBI lookup is only called with explicit factors; a result is not itself
    # authorized to establish device risk.
    tools = ["damage_mechanism_query", "standard_clause_search"]
    context = state.get("context", {})
    if state.get("professional_mode") and (context.get("_context_unknown_enums") or {}).get("medium"):
        tools.remove("damage_mechanism_query")
    if all(context.get(key) is not None for key in ("equipment_type", "material", "pressure_mpa", "service_years")):
        tools.append("rbi_lookup")
    return tools


def _call_with_retry(fn: Callable[..., Any], args: dict[str, Any]) -> tuple[Any, int, str, float]:
    error = ""
    started = time.perf_counter()
    for attempt in (1, 2):
        try:
            result = fn(**args)
            if not isinstance(result, dict):
                raise TypeError("tool result must be a dictionary")
            return result, attempt, "", round((time.perf_counter() - started) * 1000, 3)
        except Exception as exc:  # provider/tool errors terminate at this boundary
            error = f"{type(exc).__name__}: {exc}"
    return {"status": "error", "in_domain": True, "result": {}, "source": [], "message": error}, 2, error, round((time.perf_counter() - started) * 1000, 3)


def _source_rows(result: dict[str, Any]) -> list[dict[str, Any]]:
    rows = result.get("source")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict) and isinstance(row.get("clause_id"), str) and row["clause_id"]]


def _a2_candidate_lookup(query: str, top_k: int = 5) -> dict[str, Any]:
    """Read-only A2 pointer lookup; candidates are never citations or applicability proof."""
    root = Path(__file__).resolve().parents[1] / "knowledge" / "retrieval" / "r2_candidate_v1"
    try:
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        if (manifest.get("source_sha256") != "a8151797ba15a6a7452dd83aaec9fab4c0a815724ca45062eb1e2bac7b4d49ef"
                or manifest.get("human_reviewed") is not False
                or manifest.get("applicability_authority") != "none; all candidates remain UNKNOWN until case-specific review"):
            return {"status": "index_manifest_rejected", "candidates": []}
        aliases_doc = json.loads((root / "term_aliases.json").read_text(encoding="utf-8"))
        aliases = aliases_doc.get("aliases", {}) if aliases_doc.get("authority") == "query_rewrite_only" else {}
        expanded = [query]
        lowered = query.casefold()
        for phrase in sorted(aliases, key=len, reverse=True):
            if phrase.casefold() in lowered:
                expanded.extend(str(item) for item in aliases[phrase] if isinstance(item, str))
        terms = list(dict.fromkeys(term for phrase in expanded
                                   for term in re.findall(r"[\u3400-\u9fff]{2,}|[a-z0-9.+-]{2,}", phrase.casefold())))
        rows = [json.loads(line) for line in (root / "clauses.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        ranked = []
        for row in rows:
            title = str(row.get("title") or "").casefold()
            tags = " ".join(str(tag) for tag in row.get("scenario_tags", [])).casefold()
            haystack = title + " " + tags + " " + str(row.get("clause_id", "")).casefold()
            matched = [term for term in terms if term and term in haystack]
            if not matched:
                continue
            score = sum(2 if term in title else 1 for term in set(matched))
            ranked.append((score, str(row.get("clause_id") or ""), row))
        ranked.sort(key=lambda item: (-item[0], item[1]))
        candidates = []
        for score, _, row in ranked[:max(0, min(int(top_k), 5))]:
            candidates.append({key: row.get(key) for key in (
                "clause_id", "standard_code", "clause_no", "printed_page", "excerpt_ref",
                "source_hash", "knowledge_type", "title", "contextual_predicates", "review_state")})
            candidates[-1].update({"source_record_present": True, "applicability": "UNKNOWN",
                                   "semantic_relevance": "UNKNOWN_UNTIL_QUERY_REVIEW",
                                   "evidence_level": "E0", "may_support_claim": False,
                                   "candidate_score": score})
        return {"status": "ok", "index_version": manifest.get("index_version"),
                "candidate_count": len(candidates), "candidates": candidates,
                "authority": "pointer_only_not_citation_or_applicability"}
    except (OSError, ValueError, TypeError, KeyError):
        return {"status": "index_unavailable", "candidates": []}


def _focused_queries(state: CandidateState, original_query: str) -> list[str]:
    """Bounded query variants with one source-vocabulary expansion from official local data."""
    from backend.professional_answers import plan_teacher_queries
    context=state.get("context",{})
    plans=plan_teacher_queries(original_query,context,max_queries=5)
    for expansion in _expand_query_terms(original_query):
        candidate=f"{original_query} {expansion}"[:400]
        if candidate not in plans:
            plans.append(candidate)
    # For known process media, align one slot with the nearest official title
    # found in the read-only teacher clause index. Search hints are not evidence.
    if plans and not re.search(r"壳体|承压边界|压力容器",original_query):
        try:
            from orchestration.evidence_audit import load_clause_index
            media=context.get("medium") or context.get("raw_medium") or []
            media=media if isinstance(media,list) else [media]
            index=load_clause_index()
            candidates=[]
            for row in index.values():
                title=str(row.get("title") or "")
                if title and any(str(m) in title or str(m) in str((row.get("applicable_conditions") or {}).get("other") or "") for m in media if m):
                    candidates.append(title)
            if candidates:
                dynamic=" ".join([str(x) for x in media if x][:2]+[candidates[0],"适用条件 影响因素"])
                if dynamic not in plans:
                    if len(plans)>=3: plans[-1]=dynamic
                    else: plans.append(dynamic)
        except (OSError,ValueError,TypeError):
            pass
    return list(dict.fromkeys(plans))[:5]


def investigator(state: CandidateState, tools: dict[str, Callable[..., Any]], canonical: dict[str, dict[str, Any]]) -> dict[str, Any]:
    iteration = state.get("investigate_iteration", 0) + 1
    retry_query = state.get("retry_query", "")
    professional_queries = state.get("professional_queries", [])
    if state.get("professional_mode") and iteration <= len(professional_queries):
        query = professional_queries[iteration - 1]
        if retry_query:
            query = f"{query} {retry_query}"[:600]
    else:
        query = (f"{_query_variant(state.get('question', ''), iteration - 1)} {retry_query}".strip()
                 if retry_query else _query_variant(state.get("question", ""), iteration - 1))
    calls = list(state.get("tool_calls", [])); keys = list(state.get("tool_call_keys", []))
    citations = list(state.get("citations", [])); known_citations={str(x.get("clause_id")) for x in citations}
    hypotheses = list(state.get("hypotheses", [])); known_hypotheses={str(x.get("source_clause_id") or (x.get("source_clause_ids") or [""])[0]) for x in hypotheses}
    new_evidence: list[str] = []; events = [*state.get("events", []), _event(state, "investigation_iteration", "investigate", iteration=iteration,
                  public_rationale=f"RULE_DEMO selected {state.get('task_kind')} evidence tools")]
    budget = state.get("tool_budget", MAX_TOOL_CALLS); used_queries=[]
    plan=state.get("professional_plan") or []
    if state.get("professional_mode") and iteration <= len(plan):
        selected=plan[iteration-1].get("tools",[])
        # Runtime backstop: even if caller bypasses the API validator, only the two
        # frozen read-only teacher tools can be selected.
        selected=[name for name in selected if name in {"damage_mechanism_query","standard_clause_search"}]
        selected=selected or _selected_tools(state)
    else:
        selected=_selected_tools(state)
    for name in selected:
        if budget <= 0: break
        # Professional mode already has a bounded multi-angle query plan. Do
        # exactly one planned search per investigation rather than expanding
        # every iteration into another hidden fan-out.
        queries = [query]
        for tool_query in queries:
            if budget <= 0: break
            used_queries.append(tool_query)
            args = _tool_args(name, state, tool_query)
            call_key = _digest({"tool": name, "args": args, "context": state.get("context", {})})
            if call_key in keys: continue
            result, attempts, error, duration_ms = _call_with_retry(tools[name], args)
            keys.append(call_key); budget=max(0,budget-attempts)
            raw_rows=_source_rows(result); rejected=[]; rows=raw_rows
            if name == "standard_clause_search" and state.get("task_kind") == "standard_lookup":
                rows=[]
                for row in raw_rows:
                    relevant, reason = _standard_relevance(state.get("question", ""), row, canonical.get(str(row.get("clause_id")), {}))
                    if relevant: rows.append(row)
                    else: rejected.append({"clause_id":str(row.get("clause_id", "")),"reason":reason})
            relation_by_id={str(row["clause_id"]):_source_relation(
                state.get("question",""),{**canonical.get(str(row["clause_id"]),{}),**row},state.get("context",{})) for row in rows}
            rows.sort(key=lambda row:(-float(relation_by_id[str(row["clause_id"])]["score"] or -1),str(row["clause_id"])))
            source_ids=sorted({str(row["clause_id"]) for row in rows})
            ev_key=_digest({"tool":name,"source_ids":source_ids,"result":result.get("result",{})})
            if source_ids and ev_key not in state.get("evidence_keys", []): new_evidence.append(ev_key)
            for row in rows:
                cid=str(row["clause_id"])
                if cid not in known_citations:
                    citations.append({**row,"tool":name,"semantic_relation":relation_by_id.get(cid) or _source_relation(state.get("question",""),{**canonical.get(cid,{}),**row},state.get("context",{})),
                                      "verification_level":"E0","review_status":"draft_needs_review"}); known_citations.add(cid)
            call={"tool":name,"args":args,"result":result,"selected_sources":rows,"rejected_sources":rejected,"attempts":attempts,
                  "status":"error" if error else result.get("status","ok"),"error":error,"duration_ms":duration_ms,
                  "call_key":call_key,"source_ids":source_ids,"iteration":iteration}
            calls.append(call)
            event_no=len(calls)
            events.extend([
                _event(state,"tool_called","investigate",iteration=iteration,step_id=f"{state.get('run_id')}:{name}:{event_no}",tool=name,args=args),
                _event(state,"tool_result","investigate",iteration=iteration,step_id=f"{state.get('run_id')}:{name}:{event_no}",tool=name,
                    status=("not_found" if name=="standard_clause_search" and raw_rows and not rows else call["status"]),attempts=attempts,
                    source_ids=source_ids,sources=[{k:row.get(k) for k in ("clause_id","standard_code","clause_no","page","verification_level")} for row in rows],
                    result={"status":"not_found" if name=="standard_clause_search" and raw_rows and not rows else call["status"],
                            "source":[{k:row.get(k) for k in ("clause_id","standard_code","clause_no","page","verification_level")} for row in rows]},
                    rejected_sources=rejected,retry_reason=error,duration_ms=duration_ms)])
            if name == "damage_mechanism_query":
                found=(result.get("result",{}).get("mechanisms",[]) if isinstance(result.get("result"),dict) else [])
                for item in found:
                    if isinstance(item,dict):
                        item_cid=str(item.get("clause_id") or "")
                        item_relation=relation_by_id.get(item_cid)
                        if not item_relation or item_relation.get("relation") != "topic_overlap_candidate":
                            # Tool-returned mechanism names are candidates too;
                            # never bypass the same source-relation promotion gate.
                            continue
                        hypotheses.append({"claim_id":f"{state.get('run_id')}-h{len(hypotheses)+1}","text":str(item.get("name","candidate")),
                            "source_clause_ids":[item_cid],"kind":"engineering_hypothesis",
                            "semantic_relation":item_relation,"probability":None,"risk_level":None,
                            "verification_level":"E0","review_status":"requires_human_review"})
            elif name == "standard_clause_search" and state.get("task_kind") in {"hypothesis_exploration","mixed_investigation"}:
                context=state.get("context",{})
                for row in rows:
                    cid=str(row["clause_id"])
                    if cid in known_hypotheses: continue
                    relation=relation_by_id.get(cid) or _source_relation(state.get("question",""),row,state.get("context",{}))
                    if relation["relation"] != "topic_overlap_candidate":
                        continue  # Keep weak/unknown sources cited, but do not promote them to hypotheses.
                    canonical_row=canonical.get(cid,{})
                    conditions=canonical_row.get("applicable_conditions") or row.get("applicable_conditions") or {}
                    conditions=conditions if isinstance(conditions,dict) else {}
                    checks=[]; missing=[]; mismatch=False
                    for field_name in ("material","medium","equipment_type"):
                        allowed=conditions.get(field_name) or []; actual=context.get(field_name)
                        actuals=actual if isinstance(actual,list) else ([actual] if actual not in (None,"",[]) else [])
                        if not allowed: checks.append({"field":field_name,"status":"not_specified_in_source"})
                        elif not actuals: missing.append(field_name);checks.append({"field":field_name,"status":"unknown","source_values":allowed})
                        elif all(v in allowed for v in actuals): checks.append({"field":field_name,"status":"matched","source_values":allowed})
                        else: mismatch=True;checks.append({"field":field_name,"status":"mismatch","observed_values":actuals,"source_values":allowed})
                    label="暂无法判断" if mismatch else "有条件适用" if missing or any(x["status"]=="not_specified_in_source" for x in checks) else "较匹配"
                    hypotheses.append({"claim_id":f"{state.get('run_id')}-h{len(hypotheses)+1}","text":str(canonical_row.get("title") or row.get("title") or "标准条款候选"),
                        "kind":"source_conditioned_direction","source_clause_ids":[cid],"applicability_label":label,"applicable_conditions":conditions,
                        "condition_checks":checks,"exclusion_conditions":canonical_row.get("exclusion_conditions") or [],
                        "source_excerpt":str(canonical_row.get("content_raw") or row.get("snippet") or "")[:500],
                        "required_field_evidence":list(dict.fromkeys([*missing,"现场损伤形貌","检测/测厚结果","温度与压力范围"])),
                        "semantic_relation":relation,"probability":None,"risk_level":None,"verification_level":"E0","review_status":"requires_human_review"})
                    known_hypotheses.add(cid)
    return {"phase":"investigate","investigate_iteration":iteration,"tool_calls":calls,"tool_call_keys":keys,
            "evidence_keys":list(dict.fromkeys([*state.get("evidence_keys",[]),*new_evidence])),"citations":citations,
            "hypotheses":hypotheses,"tool_budget":budget,"last_iteration_gain":len(new_evidence),
            "query_variants":list(dict.fromkeys([*state.get("query_variants",[]),*used_queries])),"retry_query":"","events":events}


def _auditor(state: CandidateState, canonical: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    sources = {str(row.get("clause_id")): row for call in state.get("tool_calls", [])
               for row in _source_rows(call.get("result", {}))}
    rows = []
    claims = state.get("hypotheses", []) or [{"claim_id": f"{state.get('run_id')}-source", "source_clause_ids": [c.get("clause_id") for c in state.get("citations", [])]}]
    for claim in claims:
        ids = claim.get("source_clause_ids", []) or [""]
        for cid in ids:
            current, official = sources.get(str(cid)), canonical.get(str(cid))
            checks = {key: bool(current and official and current.get(key) == official.get(key)) for key in ("clause_id", "standard_code", "clause_no", "page")}
            grade = "E1" if all(checks.values()) and cid else "E0"
            rows.append(AuditFinding(state.get("run_id", "run"), claim["claim_id"], str(cid), "evidence_auditor",
                                     f"review-{state.get('review_round', 1)}", {"grade": grade, "checks": checks, "verdict": "unresolved"}))
    return rows


def _skeptic(state: CandidateState) -> list[SkepticFinding]:
    # Independent view derives from raw field measurements + formal source rows;
    # it never treats Investigator prose as evidence and cannot issue a grade.
    ids = sorted({str(c.get("clause_id")) for c in state.get("citations", []) if c.get("clause_id")}) or [""]
    claims = state.get("hypotheses", []) or [{"claim_id": f"{state.get('run_id')}-source"}]
    findings = []
    for claim in claims:
        for cid in claim.get("source_clause_ids", []) or ids:
            measurements = state.get("context", {}).get("evidence", {})
            verdict = "unresolved" if not measurements else "supported_for_review_only"
            findings.append(SkepticFinding(state.get("run_id", "run"), claim["claim_id"], str(cid), "skeptic",
                                          f"review-{state.get('review_round', 1)}", {"verdict": verdict, "field_evidence_keys": sorted(measurements)}))
    return findings


def _review_branch(state: CandidateState, role: str, canonical: dict[str, dict[str, Any]], reviewer: Callable[[CandidateState], Any] | None) -> dict[str, Any]:
    if reviewer is not None:
        value = reviewer(state)
        if role == "auditor":
            return {"auditor_findings": list(value)}
        return {"skeptic_findings": list(value)}
    if role == "auditor":
        return {"auditor_findings": _auditor(state, canonical)}
    return {"skeptic_findings": _skeptic(state)}


def _review_merge(state: CandidateState) -> dict[str, Any]:
    rows = merge_findings(state.get("auditor_findings", []), state.get("skeptic_findings", []))
    disagreements = [row for row in rows if row.get("conflict_requires_review")]
    return {"review_rows": rows, "disagreements": disagreements,
            "events": [*state.get("events", []), _event(state, "review_result", "review_merge", source_ids=[r.get("source_clause_id") for r in rows if r.get("source_clause_id")],
                              public_rationale="独立审查合并；冲突按E0保留，不采用first-wins")],
            "phase": "review_merge"}


def _review_gate(state: CandidateState) -> dict[str, Any]:
    retry_reasons = sorted({str(row.get("result", {}).get("retry_reason"))
                            for row in state.get("review_rows", [])
                            if row.get("result", {}).get("retry_reason") and not row.get("conflict_requires_review")})
    # Candidate professional retrieval has a strict query ceiling. Reviewers
    # may explain a gap in the report, but must not silently expand the search.
    can_retry = (not state.get("professional_mode") and bool(retry_reasons)
                 and state.get("review_retry_count", 0) < MAX_REVIEW_RETRIES
                 and state.get("tool_budget", 0) > 0)
    retry_query = retry_reasons[0] if can_retry else ""
    events = [_event(state, "retry_reason" if can_retry else "evidence_gate", "review_gate",
                     retry_reason=retry_query,
                     public_rationale="Reviewer提出可验证补证字段" if can_retry else "无可执行补证请求或修正预算耗尽")]
    return {"phase": "review_gate", "review_retry_count": state.get("review_retry_count", 0) + int(can_retry),
            "retry_query": retry_query,
            "gate_decisions": [*state.get("gate_decisions", []), {
                "next_action": "investigate" if can_retry else "report",
                "reason_codes": ["review_requested_targeted_recheck" if can_retry else "review_complete_or_retry_budget_exhausted"],
                "missing_fields": retry_reasons if can_retry else [],
                "new_evidence_count": 0, "budget_remaining": state.get("tool_budget", 0)}],
            "events": [*state.get("events", []), *events]}


def _report(state: CandidateState, canonical: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    kind = state.get("task_kind")
    if kind == "concept":
        status, conclusion = "concept_explanation", _scc_concept_answer()
    elif kind == "general_chat":
        status, conclusion = "general_chat", rule_chat_reply(state.get("question", ""))
    elif kind == "missing_context":
        status, conclusion = "needs_user_input", "请补充材质与介质后再检索。"
    elif kind == "context_conflict":
        status, conclusion = "needs_user_input", "表单与本条描述的设备字段存在冲突，请确认后再检索。"
    elif kind in {"hypothesis_exploration","mixed_investigation"}:
        # A traceable source candidate may still support an exploratory
        # workflow status even when the relation gate correctly withholds all
        # hypothesis promotion. The report must not imply that a weak citation
        # has become an engineering hypothesis.
        status = "exploratory_directions" if state.get("hypotheses") or state.get("citations") else "unresolved"
        conclusion = ("以下仅为标准来源中的候选方向，不是该设备诊断；适用条件未核实前不得据此确定风险等级。请补充标出的现场证据，并由工程师复核。"
                     if state.get("hypotheses") else "本地标准检索未取得可追溯条款，因此不能声称标准要求；仍可先给出一般工程排查方向，缺项保持未知，不确定设备机理或风险等级。")
    elif kind == "deterministic_rbi_grade":
        if state.get("unknowns"):
            status, conclusion = "needs_user_input", "确定性风险等级输入不完整；请补充缺失字段。当前不输出风险等级。"
        else:
            status, conclusion = "draft_for_review", "已检索RBI参考信息，但模型表或通用等级不等于设备级失效可能性、后果或风险等级；需完整现场证据和人工审核。"
    elif kind in {"diagnosis", "device_diagnosis"} and _requires_wall_thickness(state.get("question", "")) and "wall_thinning" not in state.get("context", {}).get("evidence", {}):
        status, conclusion = "insufficient_evidence", "缺少本次确认所需的现场测厚结果；结论保持待核，不输出设备风险等级。"
    elif not state.get("citations"):
        status, conclusion = "unresolved", "未取得可追溯出处；无法形成受证据支持的结论。"
    elif state.get("disagreements"):
        status, conclusion = "review_conflict", "并行审查存在冲突，按E0保守保留并转人工复核。"
    else:
        status, conclusion = "draft_for_review", "已取得本轮来源；该来源只证明可追溯性，不等同设备适用性或工程结论。"
    auditor_rows = [row for row in state.get("review_rows", []) if row.get("origin_agent") == "evidence_auditor"]
    standard_sources_valid = bool(state.get("citations")) and all(
        (expected := (canonical or {}).get(str(ref.get("clause_id")))) is not None
        and all(ref.get(key) == expected.get(key) for key in ("clause_id", "standard_code", "clause_no", "page"))
        for ref in state.get("citations", []))
    audit_sources_valid = bool(auditor_rows) and all(row.get("verification_level") == "E1" for row in auditor_rows)
    provenance_verified = standard_sources_valid if state.get("task_kind") in {"standard_lookup", "hypothesis_exploration"} else audit_sources_valid
    latencies=sorted(float(call.get("duration_ms",0) or 0) for call in state.get("tool_calls",[]))
    p50=latencies[min(len(latencies)-1,int((len(latencies)-1)*.50))] if latencies else None
    p95=latencies[min(len(latencies)-1,int((len(latencies)-1)*.95))] if latencies else None
    output = {"status": status, "conclusion": conclusion,
              "verification_level": "E1" if provenance_verified and not state.get("disagreements") and status == "draft_for_review" else "E0",
              "risk_level": None, "human_signed": False,
              "citations": state.get("citations", []), "hypotheses": state.get("hypotheses", []),
              "unknowns": state.get("unknowns", []), "tool_calls": len(state.get("tool_calls", [])),
              "tool_latency_ms":{"p50":round(p50,3) if p50 is not None else None,"p95":round(p95,3) if p95 is not None else None,"sample_count":len(latencies)},
              "review_rows": state.get("review_rows", []), "disagreements": state.get("disagreements", [])}
    return {"phase": "report", "output": output,
            "events": [*state.get("events", []), _event(state, "final", "report", source_ids=[c.get("clause_id") for c in state.get("citations", [])], public_rationale=status, output_status=status)]}


@dataclass
class IndustrialCandidate:
    """Factory for an isolated LangGraph candidate; injected tools are test doubles."""
    tool_registry: dict[str, Callable[..., Any]] | None = None
    clause_index: dict[str, dict[str, Any]] = field(default_factory=dict)
    auditor: Callable[[CandidateState], Any] | None = None
    skeptic: Callable[[CandidateState], Any] | None = None

    def __post_init__(self) -> None:
        if self.tool_registry is None:
            self.tool_registry = _default_registry()
        if set(self.tool_registry) != set(TEACHER_TOOLS):
            raise ValueError(f"exactly the three frozen teacher tools required: {TEACHER_TOOLS}")
        if not self.clause_index:
            from orchestration.evidence_audit import load_clause_index
            self.clause_index = load_clause_index()
        self.graph = self._build()

    def _build(self):
        from langgraph.graph import END, START, StateGraph

        tools = self.tool_registry
        canonical = self.clause_index
        auditor, skeptic = self.auditor, self.skeptic
        builder = StateGraph(CandidateState)
        builder.add_node("route", route_task)
        builder.add_node("investigator", lambda s: investigator(s, tools, canonical))
        builder.add_node("evidence_gate", evidence_gate)
        builder.add_node("auditor", lambda s: _review_branch(s, "auditor", canonical, auditor))
        builder.add_node("skeptic", lambda s: _review_branch(s, "skeptic", canonical, skeptic))
        builder.add_node("merge", _review_merge)
        builder.add_node("review_gate", _review_gate)
        builder.add_node("report", lambda s: _report(s, canonical))
        builder.add_edge(START, "route")
        builder.add_conditional_edges("route", lambda s: "report" if (
            s["task_kind"] in {"missing_context", "general_chat", "concept", "context_conflict"}
            or (s["task_kind"] == "deterministic_rbi_grade" and bool(s.get("unknowns")))
        ) else "investigator", {"report": "report", "investigator": "investigator"})
        builder.add_edge("investigator", "evidence_gate")
        def after_gate(s: CandidateState) -> str:
            action = s.get("gate_decisions", [])[-1]["next_action"]
            if action == "investigate" and s.get("investigate_iteration", 0) < MAX_INVESTIGATIONS and s.get("tool_budget", 0) > 0:
                return "investigator"
            if action == "review":
                return "review"
            return "report"
        builder.add_conditional_edges("evidence_gate", after_gate,
                                      {"investigator": "investigator", "review": "review_dispatch", "report": "report"})
        # A dedicated dispatch node keeps the role fan-out explicit in the trace.
        builder.add_node("review_dispatch", lambda s: {"phase": "review_dispatch", "review_round": s.get("review_round", 0) + 1,
                                                         "events": [*s.get("events", []), _event(s, "review_started", "review_dispatch", public_rationale="独立Auditor与Skeptic并行") ]})
        builder.add_edge("review_dispatch", "auditor")
        # Explicit fan-out: both reviewers run from the same immutable snapshot.
        builder.add_edge("review_dispatch", "skeptic")
        builder.add_edge(["auditor", "skeptic"], "merge")
        builder.add_edge("merge", "review_gate")
        builder.add_conditional_edges("review_gate",
                                      lambda s: "investigator" if s["gate_decisions"][-1]["next_action"] == "investigate" else "report",
                                      {"investigator": "investigator", "report": "report"})
        builder.add_edge("report", END)
        return builder.compile()

    def run(self, question: str, context: dict[str, Any] | None = None, *, run_id: str | None = None,
            tool_budget: int = MAX_TOOL_CALLS, recursion_limit: int = 40,
            on_event: Callable[[dict[str, Any]], None] | None = None,
            professional_mode: bool = False, professional_plan: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        if not 0 <= tool_budget <= MAX_TOOL_CALLS:
            raise ValueError(f"tool_budget must be between 0 and {MAX_TOOL_CALLS}")
        started = time.perf_counter()
        initial: CandidateState = {
            "run_id": run_id or str(uuid4()), "question": question, "context": dict(context or {}),
            "mode": "RULE_DEMO", "task_kind": "", "phase": "start", "investigate_iteration": 0,
            "review_round": 0, "review_retry_count": 0, "retry_query": "",
            "tool_budget": tool_budget, "tool_calls": [], "tool_call_keys": [],
            "evidence_keys": [], "citations": [], "hypotheses": [], "unknowns": [], "gate_decisions": [],
            "auditor_findings": [], "skeptic_findings": [], "review_rows": [], "disagreements": [],
            "output": {}, "events": [], "query_variants": [], "last_iteration_gain": 0,
            "professional_mode": bool(professional_mode), "professional_queries": [],
            "professional_plan": list(professional_plan or []), "professional_intent": "",
        }
        final = dict(initial)
        sent = 0
        for update in self.graph.stream(initial, {"recursion_limit": recursion_limit}, stream_mode="updates"):
            for node, delta in update.items():
                if not isinstance(delta, dict):
                    continue
                final.update(delta)
                current_events = delta.get("events")
                if isinstance(current_events, list):
                    # Candidate nodes keep an append-only event list. Updates contain
                    # its current value, so only forward each new row to the durable sink.
                    for row in current_events[sent:]:
                        if on_event:
                            on_event(row)
                    sent = max(sent, len(current_events))
                elif node in {"auditor", "skeptic"} and on_event:
                    on_event(_event(final, "agent_completed", node, public_rationale=f"{node} independent review branch completed"))
        if not final.get("output"):
            raise RuntimeError("industrial graph ended without a report")
        a2_result = _a2_candidate_lookup(question)
        final["a2_retrieval"] = a2_result
        a2_event = _event(final, "a2_candidate_retrieval", "a2_index",
                          query_sha256=_digest({"query": question}),
                          index_version=a2_result.get("index_version"),
                          candidate_count=len(a2_result.get("candidates", [])),
                          candidates=a2_result.get("candidates", []),
                          status=a2_result.get("status"),
                          authority="pointer_only_not_citation_or_applicability")
        final["events"] = [*final.get("events", []), a2_event]
        if on_event:
            on_event(a2_event)
        final["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 3)
        final["output"]["elapsed_ms"] = final["elapsed_ms"]
        return final


def build_industrial_candidate(**kwargs: Any):
    """Convenience API: ``build_industrial_candidate(...).run(...)``."""
    return IndustrialCandidate(**kwargs)

