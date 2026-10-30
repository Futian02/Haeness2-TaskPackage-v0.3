"""三个工具的落地实现（数据驱动，不硬编码任何条款内容）。

对应文件：
- 04_接口文档/工具接口规范.md        第二部分的三个工具定义（唯一口径）
- 04_接口文档/schema/tool_response.schema.json  统一返回外壳
- 04_接口文档/enums.json             材质/介质/设备类型白名单与别名
- 04_接口文档/material_family.json   牌号 -> 材料类别
- 04_接口文档/risk_level_mapping.xlsx 风险等级映射（定稿，只读）
- 05_提交区/clauses.jsonl            条款库（只读）

设计红线（全部来自规范原文）：
1. 工具只有三个，名称与参数名不得增删改。
2. 返回必须经 make_response 构造，五个顶层字段，status=ok 时 source 非空。
3. in_domain=False 时 result 必须为空对象 {}，message 必须说明超出了什么。
4. 条款内容一律从 clauses.jsonl 读取，代码里不出现任何条文文本。
5. risk_level_unified 只查 risk_level_mapping.xlsx，不自行推断。
6. 风险等级必须"成对"给出：原始等级与统一等级同源于同一条记录；
   绝不允许跨条款拼接失效可能性与后果等级（那会产出看似有依据的错误结论）。

数据现状（实测，决定了下面的实现方式）：
- damage_mechanism 82 条：mechanism_detail 八段全部非空，可直接映射。
- rbi 379 条：仅 25 条（GB/T 26610.3 第 7 章图 1 的 5x5 矩阵格 7-a~7-y）
  同时具备 likelihood 与 consequence；inspection_interval_year 全库为空（0 条）。
  因此 rbi_lookup 在缺少成对等级时按规范返回 not_found，不编造等级或周期。
"""

from __future__ import annotations

import json
import math
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

# ---------------------------------------------------------------- 路径
SUBMIT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SUBMIT_DIR.parent
CLAUSES_PATH = SUBMIT_DIR / "clauses.jsonl"
ENUMS_PATH = PROJECT_ROOT / "04_接口文档" / "enums.json"
FAMILY_PATH = PROJECT_ROOT / "04_接口文档" / "material_family.json"
MAPPING_PATH = PROJECT_ROOT / "04_接口文档" / "risk_level_mapping.xlsx"

# ---------------------------------------------------------------- 常量
STATUS_SET = ("ok", "out_of_domain", "not_found", "error")

# 八段式内容字段（规范 2.2，不得增删改名）
EIGHT_FIELDS = (
    "description",
    "morphology",
    "affected_materials",
    "influencing_factors",
    "susceptible_locations",
    "prevention",
    "detection_methods",
    "related_damages",
)

# evidence 六个子字段及类型（规范 2.2；未提供 != false）
EVIDENCE_FIELDS: Dict[str, type] = {
    "ph": (int, float),
    "cl_ppm": (int, float),
    "fe_ppm": (int, float),
    "h2s_ppm": (int, float),
    "wall_thinning": bool,
    "crack_found": bool,
}

EVIDENCE_PURPOSE = {
    "ph": "pH 决定湿硫化氢破坏与盐酸腐蚀的取舍",
    "cl_ppm": "氯离子浓度用于判别氯化铵腐蚀与氯化物应力腐蚀开裂",
    "fe_ppm": "铁离子反映腐蚀速率与腐蚀是否在持续",
    "h2s_ppm": "硫化氢浓度或分压是湿硫化氢破坏的必要判据",
    "wall_thinning": "测厚结果用于区分均匀减薄类与开裂类机理",
    "crack_found": "裂纹检测结果用于区分应力腐蚀开裂与腐蚀减薄",
}

# 判据关键词：某机理的"主要影响因素/描述"提到这些词，说明判定它需要对应证据。
# 证据没给就降权，避免"只要材质对就排第一"。
EVIDENCE_KEYWORDS: Dict[str, Tuple[str, ...]] = {
    "ph": ("pH", "PH"),
    "cl_ppm": ("氯离子", "氯化物"),
    "fe_ppm": ("铁离子",),
    "h2s_ppm": ("硫化氢", "H2S", "H₂S"),
    "wall_thinning": ("减薄", "壁厚"),
    "crack_found": ("裂纹",),
}


# ================================================================
# 0. 统一返回外壳
# ================================================================
def make_response(
    status: str = "ok",
    in_domain: bool = True,
    result: Optional[dict] = None,
    source: Optional[List[dict]] = None,
    message: str = "",
) -> dict:
    """三个工具唯一的返回构造入口，逻辑与骨架 harness.make_response 一致。"""
    if status not in STATUS_SET:
        raise ValueError(f"非法 status: {status!r}")
    resp = {
        "status": status,
        "in_domain": bool(in_domain),
        "result": result if result is not None else {},
        "source": source if source is not None else [],
        "message": message,
    }
    # 硬性红线：ok 必须带出处
    if resp["status"] == "ok" and not resp["source"]:
        raise ValueError("status=ok 的返回必须包含 source，这是硬性要求")
    # 超范围不得给结论（护栏 check_in_domain 同款规则）
    if resp["in_domain"] is False and resp["result"]:
        raise ValueError("in_domain=False 时 result 必须为空对象")
    if resp["in_domain"] is False and not resp["message"].strip():
        raise ValueError("in_domain=False 时 message 必须说明超出了什么")
    return resp


def _src(record: dict) -> dict:
    """从记录构造 source 项，只取 schema 允许的四个键。"""
    return {
        "clause_id": record["clause_id"],
        "standard_code": record["standard_code"],
        "clause_no": record["clause_no"],
        "page": int(record["page"]),
    }


# ================================================================
# 1. 数据加载
# ================================================================
@lru_cache(maxsize=1)
def load_clauses() -> Tuple[dict, dict]:
    """返回 (records_by_id, aggregates)。只读一次，进程内缓存。"""
    records: List[dict] = []
    with CLAUSES_PATH.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    by_id = {rec["clause_id"]: rec for rec in records}
    aggregates = {
        "all": records,
        "damage_mechanism": [r for r in records if r.get("knowledge_type") == "damage_mechanism"],
        "rbi": [r for r in records if r.get("knowledge_type") == "rbi"],
    }
    return by_id, aggregates


