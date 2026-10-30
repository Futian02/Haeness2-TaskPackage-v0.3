"""Conservative extraction of explicitly stated equipment context.

Values are never inferred from symptoms.  This module only recognizes labeled
or unambiguous user-stated fields and returns provenance for the audit trace.
"""
from __future__ import annotations

import re
import json
from pathlib import Path
from typing import Any

_FIELDS = ("equipment", "equipment_type", "component", "material", "medium",
           "temperature_c", "wall_temperature_c", "pressure_mpa",
           "h2s_partial_pressure_mpa", "flow_velocity_m_s", "thickness_mm",
           "service_years", "damage_morphology")
_MATERIALS = (
    ("300系列不锈钢", ("300系列不锈钢", "300系不锈钢", "300系列", "300系")),
    ("奥氏体不锈钢", ("奥氏体不锈钢", "304L", "316L", "304", "316")),
    ("碳钢", ("碳钢", "碳素钢", "低合金钢", "20#钢", "20号钢", "Q345R")),
    ("Cr-Mo钢", ("Cr-Mo钢", "铬钼钢", "铬钼合金钢")),
    ("双相不锈钢", ("双相不锈钢", "2205")),
)
_EQUIPMENT = (("管道", ("管道", "管线", "弯头")), ("压力容器", ("压力容器",)),
              ("换热器", ("换热器",)), ("反应釜", ("反应釜",)), ("储罐", ("储罐",)),
              ("塔器", ("塔器",)), ("泵", ("泵",)), ("阀门", ("阀门",)),
              ("锅炉", ("锅炉",)), ("压缩机", ("压缩机",)))
_MEDIUM = ("湿硫化氢", "氯化氢", "有机氯化物", "氯化铵", "硫氢化铵", "环烷酸",
           "高温硫化物腐蚀介质", "连多硫酸", "氰化物", "氢氧化钠", "胺液", "二氧化碳",
           "氯离子", "氧气", "循环水", "酸式酸性水", "碱式酸性水", "氨", "含盐水")


def _teacher_aliases(field: str) -> dict[str, str]:
    """Read the frozen enum vocabulary when present; never extend its values."""
    path = Path(__file__).resolve().parents[1] / "upstream" / "04_接口文档" / "enums.json"
    try:
        table = json.loads(path.read_text(encoding="utf-8")).get(field, {})
    except (OSError, ValueError, TypeError):
        table = {}
    result: dict[str, str] = {}
    for canonical, spec in table.items():
        result[str(canonical).casefold()] = str(canonical)
        if isinstance(spec, dict):
            for alias in spec.get("aliases", []):
                result[str(alias).casefold()] = str(canonical)
    # Minimal local fallback is still restricted to the frozen canonical
    # values; it supports test environments without the upstream data folder.
    if not result:
        for canonical in (_MEDIUM if field == "medium" else tuple(x[0] for x in _MATERIALS)):
            result[canonical.casefold()] = canonical
    return result


_MATERIAL_ALIASES = _teacher_aliases("material")
_MEDIUM_ALIASES = _teacher_aliases("medium")
for _alias in ("304", "304L", "316", "316L", "321", "347", "S30408", "S31608"):
    _MATERIAL_ALIASES.setdefault(_alias.casefold(), "奥氏体不锈钢")


def _clean(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(v).strip() for v in value if str(v).strip())[:300]
    return str(value or "").strip()[:300]


def _value(text: str, labels: str) -> str | None:
    # Keep commas inside bracketed/JSON arrays, but stop at ordinary Chinese
    # sentence delimiters. Closing wrappers are normalized downstream.
    match = re.search(rf"(?:{labels})\s*(?:为|是|：|:|=)\s*(\[[^\]]*\]|\([^)]*\)|\{{[^}}]*\}}|[^，,。；;\n]+)", text, re.I)
    return match.group(1).strip()[:120] if match else None


