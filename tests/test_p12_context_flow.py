import tempfile
import unittest
from pathlib import Path

from backend.context_slots import extract_explicit_context
from backend.store import Store
from orchestration.r9_industrial_candidate import IndustrialCandidate


class P12NaturalLanguageContextTests(unittest.TestCase):
    def test_case_a_extracts_and_calls_existing_teacher_tools(self):
        question = "设备：塔顶碱液管线弯头，材质：300系列不锈钢，介质：碱式酸性水，温度：60°C，该减薄属于哪类腐蚀？"
        parsed = extract_explicit_context(question)
        self.assertEqual(parsed["values"]["material"], "300系列不锈钢")
        self.assertEqual(parsed["values"]["medium"], ["碱式酸性水"])
        self.assertEqual(parsed["values"]["temperature_c"], 60)
        result = IndustrialCandidate().run(question, parsed["values"])["output"]
        self.assertGreaterEqual(result["tool_calls"], 1)
        self.assertTrue(any("酸性水腐蚀" in row["text"] for row in result["hypotheses"]))
        self.assertTrue(any(row["clause_id"] == "GBT30579-2022-5.23" for row in result["citations"]))
        self.assertIsNone(result["risk_level"])

    def test_no_temperature_from_material_number_and_no_observed_thinning_from_question(self):
        result = extract_explicit_context("材质：300系列不锈钢，有减薄吗？")
        self.assertEqual(result["values"]["material"], "300系列不锈钢")
        self.assertNotIn("temperature_c", result["values"])
        self.assertNotIn("wall_thinning", result["values"])

    def test_case_b_greeting_is_chat_not_tool_run(self):
        result = IndustrialCandidate().run("你好", {})["output"]
        self.assertEqual(result["status"], "general_chat")
        self.assertEqual(result["tool_calls"], 0)

    def test_case_c_missing_equipment_context_asks_without_risk_grade_or_tools(self):
        result = IndustrialCandidate().run("这个设备风险等级是多少？", {})["output"]
        self.assertEqual(result["status"], "needs_user_input")
        self.assertEqual(result["tool_calls"], 0)
        self.assertIsNone(result["risk_level"])

    def test_case_d_structured_form_wins_but_conflict_is_explicit(self):
        result = extract_explicit_context("材质：碳钢，介质：氯化氢", {"material": "300系列不锈钢"})
        self.assertEqual(result["values"]["material"], "300系列不锈钢")
        self.assertEqual(result["conflicts"][0]["field"], "material")

    def test_case_e_same_session_context_is_read_only_and_isolated(self):
        with tempfile.TemporaryDirectory() as temp:
            store = Store(Path(temp) / "history.db")
            first = store.create_conversation("one")
            second = store.create_conversation("two")
            store.create_run_with_message(first["id"], "我的是碳钢管道，介质湿硫化氢", {"material":"碳钢", "medium":["湿硫化氢"]}, "RULE_DEMO", [])
            self.assertEqual(store.latest_confirmed_context(first["id"]), {})  # queued is not confirmed
            run = store.create_run(first["id"], "已确认", {"material":"碳钢", "medium":["湿硫化氢"]}, "RULE_DEMO")
            store.set_run_status(run["id"], "completed")
            self.assertEqual(store.latest_confirmed_context(first["id"])["material"], "碳钢")
            self.assertEqual(store.latest_confirmed_context(second["id"]), {})


if __name__ == "__main__":
    unittest.main()
