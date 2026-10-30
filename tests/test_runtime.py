"""Pure R0 tests that run even before cloning the upstream project."""
import unittest

from app.runtime import build_task, check_trace_sources, split_medium


class TaskInputTests(unittest.TestCase):
    def test_normalize_medium(self):
        self.assertEqual(split_medium("湿硫化氢，氯化氢、氯化铵"), ["湿硫化氢", "氯化氢", "氯化铵"])

    def test_empty_medium_rejected(self):
        with self.assertRaises(ValueError):
            split_medium(" , ， ")

    def test_task_preserves_teacher_fields(self):
        task = build_task("常压塔", "碳钢", "氯化氢", "操作温度95℃", "", "为何腐蚀？")
        self.assertEqual(
            set(task), {"equipment", "material", "medium", "operating_condition", "field_evidence", "question"},
        )
        self.assertEqual(task["medium"], ["氯化氢"])

    def test_no_question_rejected(self):
        with self.assertRaises(ValueError):
            build_task("常压塔", "碳钢", "氯化氢", "", "", "")

    def test_basis_must_appear_in_tool_sources(self):
        trace = {
            "steps": [{"result": {"source": [{"clause_id": "A-1"}]}}],
            "final_answer": {"basis": ["A-1", "B-2"]},
        }
        self.assertEqual(check_trace_sources(trace), ["结论引用条款 B-2 未出现在本次工具返回中"])

    def test_no_basis_with_no_sources(self):
        self.assertEqual(check_trace_sources({"steps": [], "final_answer": {"basis": []}}), [])


if __name__ == "__main__":
    unittest.main()