@lru_cache(maxsize=1)
def load_enums() -> Dict[str, Dict[str, dict]]:
    with ENUMS_PATH.open(encoding="utf-8") as fh:
        data = json.load(fh)
    return {name: data[name] for name in ("material", "medium", "equipment_type")}


@lru_cache(maxsize=1)
def load_family() -> Dict[str, List[str]]:
    if not FAMILY_PATH.exists():
        return {}
    data = json.loads(FAMILY_PATH.read_text(encoding="utf-8"))
    return {key: value["belongs_to"] for key, value in data["family"].items()}


@lru_cache(maxsize=1)
def load_risk_mapping() -> Tuple[Dict[Tuple[str, str], Tuple[str, str]], Dict[str, str]]:
    """读定稿映射表：((失效可能性, 失效后果) -> (原始等级, 统一等级), 用语 -> 统一等级)。"""
    try:
        import openpyxl
    except ImportError:  # pragma: no cover
        return {}, {}
    wb = openpyxl.load_workbook(MAPPING_PATH, data_only=True, read_only=True)
    pairs: Dict[Tuple[str, str], Tuple[str, str]] = {}
    if "GBT26610.3-2014" in wb.sheetnames:
        for row in wb["GBT26610.3-2014"].iter_rows(min_row=2, values_only=True):
            if row and row[0] is not None and row[1] is not None:
                key = (str(row[0]).strip(), str(row[1]).strip())
                pairs[key] = (str(row[2]).strip(), str(row[3]).strip())
    words: Dict[str, str] = {}
    if "按用语对应" in wb.sheetnames:
        for row in wb["按用语对应"].iter_rows(min_row=2, values_only=True):
            if row and row[0]:
                words[str(row[0]).strip()] = str(row[1]).strip()
    wb.close()
    return pairs, words


# ================================================================
# 2. 归一化与文本工具
# ================================================================
def normalize_enum(table_name: str, value: str) -> str:
    """别名 -> 规范值；已在表内则原样返回；不在表内返回 None。"""
    table = load_enums().get(table_name, {})
    if not isinstance(value, str):
        return None
    if value in table:
        return value
    for canonical, entry in table.items():
        if value in entry.get("aliases", []):
            return canonical
    return None


def material_candidates(material: str) -> List[str]:
    """牌号向上扩展为材料类别，用于匹配 affected_materials（保留标准原文写法）。"""
    family = load_family()
    out: List[str] = []
    queue = [material]
    while queue:
        item = queue.pop(0)
        if item in out:
            continue
        out.append(item)
        queue.extend(family.get(item, []))
    return out


def _snippet(text: str, limit: int = 200) -> str:
    """≤200 字；按句读边界截断并加省略号（规范允许为要点摘录，不要求原文截断）。"""
    text = re.sub(r"\s+", " ", (text or "").strip())
    if len(text) <= limit:
        return text
    cut = text[: limit - 1]
    for mark in ("。", "；", ";", "，", ","):
        pos = cut.rfind(mark)
        if pos >= limit * 0.5:
            return cut[: pos + 1].rstrip() + "…"
    return cut.rstrip() + "…"


def _tokens(keyword: str) -> List[str]:
    """关键词切分为检索项：空白与常见标点切分，去重保序。"""
    raw = re.split(r"[\s,，、;；/|()（）【】\[\]{}]+", keyword or "")
    terms: List[str] = []
    for item in raw:
        item = item.strip()
        if item and item not in terms:
            terms.append(item)
    return terms or ([keyword.strip()] if keyword and keyword.strip() else [])


def _coverage(term: str, text: str) -> float:
    """单项覆盖率：整体命中记 1；否则按 2-gram 覆盖率折算。"""
    if not term:
        return 0.0
    if term in text:
        return 1.0
    if len(term) < 2:
        return 0.0
    grams = [term[i : i + 2] for i in range(len(term) - 1)]
    if not grams:
        return 0.0
    return sum(1 for gram in grams if gram in text) / len(grams)


# ================================================================
# 3. 工具一：damage_mechanism_query
# ================================================================
def _validate_evidence(evidence: Any) -> Tuple[Optional[dict], Optional[str]]:
    """校验 evidence；返回 (规整后的证据, 错误说明)。未提供的字段不写入。"""
    if evidence is None:
        return {}, None
    if not isinstance(evidence, dict):
        return None, "evidence 必须是对象，子字段为 ph/cl_ppm/fe_ppm/h2s_ppm/wall_thinning/crack_found"
    cleaned: Dict[str, Any] = {}
    for key, value in evidence.items():
        if key not in EVIDENCE_FIELDS:
            return None, f"evidence 含未知子字段 {key!r}，只允许 {sorted(EVIDENCE_FIELDS)}"
        if value is None:
            continue  # 明确无关
        expected = EVIDENCE_FIELDS[key]
        if expected is bool:
            if not isinstance(value, bool):
                return None, f"evidence.{key} 应为 boolean，收到 {type(value).__name__}"
        else:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                return None, f"evidence.{key} 应为 number，收到 {type(value).__name__}"
        cleaned[key] = value
    return cleaned, None


def _temperature_ok(record: dict, temperature_c: Optional[float]) -> Tuple[bool, str]:
    """按 applicable_conditions.temperature_c=[下限,上限] 判断；null 表示开区间。"""
    if temperature_c is None:
        return True, ""
    low, high = (record.get("applicable_conditions") or {}).get("temperature_c") or [None, None]
    if low is not None and temperature_c < low:
        return False, f"{temperature_c}℃ 低于该条款适用下限 {low}℃"
    if high is not None and temperature_c > high:
        return False, f"{temperature_c}℃ 高于该条款适用上限 {high}℃"
    return True, ""


def medium_terms(mediums: List[str]) -> Dict[str, List[str]]:
    """规范介质 -> 该介质自身及其全部已登记别名，用于正文匹配。

    介质枚举里只有 26/82 条损伤机理条款登记了 applicable_conditions.medium，
    其余条款的介质信息只存在于正文，因此正文匹配需要带上别名（如 氯化氢/HCl/盐酸）。
    """
    table = load_enums().get("medium", {})
    out: Dict[str, List[str]] = {}
    for canonical in mediums:
        terms = [canonical]
        for alias in table.get(canonical, {}).get("aliases", []):
            if alias not in terms:
                terms.append(alias)
        out[canonical] = terms
    return out


