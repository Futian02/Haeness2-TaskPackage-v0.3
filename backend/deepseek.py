"""Small OpenAI-compatible DeepSeek report adapter.

Only the bounded deterministic graph result is sent for phrasing. Attachments,
standard quotations, local paths, API credentials, and hidden reasoning are not
included. A provider error is surfaced to the caller; it is never relabelled as
a successful LLM answer or silently replaced by RULE_DEMO.
"""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


class ModelGenerationError(RuntimeError):
    """Provider failure with a finite, user-safe public error code."""

    def __init__(self, code: str, message: str, *, finish_reason: str | None = None,
                 usage: dict[str, int] | None = None, model: str | None = None):
        super().__init__(message)
        self.code = code
        self.finish_reason = finish_reason
        self.usage = usage
        self.model = model


@dataclass(frozen=True)
class GenerationResult:
    content: str
    duration_ms: int
    finish_reason: str | None = None
    usage: dict[str, int] | None = None
    model: str | None = None

    # Preserve historical ``content, duration = generate_*()`` call sites.
    def __iter__(self):
        yield self.content
        yield self.duration_ms


def _safe_usage(value: Any) -> dict[str, int] | None:
    if not isinstance(value, dict):
        return None
    result = {}
    for key in ("prompt_tokens", "completion_tokens", "total_tokens", "prompt_cache_hit_tokens", "prompt_cache_miss_tokens"):
        item = value.get(key)
        if isinstance(item, int) and 0 <= item <= 10_000_000:
            result[key] = item
    return result or None


def _response_metadata(response_data: dict[str, Any], fallback_model: str) -> tuple[str, str | None, dict[str, int] | None]:
    choices = response_data.get("choices") or []
    choice = choices[0] if choices and isinstance(choices[0], dict) else {}
    message = choice.get("message") or {}
    content = message.get("content")
    finish_reason = choice.get("finish_reason")
    usage = _safe_usage(response_data.get("usage"))
    returned_model = str(response_data.get("model") or fallback_model)[:120]
    if finish_reason == "length":
        raise ModelGenerationError("output_truncated", "模型输出达到长度上限；请重试或缩短请求",
                                   finish_reason="length", usage=usage, model=returned_model)
    # Do not persist or surface reasoning_content from reasoning-capable APIs.
    if not isinstance(content, str) or not content.strip():
        code = "content_filtered" if finish_reason == "content_filter" else "empty_response"
        raise ModelGenerationError(code, "模型没有返回可显示的回答",
                                   finish_reason=finish_reason if isinstance(finish_reason, str) else None,
                                   usage=usage, model=returned_model)
    # 16k output tokens can exceed 80k characters for multilingual/code output;
    # keep a bounded envelope above the supported profile instead of silently
    # truncating a successful answer before it reaches SQLite/UI.
    return content.strip()[:250000], finish_reason if isinstance(finish_reason, str) else None, usage


def _chat_generation_options() -> dict[str, Any]:
    """Legacy helper retained for callers; conservative general-chat profile."""
    try:
        max_tokens = int(os.getenv("DEEPSEEK_CHAT_MAX_TOKENS", "8192"))
    except ValueError:
        max_tokens = 8192
    options: dict[str, Any] = {"max_tokens": max(2048, min(max_tokens, 16384))}
    thinking = os.getenv("DEEPSEEK_THINKING_MODE", "").strip().lower()
    if thinking in {"enabled", "disabled"}:
        options["thinking"] = {"type": thinking}
    return options


def _token_limit(env_name: str, default: int, *, low: int = 2048, high: int = 16384) -> int:
    try:
        configured = int(os.getenv(env_name, str(default)))
    except (TypeError, ValueError):
        configured = default
    return max(low, min(configured, high))


def _chat_profile(question: str, provider: str) -> dict[str, Any]:
    """Select a bounded output budget from the current user task, not a fixed 900-token cap."""
    code_request = bool(re.search(
        r"代码|编程|程序|脚本|HTML|SVG|CSS|JavaScript|TypeScript|Python|C\+\+|实现|继续生成|补全|代码块|网页|组件|函数|class |function ",
        question, re.IGNORECASE))
    if code_request:
        chat_override = _token_limit("DEEPSEEK_CHAT_MAX_TOKENS", 8192)
        limit = _token_limit("DEEPSEEK_CODE_MAX_TOKENS", chat_override)
    else:
        limit = _token_limit("DEEPSEEK_CHAT_MAX_TOKENS", 4096)
    options: dict[str, Any] = {"max_tokens": limit}
    # DeepSeek-specific knobs are not sent to generic OpenAI-compatible endpoints.
    if provider == "deepseek":
        thinking = os.getenv("DEEPSEEK_THINKING_MODE", "disabled" if code_request else "disabled").strip().lower()
        if thinking in {"enabled", "disabled"}:
            options["thinking"] = {"type": thinking}
        effort = os.getenv("DEEPSEEK_REASONING_EFFORT", "").strip().lower()
        if effort in {"none", "low", "high", "max"}:
            options["reasoning_effort"] = effort
    return options