_FIELD_PATTERNS = {
    "equipment": r"(?:设备名称|设备名|设备|装置|管线|管道)",
    "equipment_type": r"(?:设备类型|设备型式|设备类别)",
    "component": r"(?:部位|位置|构件|所在部位|损伤部位)",
    "material": r"(?:材质|材料|母材)",
    "medium": r"(?:工艺介质|介质|流体)",
    "temperature_c": r"(?<!壁)(?<!壁面)(?:工况温度|操作温度|运行温度|介质温度|实测温度|测量温度|检测温度|温度)",
    "wall_temperature_c": r"(?:壁温|壁面温度|金属温度|管壁温度|壳壁温度)",
    "pressure_mpa": r"(?:总压|系统压力|操作压力|运行压力|压力)",
    "h2s_partial_pressure_mpa": r"(?:H\s*[₂2]\s*S|硫化氢)\s*(?:分压|partial\s*pressure)",
    "flow_velocity_m_s": r"(?:流速|流动速度|线速度)",
    "thickness_mm": r"(?:壁厚|剩余厚度|实测厚度|厚度)",
    "service_years": r"(?:运行|服役|投用|使用)年限",
    "damage_morphology": r"(?:损伤形貌|损伤类型|损伤形式|形貌|损伤)",
}
_UNCERTAIN = re.compile(r"(?:可能|也许|大概|疑似|怀疑|不确定|待确认|待核实|尚未确认|假设|如果|假如|听说|据说)")
_NEGATED = re.compile(r"(?:不是|并非|不含|没有|无|未检出|未发现|不属于|排除|否认)")
_MEASURED = re.compile(r"(?:实测|测得|测量值|检测结果|监测值|仪表显示|化验结果)")
_UNIT_VALUE = re.compile(r"(?P<num>-?\d+(?:\.\d+)?)\s*(?P<unit>摄氏度|度C|℃|°\s*C|°\s*F|℉|MPa|kPa|bar|Pa|m/s|米/秒|ft/s|毫米|mm|厘米|cm|年|K)?", re.I)


def _find_labeled(text: str, labels: str) -> re.Match[str] | None:
    return re.search(rf"(?P<label>{labels})\s*(?:为|是|：|:|=)\s*(?P<value>\[[^\]]*\]|\([^)]*\)|\{{[^}}]*\}}|[^，,。；;\n]+)", text, re.I)


def _assertion_state(text: str, start: int, end: int) -> str:
    """Classify nearby language without upgrading uncertainty to a fact."""
    before = text[max(0, start - 36):start]
    before = re.split(r"[，,；;\n。]", before)[-1]
    span = text[start:end]
    after = text[end:min(len(text), end + 24)]
    if re.search(r"(?:是否|有没有|有无|会不会|是否存在|是否发生)\s*$", before) or re.match(
            r"\s*(?:吗|是否|有没有|有无|会不会)(?:[？?]|\s)", after[:14]):
        return "UNCERTAIN"
    if _UNCERTAIN.search(before) or _UNCERTAIN.search(span):
        return "UNCERTAIN"
    if _NEGATED.search(before) or _NEGATED.search(span):
        # In “not X, but Y”, X remains negated and Y is asserted only when
        # immediately introduced by the corrective conjunction.
        if re.search(r"(?:而是|改为|实际为|应为)\s*$", before):
            return "USER_ASSERTED"
        if re.search(r"而是|改为|实际为|应为", after):
            return "NEGATED"
        return "NEGATED"
    return "USER_REPORTED_MEASUREMENT" if _MEASURED.search(before) else "USER_ASSERTED"


def _number_to_unit(value: str, field: str) -> tuple[int | float, str] | None:
    match = _UNIT_VALUE.search(value)
    if not match:
        return None
    number = float(match.group("num"))
    unit = (match.group("unit") or "").replace(" ", "").casefold()
    if field in {"temperature_c", "wall_temperature_c"}:
        if unit in {"°f", "℉"}:
            number = (number - 32) * 5 / 9
        elif unit in {"度c", "摄氏度"}:
            pass
        elif unit not in {"", "℃", "°c"}:
            return None
        return (round(number, 2), "degC")
    if field in {"pressure_mpa", "h2s_partial_pressure_mpa"}:
        factors = {"": 1.0, "mpa": 1.0, "kpa": 0.001, "bar": 0.1, "pa": 0.000001}
        if unit not in factors:
            return None
        return (round(number * factors[unit], 6), "MPa")
    if field == "flow_velocity_m_s":
        factors = {"": 1.0, "m/s": 1.0, "米/秒": 1.0, "ft/s": 0.3048}
        if unit not in factors:
            return None
        return (round(number * factors[unit], 4), "m/s")
    if field == "thickness_mm":
        factors = {"": 1.0, "毫米": 1.0, "mm": 1.0, "厘米": 10.0, "cm": 10.0}
        if unit not in factors:
            return None
        return (round(number * factors[unit], 4), "mm")
    if field == "service_years":
        return (number, "year")
    return None


