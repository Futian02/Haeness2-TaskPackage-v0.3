# -*- coding: utf-8 -*-
"""生成 05_提交区/guardrail_cases.jsonl（异常用例，四类各 ≥3 条）与
05_提交区/normal_cases.jsonl（正常用例，≥30 条）。

所有用例的拦截类型/放行行为都经实测确认：
- 异常用例先由 `_probe_guardrail.py` 探测各分支实际抛出的 GuardrailError.kind；
- 正常用例先由 `_scan_normal.py` 扫描出确实能放行的 材质×介质×温度 组合。
生成后再由官方脚本 run_guardrail_tests.py 复核。
"""
import json, os
from collections import Counter

OUT_DIR = '05_提交区'

# ============================================================
# 一、护栏用例：四类异常各 ≥3 条，全部应被拦截
#    category 必须与实际抛出的 GuardrailError.kind 精确一致
# ============================================================
GR = [
    # ---------- unknown_tool：工具名错误（实测 kind=unknown_tool）----------
    {"case_id": "GR-UT-01", "category": "unknown_tool",
     "description": "工具名拼错：querry 误作 query",
     "call": {"tool": "damage_mechanism_querry",
              "args": {"material": "碳钢", "medium": ["氯化氢"]}},
     "expect": "blocked"},
    {"case_id": "GR-UT-02", "category": "unknown_tool",
     "description": "工具名大小写错：模型按驼峰输出",
     "call": {"tool": "Damage_Mechanism_Query",
              "args": {"material": "碳钢", "medium": ["氯化氢"]}},
     "expect": "blocked"},
    {"case_id": "GR-UT-03", "category": "unknown_tool",
     "description": "臆造第四个工具 rbi_risk_lookup",
     "call": {"tool": "rbi_risk_lookup",
              "args": {"equipment_type": "换热器", "material": "碳钢"}},
     "expect": "blocked"},
    {"case_id": "GR-UT-04", "category": "unknown_tool",
     "description": "工具名带版本后缀",
     "call": {"tool": "damage_mechanism_query_v2",
              "args": {"material": "碳钢", "medium": ["氯化氢"]}},
     "expect": "blocked"},
    {"case_id": "GR-UT-05", "category": "unknown_tool",
     "description": "用中文自然语言当工具名",
     "call": {"tool": "损伤机理查询",
              "args": {"material": "碳钢", "medium": ["氯化氢"]}},
     "expect": "blocked"},
    {"case_id": "GR-UT-06", "category": "unknown_tool",
     "description": "把 standard_clause_search 写成标准条款检索的直译",
     "call": {"tool": "standard_clause_retrieval",
              "args": {"keyword": "湿硫化氢"}},
     "expect": "blocked"},

    # ---------- missing_param：必填参数缺失（实测 kind=missing_param）----------
    {"case_id": "GR-MP-01", "category": "missing_param",
     "description": "damage_mechanism_query 缺必填参数 medium",
     "call": {"tool": "damage_mechanism_query", "args": {"material": "碳钢"}},
     "expect": "blocked"},
    {"case_id": "GR-MP-02", "category": "missing_param",
     "description": "damage_mechanism_query 缺必填参数 material",
     "call": {"tool": "damage_mechanism_query", "args": {"medium": ["氯化氢"]}},
     "expect": "blocked"},
    {"case_id": "GR-MP-03", "category": "missing_param",
     "description": "damage_mechanism_query 两个必填参数全缺",
     "call": {"tool": "damage_mechanism_query", "args": {}},
     "expect": "blocked"},
    {"case_id": "GR-MP-04", "category": "missing_param",
     "description": "rbi_lookup 缺必填参数 material",
     "call": {"tool": "rbi_lookup", "args": {"equipment_type": "换热器"}},
     "expect": "blocked"},
    {"case_id": "GR-MP-05", "category": "missing_param",
     "description": "rbi_lookup 缺必填参数 equipment_type",
     "call": {"tool": "rbi_lookup", "args": {"material": "碳钢"}},
     "expect": "blocked"},
    {"case_id": "GR-MP-06", "category": "missing_param",
     "description": "standard_clause_search 缺必填参数 keyword",
     "call": {"tool": "standard_clause_search", "args": {}},
     "expect": "blocked"},
    {"case_id": "GR-MP-07", "category": "missing_param",
     "description": "standard_clause_search 缺 keyword 只给了 knowledge_type",
     "call": {"tool": "standard_clause_search", "args": {"knowledge_type": "rbi"}},
     "expect": "blocked"},
    {"case_id": "GR-MP-08", "category": "missing_param",
     "description": "rbi_lookup 只给必填 material 缺 equipment_type",
     "call": {"tool": "rbi_lookup", "args": {"material": "碳钢", "mechanism": "盐酸腐蚀"}},
     "expect": "blocked"},

    # ---------- bad_format：格式不合规（实测 kind=bad_format）----------
    {"case_id": "GR-BF-01", "category": "bad_format",
     "description": "介质写成物流名称，不在 enums.json medium 表中",
     "call": {"tool": "damage_mechanism_query",
              "args": {"material": "碳钢", "medium": ["液化石油气"]}},
     "expect": "blocked"},
    {"case_id": "GR-BF-02", "category": "bad_format",
     "description": "材质写成 304 而非规范值 06Cr19Ni10",
     "call": {"tool": "damage_mechanism_query",
              "args": {"material": "不锈钢304", "medium": ["氯化氢"]}},
     "expect": "blocked"},
    {"case_id": "GR-BF-03", "category": "bad_format",
     "description": "medium 写成逗号分隔字符串而非数组",
     "call": {"tool": "damage_mechanism_query",
              "args": {"material": "碳钢", "medium": "氯化氢,氯化铵"}},
     "expect": "blocked"},
    {"case_id": "GR-BF-04", "category": "bad_format",
     "description": "温度写成带单位字符串 '110℃'",
     "call": {"tool": "damage_mechanism_query",
              "args": {"material": "碳钢", "medium": ["氯化氢"], "temperature_c": "110℃"}},
     "expect": "blocked"},
    {"case_id": "GR-BF-05", "category": "bad_format",
     "description": "温度写成布尔值",
     "call": {"tool": "damage_mechanism_query",
              "args": {"material": "碳钢", "medium": ["氯化氢"], "temperature_c": True}},
     "expect": "blocked"},
    {"case_id": "GR-BF-06", "category": "bad_format",
     "description": "medium 数组元素不是字符串",
     "call": {"tool": "damage_mechanism_query",
              "args": {"material": "碳钢", "medium": [123]}},
     "expect": "blocked"},
    {"case_id": "GR-BF-07", "category": "bad_format",
     "description": "传入未定义参数 pressure",
     "call": {"tool": "damage_mechanism_query",
              "args": {"material": "碳钢", "medium": ["氯化氢"], "pressure": 1.0}},
     "expect": "blocked"},
    {"case_id": "GR-BF-08", "category": "bad_format",
     "description": "top_k 超过上限 20",
     "call": {"tool": "standard_clause_search",
              "args": {"keyword": "腐蚀", "top_k": 50}},
     "expect": "blocked"},
    {"case_id": "GR-BF-09", "category": "bad_format",
     "description": "knowledge_type 用了非枚举值 mechanism",
     "call": {"tool": "standard_clause_search",
              "args": {"keyword": "腐蚀", "knowledge_type": "mechanism"}},
     "expect": "blocked"},
    {"case_id": "GR-BF-10", "category": "bad_format",
     "description": "top_k 写成字符串而非 number",
     "call": {"tool": "standard_clause_search",
              "args": {"keyword": "腐蚀", "top_k": "5"}},
     "expect": "blocked"},
    {"case_id": "GR-BF-11", "category": "bad_format",
     "description": "args 不是 dict 而是字符串",
     "call": {"tool": "damage_mechanism_query", "args": "material=碳钢"},
     "expect": "blocked"},
    {"case_id": "GR-BF-12", "category": "bad_format",
     "description": "service_years 写成字符串",
     "call": {"tool": "rbi_lookup",
              "args": {"equipment_type": "换热器", "material": "碳钢", "service_years": "8年"}},
     "expect": "blocked"},
    {"case_id": "GR-BF-13", "category": "bad_format",
     "description": "pressure_mpa 写成字符串带单位",
     "call": {"tool": "rbi_lookup",
              "args": {"equipment_type": "换热器", "material": "碳钢", "pressure_mpa": "1.0MPa"}},
     "expect": "blocked"},
    {"case_id": "GR-BF-14", "category": "bad_format",
     "description": "evidence 不是对象而是数组",
     "call": {"tool": "damage_mechanism_query",
              "args": {"material": "碳钢", "medium": ["氯化氢"], "evidence": [5.8]}},
     "expect": "blocked"},
    {"case_id": "GR-BF-15", "category": "bad_format",
     "description": "equipment_type 不在六类枚举中",
     "call": {"tool": "damage_mechanism_query",
              "args": {"material": "碳钢", "medium": ["氯化氢"], "equipment_type": "空塔"}},
     "expect": "blocked"},

    # ---------- out_of_domain：超出适用范围 ----------
    # 判定口径：工具返回 in_domain=false 且 result 为空 → 算拦住
    {"case_id": "GR-OD-01", "category": "out_of_domain",
     "description": "12Cr5Mo + 连多硫酸 1000℃，高温下条款库未覆盖",
     "call": {"tool": "damage_mechanism_query",
              "args": {"material": "12Cr5Mo", "medium": ["连多硫酸"], "temperature_c": 1000}},
     "expect": "blocked"},
    {"case_id": "GR-OD-02", "category": "out_of_domain",
     "description": "Q245R + 碱式酸性水 1000℃，高温下条款库未覆盖",
     "call": {"tool": "damage_mechanism_query",
              "args": {"material": "Q245R", "medium": ["碱式酸性水"], "temperature_c": 1000}},
     "expect": "blocked"},
    {"case_id": "GR-OD-03", "category": "out_of_domain",
     "description": "碳钢 + 有机氯化物，条款库未覆盖该介质组合",
     "call": {"tool": "damage_mechanism_query",
              "args": {"material": "碳钢", "medium": ["有机氯化物"], "temperature_c": 200}},
     "expect": "blocked"},
    {"case_id": "GR-OD-04", "category": "out_of_domain",
     "description": "碳钢 + 连多硫酸 600℃，高温下条款库未覆盖",
     "call": {"tool": "damage_mechanism_query",
              "args": {"material": "碳钢", "medium": ["连多硫酸"], "temperature_c": 600}},
     "expect": "blocked"},
    {"case_id": "GR-OD-05", "category": "out_of_domain",
     "description": "Q245R钢板 + 碱式酸性水 -60℃，低温下条款库未覆盖",
     "call": {"tool": "damage_mechanism_query",
              "args": {"material": "Q245R钢板", "medium": ["碱式酸性水"], "temperature_c": -60}},
     "expect": "blocked"},
    {"case_id": "GR-OD-06", "category": "out_of_domain",
     "description": "mock: 工具返回 in_domain=false 却仍带着机理结论，护栏须拦下",
     "call": {"tool": "damage_mechanism_query",
              "args": {"material": "碳钢", "medium": ["氯化氢"]}},
     "mock_response": {
         "status": "out_of_domain", "in_domain": False,
         "result": {"mechanisms": [{"name": "盐酸腐蚀", "clause_id": "GBT30579-2022-5.1"}]},
         "source": [{"clause_id": "GBT30579-2022-5.1", "standard_code": "GB/T 30579-2022",
                     "clause_no": "5.1", "page": 7}],
         "message": "查询条件超出条款覆盖范围"},
     "expect": "blocked"},
    {"case_id": "GR-OD-07", "category": "out_of_domain",
     "description": "mock: status=ok 但 in_domain=false 且带 hits，护栏须拦下",
     "call": {"tool": "standard_clause_search", "args": {"keyword": "腐蚀"}},
     "mock_response": {
         "status": "ok", "in_domain": False, "result": {"hits": [{"clause_id": "X", "title": "Y",
                     "snippet": "Z", "score": 1.0}]},
         "source": [{"clause_id": "GBT26610.3-2014-7-a", "standard_code": "GB/T 26610.3-2014",
                     "clause_no": "7", "page": 11}],
         "message": "超出适用范围"},
     "expect": "blocked"},
]

