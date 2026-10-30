"""Bounded professional-response policy: guidance stays useful without upgrading evidence."""
from __future__ import annotations

import re
import unicodedata
import json
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, ValidationError

class GuidanceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=900)
    evidence_level: Literal["GENERAL_GUIDANCE", "HYPOTHESIS_UNVERIFIED", "SOURCE_SUMMARY"]
    source_ids: list[str] = Field(default_factory=list, max_length=5)
    scope: str = Field(default="", max_length=240)
    source_span_ref: str = Field(default="", max_length=500)
    observed_prerequisites: list[str] = Field(default_factory=list, max_length=12)
    verification_state: Literal["E0"] = "E0"

class ProfessionalClaim(BaseModel):
    """A claim is a typed, bounded assertion, not a free-form conclusion."""
    model_config = ConfigDict(extra="forbid")
    claim_type: Literal["GENERAL_GUIDANCE", "HYPOTHESIS", "SOURCE_SUMMARY", "DEVICE_DISPOSITION", "INSPECTION_REQUIREMENT"]
    text: str = Field(min_length=1, max_length=900)
    source_ids: list[str] = Field(default_factory=list, max_length=5)
    scope: str = Field(default="", max_length=240)
    source_span_ref: str = Field(default="", max_length=500)
    observed_prerequisites: list[str] = Field(default_factory=list, max_length=12)
    safety_consequence: str = Field(default="", max_length=240)
    verification_state: Literal["E0"] = "E0"

class MissingItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: str = Field(min_length=1, max_length=80)
    why_it_matters: str = Field(min_length=1, max_length=300)

class ProfessionalExplanationDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str = Field(min_length=1, max_length=1200)
    possible_directions: list[GuidanceItem] = Field(default_factory=list, max_length=5)
    checks: list[str] = Field(default_factory=list, max_length=8)
    missing_info: list[MissingItem] = Field(default_factory=list, max_length=8)
    safety_notice: str = Field(default="", max_length=900)
    standard_uncertainty: str = Field(default="", max_length=500)
    risk_level: None = None
    device_diagnosis_confirmed: Literal[False] = False
    claims: list[ProfessionalClaim] = Field(max_length=12)
    # This field is a server policy projection. The model is never allowed to
    # assign an operational disposition other than UNKNOWN.
    device_disposition: Literal["UNKNOWN"]

_INTENT_PATTERNS = {
    "MaintenanceSafety": re.compile(r"停机|停用|维修|修理|验收|复机|恢复使用|壳体.*(?:磕碰|碰撞|撞击|凹陷|变形)|承压边界.*(?:损伤|凹陷|变形)", re.I),
    "RBIGrade": re.compile(r"风险等级|风险分级|RBI等级|失效可能性|失效后果", re.I),
    "StandardsLookup": re.compile(r"标准|条款|验收|法规|规范|页码|GB\s*/?\s*T|TSG", re.I),
    "MechanismExploration": re.compile(r"哪类腐蚀|腐蚀机理|损伤机理|可能原因|属于哪类|減薄|减薄", re.I),
    "DeviceInvestigation": re.compile(r"设备|管线|管道|壳体|弯头|换热器|容器|损伤|腐蚀|裂纹|减薄", re.I),
    "Concept": re.compile(r"什么是|解释|介绍|原理|区别|含义", re.I),
}


def classify_professional_intent(question: str) -> list[str]:
    q = str(question or "")
    found = [name for name, pattern in _INTENT_PATTERNS.items() if pattern.search(q)]
    return found or ["Concept"]


def plan_teacher_queries(question: str, context: dict[str, Any] | None = None, *, max_queries: int = 5) -> list[str]:
    """Deterministic focused variants. These are search terms, not claims."""
    q = re.sub(r"\s+", " ", str(question or "")).strip()
    c = context or {}
    plans: list[str] = []
    shell_impact = re.search(r"壳体|容器|承压边界", q) and re.search(r"磕碰|碰撞|撞击|凹陷|变形|机械损伤", q)
    if shell_impact:
        plans += ["承压壳体 机械损伤 磕碰 凹陷", "壳体变形 裂纹 无损检测", "压力容器 碰撞损伤 修理 复检 验收", "承压设备损伤 安全状况 检验 修理"]
    else:
        raw_media = c.get("raw_medium") or c.get("medium") or []
        media = raw_media if isinstance(raw_media, list) else [raw_media]
        material = c.get("material")
        equipment = c.get("equipment") or c.get("equipment_type")
        # Keep the user's exact topic, then add context-bound synonyms; never
        # translate unknown medium into a canonical teacher enum here.
        if media or material or equipment:
            med = " ".join(str(x) for x in media if x)
            plans += [q, " ".join(x for x in (med, "腐蚀机理 损伤形态") if x),
                      " ".join(x for x in (med, str(material or ""), "局部腐蚀 减薄 流速") if x)]
        else:
            plans.append(q)
            if re.search(r"停机|验收|维修|复机", q):
                plans += ["承压设备 损伤 检验 修理 验收", "压力容器 安全状况 检验 缺陷 处理"]
            elif re.search(r"腐蚀|损伤|失效", q):
                plans += ["损伤机理 适用条件 影响因素", "设备损伤 检验 方法 适用范围"]
    dedup=[]
    for item in plans:
        item=re.sub(r"\s+", " ", item).strip()
        if item and item not in dedup:dedup.append(item)
    return dedup[:max(1,min(int(max_queries),5))]