def _medium_text(record: dict) -> str:
    """介质匹配专用文本：只看与本机理自身相关的段落。

    不扫 prevention / detection_methods / related_damages——这些段落常提到
    其他机理的介质（如「盐酸腐蚀」的相关损伤里写着氯化铵），扫全文本会串味。
    """
    detail = record.get("mechanism_detail") or {}
    parts = [record.get("title") or "", detail.get("description") or ""]
    for key in ("morphology", "influencing_factors", "susceptible_locations"):
        value = detail.get(key)
        if isinstance(value, (list, tuple)):
            parts.extend(str(v) for v in value)
        elif isinstance(value, str):
            parts.append(value)
    cond = record.get("applicable_conditions") or {}
    if cond.get("other"):
        parts.append(str(cond["other"]))
    return "\n".join(p for p in parts if p)


def _medium_signal(record: dict, mediums: List[str],
                   terms_map: Optional[Dict[str, List[str]]] = None) -> Tuple[bool, bool]:
    """返回 (强命中, 弱命中)：强=条款适用介质枚举命中；弱=本机理正文提到介质（含别名）。"""
    cond_medium = (record.get("applicable_conditions") or {}).get("medium") or []
    strong = any(m in cond_medium for m in mediums)
    terms_map = terms_map or medium_terms(mediums)
    text = _medium_text(record)
    weak = any(term and term in text for terms in terms_map.values() for term in terms)
    return strong, weak


def _evidence_support(record: dict, evidence_map: Optional[dict]) -> Tuple[int, List[str]]:
    """阳性证据加权：现场实测到的、且条款判据里提到的证据项，支持该机理。

    与"缺失降权"互补——只对**已提供且为阳性**的证据加分：
    布尔项为 True、数值项 > 0 才算阳性；为 False 不加分也不排除
    （规范明确"未提供现场证据不等同于 false"，"未见裂纹"也不能排除点蚀）。
    """
    if not evidence_map:
        return 0, []
    text = _medium_text(record)
    delta = 0
    notes: List[str] = []
    for key, value in evidence_map.items():
        # 只对布尔型阳性证据加权：pH/氯离子/铁离子/硫化氢这类数值几乎所有机理都会提到，
        # 普遍加分等于没加分；它们的判别作用交给 pH 阈值与监测项匹配处理。
        if not isinstance(value, bool) or value is not True:
            continue
        words = EVIDENCE_KEYWORDS.get(key)
        if not words or not any(word in text for word in words):
            continue
        delta += 2
        notes.append(f"现场阳性（{key}）支持该机理")
    return min(4, delta), notes


def _descendants(material: str, depth: int = 4) -> List[str]:
    """材料族向下展开：类别 -> 更具体的子类别/牌号（用于给"请细化"的建议）。"""
    family = load_family()
    out: List[str] = []
    frontier = [material]
    for _ in range(depth):
        nxt: List[str] = []
        for node in frontier:
            for child, parents in family.items():
                if node in parents and child != material and child not in out:
                    out.append(child)
                    nxt.append(child)
        frontier = nxt
        if not frontier:
            break
    return out


def _material_signal(record: dict, material: str) -> Tuple[bool, bool]:
    """返回 (精确命中, 同类命中)。

    匹配依据按可靠性排序：
      ① applicable_conditions.material —— 这是官方指南 §2.2 定义的「适用材质」，
         只登记 enums.json 能表达的规范值（实测 200 个取值 100% 命中枚举、零越界），
         枚举外的材料另写入「其他适用条件」。因此它是**最可靠**的匹配依据。
      ② mechanism_detail.affected_materials —— 摘录人照抄的原文「受影响的材料」，
         大量记录写的是叙述句（如「压力大于或等于0.1 MPa的低压氧气中碳钢即可能燃烧」）
         而非材料清单，片段切分后取不到「碳钢」这类规范名，只能作辅助。

    历史问题：早期版本只对照 ②，导致 35/82 条记录（如 9.10 高含氧气体促发的燃烧爆炸、
    8.2 热疲劳、8.10 蠕变）因叙述句切不出规范材料名而完全查不到 —— 机理明明适用
    碳钢/低合金钢，却因材质匹配失败被丢弃。现改为 ① 优先、② 辅助。
    """
    # ① 适用材质（规范化字段，优先）
    cond_materials = (record.get("applicable_conditions") or {}).get("material") or []
    if material in cond_materials:
        return True, False
    if any(c != material and c in cond_materials for c in material_candidates(material)):
        return False, True

    # ② 受影响的材料（原文照抄，辅助）：先按材料清单切分，再退回叙述句子串
    fragments = _material_fragments(record)
    if material in fragments:
        return True, False
    if any(c != material and c in fragments for c in material_candidates(material)):
        return False, True
    blob = " ".join(str(x) for x in
                    ((record.get("mechanism_detail") or {}).get("affected_materials") or []))
    if blob:
        if material in blob:
            return True, False
        if any(c != material and c in blob for c in material_candidates(material)):
            return False, True
    return False, False


_MATERIAL_SPLIT = re.compile(r"[、，,；;：:/\s]+|以及|[和及与]")


def _material_fragments(record: dict) -> List[str]:
    """匹配用：把 affected_materials 拆成单个材料名片段。"""
    items = (record.get("mechanism_detail") or {}).get("affected_materials") or []
    out: List[str] = []
    for item in items:
        for part in _MATERIAL_SPLIT.split(str(item)):
            part = part.strip(" 。.：:；;，,（）()")
            if part:
                out.append(part)
    return out


def _material_display(record: dict) -> List[str]:
    """返回用：只在元素是纯材料清单时拆开，带句意或叙述的整句原样保留。"""
    items = (record.get("mechanism_detail") or {}).get("affected_materials") or []
    out: List[str] = []
    for item in items:
        text = str(item).strip()
        pure_list = len(text) <= 60 and not any(mark in text for mark in ("：", ":", "。", "顺序", "取决"))
        if pure_list:
            parts = [p.strip(" 。.") for p in _MATERIAL_SPLIT.split(text) if p.strip(" 。.")]
            out.extend(parts or [text])
        else:
            out.append(text)
    return out