# ============================================================
# 二、正常用例：≥30 条，全部应放行
#    组合均来自 `_scan_normal.py` 实测可放行的 材质×介质×温度
# ============================================================
NC = []
def nc(desc, tool, args):
    NC.append({"case_id": "NC-%02d" % (len(NC) + 1), "category": "normal",
               "description": desc, "call": {"tool": tool, "args": args}, "expect": "pass"})

# --- damage_mechanism_query：按介质覆盖（全部实测可放行）---
nc("碳钢 + 湿硫化氢 110℃，常减压塔顶工况", "damage_mechanism_query",
   {"material": "碳钢", "medium": ["湿硫化氢"], "temperature_c": 110,
    "equipment_type": "换热器",
    "evidence": {"ph": 5.8, "cl_ppm": 42, "fe_ppm": 4.1, "wall_thinning": False}})
nc("碳钢 + 氯化氢 60℃，盐酸腐蚀工况", "damage_mechanism_query",
   {"material": "碳钢", "medium": ["氯化氢"], "temperature_c": 60, "equipment_type": "管道"})
nc("碳钢 + 氯化铵 60℃，注水点结盐工况", "damage_mechanism_query",
   {"material": "碳钢", "medium": ["氯化铵"], "temperature_c": 60, "equipment_type": "换热器"})