def validate_professional_plan(value: Any) -> list[dict[str, Any]]:
    """Accept only bounded plans over the frozen read-only teacher-tool allowlist."""
    import json
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, dict) or set(value) != {"steps"} or not isinstance(value["steps"], list):
        raise ValueError("invalid professional plan envelope")
    if not 1 <= len(value["steps"]) <= 3:
        raise ValueError("professional plan must contain 1..3 bounded steps")
    allowed = {"damage_mechanism_query", "standard_clause_search"}
    steps=[]
    for row in value["steps"]:
        if not isinstance(row, dict) or set(row) != {"query", "tools"}:
            raise ValueError("invalid professional plan step")
        query=str(row["query"]).strip()
        tools=row["tools"]
        if not query or len(query)>240 or not isinstance(tools,list) or not tools or len(tools)>2:
            raise ValueError("invalid professional query or tool count")
        if any(name not in allowed for name in tools) or len(set(tools)) != len(tools):
            raise ValueError("tool is outside frozen read-only allowlist")
        steps.append({"query":query,"tools":list(tools)})
    return steps


def _known_facts(context: dict[str, Any]) -> list[dict[str, Any]]:
    labels={"equipment":"设备/部位","equipment_type":"设备类型","material":"用户陈述材质","medium":"用户陈述介质","temperature_c":"用户陈述温度","pressure_mpa":"用户陈述压力","service_years":"用户陈述服役年限"}
    sources=context.get("_context_sources") or {}
    rows=[]
    for key,label in labels.items():
        value=context.get(key)
        if value not in (None,"",[]):
            rows.append({"field":key,"label":label,"value":value,"provenance":sources.get(key,"provided_context"),"measurement_confirmed":False})
    # Preserve an explicitly stated non-enum medium as user text. It must not
    # be canonicalized into the teacher's closed enum, but must not disappear
    # from the visible acknowledgement either.
    if context.get("medium") in (None, "", []) and context.get("raw_medium") not in (None, "", []):
        rows.append({"field":"medium","label":"用户陈述介质（未作枚举归一化）","value":context["raw_medium"],
                     "provenance":sources.get("medium","current_message_raw"),"measurement_confirmed":False})
    return rows

def known_facts_for_response(context: dict[str, Any]) -> list[dict[str, Any]]:
    return _known_facts(context)

_NUMERIC_MANDATE = re.compile(r"(?:必须|不得|不应|应当|法定|强制|小于|大于|不超过|至少|低于|高于|应控制在|≤|≥).{0,18}\d+(?:\.\d+)?\s*(?:mm|毫米|MPa|℃|°C|年|小时|天|%|级)", re.I)
_STANDARD_TOKEN = re.compile(r"(?:GB\s*/?\s*T\s*[\w.\-—]+|TSG\s*[\w.\-—]+|第\s*\d+(?:\.\d+)*\s*条|\b\d+\.\d+\s*条)", re.I)
_FORBIDDEN_RISK = re.compile(r"\bL[1-4]\b|风险等级\s*[：:]?\s*[一二三四1-4]|已确认(损伤|腐蚀|开裂)")
# Structural gate plus a semantic disposition denylist. Negated statements are
# allowed only when the negation explicitly blocks permission (e.g. “不能批准复机”).
# This is defense-in-depth: the API renders a deterministic fallback whenever
# the model's typed output is rejected; the model cannot set DEVICE_DISPOSITION.
_DISPOSITION_NEGATION = re.compile(r"(?:不能|不得|不应|禁止|无法|不可|不可以|尚不能|尚未证明|未能证明|不足以|不能据此|不可据此).{0,14}(?:批准|允许|建议|判定|确认|证明|认定|授权|推出|得出|断言|声称|继续|保持|恢复|运行|使用|投用|复机)")
_DISPOSITION_ACTION = re.compile(r"(?:继续|持续|保持|恢复|投入|带压|正常|满足|符合|免于|无需|无须|不必|不需要|不需|不用|可(?:以)?|允许|照常).{0,5}(?:运行|生产|使用|投用|复机|开车|停机|停车|检验|复查|维修|修理|验收|承压|服役)|(?:批准).{0,2}(?:运行|生产|使用|投用|复机|开车|验收通过)|(?:可运行|可投用|可复机|可开车|可保持运行|无需停机|无须停机|不必停机|不需要停机|无需检验|无需复查|无需维修|已满足验收|验收合格|符合验收要求)")

# Cue groups implement a compositional safety policy rather than relying on a
# short denylist. Normalize Unicode/formatting, split lexical polarity cues,
# and classify high-consequence propositions: safe-state, integrity unaffected,
# permission to operate, or no further action. Affirmative propositions are
# rejected unless the text explicitly states that safety is not established.
_SAFE_STATE = ("无安全隐患", "没有安全隐患", "已确认没有安全隐患", "无风险", "没有风险", "没有危险", "完好", "完整性未受影响",
               "未影响完整性", "未影响设备完整性", "不影响设备完整性", "不构成完整性问题", "不会影响承压能力", "状态正常", "运行正常", "安全状态",
               "现有证据足以判定安全", "判定安全", "确认安全", "证明安全", "属于安全", "设备安全", "容器安全", "不影响安全", "安全合格", "验收已经合格", "验收合格", "已验收合格", "安全运行条件", "可以接受", "排除泄漏风险", "不会造成失效",
               "维持当前生产计划", "运行许可没有问题", "无需担心", "acceptable", "is safe", "safe condition", "no hazard", "no risk", "does not affect integrity")
