"""Mockable structured-intent boundary and deterministic safety policy for Aetheris V2 S1-A.

No network client or credential lookup lives here. A provider is an injected callable;
without explicit feature enablement or provider injection, routing is deterministic.
"""
from __future__ import annotations

import json
import re
from enum import Enum
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

MAX_SUBTASKS = 4
MAX_QUESTION_CHARS = 4000

class MainRoute(str, Enum):
    GENERAL = "GENERAL"
    STANDARD_LOOKUP = "STANDARD_LOOKUP"
    ENGINEERING = "ENGINEERING"
    MIXED = "MIXED"
    CLARIFICATION = "CLARIFICATION"

class TaskKind(str, Enum):
    GENERAL_EXPLANATION = "GENERAL_EXPLANATION"
    STANDARD_LOOKUP = "STANDARD_LOOKUP"
    MECHANISM_EXPLORATION = "MECHANISM_EXPLORATION"
    DEVICE_DIAGNOSIS = "DEVICE_DIAGNOSIS"
    RBI_ASSESSMENT = "RBI_ASSESSMENT"
    WRITING_SYNTHESIS = "WRITING_SYNTHESIS"
    CLARIFICATION_REQUIRED = "CLARIFICATION_REQUIRED"

class IntentSubtask(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str = Field(min_length=1, max_length=24, pattern=r"^[a-z][a-z0-9_-]*$")
    kind: TaskKind
    user_goal: str = Field(min_length=1, max_length=240)
    requires: list[str] = Field(default_factory=list, max_length=8)
    depends_on: list[str] = Field(default_factory=list, max_length=4)
    task_risk: str = Field(default="LOW", pattern=r"^(LOW|SAFETY_RELEVANT|HIGH_CONSEQUENCE)$")

class RouteDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    version: str = Field(default="v2a.1", pattern=r"^v2a\.1$")
    primary_route: MainRoute
    subtasks: list[IntentSubtask] = Field(default_factory=list, max_length=MAX_SUBTASKS)
    safety_relevance: bool
    confidence: float = Field(ge=0.0, le=1.0)
    reasons_public: list[str] = Field(default_factory=list, max_length=5)
    needs_clarification: bool = False
    clarification_question: str | None = Field(default=None, max_length=300)
    model_usage: dict[str, Any] = Field(default_factory=dict, max_length=8)

    @field_validator("reasons_public")
    @classmethod
    def cap_reasons(cls, v: list[str]) -> list[str]:
        if any(len(x) > 240 for x in v): raise ValueError("reason too long")
        return v

    @field_validator("model_usage")
    @classmethod
    def reject_authority_claims(cls, v: dict[str, Any]) -> dict[str, Any]:
        allowed = {"request_count", "source"}
        if set(v) - allowed:
            raise ValueError("model_usage is server-owned; model cannot assert authority or tool execution")
        return v

    @model_validator(mode="after")
    def validate_dag(self) -> "RouteDecision":
        ids=[x.id for x in self.subtasks]
        if len(ids)!=len(set(ids)): raise ValueError("duplicate subtask id")
        known=set(ids); seen=set()
        for task in self.subtasks:
            if any(dep not in known for dep in task.depends_on): raise ValueError("unknown dependency")
            if task.id in task.depends_on: raise ValueError("self dependency")
            if any(dep not in seen for dep in task.depends_on): raise ValueError("DAG must be topologically ordered")
            seen.add(task.id)
        if self.primary_route == MainRoute.MIXED and len(self.subtasks)<2:
            raise ValueError("MIXED requires at least two bounded subtasks")
        # A model must not disguise an engineering subtask as an apparently safe
        # general/standard answer. Structural validity is not safety authority.
        engineering_kinds = {TaskKind.MECHANISM_EXPLORATION, TaskKind.DEVICE_DIAGNOSIS, TaskKind.RBI_ASSESSMENT}
        contains_engineering = any(task.kind in engineering_kinds or task.task_risk in {"SAFETY_RELEVANT", "HIGH_CONSEQUENCE"} for task in self.subtasks)
        if contains_engineering and (not self.safety_relevance or self.primary_route not in {MainRoute.ENGINEERING, MainRoute.MIXED}):
            raise ValueError("engineering subtask requires safety-relevant engineering dispatch")
        return self

    def snapshot(self) -> dict[str, Any]:
        data=self.model_dump(mode="json")
        data["dispatch_route"] = dispatch_route(self).value
        return data

# Domain and intent cues are used as a conservative floor, not as a substitute for model semantics.
_DEVICE = re.compile(r"设备|装置|管道|管线|容器|换热器|反应器|反应釜|储罐|锅炉|泵|阀门|焊缝|焊接接头|弯头|塔器|蒸馏塔|塔|炉管|底板|管束|本台|这台|那台|那个设备|该设备|现场|测厚|壁厚|工况|运行|制冷装置",re.I)
_HAZARD = re.compile(r"裂纹|开裂|减薄|测厚|壁厚下降|数据下降|下降|上升|氯离子|点蚀|鼓泡|沉积|锈蚀|冲蚀|起跳|压降|泄漏|腐蚀|H2S|H₂S|湿硫化氢|氯化氢|HCl|氢致开裂|HIC|SOHIC|SSC|应力腐蚀|损伤|失效|异常|振动|温升|压力|运行|数据不足|资料不足|线性指示|缺陷|指示|温度|材质|材料|介质|工况|周期|失效可能性|失效后果|RBI风险|风险等级|风险分级|风险|还能运行|安全运行|能否|是否安全|单位",re.I)
_ENGINEERING_INTENT = re.compile(r"分析|诊断|判断|评估|研判|原因|机理|怎么办|怎么查|如何查|初查|检查|检测|核查|是否|能否|还能|等级|周期|建议|风险|措施|处理|为什么|为什么会|发生|出现|故障|异常|适用|影响|代表什么|意味着|怎么理解|补|列|梳理|哪些|区分|核对|取证|调查|继续运行|重新|重查|重梳|排查|重评",re.I)
_STANDARD = re.compile(r"GB\s*/?\s*T\s*\d|TSG\s*\d|标准|条款|第\s*\d+(?:\.\d+)*\s*条|表\s*\d+", re.I)
_STANDARD_ACTION = re.compile(r"查|检索|查询|原文|条文|条款|页码|哪一页|全文位置|写了什么|规定|定义|对应|是什么|如何|怎么|确定|标准怎么|标准中|按.*标准|根据.*标准",re.I)
_GENERAL_MIX = re.compile(r"你是谁|你是什么模型|你可以做什么|顺便|另外|同时|再.*(介绍|解释)|写成报告|整理成报告|总结成报告")
_TRANSFORM_ONLY = re.compile(r"翻译|润色|改写|校对|改成.*语气|改成.*中文|更通顺|保持事实不变|写一篇.*科普|写.*诗|广告语|课程大纲|翻译成|总结这段",re.I)

class LocalIntentPolicy:
    def __init__(self, legacy_classifier: Callable[[str, dict[str, Any] | None], str] | None = None):
        self.legacy_classifier=legacy_classifier

    def analyze(self, question: str) -> tuple[MainRoute, bool, list[IntentSubtask], list[str]]:
        q=str(question or "")[:MAX_QUESTION_CHARS]
        has_device=bool(_DEVICE.search(q)) and not bool(re.search(r"只查标准|不评估设备|不做设备研判|不涉及具体设备",q)); has_hazard=bool(_HAZARD.search(q))
        has_engineering=bool(_ENGINEERING_INTENT.search(q))
        # An explicit numbered clause is a lookup request even without a verb
        # (e.g. "GB/T 30579 标准第5.23条"). Keep it before general fallback.
        numbered_clause=bool(re.search(r"第\s*\d+(?:\.\d+)*\s*条?",q))
        has_standard=bool(numbered_clause or (_STANDARD.search(q) and (_STANDARD_ACTION.search(q) or re.search(r"GB\s*/?\s*T\s*\d|TSG\s*\d",q,re.I))) or (re.search(r"检索|查询|查找",q) and re.search(r"出处|条文|条款|规范|标准",q)))
        transform_only=bool(_TRANSFORM_ONLY.search(q)) and not (has_device and has_hazard and has_engineering and re.search(r"判断|分析|诊断|风险|安全|原因|检验周期",q))
        correction_context=bool(re.search(r"更正|改为|重新|重查|补充|前面|刚才|上面|之前|填错|待确认",q) and re.search(r"材质|材料|介质|温度|压力|工况|设备|管道|容器|裂纹|腐蚀|壁厚|测厚|周期",q)) or bool(re.search(r"改成|改为",q) and re.search(r"温度|压力|材质|材料|介质|工况",q))
        safety=bool((has_device and has_hazard and has_engineering) or
                    (has_hazard and has_engineering and re.search(r"现场|出现|发现|下降|上升|异常|泄漏|还能运行|裂纹|测厚|点蚀|鼓泡|减薄|缺陷",q)) or correction_context)
        explicit_lookup_only=bool(has_standard and re.search(r"只查|不评估设备|不需要设备研判|不做设备研判",q) and not re.search(r"这台|该设备|这只|这条管|现场.*(裂纹|泄漏|腐蚀|减薄)",q))
        if explicit_lookup_only:
            safety=False
        mechanism_question = bool(re.search(r"腐蚀机理|损伤机理|失效机理|机理方向|哪类腐蚀|属于哪类损伤|损伤模式", q))
        if mechanism_question and not has_standard and not transform_only and not explicit_lookup_only:
            return MainRoute.ENGINEERING, True, [IntentSubtask(id="exploration", kind=TaskKind.MECHANISM_EXPLORATION, user_goal="对专业损伤机理开展有来源、保留未知项的初步探索", task_risk="SAFETY_RELEVANT")], ["识别到专业损伤机理或模式问题；不依赖已填设备参数"]
        if transform_only and not safety:
            if has_standard:
                task=IntentSubtask(id="writing",kind=TaskKind.WRITING_SYNTHESIS,user_goal="忠实处理用户提供文本；不添加工程结论")
                return MainRoute.GENERAL,False,[task],["显式文字转换意图；不启动设备诊断"]
            return MainRoute.GENERAL,False,[IntentSubtask(id="writing",kind=TaskKind.WRITING_SYNTHESIS,user_goal="按用户要求忠实写作或转换文本")],["显式写作/翻译意图；不启动设备诊断"]
        if safety:
            tasks=[]
            if has_standard: tasks.append(IntentSubtask(id="standard",kind=TaskKind.STANDARD_LOOKUP,user_goal="查询明确提及的标准条款与出处",task_risk="SAFETY_RELEVANT"))
            risk_kind=TaskKind.RBI_ASSESSMENT if re.search(r"风险等级|风险分级|风险评估|风险分析|设备风险|风险是多少|检验周期|还能运行|是否安全|失效可能性|失效后果",q) else TaskKind.MECHANISM_EXPLORATION
            tasks.append(IntentSubtask(id="engineering",kind=risk_kind,user_goal="对设备问题开展有来源、保留未知项的专业初步分析",depends_on=["standard"] if tasks else [],task_risk="HIGH_CONSEQUENCE" if risk_kind==TaskKind.RBI_ASSESSMENT else "SAFETY_RELEVANT"))
            mixed=bool(_GENERAL_MIX.search(q) or (has_standard and len(tasks)>1) or (has_standard and re.search(r"分析|诊断|判断|评估",q)))
            if mixed:
                tasks.append(IntentSubtask(id="synthesis",kind=TaskKind.WRITING_SYNTHESIS,user_goal="仅整理已通过证据门禁的输出，不新增事实",depends_on=["engineering"],task_risk="SAFETY_RELEVANT"))
                return MainRoute.MIXED,True,tasks,["安全相关设备任务优先；普通子问与工程子问分离"]
            return MainRoute.ENGINEERING,True,tasks,["确定性安全门将设备安全请求优先送专业路径"]
        if has_standard:
            return MainRoute.STANDARD_LOOKUP,False,[IntentSubtask(id="standard",kind=TaskKind.STANDARD_LOOKUP,user_goal="从老师标准检索工具取得可追溯条款")],["检测到明确标准/条款查证意图"]
        if re.search(r"什么是|解释|介绍|讲讲|原理",q) and has_hazard and not has_device:
            return MainRoute.GENERAL,False,[IntentSubtask(id="explain",kind=TaskKind.GENERAL_EXPLANATION,user_goal="解释一般概念，不作现场判断")],["一般概念解释，不是现场设备结论"]
        # The existing classifier is retained only as a weak cue; never let its hello/about shortcut downgrade safety.
        legacy=self.legacy_classifier(q,{}) if self.legacy_classifier else "general_chat"
        if legacy in {"standard_lookup"}: return MainRoute.STANDARD_LOOKUP,False,[IntentSubtask(id="standard",kind=TaskKind.STANDARD_LOOKUP,user_goal="查证标准条文")],["兼容现有标准查询识别"]
        if legacy not in {"general_chat","standard_lookup"}:
            return MainRoute.ENGINEERING,True,[IntentSubtask(id="exploration",kind=TaskKind.MECHANISM_EXPLORATION,user_goal="专业初步探索并列出未知工况",task_risk="SAFETY_RELEVANT")],["兼容性门禁将现有专业分类保守送入专业路径"]
        return MainRoute.GENERAL,False,[IntentSubtask(id="general",kind=TaskKind.GENERAL_EXPLANATION,user_goal="普通对话")],["未发现标准查证或具体设备安全任务"]

def dispatch_route(decision: RouteDecision) -> MainRoute:
    if decision.safety_relevance or decision.primary_route in {MainRoute.ENGINEERING,MainRoute.MIXED}:
        return MainRoute.ENGINEERING
    return decision.primary_route

def _rule_decision(question: str, policy: LocalIntentPolicy) -> RouteDecision:
    route,safety,tasks,reasons=policy.analyze(question)
    return RouteDecision(primary_route=route,safety_relevance=safety,subtasks=tasks,confidence=0.55,reasons_public=reasons,needs_clarification=False,model_usage={"request_count":0,"source":"deterministic_fallback"})

def _decode_structured(raw: Any) -> RouteDecision:
    if isinstance(raw, RouteDecision): return raw
    if isinstance(raw, bytes): raw=raw.decode("utf-8")
    if isinstance(raw,str):
        if len(raw)>16000: raise ValueError("structured_response_too_large")
        return RouteDecision.model_validate_json(raw, strict=True)
    if not isinstance(raw,dict): raise ValueError("structured_response_not_object")
    return RouteDecision.model_validate(raw, strict=True)

def _gate(question: str, proposed: RouteDecision, policy: LocalIntentPolicy) -> RouteDecision:
    safe=_rule_decision(question,policy)
    # Local floor prevents model downgrade. For a clear safety request, route and required safety task are deterministic.
    if safe.safety_relevance:
        if not proposed.safety_relevance or dispatch_route(proposed)!=MainRoute.ENGINEERING:
            proposed=safe.model_copy(deep=True)
            proposed.reasons_public=["政策门升级模型建议：安全相关设备请求不能路由为普通聊天。",*safe.reasons_public][:5]
        elif proposed.primary_route not in {MainRoute.ENGINEERING,MainRoute.MIXED}:
            proposed=safe.model_copy(deep=True)
        return proposed
    if safe.primary_route==MainRoute.STANDARD_LOOKUP and proposed.primary_route==MainRoute.GENERAL:
        return safe.model_copy(deep=True)
    return proposed

class LLMStructuredIntentRouter:
    """Strict schema + policy gate; provider is injected and never created from credentials here."""
    def __init__(self, provider: Callable[[str], Any] | None=None, *, enabled: bool=False, policy: LocalIntentPolicy | None=None):
        self.provider=provider; self.enabled=bool(enabled); self.policy=policy or LocalIntentPolicy()

    def route(self, question: str) -> RouteDecision:
        q=str(question or "")[:MAX_QUESTION_CHARS]
        if not self.enabled: return _rule_decision(q,self.policy)
        if self.provider is None:
            d=_rule_decision(q,self.policy); d.model_usage={"request_count":0,"source":"fallback","fallback_reason":"provider_not_injected"}; return d
        prompt=json.dumps({"task":"Classify intent into the strict RouteDecision schema. Propose only; never authorize tools, facts, sources, risk grades, or human review.","question":q,"max_subtasks":MAX_SUBTASKS,"allowed_routes":[x.value for x in MainRoute],"schema":RouteDecision.model_json_schema()},ensure_ascii=False)
        try:
            proposed=_decode_structured(self.provider(prompt))
            candidate = proposed.model_copy(deep=True)
            decision=_gate(q,proposed,self.policy)
            gated = decision.model_dump(mode="json") != candidate.model_dump(mode="json")
            decision.model_usage={"request_count":1,"source":"injected_provider","policy_gated":gated}
            return decision
        except (TimeoutError,ValueError,TypeError,KeyError,json.JSONDecodeError,ValidationError) as exc:
            d=_rule_decision(q,self.policy); d.model_usage={"request_count":1,"source":"fallback","fallback_reason":type(exc).__name__[:64]}; return d
        except Exception as exc:
            d=_rule_decision(q,self.policy); d.model_usage={"request_count":1,"source":"fallback","fallback_reason":"provider_error"}; return d


def router_from_environment(provider: Callable[[str],Any] | None=None) -> LLMStructuredIntentRouter:
    import os
    return LLMStructuredIntentRouter(provider,enabled=os.getenv("V2A_LLM_ROUTER_ENABLED","0").lower() in {"1","true","yes"})