def _extract_value_span(text: str, field: str) -> re.Match[str] | None:
    labels = _FIELD_PATTERNS[field]
    numeric = {"temperature_c", "wall_temperature_c", "pressure_mpa", "h2s_partial_pressure_mpa",
               "flow_velocity_m_s", "thickness_mm", "service_years"}
    if field in numeric:
        direct = re.search(
            rf"(?P<label>{labels})\s*(?:(?:为|是|：|:|=)\s*)?(?P<value>-?\d+(?:\.\d+)?\s*(?:摄氏度|度C|℃|°\s*C|°\s*F|℉|MPa|kPa|bar|Pa|m/s|米/秒|ft/s|毫米|mm|厘米|cm|年|K|[A-Za-z/]+)?)",
            text, re.I)
        if direct:
            return direct
    correction = re.search(rf"(?P<label>{labels})\s*(?:不是|并非|原为|原是)[^，,。；;\n]*?(?:而是|改为|实际为|应为)\s*(?P<value>[^，,。；;\n]+)", text, re.I)
    if correction:
        return correction
    match = _find_labeled(text, labels)
    if not match:
        return None
    # Resolve explicit correction syntax inside a labeled value, preserving
    # the exact span of the corrected value rather than retaining its negated
    # predecessor (e.g. “更正：材质不是碳钢，而是316L”).
    value = match.group("value")
    corrected = re.search(r"(?:而是|改为|实际为|應为|应为)\s*([^，,。；;]+)", value)
    if corrected:
        start = match.start("value") + corrected.start(1)
        end = match.start("value") + corrected.end(1)
        return _SpanMatch(match, start, end)
    return match


class _SpanMatch:
    """Small adapter so correction subspans retain the regex Match API."""
    def __init__(self, match: re.Match[str], value_start: int, value_end: int):
        self._match, self._start, self._end = match, value_start, value_end

    def group(self, name: str) -> str:
        return self._match.string[self._start:self._end] if name == "value" else self._match.group(name)

    def start(self, name: str | int = 0) -> int:
        if name == "value": return self._start
        return self._match.start(name)

    def end(self, name: str | int = 0) -> int:
        if name == "value": return self._end
        return self._match.end(name)

    def span(self, name: str | int = 0) -> tuple[int, int]:
        return (self.start(name), self.end(name))


def _alias_has_fact_context(text: str, start: int, end: int, field: str) -> bool:
    before = text[max(0, start - 18):start]
    after = text[end:min(len(text), end + 14)]
    if field == "medium":
        return bool(re.search(r"(?:介质|工况|环境|处于|含有|含|运行在|接触|流经|湿环境|气氛|工艺)", before)
                    or re.search(r"(?:介质|环境|工况|管线|设备|材料)", after))
    return bool(re.search(r"(?:材质|材料|母材|采用|使用|由|制成|设备|管道|容器)", before)
                or re.search(r"(?:材质|材料|钢制|设备|管道|容器)", after))


def _normalize_text_field(field: str, raw: str) -> tuple[Any, list[str]]:
    unwrapped = _unwrap(raw)
    if field == "material":
        canonical = _normalize_material(unwrapped)
        return (canonical, [] if canonical else [unwrapped])
    if field == "medium":
        normalized = _normalize_medium_items(raw)
        items = raw if isinstance(raw, list) else re.split(r"[,，、/和及]", unwrapped)
        unknown = [_unwrap(str(item)) for item in items
                   if _unwrap(str(item)) and _unwrap(str(item)).casefold() not in _MEDIUM_ALIASES]
        return (normalized, list(dict.fromkeys(unknown)))
    if field == "equipment_type":
        lower = unwrapped.casefold()
        for canonical, aliases in _EQUIPMENT:
            if any(alias.casefold() in lower for alias in aliases):
                return canonical, []
        return unwrapped or None, []
    if field == "equipment":
        return unwrapped or None, []
    if field == "damage_morphology":
        return unwrapped or None, []
    if field == "component":
        return unwrapped or None, []
    return unwrapped or None, []