_NO_FOLLOWUP = ("无需", "无须", "不必", "不需要", "不需", "不用", "没有必要", "并非必要", "并非必需", "免于", "可以省略", "可省略", "不是需要处理的",
                "不需要再", "无需再", "no action is required", "no further inspection", "does not need", "not necessary")
_FOLLOWUP_ACTION = ("措施", "处理", "处置", "核验", "复核", "确认", "评估", "检查", "检验", "检测", "无损检测", "维修", "修理", "停车",
                    "隔离", "停机", "停用", "复机", "复查", "专业人员", "专业评估", "后续工作", "补充确认", "inspection", "action", "repair", "assessment")
_SAFE_EPISTEMIC_DENIAL = ("不能确认安全", "无法确认安全", "尚未确认安全", "未能确认安全", "不足以确认安全", "不能判定安全",
                          "不能据此判定安全", "不足以判定安全", "不能证明安全", "无法证明安全", "不代表安全", "并非证明安全",
                          "不能确认设备安全", "无法确认设备安全", "尚未确认设备安全", "不足以确认设备安全", "不能据此认为设备安全",
                          "cannot confirm safety", "not enough to determine safe", "does not establish safety", "safety is unconfirmed")
_DIRECT_PERMISSION = ("可运行", "可以运行", "可连续运行", "继续运行", "继续带压运行", "允许运行", "批准运行", "可恢复生产", "可以恢复生产", "恢复生产", "可继续生产", "可以继续生产", "可正常生产", "继续生产", "可以按原计划生产", "按原计划生产", "可以维持生产",
                      "可使用", "可以使用", "允许使用", "可投用", "可以投用", "允许投用", "可复机", "可以复机", "批准复机",
                      "可开车", "可以开车", "允许开车", "可带压运行", "保持运行", "维持运行", "安全运行", "验收合格", "已满足验收",
                      "验收通过", "满足验收要求", "允许继续运行", "无需停机", "不必停机", "不必停车", "无需检验", "无需修理", "无需隔离", "免于检查",
                      "safe to operate", "safe to run", "restart is acceptable", "continue operation", "no action is required")
_PERMISSION_EPISTEMIC_DENIAL = ("不能", "不应", "不得", "不可", "无法", "不足以", "尚未证明", "尚未确认", "未能证明", "不能据此", "不可据此", "不代表", "没有证据支持", "不支持", "not", "cannot", "insufficient")


def _normalize_for_policy(text: str) -> str:
    value=unicodedata.normalize("NFKC",str(text or "")).casefold()
    value="".join(ch for ch in value if ch not in "\u200b\u200c\u200d\ufeff\u2060\u00ad")
    return re.sub(r"[\s\W_]", "", value, flags=re.UNICODE)


def _contains_affirmed_safe_state(text: str) -> bool:
    # Interpret each clause independently. This avoids a source title like
    # “安全状况评定原则” or a later disclaimer neutralizing a separate
    # unsupported assertion elsewhere in the answer.
    clauses=re.split(r"[。！？；;!?，,\n]+",unicodedata.normalize("NFKC",str(text or "")).casefold())
    targets=("设备","容器","压力边界","管线","管道","弯头","换热器","装置","系统","损伤","缺陷","完整性","运行","the vessel","equipment","asset","integrity","operation")
    affirmative_ops=("已确认","已经确认","足以判定","可判定","可以判定","证明","说明","表明","属于","保持","继续","允许","可","没有","无","未影响","does not","is","safe")
    for clause in clauses:
        value=_normalize_for_policy(clause)
        denied=any(_normalize_for_policy(cue) in value for cue in _SAFE_EPISTEMIC_DENIAL)
        positives=any(_normalize_for_policy(cue) in value for cue in _SAFE_STATE)
        target_present=any(_normalize_for_policy(x) in value for x in targets)
        # Standards often use “安全状况等级/安全附件/安全使用要求” while
        # describing an assessment framework. Those terms alone are not an
        # assertion that the current asset is safe.
        safety_residual=value
        for descriptive_term in ("安全状况等级","安全状况","安全附件","安全使用要求","安全评定原则","安全边界","安全措施","安全提示","安全风险","安全分析"):
            safety_residual=safety_residual.replace(_normalize_for_policy(descriptive_term),"")
        safe_word=_normalize_for_policy("安全") in safety_residual or _normalize_for_policy("safe") in safety_residual
        affirmative=any(_normalize_for_policy(x) in value for x in affirmative_ops)
        negative_hazard=any(_normalize_for_policy(x) in value for x in ("未发现安全隐患","未见安全隐患","没有发现危险","未发现危险","no hazard found"))
        if not denied and (positives or (target_present and safe_word and affirmative) or (negative_hazard and (target_present or affirmative))):
            return True
    return False