def _match_level(exact: bool, family: bool, strong_medium: bool, weak_medium: bool,
                 equipment_hit: bool, temperature_c: Optional[float], temp_bounded: bool,
                 missing_evidence: int = 0, support: int = 0) -> str:
    """匹配强度。high 需要四个维度精确命中且该机理所需证据齐全；
    证据不齐时最多给 medium —— 否则会出现"缺关键证据却排在首位"的误导性排序。
    常规直配（材质+介质）按标注示范的口径取 medium。"""
    # high = 四维精确命中 + 该机理所需证据齐全 + 至少一项现场阳性证据支持。
    # 只满足"看起来匹配"而没有现场证据时封顶 medium，与标注示范的口径一致。
    if (exact and strong_medium and equipment_hit and temperature_c is not None
            and temp_bounded and missing_evidence == 0 and support > 0):
        return "high"
    if (exact or family) and (strong_medium or weak_medium):
        return "medium"
    return "low"


def damage_mechanism_query(
    material: str,
    medium: List[str],
    temperature_c: Optional[float] = None,
    equipment_type: Optional[str] = None,
    evidence: Optional[dict] = None,
) -> dict:
    """输入材质+介质（+温度/设备/现场证据），返回可能的损伤机理及鉴别要点。"""
    # --- 入参校验与归一化（护栏已归一化，这里再兜底一次，便于单独调用）---
    canon_material = normalize_enum("material", material) or material
    if not isinstance(medium, list) or not medium:
        return make_response(
            "error", False, {}, [],
            "medium 必须是非空字符串数组，例如 [\"湿硫化氢\",\"氯化氢\"]；不接受逗号分隔的字符串。",
        )
    canon_mediums: List[str] = []
    for item in medium:
        canon = normalize_enum("medium", item)
        if canon is None:
            return make_response(
                "error", False, {}, [],
                f"介质 {item!r} 不在 enums.json 的 medium 表中；请改用规范值或已登记的别名。",
            )
        canon_mediums.append(canon)
    if equipment_type is not None:
        canon_equipment = normalize_enum("equipment_type", equipment_type)
        if canon_equipment is None:
            return make_response(
                "error", False, {}, [],
                f"设备类型 {equipment_type!r} 不在 enums.json 的 equipment_type 表中；"
                f"合法取值：{sorted(load_enums()['equipment_type'])}。",
            )
        equipment_type = canon_equipment

    evidence_map, evidence_error = _validate_evidence(evidence)
    if evidence_error:
        return make_response("error", False, {}, [], evidence_error)

    _, aggregates = load_clauses()
    candidates: List[Tuple[float, dict, dict]] = []   # (score, record, 信号)
    excluded: List[dict] = []                          # 有信息量的排除（介质冲突/温度越界）
    excluded_records: List[dict] = []                  # 对应记录，out_of_domain 时作为 source 给出
    silent_excluded = 0                                # 仅因"未涉及输入介质"被排除的数量
    terms_map = medium_terms(canon_mediums)

    for record in aggregates["damage_mechanism"]:
        exact, family = _material_signal(record, canon_material)
        if not (exact or family):
            continue  # 材质不在受影响材料内，不作为候选
        strong_medium, weak_medium = _medium_signal(record, canon_mediums, terms_map)
        cond_medium = (record.get("applicable_conditions") or {}).get("medium") or []

        # 介质硬条件一：条款登记了适用介质且完全不匹配 -> 排除
        if cond_medium and not strong_medium:
            excluded.append({
                "name": record.get("title", ""),
                "reason": f"该条款适用介质为 {cond_medium}，与输入介质 {canon_mediums} 不匹配",
            })
            excluded_records.append(record)
            continue

        # 介质硬条件二：条款未登记适用介质，且本机理正文也没提到输入介质 -> 排除
        # （否则只要材质相同就会被列为候选，例如碳钢会误命中乙醇应力腐蚀开裂）
        # 这类排除数量多、信息量低，只计数不逐条罗列，避免返回体被噪音淹没。
        if not cond_medium and not weak_medium:
            silent_excluded += 1
            continue

        # 温度硬条件
        temp_ok, temp_reason = _temperature_ok(record, temperature_c)
        if not temp_ok:
            excluded.append({
                "name": record.get("title", ""),
                "reason": temp_reason,
            })
            excluded_records.append(record)
            continue

        equipment_hit = bool(
            equipment_type
            and equipment_type in ((record.get("applicable_conditions") or {}).get("equipment_type") or [])
        )
        score = (
            (3 if exact else 0)
            + (2 if family and not exact else 0)
            + (3 if strong_medium else 0)
            + (1 if weak_medium and not strong_medium else 0)
            + (1 if equipment_hit else 0)
        )
        temp_bounded = any(
            bound is not None
            for bound in ((record.get("applicable_conditions") or {}).get("temperature_c") or [None, None])
        )
        # 证据感知降权：该机理的判据里提到的证据项若未提供，说明当前还判不了它
        evidence_text = _medium_text(record)
        missing_keys = [
            key for key, words in EVIDENCE_KEYWORDS.items()
            if key not in (evidence_map or {}) and any(word in evidence_text for word in words)
        ]
        score -= min(2, len(missing_keys))

        # ③ 阳性证据加权（与缺失降权互补）
        support, support_notes = _evidence_support(record, evidence_map)
        score += support

        # ① 条款未登记温度边界时，无法判断给定温度下是否适用：降权并计数
        temp_unknown = (temperature_c is not None and not temp_bounded)
        if temp_unknown:
            score -= 1
        level = _match_level(exact, family, strong_medium, weak_medium, equipment_hit,
                             temperature_c, temp_bounded, len(missing_keys), support)
        candidates.append((score, record, {"level": level, "equipment_hit": equipment_hit,
                                           "missing_evidence": missing_keys,
                                           "support_notes": support_notes,
                                           "temp_unknown": temp_unknown}))

    if not candidates:
        # ② 输入的是"材料类别"（如"不锈钢"）时，条款按更具体的类别/牌号登记适用范围，
        # 这不是"超出条款覆盖范围"，而是"需要细化"。按类别本身检索必然 0 候选。
        descendants = _descendants(canon_material)
        known = set()
        for rec in aggregates["damage_mechanism"]:
            known.update(_material_fragments(rec))
        # 只有"该类别本身没有被条款直接登记"时，才属于'需要细化'的情形。
        # 像「碳钢」既是类别、又直接出现在条款受影响材料里，命中不到候选说明是介质/温度
        # 不匹配（应报超范围），不能反过来让用户去细化材质。
        if descendants and canon_material not in known:
            usable = [item for item in descendants if item in known]
            hint = "、".join((usable or descendants)[:6])
            message = (
                f"「{canon_material}」是材料类别，条款按更具体的类别或牌号登记适用范围，"
                f"按类别本身检索不到候选。请细化为：{hint}；或直接给出牌号（如 06Cr19Ni10）。"
            )
            return make_response("not_found", True, {}, [], message)

        scope = f"材质 {canon_material}、介质 {canon_mediums}"
        if temperature_c is not None:
            scope += f"、温度 {temperature_c}℃"
        near = "；".join(f"{item['name']}（{item['reason']}）" for item in excluded[:5])
        message = f"当前条款库未覆盖 {scope} 的损伤机理判定。"
        if near:
            message += f"已核对的相近条款被排除：{near}。"
        if silent_excluded:
            message += f"另有 {silent_excluded} 条同材质条款因未涉及输入介质被排除。"
        message += "建议补充材质牌号或改用标准条款检索（standard_clause_search）。"
        # ⑧ 与标注示范 UG-DEMO-0003 一致：给出"本次核对过适用边界的条款"作为 source；
        # 若没有核对记录（材质完全不在库中），保持为空，与 UG-DEMO-0005 一致。
        checked_sources = [_src(rec) for rec in excluded_records[:5]]
        if checked_sources:
            message += "（source 为本次核对过适用边界的条款。）"
        return make_response("out_of_domain", False, {}, checked_sources, message)

    # --- 组装 mechanisms（按匹配强度与得分排序）---
    order = {"high": 0, "medium": 1, "low": 2}
    candidates.sort(key=lambda item: (order[item[2]["level"]], -item[0], item[1]["clause_id"]))
    total_candidates = len(candidates)
    total_excluded = len(excluded)
    temp_unknown_count = sum(1 for _, _, sig in candidates if sig.get("temp_unknown"))
    support_hits: List[str] = []
    for _, rec, sig in candidates[:6]:
        for note in sig.get("support_notes") or []:
            line = f"{rec.get('title', '')}：{note}"
            if line not in support_hits:
                support_hits.append(line)
    mechanisms: List[dict] = []
    for score, record, signal in candidates[:6]:
        detail = record.get("mechanism_detail") or {}
        entry = {
            "name": record.get("title", ""),
            "clause_id": record["clause_id"],
            "description": detail.get("description", ""),
            "match_level": signal["level"],
        }
        for key in EIGHT_FIELDS[1:]:
            value = detail.get(key) or []
            entry[key] = value if isinstance(value, list) else [value]
        # 受影响的材料：若元素本身是纯材料清单则拆成独立条目，便于与入参材质对照
        entry["affected_materials"] = _material_display(record)
        mechanisms.append(entry)

    # --- discriminator：由"缺哪些证据"与候选自身的判别要点生成 ---
    missing = [key for key in EVIDENCE_FIELDS if key not in (evidence_map or {})]
    names = [item["name"] for item in mechanisms]
    parts: List[str] = []
    # ④ 区分"总候选数"与"列出条数"，避免把截断后的 6 条误当成全部
    if total_candidates > len(names):
        parts.append(f"共 {total_candidates} 个候选，按匹配强度列出前 {len(names)} 个：{'、'.join(names)}。")
    elif len(names) > 1:
        parts.append(f"共 {len(names)} 个候选：{'、'.join(names)}。")
    else:
        parts.append(f"当前候选为{'、'.join(names)}。")
    if missing:
        hints = "；".join(f"{key}（{EVIDENCE_PURPOSE[key]}）" for key in missing[:4])
        parts.append(f"尚缺现场证据：{hints}。")
    else:
        parts.append("现场证据已按输入采用。")
    if len(mechanisms) >= 2:
        first, second = mechanisms[0], mechanisms[1]
        factors_a = "、".join((first.get("influencing_factors") or [])[:2]) or "见条款"
        factors_b = "、".join((second.get("influencing_factors") or [])[:2]) or "见条款"
        parts.append(
            f"区分 {first['name']} 与 {second['name']}：前者关注 {factors_a}，后者关注 {factors_b}。"
        )
    if support_hits:
        parts.append("现场证据支持：" + "；".join(support_hits[:3]) + "。")
    if temp_unknown_count and temperature_c is not None:
        parts.append(
            f"其中 {temp_unknown_count} 个候选未在条款中登记温度边界，"
            f"无法判断 {temperature_c:g}℃ 下是否适用，需核对条款原文。"
        )
    if silent_excluded:
        parts.append(f"另有 {silent_excluded} 条同材质条款因未涉及输入介质被排除。")
    # ⑪ excluded 只详列 12 条，其余必须显式说明，避免让人以为排除项只有这些
    if total_excluded > 12:
        parts.append(f"另有 {total_excluded - 12} 个候选因介质或温度不匹配被排除（未逐条列出）。")
    parts.append("证据不足时不应给出确定结论，应补充上述数据后再判定。")
    discriminator = "".join(parts)

    sources: List[dict] = []
    seen = set()
    for item in mechanisms:
        record = load_clauses()[0][item["clause_id"]]
        if record["clause_id"] not in seen:
            seen.add(record["clause_id"])
            sources.append(_src(record))

    return make_response("ok", True,
                         {"mechanisms": mechanisms, "discriminator": discriminator,
                          "excluded": excluded[:12]},
                         sources, "")