def _provider_error(exc: Exception) -> ModelGenerationError:
    if isinstance(exc, HTTPError):
        if exc.code == 402:
            return ModelGenerationError("provider_payment_required", "模型服务账户额度或付款方式需要检查")
        if exc.code == 429:
            return ModelGenerationError("provider_rate_limited", "模型服务暂时繁忙，请稍后重试")
        if exc.code in (401, 403):
            return ModelGenerationError("provider_auth_error", "模型服务认证失败，请检查本地配置")
        if 400 <= exc.code < 500:
            return ModelGenerationError("provider_request_error", "模型服务拒绝了本次请求")
        return ModelGenerationError("provider_unavailable", "模型服务暂时不可用，请重试")
    if isinstance(exc, (TimeoutError,)) or isinstance(exc, URLError) and isinstance(getattr(exc, "reason", None), TimeoutError):
        return ModelGenerationError("provider_timeout", "模型请求超时，请重试")
    if isinstance(exc, (URLError, OSError)):
        return ModelGenerationError("provider_network_error", "模型连接中断，请检查网络后重试")
    if isinstance(exc, json.JSONDecodeError):
        return ModelGenerationError("provider_invalid_response", "模型服务返回格式异常，请重试")
    return ModelGenerationError("provider_error", "模型生成失败，请重试")


def _load_local_env() -> None:
    """Load ignored .env.local values without overriding the process environment."""
    path = ROOT / ".env.local"
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name, value = name.strip(), value.strip()
        if value.startswith(("'", '"')) and value.endswith(value[:1]) and len(value) >= 2:
            value = value[1:-1]
        if name.startswith("DEEPSEEK_") and name not in os.environ:
            os.environ[name] = value


_load_local_env()


def settings() -> dict[str, Any]:
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
    if base_url.endswith("/chat/completions"):
        endpoint = base_url
    else:
        endpoint = base_url + "/chat/completions"
    return {
        "api_key": os.getenv("DEEPSEEK_API_KEY", "").strip(),
        "base_url": base_url,
        "endpoint": endpoint,
        "model": os.getenv("DEEPSEEK_MODEL", "deepseek-flash").strip() or "deepseek-flash",
        "timeout": max(3.0, min(float(os.getenv("DEEPSEEK_TIMEOUT_SECONDS", "45")), 90.0)),
    }


def is_configured() -> bool:
    config = settings()
    return bool(config["api_key"] and config["base_url"].startswith("https://") and config["model"])