def _contains_no_followup_claim(text: str) -> bool:
    for clause in re.split(r"[。！？；;!?，,\n]+",str(text or "")):
        value=_normalize_for_policy(clause)
        # Epistemic denial blocks an inference that no further action is needed,
        # but only in the same clause. A later contrastive permission remains blocked.
        denial=any(_normalize_for_policy(cue) in value for cue in ("不能据此认为无需", "不能认定无需", "不能证明无需", "不足以说明无需", "not enough to conclude no action"))
        if not denial and any(_normalize_for_policy(need) in value for need in _NO_FOLLOWUP) and any(_normalize_for_policy(action) in value for action in _FOLLOWUP_ACTION):
            return True
    return False

def _contains_disposition_permission(text: str) -> bool:
    if _contains_affirmed_safe_state(text) or _contains_no_followup_claim(text):
        return True
    clauses=re.split(r"[。！？；;!?，,\n]+",unicodedata.normalize("NFKC",str(text or "")).casefold())
    for clause in clauses:
        value=_normalize_for_policy(clause)
        # Catch productive paraphrases (e.g. “可维持生产” / “可恢复运行”)
        # rather than relying only on a finite phrase list. A local epistemic
        # denial immediately before the action remains an allowed warning.
        for match in _DISPOSITION_ACTION.finditer(value):
            prefix=value[max(0,match.start()-28):match.start()]
            if any(_normalize_for_policy(denial) in prefix for denial in _PERMISSION_EPISTEMIC_DENIAL):
                continue
            return True
        for phrase in _DIRECT_PERMISSION:
            cue=_normalize_for_policy(phrase)
            pos=value.find(cue)
            if pos < 0:continue
            prefix=value[max(0,pos-20):pos]
            if any(_normalize_for_policy(denial) in prefix for denial in _PERMISSION_EPISTEMIC_DENIAL):
                continue
            return True
    return False


def _validate_content(text: str, source_catalog: dict[str, dict[str, Any]], source_ids: set[str]) -> None:
    if _FORBIDDEN_RISK.search(text) or _contains_disposition_permission(text):
        raise ValueError("blocked_unverified_device_or_risk_conclusion")
    tokens=_STANDARD_TOKEN.findall(text)
    if tokens:
        rows=[row for cid,row in source_catalog.items() if cid in source_ids]
        if not rows:
            raise ValueError("blocked_unverified_standard_reference")
        for token in tokens:
            compact=re.sub(r"\s+","",token).lower()
            if token.startswith("第"):
                clause=re.sub(r"\D","",token)
                clause_parts=re.search(r"(\d+(?:\.\d+)*)",token)
                clause_no=clause_parts.group(1) if clause_parts else ""
                if not any(str(row.get("clause_no"))==clause_no for row in rows):
                    raise ValueError("blocked_unverified_standard_reference")
            elif not any(compact in re.sub(r"\s+","",str(row.get("standard_code") or "")).lower() for row in rows):
                raise ValueError("blocked_unverified_standard_reference")
    if _NUMERIC_MANDATE.search(text):
        raise ValueError("blocked_unverified_numeric_mandate")


def validate_professional_draft(raw: Any, source_catalog: dict[str, dict[str, Any]]) -> ProfessionalExplanationDraft:
    """Parse strict structured response and enforce source/risk/threshold gates."""
    if isinstance(raw,str):
        txt=raw.strip()
        if txt.startswith("```"):
            txt=re.sub(r"^```(?:json)?\s*|\s*```$","",txt,flags=re.I)
        import json
        raw=json.loads(txt)
    draft=ProfessionalExplanationDraft.model_validate(raw)
    available=set(source_catalog)
    for item in draft.possible_directions:
        if any(cid not in available for cid in item.source_ids):
            raise ValueError("blocked_unknown_source_id")
        if item.evidence_level=="SOURCE_SUMMARY" and not item.source_ids:
            raise ValueError("source_summary_requires_real_source_id")
        if item.evidence_level=="SOURCE_SUMMARY" and (not item.scope.strip() or not item.observed_prerequisites):
            raise ValueError("source_summary_requires_claim_scope_and_prerequisites")
        if item.evidence_level=="SOURCE_SUMMARY":
            if not item.source_span_ref.strip() or item.text.strip() != item.source_span_ref.strip():
                raise ValueError("source_summary_must_be_exact_source_span")
            if not any(item.source_span_ref.strip() in str(source_catalog[cid].get("content_excerpt") or "") for cid in item.source_ids):
                raise ValueError("source_summary_span_not_in_cited_source")
        _validate_content(item.text,source_catalog,set(item.source_ids))
        for metadata_text in [item.scope, item.source_span_ref, *item.observed_prerequisites]:
            if metadata_text:
                _validate_content(metadata_text,source_catalog,set(item.source_ids))
    if draft.device_disposition != "UNKNOWN":
        raise ValueError("blocked_model_device_disposition")
    for claim in draft.claims:
        if claim.claim_type == "DEVICE_DISPOSITION":
            raise ValueError("blocked_model_device_disposition_claim")
        if any(cid not in available for cid in claim.source_ids):
            raise ValueError("blocked_unknown_source_id")
        if claim.claim_type == "SOURCE_SUMMARY":
            if not claim.source_ids or not claim.scope.strip() or not claim.observed_prerequisites:
                raise ValueError("source_summary_requires_claim_scope_and_prerequisites")
            if not claim.source_span_ref.strip() or claim.text.strip() != claim.source_span_ref.strip():
                raise ValueError("source_summary_must_be_exact_source_span")
            if not any(claim.source_span_ref.strip() in str(source_catalog[cid].get("content_excerpt") or "") for cid in claim.source_ids):
                raise ValueError("source_summary_span_not_in_cited_source")
        elif claim.source_ids and claim.claim_type not in {"HYPOTHESIS", "INSPECTION_REQUIREMENT"}:
            raise ValueError("source_ids_not_valid_for_claim_type")
        _validate_content(claim.text,source_catalog,set(claim.source_ids))
        for metadata_text in [claim.scope, claim.source_span_ref, claim.safety_consequence, *claim.observed_prerequisites]:
            if metadata_text:
                _validate_content(metadata_text,source_catalog,set(claim.source_ids))
    for missing in draft.missing_info:
        _validate_content(missing.field,source_catalog,set())
        _validate_content(missing.why_it_matters,source_catalog,set())
    # Free-form envelope fields have no claim-level attribution. They may not
    # cite a standard at all; standard-bearing prose must live in a typed item
    # with its own source IDs, scope and prerequisites.
    for text in [draft.summary,*draft.checks,draft.safety_notice,draft.standard_uncertainty]:
        _validate_content(text,source_catalog,set())
    return draft