# ================================================================
# 4. 工具二：rbi_lookup
# ================================================================
# 检验周期抽取：只接受无歧义表述。
_INTERVAL_RE = re.compile(r"每\s*(\d+)\s*年")
_INTERVAL_REJECT = ("不得超过", "最长", "不超过", "投用后", "首次", "级", "根据", "取决", "参照", "或者")


def _interval_from_text(text: str) -> Tuple[Optional[int], Optional[str]]:
    """返回 (年限, 被拒绝的理由)。

    只接受"每 N 年检验一次"这类无前提的周期；对'最长不得超过9年'（上限）、
    '投用后3年内'（首次检验）、'1、2级一般每6年'（依赖安全状况等级）等
    一律不取数，避免产出看似有依据、实则错误的年限。
    """
    text = text or ""
    match = _INTERVAL_RE.search(text)
    if not match:
        return None, None
    window = text[max(0, match.start() - 20) : match.end() + 20]
    for word in _INTERVAL_REJECT:
        if word in window:
            return None, f"条款中的周期表述带前提（含「{word}」），不能直接取作年限：{window.strip()}"
    return int(match.group(1)), None


def _canon_mechanism(name: str) -> str:
    """机理名归一化：去首尾空白，统一全角/半角括号与全角/半角逗号。

    模型可能写成「高温硫化物腐蚀（无氢气环境）」（全角括号）或在名字前后带空格，
    指的是同一条款，不应因此判为查不到。
    """
    s = (name or "").strip()
    table = {
        "（": "(", "）": ")", "，": ",", "：": ":", "；": ";",
        "　": " ", "－": "-", "—": "-",
    }
    return "".join(table.get(ch, ch) for ch in s)


