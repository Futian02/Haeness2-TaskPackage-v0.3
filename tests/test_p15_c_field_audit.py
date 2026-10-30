import importlib.util
import tempfile
import unittest
import csv
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("p15_c_field_audit",ROOT/"scripts/p15_c_field_audit.py")
qa=importlib.util.module_from_spec(spec);spec.loader.exec_module(qa)
spec2=importlib.util.spec_from_file_location("p15_c_prepare_review_and_merge",ROOT/"scripts/p15_c_prepare_review_and_merge.py")
prep=importlib.util.module_from_spec(spec2);spec2.loader.exec_module(prep)

class FieldAuditTests(unittest.TestCase):
    def test_workbook_contract_headers_and_expected_sheets(self):
        for path,headers in ((qa.RBI,qa.RBI_HEADERS),(qa.DM,qa.DM_HEADERS)):
            wb=qa.load_workbook(path,read_only=True,data_only=True)
            self.assertEqual(wb.sheetnames,qa.EXPECTED_SHEETS)
            self.assertEqual([qa.txt(x) for x in next(wb["摘录表"].iter_rows(values_only=True))],headers)
            self.assertIn(len(headers),(23,25))

    def test_blank_optional_is_source_unspecified_not_failure(self):
        self.assertEqual(qa.classify_nonempty("rbi","检验周期(年)",None,{})[0],"SOURCE_UNSPECIFIED")

    def test_original_excerpt_and_numeric_range_require_source_review(self):
        self.assertEqual(qa.classify_nonempty("dm","原文摘录","一段文本",{})[0],"REVIEW_NEEDED")
        self.assertEqual(qa.classify_nonempty("dm","温度下限",49,{})[0],"REVIEW_NEEDED")

    def test_enum_rejects_noncanonical_values(self):
        c,r=qa.classify_nonempty("dm","适用介质","酸性水",{})
        self.assertEqual(c,"REVIEW_NEEDED");self.assertIn("枚举非法",r)

    def test_matrix_values_match_teacher_mapping(self):
        mapping=qa.load_risk_map()
        self.assertTrue(mapping)
        self.assertIsNotNone(mapping.get(("1","A")) or mapping.get(("1","a")))

    def test_source_workbooks_are_not_modified(self):
        self.assertEqual(len(qa.sha(qa.RBI)),64);self.assertEqual(len(qa.sha(qa.DM)),64)

    def test_official_matrix_and_area_thresholds_have_machine_consistency_gate(self):
        with tempfile.TemporaryDirectory() as d:
            issues=qa.audit_official_clause_semantics(Path(d)/"audit.json")
        errors=[x for x in issues if x["severity"]=="ERROR"]
        self.assertEqual(errors,[])
        reviews=[x for x in issues if x["rule"]=="DM_HIGH_RISK_SEMANTICS"]
        self.assertEqual(len(reviews),3)
        self.assertTrue(all(x["source_truth"]=="NOT_INDEPENDENTLY_VISUAL_VERIFIED" for x in reviews))

    def test_human_review_sample_is_deterministic_and_unsigned(self):
        with tempfile.TemporaryDirectory() as d:
            p1=Path(d)/"first.csv";p2=Path(d)/"second.csv"
            prep.seed50(p1,20261029);prep.seed50(p2,20261029)
            self.assertEqual(p1.read_bytes(),p2.read_bytes())
            with p1.open(encoding="utf-8-sig",newline="") as f: rows=list(csv.DictReader(f))
        self.assertEqual(len(rows),50)
        self.assertTrue(all(x["human_status"]=="PENDING_HUMAN_REVIEW" and not x["pass_fail"] and not x["independent_reviewer_identity"] for x in rows))
        self.assertTrue(all(x["source_pdf"].startswith(("upstream/01_RBI标准/","upstream/02_损伤机理参考/")) for x in rows))

    def test_all_known_standard_pdf_paths_exist(self):
        self.assertTrue(all((qa.UP/path).is_file() for path in qa.PDF_BY_STANDARD.values()))

    def test_ab_candidate_cell_changes_match_their_frozen_ledgers_exactly(self):
        a=ROOT/"work/data_staging/p15/A_RBI/条款摘录表_RBI_P15_A_candidate.xlsx"
        b=ROOT/"work/data_staging/p15/B_DM/条款摘录表_损伤机理_P15_B_candidate.xlsx"
        if not (a.exists() and b.exists()): self.skipTest("A/B P15 candidates not available yet")
        a_diff=prep.compare_candidate(qa.RBI,a,ROOT/"work/data_staging/p15/A_RBI/P15_A_FIELD_CHANGELOG.csv","RBI")
        b_diff=prep.compare_candidate(qa.DM,b,ROOT/"docs/data_quality/P15_B_FIELD_CHANGELOG.csv","DM")
        self.assertEqual(len(a_diff),64);self.assertEqual(len(b_diff),9)

if __name__=="__main__": unittest.main()