def deterministic_draft(question: str, context: dict[str, Any], source_catalog: dict[str, dict[str, Any]]) -> ProfessionalExplanationDraft:
    intents=classify_professional_intent(question)
    known=_known_facts(context)
    fact_text="；".join(f"{x['label']}={x['value']}（用户提供，尚非现场独立验证）" for x in known) or "本轮未提供可确认的设备材料、介质或运行参数。"
    safety=any(x in question for x in ("停机","停用","维修","验收","复机","磕碰","撞击"))
    dirs=[]; checks=[]; missing=[]
    if "MaintenanceSafety" in intents:
        summary=f"已收到问题：{fact_text} 当前只能提供分层排查建议，不能据描述确认壳体缺陷程度、法定验收限值或复机许可。"
        dirs=[GuidanceItem(text="若损伤位于承压边界，或发现泄漏、疑似裂纹、持续变形、密封异常、完整性无法确认，应优先采取现场保护性隔离/停止使用评估措施，并按设备管理制度联系有资质人员；这不是远程停机指令或法规阈值。",evidence_level="GENERAL_GUIDANCE"),
              GuidanceItem(text="区分表面擦伤/涂层损坏、凹陷或局部屈曲、裂纹/焊缝受损；仅凭‘磕碰’描述不能判定严重度。",evidence_level="GENERAL_GUIDANCE")]
        checks=["确认设备是否属于承压边界及其类别、介质和运行压力；保留损伤位置、方向与照片。","由合格人员测量损伤长宽深、曲率/变形范围并检查泄漏、裂纹、焊缝、支撑和密封；按适用方案选择表面或体积无损检测。","验收/复机前核对适用监管标准、设计/制造记录、经批准的修理方案和修后检验记录；本轮尚未证实可直接适用的具体条款。"]
        missing=[MissingItem(field="设备类别与是否承压",why_it_matters="决定适用的安全评估和监管路径。"),MissingItem(field="损伤尺寸、位置、形貌及NDT结果",why_it_matters="没有缺陷实测数据不能给出验收结论。"),MissingItem(field="设计资料、运行压力与修理记录",why_it_matters="用于有资质人员校核适用规则和修复方案。")]
    elif known:
        summary="已将用户提供的工况纳入本轮分析；这些字段未作独立复验，减薄形貌和具体机理仍待现场证据确认。"
        dirs=[GuidanceItem(text="可先把问题作为候选机理调查：结合介质组成、pH/杂质、流速/湍流、温压、沉积/水相和损伤形貌比较候选机制；缺项保持未知，不据此排除机理。",evidence_level="GENERAL_GUIDANCE"),
              GuidanceItem(text="‘减薄’描述应由测厚数据及其位置分布确认；温度输入不自动等于金属壁温。",evidence_level="GENERAL_GUIDANCE")]
        checks=["先核实介质化验/水相与pH、关键杂质及流动条件，再与损伤形貌和测厚分布交叉判断。","本地标准检索结果仅作为候选条款；需核对原文、对象、材料、介质、温压和局部条件后才能谈适用性。"]
        medium=context.get("medium") or []
        if any("酸性水" in str(x) for x in (medium if isinstance(medium,list) else [medium])):
            dirs.append(GuidanceItem(text="酸性水相关腐蚀可作为待查方向；弯头处局部减薄还应排查流速/湍流导致的冲蚀或腐蚀-冲蚀协同，并用现场介质分析和损伤形貌区分，不能只凭当前输入确定类别。",evidence_level="HYPOTHESIS_UNVERIFIED"))
        missing=[MissingItem(field="介质pH与关键组分（如硫化物/氯化物）",why_it_matters="用于区分酸性/碱性水及具体腐蚀环境。"),MissingItem(field="流速/流态、沉积物及实测减薄分布",why_it_matters="用于判断弯头局部冲蚀、沉积下腐蚀等竞争解释。"),MissingItem(field="材料牌号或材质证明",why_it_matters="300系列不锈钢不能替代304/316等具体牌号和状态确认。")]
    else:
        is_scc = bool(re.search(r"应力腐蚀开裂|SCC", question, re.I))
        if is_scc:
            summary="应力腐蚀开裂（SCC）是易感材料在特定腐蚀环境与拉应力共同作用下发生的局部开裂；它不同于单纯均匀腐蚀，裂纹可能在总体减薄不明显时发展。"
            dirs=[GuidanceItem(text="一般机理框架通常包括三要素：材料具有相应环境敏感性、存在腐蚀介质/特定环境、存在拉应力（可来自载荷或残余应力）。缺少任一要素的现场证据时，只能解释概念，不能据此诊断某台设备。",evidence_level="GENERAL_GUIDANCE")]
            checks=["工程排查时分别核对材料牌号与热处理状态、介质及温度/浓度等环境因素、焊接或装配残余应力和载荷；再由专业人员通过表面/体积检测确认是否存在裂纹。"]
        else:
            summary="可以先解释一般工程概念，不要求先补齐设备工况；若涉及具体设备诊断、标准条款或RBI等级，再按对应证据门槛处理。"
            dirs=[GuidanceItem(text="一般工程原理可以先讨论；在缺少现场数据时，具体设备是否存在某种损伤仍属待验证问题。",evidence_level="GENERAL_GUIDANCE")]
            checks=["概念解释与设备确诊分开；请求具体条款时应先检索真实本地来源。"]
        missing=[MissingItem(field="具体对象与问题边界（仅在要求设备级判断时）",why_it_matters="概念解释不依赖完整工况；设备级适用性判断需要对应对象。")]
    if source_catalog:
        standard_uncertainty="已获得候选来源，但条款来源存在不等于设备适用性或语义支持已验证；本轮具体标准要求未核实，逐条核对前不作标准结论。"
    else:
        standard_uncertainty="本轮本地标准检索未取得可追溯条款；一般工程建议不等于标准要求，本轮具体标准条款未核实。"
    if safety:
        safety_notice="如存在泄漏、快速扩展变形、裂纹迹象、异常振动/声响、压力边界失效征兆，应按现场应急和设备管理程序采取保护措施并由有资质人员评估；不能据本回答批准继续运行或复机。"
    else:safety_notice="本回答仅为一般工程指导/待核假设，不是设备确诊或风险等级。"
    return ProfessionalExplanationDraft(summary=summary,possible_directions=dirs,checks=checks,missing_info=missing,
        safety_notice=safety_notice,standard_uncertainty=standard_uncertainty,claims=[],device_disposition="UNKNOWN")