def _determination_path(mechanism: Optional[str], equipment_type: Optional[str] = None):
    """构造 GB/T 26610.3-2014 的失效可能性等级判定路径。

    等级不是查表查出来的：5.1.2 原文要求「将上述 6 个因子的值相加」再查表 1。
    其中只有损伤因子(DF)能由损伤机理名推出，其余五个因子依赖装置级现场信息，
    条款库与工具入参都不提供。因此这里返回「怎么算、还缺什么」，
    等级字段一律留 null（接口规范 2.3：找不到依据就填 null，不要凭经验给数）。

    返回 (result, sources, message)；无法构造路径时返回 None。
    """
    if not mechanism:
        return None
    name = _canon_mechanism(mechanism)
    try:
        from _df_rules import (DF_CLAUSE_IDS, DF_RULES, LEVEL_TABLES, MATRIX_NO,
                               OTHER_FACTORS, classify_df)
    except Exception:
        return None

    letter, df_value, criterion, keyword = classify_df(name)
    df_clause = DF_CLAUSE_IDS.get(letter)
    if not df_clause:
        return None

    # 只有当该机理确实是条款库里 GB/T 30579-2022 的损伤模式时，才给判定路径。
    # 库里没有的机理名（模型臆造、别名写错）不得按兜底项 j 硬套，
    # 否则等于对不存在的机理给出结论。
    # 匹配时忽略首尾空白与全角/半角括号差异——模型写出「高温硫化物腐蚀（无氢气环境）」
    # 指的是同一条款，不应因此判为查不到。
    _, aggregates = load_clauses()
    known = {rec.get("title") for rec in aggregates["damage_mechanism"]}
    canon = _canon_mechanism(name)
    if canon not in {_canon_mechanism(t) for t in known if t}:
        return None

    by_id = {rec["clause_id"]: rec for rec in aggregates["rbi"]}
    # 按 clause_no 前缀索引：因子条款有的已按选项拆成多行（5.2.2-a~j），
    # 有的仍是一条（未拆行时 clause_id 无后缀）。用前缀取首条即可，避免依赖具体 id。
    by_no: Dict[str, dict] = {}
    for rec in aggregates["rbi"]:
        no = str(rec.get("clause_no") or "")
        std = rec.get("standard_code") or ""
        if not std.startswith("GB/T 26610.3"):
            continue
        base = no.split("-")[0]
        if base not in by_no:
            by_no[base] = rec

    def pick(no: str):
        return by_no.get(no)

    sources: List[dict] = []
    seen_ids = set()

    def add_source(rec: Optional[dict]):
        if rec and rec["clause_id"] not in seen_ids:
            seen_ids.add(rec["clause_id"])
            sources.append(_src(rec))

    df_rec = by_id.get(df_clause)
    add_source(df_rec)

    # 六个因子里，除 DF 外还需补充现场信息，逐条给出条款出处。
    # IF1 适用于容器、IF2 适用于管道，二者只取与本次设备类型相符的一条。
    need: List[str] = []
    df_desc = ""
    if df_rec:
        cond = df_rec.get("applicable_conditions") or {}
        df_desc = cond.get("other") or ""
    need.append(
        f"①损伤因子 DF——依据 GB/T 26610.3-2014 5.2.2 第{letter})项"
        f"「{criterion}」，该机理归入此项，DF={df_value}"
    )

    for no, label, info in OTHER_FACTORS:
        if no == "5.2.3.2" and equipment_type != "管道":
            continue
        if no == "5.2.3.1" and equipment_type == "管道":
            continue
        rec = pick(no)
        if rec is None:
            continue
        add_source(rec)
        need.append(f"{label}——查 5.2 节 {no}，需补充：{info}")

    # 等级换算表与矩阵
    level_desc = []
    for no, label in LEVEL_TABLES:
        rec = pick(no)
        if rec is None:
            continue
        add_source(rec)
        level_desc.append(label)
    matrix_rec = pick(MATRIX_NO)
    add_source(matrix_rec)

    need_txt = "；".join(need)
    message = (
        f"该机理的失效可能性等级须按 GB/T 26610.3-2014 判定，本条款库不提供装置级因子数据，"
        f"故不给出等级数值。判定路径如下：{need_txt}。"
        f"六项相加得失效可能性因子后，按表1（5.1.2）定失效可能性等级；"
        f"失效后果按表2（6.3.1.2，燃烧与爆炸）或表9（6.4.2.2，中毒）定等级；"
        f"两者组合查图1风险矩阵（{MATRIX_NO} 条）得风险等级与统一等级 L1~L4。"
        f"需补充的现场信息已逐项列在上方，可据此继续用 standard_clause_search 查具体赋值规则。"
    )

    result = {
        "likelihood": None,
        "consequence": None,
        "risk_level": None,
        "risk_level_unified": None,
        "inspection_interval_year": None,
        "inspection_methods": [],
        "basis_note": (
            f"损伤因子 DF={df_value}（GB/T 26610.3-2014 5.2.2 第{letter})项，判据「{criterion}」"
            + (f"，对应 {df_desc}" if df_desc else "")
            + "）。其余五因子需现场信息，失效可能性因子合计值、失效后果等级、"
              "风险等级与统一等级待补齐后按表1/表2或表9/图1确定。"
        ),
    }
    if not sources:
        return None
    return result, sources, message


def _rbi_recall(mechanism: Optional[str], medium: Optional[List[str]],
                equipment_type: Optional[str]) -> List[dict]:
    """召回 rbi 记录：优先按机理名匹配标题，其次按介质/设备类型匹配适用条件。"""
    _, aggregates = load_clauses()
    records = aggregates["rbi"]
    hits: List[dict] = []
    if mechanism:
        key = mechanism.strip()
        for record in records:
            title = record.get("title") or ""
            if key and (key in title or title in key):
                hits.append(record)
        if hits:
            return hits
        # 标题未命中时退化为正文检索（仍属同一机理线索）
        for record in records:
            if key and key in (record.get("content_raw") or ""):
                hits.append(record)
        return hits
    for record in records:
        cond = record.get("applicable_conditions") or {}
        if medium and any(m in (cond.get("medium") or []) for m in medium):
            hits.append(record)
        elif equipment_type and equipment_type in (cond.get("equipment_type") or []):
            hits.append(record)
    return hits


