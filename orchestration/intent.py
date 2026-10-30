"""Small intent router for a dual-purpose engineering assistant.

Classify before requiring equipment context; free-form ordinary chat should
never be reported as a failed RBI assessment. This is intentionally simple,
not a new agent framework.
"""
from __future__ import annotations
import re
from typing import Any

_HELLO = re.compile(r"^(你好[呀啊哇！!。~～]*|您好[！!。]*|嗨[呀！!。]*|哈喽[！!。]*|hi[!. ]*|hello[!. ]*|在吗[？?！!]*)$", re.I)
_ABOUT = re.compile(r"(你(是(谁|什么模型)|用的?是什么模型|可以(做|干|帮我做)什么|能(做|干|帮我做)什么|有什么(功能|本领))|介绍(一下)?(你自己|你的功能)|你是谁)")
_EQUIPMENT = re.compile(r"(设备|管道|容器|换热器|反应釜|压力容器|储罐|泵|阀门|焊缝|壁厚|减薄|腐蚀|开裂|裂纹|损伤|失效|检验|RBI|风险等级|风险分级|风险评估|介质|氯化铵|硫化氢)", re.I)
_DEVICE_OBJECT = re.compile(r"(设备|管道|容器|换热器|反应釜|压力容器|储罐|泵|阀门|焊缝|本台|这台|该设备|该管道)", re.I)
_STANDARD = re.compile(r"(标准|条款|页码|GB\s*/?\s*T\s*\d|TSG\s*\d|规范原文)", re.I)
_CONCEPT = re.compile(r"^(什么是|介绍一下|解释一下|讲讲|科普一下|给我讲讲|帮我解释)(?!.*第\d+(?:\.\d+)*条)", re.I)
_APPLY = re.compile(r"(这(个|台|条|套)|本(台|设备)|判断|评估|研判|给出.*等级|是否安全|定级|确定风险|风险分级|损伤原因|腐蚀原因|失效可能性|失效后果)", re.I)

# Explicit non-engineering requests must be resolved from the current turn,
# before considering a prior engineering context. These are intent signals,
# not a deny-list: a turn that also explicitly asks for a standard/equipment
# judgment is handled by the more specific rules below.
_WEATHER = re.compile(r"(天气|气温|降雨|下雨|天气预报)")
_CODE = re.compile(r"(写(一段|个|一个)?(html|svg|代码|程序|脚本)|创建.*(html|svg|网页|代码|动画)|生成.*(html|svg|网页|代码)|\bhtml\b|\bsvg\b|\bpython\b|\bjavascript\b)", re.I)
_FOLLOWUP_ENGINEERING = re.compile(r"(这(个|台|种|些)|它|上述|刚才|前面|该设备|该管道|该介质).{0,16}(检测|腐蚀|损伤|机理|失效|处理|原因|适用|风险|工况)|^(那|所以|继续|再).{0,12}(怎么|如何|检测|处理|分析|判断|适用|补充)")
_MECHANISM = re.compile(r"(腐蚀|损伤|失效)机理|机理方向|损伤模式|腐蚀类型|属于哪类腐蚀|可能.*(腐蚀|损伤|失效)")
_RISK_GRADE = re.compile(r"(风险等级|风险分级|RBI等级|风险级别|风险是多少|设备风险|风险分析|风险评估|给出.*风险)")
_EXPLICIT_MATERIAL = re.compile(r"(碳钢|低合金钢|不锈钢|Cr-Mo|铬钼钢|20#钢|20号钢|Q245R|Q345R|06Cr19Ni10|06Cr17Ni12Mo2|S30408|S31608)", re.I)
_EXPLICIT_MEDIUM = re.compile(r"(湿硫化氢|H2S|H₂S|氯化氢|\bHCl\b|碱式酸性水|酸式酸性水|氯化铵|硫氢化铵|胺液|氢氧化钠)", re.I)


def classify_intent(question: str, context: dict[str, Any] | None = None) -> str:
    """Compatibility projection over the V2 deterministic policy.

    The policy is a routing floor only; it cannot authorize tools or factual claims.
    """
    from backend.intent_router_v2 import LocalIntentPolicy, MainRoute, TaskKind
    c=context or {}
    if c.get("_context_conflicts"):
        return "context_conflict"
    decision_route,safety,tasks,_=LocalIntentPolicy().analyze(question)
    # A current-turn plain follow-up may use same-conversation confirmed context;
    # it never causes cross-conversation context loading.
    q=re.sub(r"\s+","",question or "")
    if not safety and decision_route==MainRoute.GENERAL and any(c.get(k) for k in ("equipment","equipment_type","material","medium")):
        # Preserve the pre-V2 R9 behavior for contextual, terse equipment
        # follow-ups. V2 may classify a short noun phrase as general, but
        # "设备腐蚀" is still a professional follow-up when facts were supplied.
        # Explicit writing/concept requests must NOT inherit stale equipment.
        explicit_general=bool(_WEATHER.search(q) or _CODE.search(q) or
                              re.search(r"翻译|润色|改写|科普|写.*(?:诗|文章|报告)|^什么是|^介绍|^解释|^讲讲",q))
        contextual_device=bool(_DEVICE_OBJECT.search(q) and
                               re.search(r"腐蚀|损伤|失效|裂纹|开裂|减薄|测厚|情况|可能.*什么|分析|判断|检查|检测|异常|风险",q))
        if not explicit_general and (_FOLLOWUP_ENGINEERING.search(q) or contextual_device):
            return "deterministic_rbi_grade" if _RISK_GRADE.search(q) else "device_diagnosis"
    if decision_route==MainRoute.STANDARD_LOOKUP:
        return "standard_lookup"
    if decision_route in {MainRoute.ENGINEERING,MainRoute.MIXED} or safety:
        if any(t.kind==TaskKind.RBI_ASSESSMENT for t in tasks) and _RISK_GRADE.search(q):
            return "deterministic_rbi_grade"
        explicit_context = any(c.get(k) for k in ("material", "medium", "equipment", "equipment_type"))
        specific_equipment = bool(re.search(r"这台|这只|该设备|该管道|本台|本设备", q))
        explicit_environment = bool(_EXPLICIT_MATERIAL.search(q) and _EXPLICIT_MEDIUM.search(q))
        if specific_equipment or explicit_context or explicit_environment:
            return "device_diagnosis"
        return "hypothesis_exploration"
    return "general_chat"


def rule_chat_reply(question: str, *, model_name: str | None = None) -> str:
    q = re.sub(r"\s+", "", question).strip()
    if _ABOUT.search(q):
        provider = f"已配置的 DeepSeek 模型（{model_name}）" if model_name else "本地规则模式"
        return (f"我是 Aether，基于{provider}的机械设备分析助手。"
                "我可以陪你日常聊天、解释技术概念，也能查询损伤机理、RBI 与标准条款。"
                "涉及具体设备风险时，我会要求必要的工况和检测数据，并标明证据不足的部分。")
    if _HELLO.fullmatch(q):
        return "你好！我是 Aether。可以直接和我聊天，也可以问机械设备、腐蚀机理或相关标准的问题。"
    return "当前未启用通用语言模型；可配置 DeepSeek 后进行普通对话。设备研判仍需现场工况与证据。"