nc("碳钢 + 氨 450℃，合成氨装置工况", "damage_mechanism_query",
   {"material": "碳钢", "medium": ["氨"], "temperature_c": 450, "equipment_type": "容器"})
nc("碳钢 + 氢氧化钠 200℃，碱腐蚀工况", "damage_mechanism_query",
   {"material": "碳钢", "medium": ["氢氧化钠"], "temperature_c": 200, "equipment_type": "容器"})
nc("碳钢 + 氧气 60℃，高含氧环境", "damage_mechanism_query",
   {"material": "碳钢", "medium": ["氧气"], "temperature_c": 60, "equipment_type": "管道"})
nc("碳钢 + 环烷酸 200℃，常减压高温环烷酸腐蚀", "damage_mechanism_query",
   {"material": "碳钢", "medium": ["环烷酸"], "temperature_c": 200, "equipment_type": "管道"})
nc("碳钢 + 二氧化碳 60℃，二氧化碳腐蚀", "damage_mechanism_query",
   {"material": "碳钢", "medium": ["二氧化碳"], "temperature_c": 60})
nc("碳钢 + 循环水 110℃，冷却水腐蚀", "damage_mechanism_query",
   {"material": "碳钢", "medium": ["循环水"], "temperature_c": 110, "equipment_type": "换热器"})