def rbi_lookup(
    equipment_type: str,
    material: str,
    mechanism: Optional[str] = None,
    medium: Optional[List[str]] = None,
    temperature_c: Optional[float] = None,
    pressure_mpa: Optional[float] = None,
    service_years: Optional[float] = None,
) -> dict:
    """输入设备信息与已识别机理，返回风险等级、检验周期与推荐检验方法。"""
    canon_equipment = normalize_enum("equipment_type", equipment_type) or equipment_type
    canon_material = normalize_enum("material", material) or material
    canon_mediums: List[str] = []
    if medium:
        if not isinstance(medium, list):
            return make_response("error", False, {}, [], "medium 必须是字符串数组")
        for item in medium:
            canon = normalize_enum("medium", item)
            if canon is None:
                return make_response("error", False, {}, [],
                                     f"介质 {item!r} 不在 enums.json 的 medium 表中。")
            canon_mediums.append(canon)

    recalled = _rbi_recall(mechanism, canon_mediums, canon_equipment)

    # 只有"成对"的等级才可用：同一条记录必须同时具备失效可能性与失效后果。
    paired = [
        record for record in recalled
        if (record.get("rbi_detail") or {}).get("likelihood")
        and (record.get("rbi_detail") or {}).get("consequence")
    ]

    if not paired:
        # 库里没有同时给出可能性与后果的记录时，不编造等级，
        # 改为返回 GB/T 26610.3-2014 的**判定路径**：该机理对应哪个 DF 项、
        # 其余五个因子各需补充什么现场信息、六项相加后查哪张表换算等级。
        path = _determination_path(mechanism, canon_equipment)
        if path is None:
            if mechanism:
                message = (
                    f"条款库中没有与机理「{mechanism}」相关的 RBI 条款，"
                    f"无法给出风险等级与检验周期。建议改用 standard_clause_search 检索相关条款。"
                )
            else:
                # ⑤ 诚实说明参数为何没起作用，避免让人以为"已按设备/材质筛过"
                message = (
                    "条款库中的 RBI 记录未登记适用设备与材质（applicable_conditions 为空），"
                    "无法按 equipment_type / material 检索，因此仅凭设备类型与材质查不到条款。"
                    "请提供已识别的 mechanism，或改用 standard_clause_search 按关键词检索。"
                )
            return make_response("not_found", True, {}, [], message)
        result, sources, message = path
        return make_response("ok", True, result, sources, message)

    # 取首条成对记录；原始等级与统一等级必须同源于它。
    record = paired[0]
    detail = record.get("rbi_detail") or {}
    likelihood = str(detail.get("likelihood")).strip()
    consequence = str(detail.get("consequence")).strip()

    pairs, words = load_risk_mapping()
    mapped = pairs.get((likelihood, consequence))
    risk_level = detail.get("risk_level")
    unified = detail.get("risk_level_unified")
    note_bits: List[str] = []

    if mapped:
        mapped_level, mapped_unified = mapped
        if risk_level and risk_level != mapped_level:
            note_bits.append(
                f"条款记录的风险等级「{risk_level}」与定稿映射表「{mapped_level}」不一致，以映射表为准。"
            )
        if unified and unified != mapped_unified:
            note_bits.append(
                f"条款记录的统一等级「{unified}」与定稿映射表「{mapped_unified}」不一致，以映射表为准。"
            )
        risk_level, unified = mapped_level, mapped_unified
    elif risk_level:
        # 条款只给用语时，按用语映射页换算
        unified = words.get(risk_level, unified)
        note_bits.append(f"等级按原文用语「{risk_level}」对应统一等级。")
    else:
        note_bits.append("该条款未给出风险等级用语，统一等级无法换算。")

    # 检验周期：只从同一机理命中的条款里取无歧义表述
    interval: Optional[int] = None
    interval_source: Optional[dict] = None
    interval_notes: List[str] = []
    for item in recalled:
        value, rejected = _interval_from_text(item.get("content_raw") or "")
        if value is not None:
            interval, interval_source = value, item
            break
        if rejected:
            interval_notes.append(rejected)

    methods: List[str] = []
    for item in recalled:
        for method in (item.get("rbi_detail") or {}).get("inspection_methods") or []:
            if method not in methods:
                methods.append(method)

    sources = [_src(record)]
    if interval_source is not None and interval_source["clause_id"] != record["clause_id"]:
        sources.append(_src(interval_source))

    if interval is None:
        if interval_notes:
            note_bits.append(
                "检验周期置空：" + interval_notes[0] + "需要补充安全状况等级等前提后才能确定年限。"
            )
        else:
            note_bits.append("检验周期置空：相关条款未给出可直接取用的周期表述。")
    else:
        note_bits.append(f"检验周期取自 {interval_source['standard_code']} {interval_source['clause_no']}。")
    note_bits.append(
        f"依据：{record['standard_code']} {record['clause_no']}（失效可能性 {likelihood}、失效后果 {consequence}）。"
    )
    note_bits.append("库中 RBI 记录未登记适用设备与材质，本次未按 equipment_type / material 筛选。")

    result = {
        "likelihood": likelihood,
        "consequence": consequence,
        "risk_level": risk_level,
        "risk_level_unified": unified,
        "inspection_interval_year": interval,
        "inspection_methods": methods,
        "basis_note": "".join(note_bits),
    }
    return make_response("ok", True, result, sources, "")