def render_professional_response(draft: ProfessionalExplanationDraft, known_facts: list[dict[str,Any]], source_catalog: dict[str,dict[str,Any]]) -> str:
    # This is the last trust boundary: callers cannot bypass structured checks
    # by invoking the renderer directly with a hand-built or mutated model.
    try:
        draft=validate_professional_draft(draft.model_dump(mode="json"),source_catalog)
    except (ValueError, ValidationError, TypeError):
        draft=ProfessionalExplanationDraft(
            summary="当前生成内容未通过高后果结论校验，已回退到有界工程排查建议；缺失数据不能作为无缺陷或安全证明。",
            possible_directions=[GuidanceItem(text="记录损伤位置、形貌、长宽深及变化，核实设备是否属于承压边界、设备类别和设计/运行条件；后续评估由有资质人员结合实测检查确定。",evidence_level="GENERAL_GUIDANCE")],
            checks=["保存照片、测量和检测记录；发现泄漏、疑似裂纹、持续变形或边界失效征兆时，依现场程序采取保护性处置并联系责任人员。"],
            missing_info=[MissingItem(field="设备类别、损伤实测和适用工况",why_it_matters="这些资料决定后续检查路径；仅凭自然语言描述不能评定L级、风险或复机条件。")],
            safety_notice="本回答不作设备处置许可或安全结论。",standard_uncertainty="具体标准适用性尚未核实；应核对适用条款及其对象和前提。",
            risk_level=None,device_diagnosis_confirmed=False,claims=[],device_disposition="UNKNOWN")
    def display_value(value: Any) -> str:
        if isinstance(value, list): return "、".join(str(item) for item in value)
        if isinstance(value, dict): return json.dumps(value,ensure_ascii=False,sort_keys=True)
        return str(value)
    parts=[]
    # Safety-significant questions must lead with actionable hazard triage,
    # rather than burying it after retrieval metadata.
    safety_first = draft.safety_notice.startswith("如存在")
    if safety_first:
        parts.append("**先行安全提示 / 安全边界：** "+draft.safety_notice)
    parts += ["**已知工况：** "+("；".join(f"{x.get('label') or x.get('field') or '工况'}={display_value(x.get('value'))}（{x.get('provenance', 'provided_context')}，未作独立实测确认）" for x in known_facts) if known_facts else "本轮未提供可确认工况。"),draft.summary]
    if draft.possible_directions:
        parts.append("**可能方向（非设备确诊）：**\n"+"\n".join(f"- [{x.evidence_level}] {x.text}" for x in draft.possible_directions))
    if source_catalog:
        actual=[]
        relevance_order=("损伤相关", "检查方法候选", "一般评定原则", "主题直接匹配", "条件性检验周期", "埋藏缺陷")
        ranked=sorted(source_catalog.items(),key=lambda item:next((i for i,term in enumerate(relevance_order) if term in str(item[1].get("relevance_label") or "")),len(relevance_order)))
        displayed=ranked[:3]
        for cid,r in displayed:
            row=(f"- {r.get('standard_code','')} {r.get('clause_no','')}《{r.get('title','未标注标题')}》（印刷页 {r.get('page','未知')}；"
                 f"来源ID `{cid}`；相关性：{r.get('relevance_label','候选待核')}；适用边界：{r.get('scope_note','')}）")
            excerpt=str(r.get("content_excerpt") or "").strip()
            if excerpt: row += f"\n  - 原文短摘：{excerpt[:160]}{'…' if len(excerpt)>160 else ''}"
            if cid == "TSG21-2016-8.5.8":
                row += "\n  - 安全解释：原文中的3/4/5级属于满足条款前提后的条件性等级，不是当前设备等级；未核实裂纹及处置前提前不得套用。"
            actual.append(row)
        parts.append("**本轮检索到的本地标准候选（仅为实际返回且通过语义/边界筛选，不等于设备验收结论）：**\n"+"\n".join(actual))
        if len(ranked)>len(displayed):
            parts.append(f"另有{len(ranked)-len(displayed)}条低优先级来源候选未展开；完整标识保留在审查轨迹中，均为E0待核。")
    else:
        parts.append("**标准状态：** 本地检索未取得可追溯条款（没有取得可追溯条款）；未引用具体标准条款或法定限值。")
    if draft.checks:parts.append("**下一步排查：**\n"+"\n".join(f"{i+1}. {x}" for i,x in enumerate(draft.checks)))
    if draft.missing_info:parts.append("**缺项及原因：**\n"+"\n".join(f"- {x.field}：{x.why_it_matters}" for x in draft.missing_info))
    if draft.safety_notice and not safety_first:
        parts.append("**安全边界：** "+draft.safety_notice)
    if draft.standard_uncertainty:parts.append("**来源说明：** "+draft.standard_uncertainty)
    parts.append("设备确诊、法定验收/复机结论和RBI风险等级均未确认。")
    rendered="\n\n".join(parts)
    # Re-scan the assembled user-visible answer, including labels and appended
    # text. If any field interaction creates an unsafe implication, return a
    # safe useful fallback rather than rejecting the whole request.
    # Canonical source excerpts are evidence quotations, not generated device
    # dispositions. They remain visibly attributed and scoped above, while all
    # model/generated prose is still rescanned as a separate trust domain.
    generated_text = re.sub(r"(?m)^\s*- 原文短摘：.*$", "", rendered)
    if _contains_disposition_permission(generated_text):
        return ("**已知工况：** "+("；".join(f"{x.get('label') or x.get('field') or '工况'}={display_value(x.get('value'))}（用户提供，未独立核实）" for x in known_facts) if known_facts else "本轮未提供可确认工况。")+
                "\n\n**一般工程指导：** 本轮输入不足以给出设备L级、风险结论或复机许可；不得把缺失数据当成无缺陷证据。记录损伤位置、形貌、长宽深及变化，核实是否属于承压边界、设备类别、设计资料和运行参数。\n\n"
                "如发现泄漏、疑似裂纹、持续变形、异常振动或边界失效征兆，按现场管理程序采取保护性处置并联系有资质人员；保存照片、检测结果、维修与复检记录。\n\n"
                "**待核门槛：** 由具备资质的责任人员依据适用标准、设备资料和实测检查确定后续评估。具体标准适用性、设备状态、风险等级及验收/复机结论均未确认。")
    return rendered


