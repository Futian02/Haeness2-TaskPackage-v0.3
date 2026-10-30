"""SQLite FTS5 baseline tests; no writing to the official data package."""
import unittest

from knowledge.lexical import SqliteLexicalRetriever


class LexicalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import tempfile
        import json
        from pathlib import Path
        # A temporary synthetic corpus so tests do not depend on official data.
        cls.temp = tempfile.TemporaryDirectory()
        cls.data_path = Path(cls.temp.name) / "clauses.jsonl"
        records = [
            {"title": "盐酸腐蚀", "content_raw": "湿氯化氢和腐蚀", "clause_id": "X-1",
             "knowledge_type": "damage_mechanism", "standard_code": "GB/X", "page": 3},
            {"title": "热疲劳", "content_raw": "热循环导致开裂", "clause_id": "X-2",
             "knowledge_type": "damage_mechanism", "standard_code": "GB/X", "page": 4},
            {"title": "风险等级", "content_raw": "可能性与后果查矩阵", "clause_id": "X-3",
             "knowledge_type": "rbi", "standard_code": "GB/Y", "page": 8},
        ]
        cls.data_path.write_text(
            "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in records),
            encoding="utf-8",
        )
        cls.index = SqliteLexicalRetriever(cls.data_path)

    @classmethod
    def tearDownClass(cls):
        cls.index.close()
        cls.temp.cleanup()

    def test_exact_title(self):
        self.assertEqual(self.index.search("盐酸腐蚀")[0]["clause_id"], "X-1")

    def test_knowledge_type_filter(self):
        self.assertEqual(self.index.search("风险等级", kind="rbi")[0]["clause_id"], "X-3")
        self.assertEqual(self.index.search("风险等级", kind="damage_mechanism"), [])

    def test_short_query_fallback(self):
        self.assertEqual(self.index.search("疲劳")[0]["clause_id"], "X-2")

    def test_injection_text_escaped(self):
        self.assertIsInstance(self.index.search("腐蚀' OR 1=1"), list)

    def test_invalid_topk_and_kind(self):
        for bad in (0, 21, True):
            with self.assertRaises(ValueError):
                self.index.search("盐酸腐蚀", top_k=bad)
        with self.assertRaises(ValueError):
            self.index.search("盐酸腐蚀", kind="unknown")


if __name__ == "__main__":
    unittest.main()