# ================================================================
# 5. 工具三：standard_clause_search
# ================================================================
def standard_clause_search(keyword: str, knowledge_type: Optional[str] = None,
                           top_k: Optional[int] = 5) -> dict:
    """按关键词检索条款，兜底使用。"""
    if not isinstance(keyword, str) or not keyword.strip():
        return make_response("error", False, {}, [], "keyword 为必填参数，且不能为空。")
    if knowledge_type is not None and knowledge_type not in ("rbi", "damage_mechanism"):
        return make_response(
            "error", False, {}, [],
            f"knowledge_type 只能取 'rbi' 或 'damage_mechanism'，收到 {knowledge_type!r}。",
        )
    if top_k is None:
        top_k = 5
    if not isinstance(top_k, (int, float)) or isinstance(top_k, bool):
        return make_response("error", False, {}, [], "top_k 必须是数字。")
    top_k = max(1, min(int(top_k), 20))  # 默认 5，上限 20

    terms = _tokens(keyword)
    _, aggregates = load_clauses()
    pool = aggregates["all"] if knowledge_type is None else aggregates[knowledge_type]

    scored: List[Tuple[float, dict]] = []
    lowered = [term.lower() for term in terms]

    # ⑥ IDF 权重：越少见的检索词权重越高，避免"开裂"这类高频词主导排序。
    # 例：查「湿硫化氢 开裂」时，"湿硫化氢"的权重远高于"开裂"，6.7 才会排到 6.6 前面。
    weights: List[float] = []
    for term in lowered:
        df = sum(1 for item in pool
                 if term in (item.get("title") or "").lower()
                 or term in (item.get("content_raw") or "").lower())
        weights.append(math.log(1.0 + len(pool) / max(1, df)))
    weight_sum = sum(weights) or 1.0

    for record in pool:
        title = (record.get("title") or "").lower()
        content = (record.get("content_raw") or "").lower()
        if not lowered:
            continue
        # 至少一项检索词完整命中（标题或正文），否则不进入候选。
        # 没有这道闸，"zzzz不存在的词" 会因 2-gram（如「存在」）部分覆盖而误命中。
        if not any(term in title or term in content for term in lowered):
            continue
        title_hits = [_coverage(term, title) for term in lowered]
        content_hits = [_coverage(term, content) for term in lowered]
        title_cov = sum(w * hit for w, hit in zip(weights, title_hits)) / weight_sum
        content_cov = sum(w * hit for w, hit in zip(weights, content_hits)) / weight_sum
        score = 0.6 * title_cov + 0.4 * content_cov
        # 全部检索词都出现在标题里，说明标题高度吻合，给一点加分（封顶 1.0）
        if all(hit >= 1.0 for hit in title_hits):
            score = min(1.0, score + 0.05)
        if score <= 0:
            continue
        scored.append((score, record))

    if not scored:
        return make_response(
            "not_found", True, {}, [],
            f"条款库中没有命中「{keyword}」的条款（检索范围：{knowledge_type or '全部'}）。"
            f"可尝试更换同义词，或改用 damage_mechanism_query / rbi_lookup 做结构化查询。",
        )

    # 同名标题较多（如「风险等级的确定」有 25 条），用内容覆盖度与条款号做次级排序
    # ⑩ 同分时按条款号自然序（7-a、7-b…7-y），不再按正文长度排——否则会出现跳号（7-d 之后直接 7-f）
    scored.sort(key=lambda item: (-item[0], _natural_key(str(item[1]["clause_id"]))))
    hits: List[dict] = []
    sources: List[dict] = []
    for score, record in scored[:top_k]:
        hits.append({
            "clause_id": record["clause_id"],
            "title": record.get("title", ""),
            "snippet": _snippet(record.get("content_raw") or ""),
            "score": round(score, 4),
        })
        sources.append(_src(record))
    # ⑩ 命中里若有多条同名条款（如「风险等级的确定」共 25 条），在 message 里说清楚
    counts: Dict[str, int] = {}
    for hit in hits:
        counts[hit["title"]] = counts.get(hit["title"], 0) + 1
    same_title = [f"「{title}」{count} 条" for title, count in counts.items() if count >= 3]
    note = ""
    if same_title:
        note = ("命中结果中含同标题条款：" + "、".join(same_title[:3])
                + "。这些条款标题相同、正文不同，可结合 clause_id 或更具体的关键词进一步区分。")
    return make_response("ok", True, {"hits": hits}, sources, note)


def _natural_key(text: str):
    """条款号自然序：把数字段按数值比较，例如 7-a < 7-b < … < 7-y。"""
    return tuple((0, int(part)) if part.isdigit() else (1, part)
                 for part in re.split(r"(\d+)", text) if part)


# ================================================================
# 6. 工具声明（供 harness.build_registry 构造 ToolSpec）
# ================================================================
TOOL_DESCRIPTIONS = {
    "damage_mechanism_query": (
        "根据材质、介质、温度、设备类型和现场证据，识别可能的损伤机理，"
        "返回固定八段式内容、区分不同机理所需的补充证据（discriminator）以及被排除的机理及理由（excluded）。"
    ),
    "rbi_lookup": (
        "根据设备类型、材质与已识别的损伤机理，查询风险等级（原始等级与统一等级）、"
        "检验周期与推荐检验方法。缺少成对等级时不返回等级。"
    ),
    "standard_clause_search": (
        "按关键词或现象描述检索标准条款，作为结构化查询无法覆盖时的兜底手段。"
    ),
}

TOOL_PARAMETERS: Dict[str, Dict[str, dict]] = {
    "damage_mechanism_query": {
        "material": {"type": "string", "required": True},
        "medium": {"type": "array", "required": True},
        "temperature_c": {"type": "number", "required": False},
        "equipment_type": {"type": "string", "required": False},
        "evidence": {"type": "object", "required": False},
    },
    "rbi_lookup": {
        "equipment_type": {"type": "string", "required": True},
        "material": {"type": "string", "required": True},
        "mechanism": {"type": "string", "required": False},
        "medium": {"type": "array", "required": False},
        "temperature_c": {"type": "number", "required": False},
        "pressure_mpa": {"type": "number", "required": False},
        "service_years": {"type": "number", "required": False},
    },
    "standard_clause_search": {
        "keyword": {"type": "string", "required": True},
        "knowledge_type": {"type": "string", "required": False,
                           "enum": ["rbi", "damage_mechanism"]},
        "top_k": {"type": "number", "required": False, "maximum": 20},
    },
}

TOOL_FUNCS = {
    "damage_mechanism_query": damage_mechanism_query,
    "rbi_lookup": rbi_lookup,
    "standard_clause_search": standard_clause_search,
}


def iter_tool_definitions() -> Iterable[Tuple[str, Any, str, Dict[str, dict]]]:
    """按注册顺序给出 (名称, 函数, 描述, 参数声明)。"""
    for name in ("damage_mechanism_query", "rbi_lookup", "standard_clause_search"):
        yield name, TOOL_FUNCS[name], TOOL_DESCRIPTIONS[name], TOOL_PARAMETERS[name]