nc("碳钢 + 氯离子 60℃，点蚀风险", "damage_mechanism_query",
   {"material": "碳钢", "medium": ["氯离子"], "temperature_c": 60,
    "evidence": {"cl_ppm": 200}})
nc("碳钢 + 胺液 60℃，胺腐蚀", "damage_mechanism_query",
   {"material": "碳钢", "medium": ["胺液"], "temperature_c": 60})
nc("碳钢 + 氰化物 60℃，氰化物介质", "damage_mechanism_query",
   {"material": "碳钢", "medium": ["氰化物"], "temperature_c": 60})
nc("低合金钢 + 含盐水 60℃，含盐水腐蚀", "damage_mechanism_query",
   {"material": "低合金钢", "medium": ["含盐水"], "temperature_c": 60, "equipment_type": "管道"})
nc("低合金钢 + 高温硫化物腐蚀介质 300℃", "damage_mechanism_query",
   {"material": "低合金钢", "medium": ["高温硫化物腐蚀介质"], "temperature_c": 300,
    "equipment_type": "加热炉"})
nc("15CrMo + 胺液 200℃", "damage_mechanism_query",
   {"material": "15CrMo", "medium": ["胺液"], "temperature_c": 200})
nc("12Cr5Mo + 循环水 200℃", "damage_mechanism_query",
   {"material": "12Cr5Mo", "medium": ["循环水"], "temperature_c": 200})
nc("300系列不锈钢 + 硫氢化铵 60℃", "damage_mechanism_query",
   {"material": "300系列不锈钢", "medium": ["硫氢化铵"], "temperature_c": 60})
nc("300系列不锈钢 + 碱式酸性水 60℃", "damage_mechanism_query",
   {"material": "300系列不锈钢", "medium": ["碱式酸性水"], "temperature_c": 60})
nc("300系列不锈钢 + 酸式酸性水 60℃", "damage_mechanism_query",
   {"material": "300系列不锈钢", "medium": ["酸式酸性水"], "temperature_c": 60})