def source_catalog_from_run(citations: list[dict[str,Any]], tool_calls: list[dict[str,Any]], canonical_index: dict[str,dict[str,Any]],
                            question: str = "", context: dict[str, Any] | None = None) -> dict[str,dict[str,Any]]:
    returned={}
    for call in tool_calls or []:
        if not isinstance(call,dict):continue
        result=call.get("result") or {}
        for ref in (result.get("source") or []):
            if isinstance(ref,dict) and ref.get("clause_id"):returned[str(ref['clause_id'])]=ref
    catalog={}
    q=str(question or "")
    ctx=context or {}
    impact_question=bool(re.search(r"磕碰|碰撞|撞击|凹陷|变形|机械损伤",q))
    maintenance=bool((re.search(r"壳体|承压边界|压力容器|容器",q) and re.search(r"验收|维修|修理|停机|停用|复机",q)) or impact_question)
    media=ctx.get("medium") or ctx.get("raw_medium") or []
    media=media if isinstance(media,list) else [media]
    exact_medium=[str(x) for x in media if "酸性水" in str(x)]
    for citation in citations or []:
        catalog_state="POSSIBLE_WITH_CONDITION_UNKNOWN"
        cid=str(citation.get("clause_id") or "")
        raw=returned.get(cid); canonical=canonical_index.get(cid)
        if not raw or not canonical:continue
        if any(str(raw.get(k))!=str(canonical.get(k)) for k in ("standard_code","clause_no","page")):continue
        title=str(canonical.get("title") or "")
        relevance_label = "本轮实际检索候选"
        scope_note = "条款原文与设备/工况适用性仍需核对；不能单独支持设备级处置结论。"
        raw_text = str(canonical.get("content_raw") or "")
        if maintenance:
            # Lexical retrieval can return false friends (e.g. “collision” in
            # irradiation damage). Keep only clauses whose actual canonical
            # text supports a bounded, explicitly stated relation.
            if re.search(r"辐照|脆化|耐火材料|爆破片|安全阀|泄放装置", title + " " + raw_text):
                continue
            if re.search(r"检验周期", title) and not re.search(r"缩短", title):
                continue
            if re.search(r"表面缺陷检测", title):
                relevance_label = "检查方法候选，非损伤验收标准"
                scope_note = "条文涉及产生机械损伤现象的压力容器表面缺陷检测；需由检验人员结合缺陷位置、材料和检测方案确定。"
            elif re.search(r"埋藏缺陷检测", title):
                relevance_label = "条件性检查方法候选，非壳体凹陷验收标准"
                scope_note = "条文主要针对焊缝埋藏缺陷及特定触发条件；只有发现焊缝/埋藏缺陷线索时才可进一步适用。"
            elif re.search(r"检验周期的缩短", title) and re.search(r"机械损伤", raw_text) and re.search(r"开裂|裂纹", raw_text):
                relevance_label = "条件性检验周期候选"
                scope_note = "原文将周期缩短条件限定为机械损伤且已经发现开裂等情形；当前未确认开裂，不据此确定检验周期。"
            elif re.search(r"环境开裂和机械损伤", title) and re.search(r"机械损伤", raw_text) and re.search(r"裂纹|开裂", raw_text):
                relevance_label = "损伤相关，但仅在发现裂纹等条件下适用"
                scope_note = "原文将机械损伤与已发现裂纹等情形相连；仅在发现裂纹等符合原文情形时作条件性参考。当前用户未报告裂纹，不能据此直接判定等级或验收。"
            elif re.search(r"安全状况等级|检验结果综合评定", raw_text) and re.search(r"压力容器", raw_text):
                relevance_label = "一般评定原则候选，非凹陷验收限值"
                scope_note = "仅涉及在用压力容器综合评定原则；不能给出本损伤的尺寸阈值或修理验收值。"
            else:
                continue
        elif exact_medium:
            # Acid-/alkaline-water are distinct scenarios. Do not display the
            # opposite-form clause as though it matched this user's medium.
            required=any(x in title for x in exact_medium)
            if not required:
                continue
            conditions = canonical.get("applicable_conditions") or {}
            mismatches=[]; unknown=[]
            for field in ("equipment_type", "material", "medium"):
                allowed=conditions.get(field) or []
                actual=ctx.get(field)
                actuals=actual if isinstance(actual,list) else ([actual] if actual not in (None,"",[]) else [])
                if allowed and not actuals: unknown.append(field)
                elif allowed and any(str(value) not in {str(item) for item in allowed} for value in actuals): mismatches.append(field)
            temp_range=conditions.get("temperature_c") or []
            temp=ctx.get("temperature_c")
            local_scope_523 = cid == "GBT30579-2022-5.23"
            if len(temp_range)==2 and any(x is not None for x in temp_range) and not local_scope_523:
                if temp is None: unknown.append("temperature_c")
                elif (temp_range[0] is not None and temp < temp_range[0]) or (temp_range[1] is not None and temp > temp_range[1]): mismatches.append("temperature_c")
            if mismatches:
                continue
            if unknown:
                relevance_label="主题直接匹配；适用条件尚未完整核对"
                scope_note="来源标题匹配用户主题；仍缺条件字段："+", ".join(unknown)+"。现有用户陈述未经独立现场验证。"
            else:
                relevance_label="主题直接匹配；所列工况字段与用户陈述相符"
                scope_note="该来源讨论对应损伤机理；材料/介质/设备类型/温度仅为输入字段匹配，不能替代成分、材质和温度实测或设备诊断。"
            if local_scope_523:
                relevance_label="酸性水相关待核候选；局部温区不作为全机理排除条件"
                scope_note=("POSSIBLE_WITH_CONDITION_UNKNOWN：原条目49–66℃对应硫氢化铵气相析出的局部现象条件；"
                            f"当前用户温度为{temp if temp is not None else '未知'}℃，该局部条件是否成立仍未知。不得据此将整种酸性水腐蚀机理判为适用或不适用。")
                catalog_state="POSSIBLE_WITH_CONDITION_UNKNOWN"
            else:
                catalog_state="POSSIBLE_WITH_CONDITION_UNKNOWN" if unknown else "CANDIDATE_CONTEXT_MATCH_ONLY"
        catalog[cid]={"standard_code":canonical.get("standard_code"),"clause_no":canonical.get("clause_no"),"page":canonical.get("page"),
                      "title":canonical.get("title"),"source_id":cid,
                      "verification":"teacher_tool_return_and_canonical_metadata_match_E0","evidence_level":"E0",
                      "relevance_label":relevance_label,"scope_note":scope_note,"content_excerpt":raw_text[:220],
                      "applicability_state":catalog_state}
    return catalog
