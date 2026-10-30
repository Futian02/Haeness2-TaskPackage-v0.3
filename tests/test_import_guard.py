"""Integration checks are skipped until upstream is checked out.

The skip itself makes missing source visible, without falsely reporting
an end-to-end pass.
"""
from pathlib import Path
import unittest

from app.runtime import UPSTREAM, build_task, load_harness, run_case


@unittest.skipUnless(
    (UPSTREAM / "05_提交区" / "harness.py").is_file()
    and (UPSTREAM / "05_提交区" / "clauses.jsonl").is_file(),
    "upstream/ not cloned: integration NOT VERIFIED",
)
class UpstreamIntegrationTests(unittest.TestCase):
    def test_real_harness_registered_tools(self):
        h = load_harness()
        reg = h.build_registry()
        self.assertEqual(
            set(reg.names()),
            {"damage_mechanism_query", "standard_clause_search", "rbi_lookup"},
        )

    def test_rules_engine_end_to_end(self):
        task = build_task(
            "常压塔顶空冷器", "碳钢", "氯化氢",
            "操作温度95℃", "塔顶水pH 5.8", "可能的损伤机理是什么？",
        )
        result = run_case(task, mode="rule")
        self.assertIsInstance(result["trace"]["steps"], list)
        self.assertGreaterEqual(len(result["trace"]["steps"]), 1)
        self.assertIsNone(result["parse_stats"])


if __name__ == "__main__":
    unittest.main()