nc("300系列不锈钢 + 连多硫酸 60℃", "damage_mechanism_query",
   {"material": "300系列不锈钢", "medium": ["连多硫酸"], "temperature_c": 60})
nc("400系列不锈钢 + 环烷酸 200℃", "damage_mechanism_query",
   {"material": "400系列不锈钢", "medium": ["环烷酸"], "temperature_c": 200,
    "equipment_type": "管道"})
nc("Q245R + 湿硫化氢 120℃", "damage_mechanism_query",
   {"material": "Q245R", "medium": ["湿硫化氢"], "temperature_c": 120, "equipment_type": "储罐"})
nc("Q345R + 循环水 60℃", "damage_mechanism_query",
   {"material": "Q345R", "medium": ["循环水"], "temperature_c": 60})
nc("20 + 氯化氢 60℃", "damage_mechanism_query",
   {"material": "20", "medium": ["氯化氢"], "temperature_c": 60})
nc("300系列不锈钢 + 氯化氢 60℃", "damage_mechanism_query",
   {"material": "300系列不锈钢", "medium": ["氯化氢"], "temperature_c": 60})
nc("碳钢 + 循环水 60℃（冷却水腐蚀）", "damage_mechanism_query",
   {"material": "碳钢", "medium": ["循环水"], "temperature_c": 60})
nc("碳钢 + 多介质并列 + 完整 evidence", "damage_mechanism_query",
   {"material": "碳钢", "medium": ["湿硫化氢", "氯化氢", "氯化铵"], "temperature_c": 110,
    "equipment_type": "换热器",
    "evidence": {"ph": 5.8, "cl_ppm": 42, "fe_ppm": 4.1, "wall_thinning": False,
                 "crack_found": False}})
nc("碳钢 + 氧气 + 低温（液氧空分工况）", "damage_mechanism_query",
   {"material": "碳钢", "medium": ["氧气"], "temperature_c": -20, "equipment_type": "容器"})
nc("Q245R + 氯化氢 + 六个 evidence 字段全填", "damage_mechanism_query",
   {"material": "Q245R", "medium": ["氯化氢"], "temperature_c": 110, "equipment_type": "储罐",
    "evidence": {"ph": 2.5, "cl_ppm": 500, "fe_ppm": 12.0, "h2s_ppm": 30,
                 "wall_thinning": True, "crack_found": False}})
nc("碳钢 + 氢氧化钠 + 换热器", "damage_mechanism_query",
   {"material": "碳钢", "medium": ["氢氧化钠"], "temperature_c": 200, "equipment_type": "换热器"})
nc("碳钢 + 环烷酸 + 塔", "damage_mechanism_query",
   {"material": "碳钢", "medium": ["环烷酸"], "temperature_c": 200, "equipment_type": "塔"})

# --- 别名写法（护栏应归一化后放行，不是拦截）---
nc("材质别名 碳素钢（carbon steel）", "damage_mechanism_query",
   {"material": "碳素钢", "medium": ["氯化氢"], "temperature_c": 60})
nc("材质别名 S30408（= 06Cr19Ni10）", "damage_mechanism_query",
   {"material": "S30408", "medium": ["循环水"], "temperature_c": 60})
nc("材质别名 20#（= 20 号钢）", "damage_mechanism_query",
   {"material": "20#", "medium": ["氯化氢"], "temperature_c": 60})
nc("材质别名 Q245R钢板", "damage_mechanism_query",
   {"material": "Q245R钢板", "medium": ["循环水"], "temperature_c": 60})
nc("材质别名 低合金钢材", "damage_mechanism_query",
   {"material": "低合金钢材", "medium": ["循环水"], "temperature_c": 60})
nc("介质别名 HCl（氯化氢）", "damage_mechanism_query",
   {"material": "碳钢", "medium": ["HCl"], "temperature_c": 60})
nc("介质别名 湿H2S（湿硫化氢）", "damage_mechanism_query",
   {"material": "碳钢", "medium": ["湿H2S"], "temperature_c": 110})
nc("介质别名 NH3（氨）", "damage_mechanism_query",
   {"material": "碳钢", "medium": ["NH3"], "temperature_c": 450})