def _normalize_material(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = _unwrap(value)
    return _MATERIAL_ALIASES.get(cleaned.casefold())


def _unwrap(value: str) -> str:
    value = str(value or "").strip()
    # Python/JSON-like list wrappers are presentation syntax only. Do not
    # evaluate input; split the small accepted list grammar as plain text.
    if len(value) >= 2 and (value[0], value[-1]) in {("[", "]"), ("(", ")"), ("{", "}")}:
        value = value[1:-1].strip()
    return value.strip(" \t\r\n\"'“”‘’`")


def _normalize_medium_items(value: Any) -> list[str] | None:
    if isinstance(value, list):
        raw_items = value
    else:
        raw = _unwrap(_clean(value))
        # Accept JSON arrays, bracketed comma-separated labels, and ordinary
        # comma/顿号-separated fields. Unknown values are discarded, never
        # passed through as if they belonged to the teacher's enum.
        if raw.startswith("[") and raw.endswith("]"):
            try:
                decoded = json.loads(raw)
                raw_items = decoded if isinstance(decoded, list) else [raw]
            except (ValueError, TypeError):
                raw_items = re.split(r"[,，、/和及]", _unwrap(raw))
        else:
            raw_items = re.split(r"[,，、/和及]", raw)
    out = []
    for item in raw_items:
        key = _unwrap(str(item)).casefold()
        canonical = _MEDIUM_ALIASES.get(key)
        if canonical and canonical not in out:
            out.append(canonical)
    # Acidic water must be qualified as acid-form or alkaline-form; generic
    # “酸性水” is intentionally not an enum fallback.
    return out or None


def extract_explicit_context(question: str, structured: dict[str, Any] | None = None,
                             prior_confirmed: dict[str, Any] | None = None) -> dict[str, Any]:
    """Extract asserted facts while preserving raw evidence and source scope.

    Compatibility keys (``values``, ``sources``, ``raw_values`` and
    ``unknown_enum_values``) are kept stable for the API/Graph callers.  New
    metadata is additive.  Candidate, negated, and uncertain language is
    returned separately and is never merged into ``values``.
    """
    q = str(question or "")[:4000]
    form = structured if isinstance(structured, dict) else {}
    prior = prior_confirmed if isinstance(prior_confirmed, dict) else {}
    parsed: dict[str, Any] = {}
    raw_parsed: dict[str, Any] = {}
    spans: dict[str, dict[str, Any]] = {}
    units: dict[str, str | None] = {}
    unknown_enum_values: dict[str, list[str]] = {}
    uncertain_fields: dict[str, list[str]] = {}
    negated_fields: dict[str, list[str]] = {}
    conflicts: list[dict[str, Any]] = []

    # A phrase such as “另外一台设备” starts a new object scope: do not
    # inherit facts from the previous object in this message.
    new_object_scope = bool(re.search(r"(?:另外|另一|新的一台|另一台|换一台|改查另一)", q))
    correction = bool(re.search(r"(?:更正|纠正|改为|实际应为|前述.*错误|前面说错)", q))

    for field in _FIELDS:
        match = _extract_value_span(q, field)
        if not match:
            continue
        raw = match.group("value").strip()
        start, end = match.span("value")
        state = _assertion_state(q, match.start("value"), match.end("value"))
        if state == "UNCERTAIN":
            uncertain_fields[field] = [raw]
            continue
        if state == "NEGATED":
            negated_fields[field] = [raw]
            raw_parsed[field] = raw
            spans[field] = {"text": q[start:end], "start": start, "end": end,
                            "label_start": match.start("label"), "label_end": match.end("label"),
                            "assertion_state": state, "origin": "current_user_message"}
            continue
        parsed_value: Any
        unit: str | None = None
        if field in {"temperature_c", "wall_temperature_c", "pressure_mpa", "h2s_partial_pressure_mpa",
                     "flow_velocity_m_s", "thickness_mm", "service_years"}:
            converted = _number_to_unit(raw, field)
            if converted is None:
                # Preserve malformed or unit-ambiguous numeric input as UNKNOWN/raw.
                unknown_enum_values.setdefault(field, []).append(_unwrap(raw))
                raw_parsed[field] = raw
                spans[field] = {"text": q[start:end], "start": start, "end": end,
                                "label_start": match.start("label"), "label_end": match.end("label"),
                                "assertion_state": state, "origin": "current_user_message"}
                continue
            parsed_value, unit = converted
        else:
            parsed_value, unknown = _normalize_text_field(field, raw)
            if unknown:
                unknown_enum_values[field] = unknown
                raw_parsed[field] = raw
                spans[field] = {"text": q[start:end], "start": start, "end": end,
                                "label_start": match.start("label"), "label_end": match.end("label"),
                                "assertion_state": state, "origin": "current_user_message"}
            if parsed_value is None:
                continue
        parsed[field] = parsed_value
        raw_parsed[field] = raw
        units[field] = unit
        spans[field] = {"text": q[start:end], "start": start, "end": end,
                        "label_start": match.start("label"), "label_end": match.end("label"),
                        "assertion_state": state, "origin": "current_user_message"}

    # Curated material and medium aliases are accepted without a label, but
    # only when the alias itself is positively asserted in the local clause.
    for field, alias_map in (("material", _MATERIAL_ALIASES), ("medium", _MEDIUM_ALIASES)):
        if field in parsed:
            continue
        matches: list[tuple[int, int, str, str]] = []
        for alias, canonical in sorted(alias_map.items(), key=lambda item: len(item[0]), reverse=True):
            if not alias:
                continue
            for found in re.finditer(re.escape(alias), q, re.I):
                state = _assertion_state(q, found.start(), found.end())
                if state == "USER_ASSERTED" and _alias_has_fact_context(q, found.start(), found.end(), field):
                    matches.append((found.start(), found.end(), alias, canonical))
                elif state in {"UNCERTAIN", "NEGATED"}:
                    (uncertain_fields if state == "UNCERTAIN" else negated_fields).setdefault(field, []).append(found.group(0))
        if matches:
            # Prefer longer aliases at the same location; keep distinct media.
            matches.sort(key=lambda row: (row[0], -(row[1] - row[0])))
            selected: list[tuple[int, int, str, str]] = []
            for item in matches:
                if any(item[0] < prev[1] and prev[0] < item[1] for prev in selected):
                    continue
                selected.append(item)
            canonicals = list(dict.fromkeys(row[3] for row in selected))
            parsed[field] = canonicals if field == "medium" else canonicals[0]
            raw_parsed[field] = [q[row[0]:row[1]] for row in selected] if field == "medium" else q[selected[0][0]:selected[0][1]]
            units[field] = None
            spans[field] = {"text": raw_parsed[field], "start": selected[0][0], "end": selected[-1][1],
                            "assertion_state": "USER_ASSERTED", "origin": "curated_alias_match"}

    # Equipment class is a semantic hint, not a fabricated equipment name.
    if "equipment_type" not in parsed:
        for canonical, aliases in _EQUIPMENT:
            alias = next((a for a in sorted(aliases, key=len, reverse=True) if re.search(re.escape(a), q, re.I)), None)
            if alias:
                found = re.search(re.escape(alias), q, re.I)
                if found and _assertion_state(q, found.start(), found.end()) == "USER_ASSERTED":
                    parsed["equipment_type"] = canonical
                    raw_parsed["equipment_type"] = found.group(0)
                    spans["equipment_type"] = {"text": found.group(0), "start": found.start(), "end": found.end(),
                                                "assertion_state": "USER_ASSERTED", "origin": "curated_alias_match"}
                    units["equipment_type"] = None
                    break
    if "equipment_type" not in parsed and re.search(r"壳体|筒体|封头", q):
        unknown_enum_values.setdefault("equipment_type", []).append(
            re.search(r"壳体|筒体|封头", q).group(0))
    # Preserve locations such as “壳体” without promoting them to equipment types.
    if "component" not in parsed:
        found = re.search(r"(壳体|弯头|焊缝|接管|管壁|封头|法兰|支管|底板|筒体)", q)
        if found and _assertion_state(q, found.start(), found.end()) == "USER_ASSERTED":
            parsed["component"] = found.group(0)
            raw_parsed["component"] = found.group(0)
            spans["component"] = {"text": found.group(0), "start": found.start(), "end": found.end(),
                                   "assertion_state": "USER_ASSERTED", "origin": "morphology_location_match"}
            units["component"] = None
    if "damage_morphology" not in parsed:
        found = re.search(r"(磕碰(?:损伤)?|撞击(?:损伤)?|凹陷|减薄|裂纹|鼓包|腐蚀|冲蚀|磨损)", q)
        if found and _assertion_state(q, found.start(), found.end()) == "USER_ASSERTED":
            parsed["damage_morphology"] = found.group(0)
            raw_parsed["damage_morphology"] = found.group(0)
            spans["damage_morphology"] = {"text": found.group(0), "start": found.start(), "end": found.end(),
                                          "assertion_state": "USER_ASSERTED", "origin": "morphology_location_match"}
            units["damage_morphology"] = None

    values: dict[str, Any] = {}
    sources: dict[str, str] = {}
    raw_values: dict[str, Any] = {}
    field_details: dict[str, dict[str, Any]] = {}
    raw_form_values: dict[str, Any] = {}
    for field in _FIELDS:
        form_value = form.get(field)
        raw_form = form_value
        if field == "material" and form_value not in (None, "", []):
            form_value = _normalize_material(_clean(form_value))
            if form_value is None:
                unknown_enum_values.setdefault(field, []).append(_clean(raw_form))
        elif field == "medium" and form_value not in (None, "", []):
            form_value = _normalize_medium_items(form_value)
            if form_value is None:
                raw_items = raw_form if isinstance(raw_form, list) else [raw_form]
                unknown_enum_values.setdefault(field, []).extend(_unwrap(str(v)) for v in raw_items if _unwrap(str(v)))
        current_value = parsed.get(field)
        if form_value not in (None, "", []):
            if current_value not in (None, "", []) and _clean(form_value).casefold() != _clean(current_value).casefold():
                conflicts.append({"field": field, "form_value": form_value, "message_value": current_value,
                                  "resolution": "structured_form_wins"})
            chosen, source, raw = form_value, "structured_form", raw_form
        elif current_value not in (None, "", []):
            chosen, source, raw = current_value, "current_message", raw_parsed.get(field, current_value)
        elif not new_object_scope and prior.get(field) not in (None, "", []):
            chosen, source, raw = prior[field], "same_conversation_prior_user_statement", prior.get(f"raw_{field}", prior[field])
        else:
            continue
        values[field] = chosen
        sources[field] = source
        raw_values[field] = raw
        measured = bool(spans.get(field) and spans[field].get("assertion_state") == "USER_REPORTED_MEASUREMENT")
        if source == "structured_form":
            state = "USER_ASSERTED_STRUCTURED_FORM"
        elif source == "same_conversation_prior_user_statement":
            state = "USER_ASSERTED_PRIOR"
        else:
            state = "USER_REPORTED_MEASUREMENT" if measured else "USER_ASSERTED"
        field_details[field] = {"raw_value": raw, "normalized_value": chosen, "unit": units.get(field),
                                "source": source, "confirmation_state": state,
                                "independently_verified": False,
                                "object": values.get("equipment") or values.get("equipment_type") or "UNKNOWN",
                                "object_scope": ("new_object" if new_object_scope else
                                                 str(parsed.get("equipment") or parsed.get("equipment_type") or
                                                     prior.get("_object_scope") or "conversation_object")),
                                "source_span": spans.get(field) if source == "current_message" else None}
        if raw_form is not None:
            raw_form_values[field] = raw_form

    object_name = values.get("equipment")
    object_type = values.get("equipment_type")
    object_scope = "new_object" if new_object_scope else str(object_name or object_type or prior.get("_object_scope") or "conversation_object")
    if correction:
        for field, current in parsed.items():
            if field in prior and prior[field] != current:
                conflicts.append({"field": field, "prior_value": prior[field], "message_value": current,
                                  "resolution": "explicit_correction_supersedes_prior"})
    for field in list(unknown_enum_values):
        unknown_enum_values[field] = list(dict.fromkeys(str(x) for x in unknown_enum_values[field] if str(x).strip()))
    for field, raw in raw_parsed.items():
        if field not in raw_values:
            raw_values[field] = raw
    return {"values": values, "sources": sources, "conflicts": conflicts,
            "extraction_method": "bounded_explicit_span_parser_v2",
            "original_question": q, "raw_values": raw_values,
            "unknown_enum_values": unknown_enum_values,
            "field_details": field_details,
            "raw_spans": spans, "units": {k: units.get(k) for k in values},
            "object_scope": object_scope, "new_object_scope": new_object_scope,
            "uncertain_fields": uncertain_fields, "negated_fields": negated_fields,
            "unknown_fields": [field for field in _FIELDS if field not in values],
            "correction_detected": correction,
            "structured_raw_values": raw_form_values}
