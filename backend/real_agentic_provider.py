"""Opt-in real structured planner for isolated V2 research.

Never activated by backend/api.py or application startup. Requires explicit
construction and a configured local provider. No source PDF text, local file
paths, uploaded documents, or hidden reasoning are forwarded.
"""
from __future__ import annotations

import json
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from backend.model_profiles import safe_profile
from orchestration.agentic_contracts import (
    PlanProposal, PlannerRequest, ProviderReply, ReflectProposal, ReflectionRequest
)

_PLAN_SYSTEM = (
    "你是只读机械工程智能体的工具规划器。仅返回JSON对象，所有键都必须提供："
    "action(call_tool或finish),tool_name,query,tool_arguments,investigation_goal,"
    "evidence_gap,public_rationale,focus_clause_ids。只能建议官方标准工具"
    "standard_clause_search/damage_mechanism_query/rbi_lookup，不得要求额外工具或外部操作。"
    "材料、介质未被用户明确确认时绝对不可调用damage_mechanism_query；"
    "此时优先通过standard_clause_search进行初步调查，输入"
    "{keyword:...,knowledge_type:'damage_mechanism',top_k:5}。"
    "重要：当tool_name=standard_clause_search时，query字符串必须与tool_arguments.keyword逐字符完全相同；"
    "如需查询改写，请同时更新query和keyword，不能只更改其中一个。"
    "不得编造条款号、设备工况、风险等级。调查已足够或接近预算时action=finish、tool_name=''。"
    "public_rationale只写公开理由，不输出内部思维过程。"
)
_REFLECT_SYSTEM = (
    "你是同一只读机械工程智能体的下一步调查控制器。仅返回JSON对象："
    "continue_investigation(bool),next_evidence_gap(str),public_rationale(str)。"
    "证据不够且尚有预算时可继续，但不得超过剩余调查预算，"
    "不能把未核验的机理看作已发生，不能凭空补材料和压力。"
)


class LiveStructuredPlanner:
    """Explicitly initialized, bounded, no-unattended-retry network adapter."""

    def __init__(self, *, max_calls: int = 4, max_output_tokens: int = 900,
                 timeout_seconds: float = 25.0):
        if not 1 <= max_calls <= 6 or not 128 <= max_output_tokens <= 1500:
            raise ValueError("invalid real-provider safety budget")
        profile = safe_profile()
        if not profile or not profile.get("endpoint", "").startswith("https://"):
            raise RuntimeError("no approved HTTPS model profile")
        self.profile = profile
        self.max_calls = max_calls
        self.max_output_tokens = max_output_tokens
        self.timeout = min(timeout_seconds, float(profile.get("timeout", timeout_seconds)))
        self.calls = 0
        self.request_log: list[dict] = []

    def _request(self, *, kind: str, system: str, facts: dict, schema_cls) -> ProviderReply:
        if self.calls >= self.max_calls:
            raise RuntimeError("live planner request budget exhausted")
        self.calls += 1
        # Only synthetic/explicit case facts and source IDs; exclude any tool PDF text.
        input_data = json.dumps(facts, ensure_ascii=False, separators=(",", ":"), default=str)
        payload = {
            "model": self.profile["model"],
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": input_data[:3500]}],
            "response_format": {"type": "json_object"},
            "temperature": 0, "max_tokens": self.max_output_tokens, "stream": False
        }
        req = Request(self.profile["endpoint"], data=json.dumps(payload,ensure_ascii=False).encode("utf-8"),
            headers={"Authorization":"Bearer "+self.profile["api_key"],
                     "Content-Type":"application/json"},method="POST")
        started = time.perf_counter()
        try:
            with urlopen(req,timeout=self.timeout) as response:
                body=json.loads(response.read(262144).decode("utf-8"))
            choice=body["choices"][0]
            if choice.get("finish_reason") != "stop":
                raise ValueError("model did not complete a full JSON response")
            content=choice.get("message",{}).get("content") or ""
            result=schema_cls.model_validate_json(content)
            usage=body.get("usage") or {}
            elapsed=(time.perf_counter()-started)*1000
            self.request_log.append({"kind":kind, "status":"parsed", "latency_ms":round(elapsed),
                "input_tokens":int(usage.get("prompt_tokens") or 0),
                "output_tokens":int(usage.get("completion_tokens") or 0)})
            return ProviderReply(payload=result.model_dump(mode="json"),
                input_tokens=int(usage.get("prompt_tokens") or 0),
                output_tokens=int(usage.get("completion_tokens") or 0),
                latency_ms=elapsed,provider_name="real_live_bounded")
        except (HTTPError,URLError,KeyError,ValueError,TypeError,TimeoutError,OSError) as exc:
            elapsed=(time.perf_counter()-started)*1000
            self.request_log.append({"kind":kind,"status":"failed","error_class":type(exc).__name__,
                "http_status":getattr(exc,"code",None),"latency_ms":round(elapsed)})
            raise RuntimeError("real structured planner request or schema validation failed") from None

    def plan(self, request: PlannerRequest) -> ProviderReply:
        src=request.model_dump(mode="json")
        return self._request(kind="plan",system=_PLAN_SYSTEM,
            facts={"question":src["question"],"facts":src["facts"],"unknowns":src["unknowns"],
                   "iteration":src["iteration"],"previous_actions":src["previous_actions"],
                   "budget_remaining":src["budget_remaining"]},
            schema_cls=PlanProposal)

    def reflect(self, request: ReflectionRequest) -> ProviderReply:
        src=request.model_dump(mode="json")
        safe_summary=[{"status":x.get("status"),"source_ids":x.get("source_ids",[])}
                      for x in src["evidence_summary"][:8]]
        return self._request(kind="reflect",system=_REFLECT_SYSTEM,
            facts={"question":src["question"],"iteration":src["iteration"],
                   "unknowns":src["unknowns"],"evidence_summary":safe_summary,
                   "budget_remaining":src["budget_remaining"]},
            schema_cls=ReflectProposal)