def generate_report(question: str, output: dict[str, Any], context: dict[str, Any], profile: dict[str, Any] | None = None) -> GenerationResult:
    """Ask DeepSeek to phrase only already-computed, evidence-bounded facts."""
    config = profile or settings()
    if not config.get("api_key") or not config.get("endpoint", "").startswith("https://"):
        raise RuntimeError("DeepSeek 未配置：请设置 DEEPSEEK_API_KEY")
    citations = [
        {key: row.get(key) for key in ("clause_id", "clause_no", "standard_code", "page") if row.get(key) is not None}
        for row in (output.get("citations") or [])[:8]
    ]
    safe_result = {
        "status": output.get("status"),
        "verification_level": output.get("verification_level", "E0"),
        "conclusion": str(output.get("conclusion") or "未形成结论。")[:1600],
        "hypotheses": [str(row.get("text") or "")[:400] for row in (output.get("hypotheses") or [])[:8]],
        "unknowns": [str(value)[:160] for value in (output.get("unknowns") or [])[:20]],
        "citations": citations,
        "risk_level": None,
        "conditions": {
            key: str(context.get(key) or "未知")[:200]
            for key in ("equipment", "equipment_type", "material", "medium", "operating_condition")
        },
    }
    payload = {
        "model": config["model"],
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是兼容 Chat Completions 的中文表达整理模型，不负责检索、诊断或复核。"
                    "只可忠实改写 user 提供的 deterministic_result，不得新增事实、风险等级、检验周期、标准条文含义或设备适用结论。"
                    "保留未知项与 E0/E1 状态；若证据不足要明确说待人工复核。"
                    "输出简洁 Markdown，最多 6 条，不输出思维链。"
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {"question": str(question)[:1200], "deterministic_result": safe_result},
                    ensure_ascii=False,
                ),
            },
        ],
        "temperature": 0,
        "max_tokens": _token_limit("DEEPSEEK_REPORT_MAX_TOKENS", 3072),
        "stream": False,
    }
    request = Request(
        config["endpoint"],
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {config['api_key']}", "Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    try:
        with urlopen(request, timeout=config["timeout"]) as response:
            response_data = json.loads(response.read(2_000_000).decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        raise _provider_error(exc) from None
    content, finish_reason, usage = _response_metadata(response_data, config["model"])
    return GenerationResult(content[:12000], round((time.perf_counter() - started) * 1000),
                            finish_reason, usage, str(response_data.get("model") or config["model"])[:120])


def generate_professional_explanation(question: str, context: dict[str, Any], source_catalog: dict[str, dict[str, Any]],
                                     profile: dict[str, Any] | None = None) -> GenerationResult:
    """Candidate-only bounded expert explanation; caller must validate JSON and citations."""
    config = profile or settings()
    if not config.get("api_key") or not config.get("endpoint", "").startswith("https://"):
        raise RuntimeError("DeepSeek 未配置")
    from backend.professional_answers import classify_professional_intent, plan_teacher_queries
    facts={k:context.get(k) for k in ("equipment","equipment_type","material","medium","temperature_c","pressure_mpa","service_years") if context.get(k) not in (None,"",[])}
    # Keep raw user values useful but bounded; do not forward arbitrary context,
    # attachments, paths, or the full conversation history to a provider.
    facts={k:(str(v)[:400] if isinstance(v,str) else v) for k,v in facts.items()}
    safe_sources=[]
    for row in list(source_catalog.values())[:8]:
        item={k:row.get(k) for k in ("standard_code","clause_no","page","title","source_id","verification","scope_note","relevance_label") if row.get(k) is not None}
        # Short exact excerpts support source-span claims without uploading a
        # full standard or chapter. Final claim validation still checks against
        # the server-side canonical source catalog.
        excerpt=row.get("content_excerpt")
        if isinstance(excerpt,str) and excerpt:
            item["content_excerpt"]=excerpt[:400]
        safe_sources.append(item)
    intents=classify_professional_intent(question)
    concept_only=bool(re.search(r"(?:什么是|解释|介绍|原理|含义).{0,18}(?:应力腐蚀开裂|SCC|腐蚀|裂纹)",question,re.I)) and not facts
    answer_mode="concept_explanation" if concept_only else "engineering_investigation"
    payload={"model":config["model"],"messages":[
          {"role":"system","content":("你是机械设备专业分析助手，不是模板改写器。基于有限事实主动进行专业分析：提出条件性机理假设、至少一个竞争解释、区分这些解释的观测/检验方向；题目为概念解释时直接解释概念和机制，不强制索要设备参数。输出严格JSON，不输出思维链：summary最多2句；possible_directions最多3条且每条不超过160字；checks最多5条；missing_info最多5条；全篇中文不超过1200字。"
              "应力腐蚀开裂概念题应解释拉应力（残余/外加载荷）、材料敏感性、特定腐蚀环境的协同条件，以及裂纹萌生/扩展机制；指出仅具备单项因素不足以据此诊断具体设备。可以使用通用工程知识作GENERAL_GUIDANCE，不要假引标准。"
              "只能给一般工程指导或待核假设；不得声称设备确诊、法定阈值、强制停机/复机许可、RBI风险等级、检验周期。"
            "已确认source IDs只能从提供列表选。引用任何标准号/条款/页码必须使用这些source且逐条source_ids列明。若缺条件，列入missing_info并解释用途，不得反向把UNKNOWN写成不适用。"
            "设备处置字段只能为device_disposition=UNKNOWN，不能输出设备可运行/无需停机/复机/已验收等许可。每项来源摘要必须逐claim绑定source_ids、scope、observed_prerequisites并保持verification_state=E0；不要把条款编号存在误当成语义支持。"
            "标准摘要必须将text与source_span_ref逐字一致，source_span_ref必须是所引source的原始短片段；scope和observed_prerequisites必须逐条列出，输出层会验证片段和source ID。"
            "claims中给每项可见专业断言分类GENERAL_GUIDANCE/HYPOTHESIS/SOURCE_SUMMARY/INSPECTION_REQUIREMENT；不需要把每句重复到summary与claims。来源摘要只在source_catalog有对应excerpt时生成，text和source_span_ref必须逐字引用提供的短excerpt；source_id存在不代表该条款支持该句。"
            "按JSON schema: summary:string, possible_directions:[{text,evidence_level:GENERAL_GUIDANCE|HYPOTHESIS_UNVERIFIED|SOURCE_SUMMARY,source_ids:[],scope:string,source_span_ref:string,observed_prerequisites:[],verification_state:E0}], claims:[{claim_type:GENERAL_GUIDANCE|HYPOTHESIS|SOURCE_SUMMARY|DEVICE_DISPOSITION|INSPECTION_REQUIREMENT,text:string,source_ids:[],scope:string,source_span_ref:string,observed_prerequisites:[],safety_consequence:string,verification_state:E0}], device_disposition:UNKNOWN, checks:[string], missing_info:[{field,why_it_matters}], safety_notice:string, standard_uncertainty:string, risk_level:null, device_diagnosis_confirmed:false。")},
        {"role":"user","content":json.dumps({"question":str(question)[:1800],"professional_intents":intents,"answer_mode":answer_mode,"explicit_user_facts":facts,
            "fact_provenance":context.get("_context_sources",{}),"tool_query_plan":plan_teacher_queries(question,context),"verified_current_run_source_catalog":safe_sources,
            "note":"source membership and metadata prove provenance only, not semantic support or equipment applicability"},ensure_ascii=False)}],
        "temperature":0.15,"max_tokens":1800,"response_format":{"type":"json_object"},"stream":False}
    # This endpoint is for a concise user-facing JSON answer. Disabling
    # hidden reasoning prevents the bounded completion budget from being
    # consumed before the visible JSON is produced.
    if config.get("provider") == "deepseek":
        payload["thinking"] = {"type":"disabled"}
    request=Request(config["endpoint"],data=json.dumps(payload,ensure_ascii=False).encode("utf-8"),headers={"Authorization":f"Bearer {config['api_key']}","Content-Type":"application/json"},method="POST")
    started=time.perf_counter()
    try:
        with urlopen(request,timeout=min(float(config["timeout"]),30.0)) as response:
            response_data=json.loads(response.read(500_000).decode("utf-8"))
    except (HTTPError,URLError,TimeoutError,json.JSONDecodeError,OSError) as exc:
        raise _provider_error(exc) from None
    content,finish_reason,usage=_response_metadata(response_data,config["model"])
    return GenerationResult(content,round((time.perf_counter()-started)*1000),finish_reason,usage,str(response_data.get("model") or config["model"])[:120])


def plan_professional_investigation(question: str, context: dict[str, Any],
                                    profile: dict[str, Any] | None = None) -> GenerationResult:
    """Ask for a tiny, schema-bounded proposal; application validates tools and executes them."""
    config=profile or settings()
    if not config.get("api_key") or not config.get("endpoint","").startswith("https://"):
        raise RuntimeError("DeepSeek 未配置")
    from backend.professional_answers import classify_professional_intent
    facts={k:context.get(k) for k in ("equipment","equipment_type","material","medium","temperature_c","pressure_mpa","service_years") if context.get(k) not in (None,"",[])}
    payload={"model":config["model"],"messages":[
        {"role":"system","content":("为设备工程调查提出最多3步只读检索计划。只输出JSON：{steps:[{query:string,tools:[damage_mechanism_query|standard_clause_search]}]}。"
          "每步query不超过240字符，tools只能是列出的两个只读老师工具；不允许网络、文件、写入、RBI定级、风险结论或现场诊断。"
          "根据问题选择工具：机理调查可选damage_mechanism_query；标准、验收、检验或维修条款只选standard_clause_search。"
          "缺失工况作为待补证，不得因此拒绝检索。工具调用预算最多3步，每步工具最多2个。")},
        {"role":"user","content":json.dumps({"question":str(question)[:1600],"intents":classify_professional_intent(question),
            "explicit_user_facts":facts,"fact_provenance":context.get("_context_sources",{}),
            "unknown_enum_values":context.get("_context_unknown_enums",{}),
            "source":"本机冻结知识库的真实只读教师工具；模型只提查询计划，程序核验并执行"},ensure_ascii=False)}],
        "temperature":0.0,"max_tokens":600,"response_format":{"type":"json_object"},"stream":False}
    if config.get("provider")=="deepseek":payload["thinking"]={"type":"disabled"}
    request=Request(config["endpoint"],data=json.dumps(payload,ensure_ascii=False).encode(),headers={"Authorization":f"Bearer {config['api_key']}","Content-Type":"application/json"},method="POST")
    started=time.perf_counter()
    try:
        with urlopen(request,timeout=min(float(config["timeout"]),15.0)) as response:
            response_data=json.loads(response.read(200_000).decode("utf-8"))
    except (HTTPError,URLError,TimeoutError,json.JSONDecodeError,OSError) as exc:
        raise _provider_error(exc) from None
    content,finish_reason,usage=_response_metadata(response_data,config["model"])
    return GenerationResult(content,round((time.perf_counter()-started)*1000),finish_reason,usage,str(response_data.get("model") or config["model"])[:120])

def generate_chat(question: str, profile: dict[str, Any] | None = None) -> GenerationResult:
    """Ordinary chat with bounded same-conversation history and no file/context upload."""
    config = profile or settings()
    if not config.get("api_key") or not config.get("endpoint", "").startswith("https://"):
        raise RuntimeError("DeepSeek 未配置")
    model = config["model"]
    history = profile.get("_history", []) if isinstance(profile, dict) else []
    messages = [{"role": "system", "content": (
        f"你是 Aether，一个亲切、简洁、自然的中文 AI 助手，当前使用服务端配置的模型 {model}。"
        "可以进行普通聊天、学习交流、技术解释与创意写作。"
        "用户问你是什么模型时如实说明当前配置名，不声称具备实时联网或尚未接入的工具。"
        "涉及机械设备的具体损伤、RBI风险分级、标准条款时，不编造测量值、标准引文、"
        "检验周期或已审核结论。普通问候不要求材质、介质等设备信息。"
        "自然回答用户当前问题，不输出状态码、证据等级或内部步骤。"
    )}]
    web_sources = profile.get("_web_sources", []) if isinstance(profile, dict) else []
    if isinstance(web_sources, list) and web_sources:
        safe_sources = []
        for source in web_sources[:5]:
            if not isinstance(source, dict):
                continue
            safe_sources.append({
                "title": str(source.get("title") or "")[:240],
                "url": str(source.get("url") or "")[:1000],
                "retrieved_at": str(source.get("retrieved_at") or "")[:80],
                "summary": str(source.get("summary") or source.get("snippet") or "")[:700],
            })
        if safe_sources:
            messages[0]["content"] += (
                "如果下面提供了外部搜索结果，只能把它们作为外部网络参考，不得称为老师标准条文或权威设备结论；"
                "无法确认时明确说明。外部来源：" + json.dumps(safe_sources, ensure_ascii=False)
            )
    # Keep no more than 12 prior user/visible-assistant turns. Estimate tokens
    # conservatively by characters and retain the newest conversational context.
    bounded = []
    remaining_chars = 16000
    for item in reversed(history[-24:] if isinstance(history, list) else []):
        if not isinstance(item, dict) or item.get("role") not in {"user", "assistant"}:
            continue
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        content = content[-min(len(content), 4000):]
        if len(content) > remaining_chars:
            content = content[-remaining_chars:]
        if not content:
            break
        bounded.append({"role": item["role"], "content": content})
        remaining_chars -= len(content)
        if remaining_chars <= 0 or len(bounded) >= 24:
            break
    messages.extend(reversed(bounded))
    # A failed run is a short, public, same-chat summary—not provider internals.
    failed_summary = profile.get("_failed_run_summary") if isinstance(profile, dict) else None
    if isinstance(failed_summary, str) and failed_summary.strip():
        messages.append({"role": "system", "content": "同一会话最近一次任务未完成：" + failed_summary[:500]})
    messages.append({"role": "user", "content": question[:4000]})
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.5,
        **_chat_profile(question, str(config.get("provider") or "deepseek")),
        "stream": False,
    }
    request = Request(config["endpoint"],
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {config['api_key']}", "Content-Type": "application/json"},
        method="POST")
    started = time.perf_counter()
    try:
        with urlopen(request, timeout=config["timeout"]) as response:
            response_data = json.loads(response.read(2_000_000).decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        raise _provider_error(exc) from None
    content, finish_reason, usage = _response_metadata(response_data, model)
    return GenerationResult(content, round((time.perf_counter() - started) * 1000),
                            finish_reason, usage, str(response_data.get("model") or model)[:120])