nc("设备别名 空冷器（换热器）", "damage_mechanism_query",
   {"material": "碳钢", "medium": ["湿硫化氢"], "temperature_c": 60,
    "equipment_type": "空冷器"})
nc("设备别名 塔器（塔）", "damage_mechanism_query",
   {"material": "碳钢", "medium": ["环烷酸"], "temperature_c": 200,
    "equipment_type": "塔器"})
nc("设备别名 工艺管道（管道）+ 低合金钢含盐水", "damage_mechanism_query",
   {"material": "低合金钢", "medium": ["含盐水"], "temperature_c": 60,
    "equipment_type": "工艺管道"})
nc("设备别名 回流罐（容器）", "damage_mechanism_query",
   {"material": "碳钢", "medium": ["氯化氢"], "temperature_c": 60,
    "equipment_type": "回流罐"})

# --- rbi_lookup ---
nc("rbi_lookup 换热器 + 碳钢 + 盐酸腐蚀", "rbi_lookup",
   {"equipment_type": "换热器", "material": "碳钢", "mechanism": "盐酸腐蚀",
    "medium": ["氯化氢"], "temperature_c": 110, "service_years": 8})
nc("rbi_lookup 管道 + 湿硫化氢破坏", "rbi_lookup",
   {"equipment_type": "管道", "material": "碳钢", "mechanism": "湿硫化氢破坏",
    "medium": ["湿硫化氢"], "service_years": 12})
nc("rbi_lookup 容器 + 氢脆", "rbi_lookup",
   {"equipment_type": "容器", "material": "低合金钢", "mechanism": "氢脆",
    "temperature_c": 300, "pressure_mpa": 15.0})
nc("rbi_lookup 塔 + 环烷酸腐蚀", "rbi_lookup",
   {"equipment_type": "塔", "material": "碳钢", "mechanism": "环烷酸腐蚀",
    "medium": ["环烷酸"], "temperature_c": 200})
nc("rbi_lookup 加热炉 + 热疲劳", "rbi_lookup",
   {"equipment_type": "加热炉", "material": "碳钢", "mechanism": "热疲劳",
    "service_years": 20})
nc("rbi_lookup 储罐 + 氯化铵腐蚀", "rbi_lookup",
   {"equipment_type": "储罐", "material": "碳钢", "mechanism": "氯化铵腐蚀",
    "medium": ["氯化铵"]})
nc("rbi_lookup 给必填两项 + mechanism", "rbi_lookup",
   {"equipment_type": "换热器", "material": "碳钢", "mechanism": "盐酸腐蚀"})
nc("rbi_lookup 材料别名 碳素钢", "rbi_lookup",
   {"equipment_type": "换热器", "material": "碳素钢", "mechanism": "盐酸腐蚀"})

# --- standard_clause_search ---
nc("检索 湿硫化氢", "standard_clause_search", {"keyword": "湿硫化氢"})
nc("检索 氯化铵", "standard_clause_search", {"keyword": "氯化铵"})
nc("检索 检验周期 限定RBI", "standard_clause_search",
   {"keyword": "检验周期", "knowledge_type": "rbi"})
nc("检索 风险等级", "standard_clause_search", {"keyword": "风险等级"})
nc("检索 带 top_k=10", "standard_clause_search", {"keyword": "腐蚀", "top_k": 10})
nc("检索 带 top_k=1", "standard_clause_search", {"keyword": "腐蚀", "top_k": 1})
nc("检索 现象描述：塔顶 腐蚀", "standard_clause_search",
   {"keyword": "塔顶 腐蚀"})
nc("检索 现象描述：焊缝附近发现裂纹", "standard_clause_search",
   {"keyword": "焊缝 裂纹 磁粉检测"})
nc("检索 现象描述：湿硫化氢 裂纹 检测", "standard_clause_search",
   {"keyword": "湿硫化氢 裂纹 检测"})

def dump(path, rows):
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    print('已写出 %s：%d 条' % (path, len(rows)))

dump(os.path.join(OUT_DIR, 'guardrail_cases.jsonl'), GR)
dump(os.path.join(OUT_DIR, 'normal_cases.jsonl'), NC)
print()
print('护栏用例分类分布:', dict(Counter(c['category'] for c in GR)))
print('正常用例数:', len(NC))
