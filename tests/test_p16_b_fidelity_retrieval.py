import csv
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "work/data_staging/p16/B_REMAINDER"


def rows(name):
    with (OUT / name).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


class P16BFidelityRetrievalTests(unittest.TestCase):
    def test_remaining_table_queue_is_complete_and_pending(self):
        data = rows("P16_B_PRIORITY_TRIAGE.csv")
        self.assertEqual(len(data), 211)
        self.assertEqual(len({row["clause_id"] for row in data}), 211)
        self.assertTrue(all(row["human_review_status"] == "NOT_DONE" for row in data))
        self.assertTrue(all(row["release_eligible"] == "NO" for row in data))
        captured = [row for row in data if row.get("targeted_ocr_status")]
        self.assertEqual(len(captured), 20)
        self.assertTrue(all(row["source_status"] == "AI_VISUAL_NUMERIC_ROW_MATCH_F_TEXT_PENDING_HUMAN" for row in captured))
        self.assertTrue(all("bbox" in row["failure_reason"].lower() for row in captured))
        self.assertTrue(all(row["table_id"] == "表2" and row["table_row"] and "FG总计" in row["table_column"] for row in captured))
        self.assertEqual(sum(row["source_status"] == "SOURCE_UNRESOLVED_CELL_PAGE_LOCATED" for row in data), 191)

    def test_damage_mechanism_review_has_all_656_plus_656_fields(self):
        data = rows("P16_B_DM_FIELD_REVIEW.csv")
        self.assertEqual(len(data), 1312)
        self.assertEqual(sum(row["field_letter"] in "GHIJKLMN" for row in data), 656)
        self.assertEqual(sum(row["field_letter"] in "OPQRSTUV" for row in data), 656)
        self.assertTrue(all(row["semantic_review_status"] == "PENDING_SOURCE_SENTENCE_REVIEW" for row in data))
        for clause in ("5.6", "5.23", "6.7"):
            self.assertTrue(any(row["clause_id"] == clause and row["p16_priority"] == "P0_CRITICAL_CONDITION" for row in data))

    def test_supplement_chapters_remain_non_ingested_candidates(self):
        data = rows("P16_B_SUPPLEMENT_REVIEW.csv")
        self.assertEqual(len(data), 56)
        self.assertTrue(all(row["direct_dm_eligible"] == "NO_EVIDENCE" for row in data))
        self.assertTrue(all(row["human_review_status"] == "NOT_DONE" for row in data))
        self.assertTrue(all("DO NOT INGEST" in row["decision"] for row in data))
        pipe = [row for row in data if row["standard_code"] == "GB/T 21447-2018"]
        self.assertTrue(any(row["title_candidate_from_targeted_ocr"] == "干扰防护" for row in pipe))
        self.assertTrue(any(row["title_confidence"] == "UNRESOLVED" for row in pipe))

    def test_retrieval_comparison_keeps_gold_and_records_latency(self):
        base = rows("P16_B_RETRIEVAL_BASELINE_46.csv")
        candidate = rows("P16_B_RETRIEVAL_CANDIDATE_46.csv")
        self.assertEqual(len(base), 46)
        self.assertEqual(len(candidate), 46)
        base_by = {row["case_id"]: row for row in base}
        candidate_by = {row["case_id"]: row for row in candidate}
        misses = {"likelihood_method", "matrix_5e", "matrix_mapping", "inspection_strategy", "dm_56_light_phase"}
        self.assertTrue(misses.issubset(base_by))
        for cid in misses:
            self.assertEqual(base_by[cid]["expected_clause_ids"], candidate_by[cid]["expected_clause_ids"])
            self.assertTrue(candidate_by[cid]["first_gold_rank"])
            self.assertTrue(float(base_by[cid]["warm_latency_mean_ms_30"]) >= 0)
            self.assertTrue(float(candidate_by[cid]["warm_latency_p95_ms_30"]) >= 0)
        summary = json.loads((OUT / "P16_B_RUN_SUMMARY.json").read_text(encoding="utf-8"))
        self.assertTrue(summary["retrieval_gold_unchanged"])
        self.assertEqual(summary["retrieval_baseline"]["retrieved_relevant"], 37)
        self.assertEqual(summary["retrieval_candidate"]["retrieved_relevant"], 42)
        self.assertIn("not expert validation", summary["retrieval_evaluation_scope"])
        self.assertFalse(summary["teacher_tools_changed"])
        self.assertFalse(summary["formal_data_changed"])
        diagnosis = (ROOT / "docs/data_quality/P16_B_RETRIEVAL_DIAGNOSIS.md").read_text(encoding="utf-8")
        for cid in misses:
            self.assertIn(f"`{cid}`", diagnosis)

    def test_source_grounded_damage_mechanism_proposals_are_not_applied(self):
        proposals = [json.loads(line) for line in (OUT / "P16_B_CHANGE_PROPOSALS.jsonl").read_text(encoding="utf-8").splitlines()]
        by_id = {item["proposal_id"]: item for item in proposals}
        expected = {
            "P16B-DM-56-MATERIAL-5.6.3",
            "P16B-DM-56-TERM-SCOPE-5.6.4",
            "P16B-DM-56-EQUIPMENT-5.6.5",
            "P16B-DM-523-MATERIAL-SCOPE",
            "P16B-DM-67-CONDITION-SEMANTICS",
        }
        self.assertTrue(expected.issubset(by_id))
        for proposal_id in expected:
            proposal = by_id[proposal_id]
            self.assertIn("GBT30579-2022", proposal["clause_id"])
            self.assertIn("GBT30579-2022", proposal["source_pdf"])
            self.assertTrue(proposal["review_required"])
            self.assertIn("PENDING_HUMAN", proposal["review_status"])
        self.assertIn("5Cr-0.5Mo", by_id["P16B-DM-56-MATERIAL-5.6.3"]["new_value_proposal"])
        self.assertIn("烃相介质", by_id["P16B-DM-56-TERM-SCOPE-5.6.4"]["new_value_proposal"])
        self.assertIn("0.0003 MPa", by_id["P16B-DM-67-CONDITION-SEMANTICS"]["new_value_proposal"])
        summary = json.loads((OUT / "P16_B_RUN_SUMMARY.json").read_text(encoding="utf-8"))
        self.assertEqual(summary["change_proposal_count"], len(proposals))
        self.assertEqual(summary["change_proposal_count"], 11)


if __name__ == "__main__":
    unittest.main()
