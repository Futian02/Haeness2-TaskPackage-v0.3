from __future__ import annotations

import unittest

from backend.context_slots import extract_explicit_context
from orchestration.evidence_audit import load_clause_index
from orchestration.intent import classify_intent
from orchestration.r9_industrial_candidate import IndustrialCandidate, TEACHER_TOOLS


CLAUSE = {
    "clause_id": "GBT30579-2022-5.23",
    "standard_code": "GB/T 30579-2022",
    "clause_no": "5.23",
    "page": 42,
    "title": "酸性水腐蚀",
    "content_raw": "适用于酸式酸性水及碱式酸性水环境。应结合介质组分、pH、温度和现场形貌核查。",
    "applicable_conditions": {"medium": ["酸式酸性水", "碱式酸性水"]},
    "exclusion_conditions": ["未确认酸性水类别时不可直接套用"],
}


def response(source=None, result=None):
    return {"status": "ok", "in_domain": True, "result": result or {},
            "source": source if source is not None else [CLAUSE], "message": ""}


class P13RouterAndHypothesisTests(unittest.TestCase):
    def test_addendum_30_case_cross_topic_routing_matrix(self):
        stale = {"material": "碳钢", "medium": ["湿硫化氢"], "equipment_type": "管道"}
        groups = {
            "general": [
                "你好", "你是什么模型", "写一首秋天的诗", "今天的天气如何", "创建HTML自行车动画",
                "请继续写SVG代码", "什么是图灵机？", "解释一下HTTP协议", "帮我写Python排序代码", "最新天气预报",
            ],
            "engineering": [
                "设备腐蚀机理", "分析湿硫化氢损伤机理", "该减薄属于哪类腐蚀？", "这台设备风险等级是多少？",
                "请判断该管道RBI风险等级", "分析碳钢管道湿硫化氢腐蚀机理", "这台设备运行情况是否安全",
                "这台设备风险是多少", "设备腐蚀原因", "本台压力容器风险评估",
            ],
            "standard": [
                "GB/T 26610.5-2022 表2面积后果等级", "查询标准第5.2条", "风险等级的确定标准条款",
                "GB/T 30579-2022 第5.23条", "查一下TSG 21中的压力容器条款",
            ],
            "misleading_stale_context": [
                "今天的天气如何", "创建HTML动画", "什么是图灵机？", "写一首春天的诗", "帮我写CSS Grid示例代码",
            ],
        }
        expected_by_group = {
            "general": ["general_chat"] * 10,
            "engineering": ["hypothesis_exploration", "hypothesis_exploration", "hypothesis_exploration",
                            "deterministic_rbi_grade", "deterministic_rbi_grade", "device_diagnosis",
                            "device_diagnosis", "deterministic_rbi_grade", "hypothesis_exploration",
                            "deterministic_rbi_grade"],
            "standard": ["standard_lookup"] * 5,
            "misleading_stale_context": ["general_chat"] * 5,
        }
        self.assertEqual(sum(len(items) for items in groups.values()), 30)
        for group, questions in groups.items():
            for question, expected in zip(questions, expected_by_group[group]):
                context = stale if group == "misleading_stale_context" else {}
                with self.subTest(group=group, question=question):
                    self.assertEqual(classify_intent(question, context), expected)

    def tools(self):
        calls = {name: [] for name in TEACHER_TOOLS}

        def damage(**kwargs):
            calls["damage_mechanism_query"].append(kwargs)
            return response(result={"mechanisms": []})

        def rbi(**kwargs):
            calls["rbi_lookup"].append(kwargs)
            return response(result={"risk_level_unified": "L5"})

        def search(**kwargs):
            calls["standard_clause_search"].append(kwargs)
            return response(result={"hits": [{"clause_id": CLAUSE["clause_id"]}]})

        return {"damage_mechanism_query": damage, "rbi_lookup": rbi,
                "standard_clause_search": search}, calls

    def test_twenty_synthetic_current_turn_intent_cases(self):
        stale = {"material": "碳钢", "medium": ["湿硫化氢"], "equipment_type": "管道"}
        cases = [
            ("你好", "general_chat"), ("你是什么模型", "general_chat"),
            ("帮我写一首秋天的诗", "general_chat"), ("今天的天气如何", "general_chat"),
            ("创建一个HTML自行车动画", "general_chat"), ("请继续写SVG代码", "general_chat"),
            ("什么是图灵机？", "general_chat"), ("介绍一下腐蚀", "general_chat"),
            ("GB/T 26610.5-2022 表2面积后果等级", "standard_lookup"),
            ("查询标准第5.2条", "standard_lookup"), ("风险等级的确定标准条款", "standard_lookup"),
            ("设备腐蚀机理", "device_diagnosis"),
            ("该减薄属于哪类腐蚀？", "device_diagnosis"),
            ("分析湿硫化氢损伤机理", "device_diagnosis"),
            ("这台设备风险等级是多少？", "deterministic_rbi_grade"),
            ("请判断该管道的RBI风险等级", "deterministic_rbi_grade"),
            ("分析碳钢管道硫化氢腐蚀机理", "device_diagnosis"),
            ("这台设备运行情况是否安全", "device_diagnosis"),
            ("怎么检测它的腐蚀", "device_diagnosis"),
            ("创建HTML动画，顺便查询GB/T条款", "standard_lookup"),
        ]
        for question, expected in cases:
            with self.subTest(question=question):
                self.assertEqual(classify_intent(question, stale), expected)

    def test_weather_code_and_concept_are_not_poisoned_by_prior_slots(self):
        prior = {"material": "碳钢", "medium": ["湿硫化氢"], "equipment_type": "管道"}
        for question in ("今天的天气如何", "创建HTML自行车动画", "什么是图灵机？"):
            self.assertEqual(classify_intent(question, prior), "general_chat")

    def test_labeled_bracket_medium_and_json_array_normalize_to_frozen_enum(self):
        one = extract_explicit_context("材质：[300系列不锈钢]，介质：[碱式酸性水]")
        self.assertEqual(one["values"]["material"], "300系列不锈钢")
        self.assertEqual(one["values"]["medium"], ["碱式酸性水"])
        two = extract_explicit_context('介质: [湿硫化氢, 氯化氢]')
        self.assertEqual(two["values"]["medium"], ["湿硫化氢", "氯化氢"])
        three = extract_explicit_context('介质: ["湿H2S", "HCl"]')
        self.assertEqual(three["values"]["medium"], ["湿硫化氢", "氯化氢"])

    def test_unknown_generic_acidic_water_is_not_promoted_to_enum(self):
        parsed = extract_explicit_context("介质：酸性水")
        self.assertNotIn("medium", parsed["values"])
        self.assertNotIn("medium", extract_explicit_context("介质：水") ["values"])
        self.assertEqual(extract_explicit_context("设备材质为碳钢，处于HCl环境") ["values"]["medium"], ["氯化氢"])

    def test_partial_context_routes_to_source_conditioned_exploration(self):
        tools, calls = self.tools()
        graph = IndustrialCandidate(tool_registry=tools, clause_index={CLAUSE["clause_id"]: CLAUSE})
        result = graph.run("该减薄属于哪类腐蚀？", {"medium": ["碱式酸性水"]})
        output = result["output"]
        self.assertEqual(result["task_kind"], "hypothesis_exploration")
        self.assertEqual(calls["damage_mechanism_query"], [])
        self.assertEqual(len(calls["standard_clause_search"]), 1)
        self.assertEqual(output["status"], "exploratory_directions")
        self.assertIsNone(output["risk_level"])
        self.assertEqual(output["verification_level"], "E0")
        candidate = output["hypotheses"][0]
        self.assertEqual(candidate["source_clause_ids"], [CLAUSE["clause_id"]])
        self.assertEqual(candidate["applicability_label"], "有条件适用")
        self.assertIsNone(candidate["probability"])
        self.assertEqual(candidate["review_status"], "requires_human_review")
        self.assertTrue(candidate["required_field_evidence"])
        self.assertIn("适用条件未核实", output["conclusion"])

    def test_no_source_means_no_hypothesis_and_risk_stays_unknown(self):
        tools, _ = self.tools()
        tools["standard_clause_search"] = lambda **kwargs: response(source=[], result={"hits": []})
        result = IndustrialCandidate(tool_registry=tools, clause_index={CLAUSE["clause_id"]: CLAUSE}).run(
            "分析腐蚀机理", {})["output"]
        self.assertEqual(result["status"], "unresolved")
        self.assertEqual(result["hypotheses"], [])
        self.assertIsNone(result["risk_level"])

    def test_unqualified_risk_grade_requests_missing_inputs_without_tools(self):
        tools, calls = self.tools()
        graph = IndustrialCandidate(tool_registry=tools, clause_index={CLAUSE["clause_id"]: CLAUSE})
        result = graph.run("这台设备风险等级是多少？", {})
        self.assertEqual(result["task_kind"], "deterministic_rbi_grade")
        self.assertEqual(result["output"]["status"], "needs_user_input")
        self.assertIsNone(result["output"]["risk_level"])
        self.assertEqual(sum(map(len, calls.values())), 0)
        self.assertTrue({"material", "medium", "equipment_type", "pressure_mpa", "service_years"}.issubset(
            set(result["output"]["unknowns"])))

    def test_teacher_registry_remains_exact_three_tools(self):
        tools, _ = self.tools()
        graph = IndustrialCandidate(tool_registry=tools, clause_index={CLAUSE["clause_id"]: CLAUSE})
        self.assertEqual(set(graph.tool_registry), set(TEACHER_TOOLS))

    def test_ten_real_clause_rows_remain_traceable_without_promoting_source_presence(self):
        # Read-only source linkage check. Generic RBI rows with no semantic
        # overlap remain citations, not promoted mechanism hypotheses.
        index = load_clause_index()
        rows = list(index.values())[:10]
        self.assertEqual(len(rows), 10)
        tools, _ = self.tools()
        tools["standard_clause_search"] = lambda **kwargs: response(source=rows,
            result={"hits": [{"clause_id": row["clause_id"]} for row in rows]})
        result = IndustrialCandidate(tool_registry=tools, clause_index=index).run("分析腐蚀机理", {})
        output = result["output"]
        self.assertEqual(output["hypotheses"], [])
        self.assertEqual({row["clause_id"] for row in output["citations"]}, {row["clause_id"] for row in rows})
        for citation in output["citations"]:
            canonical = index[citation["clause_id"]]
            self.assertTrue(canonical.get("content_raw"))
            self.assertEqual(citation["verification_level"], "E0")
            self.assertEqual(citation["semantic_relation"]["applicability"], "UNKNOWN")
            self.assertFalse(citation["semantic_relation"]["may_support_claim"])


if __name__ == "__main__":
    unittest.main()
