import csv
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import p16_c_machine_gate as gate

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "work/data_staging/p16/C_GATE"


def csv_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_json(path: Path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")


class P16CHuman50GateTests(unittest.TestCase):
    def test_exact_frozen_50_ids_and_order_are_compared(self):
        source = csv_rows(ROOT / "work/data_staging/p15/C_QA/P15_C_HUMAN_REVIEW50.csv")
        sample = csv_rows(OUT / "P16_C_MACHINE_SAMPLE_INDEX.csv")
        ok, detail = gate.exact_sample_check(source, sample)
        self.assertTrue(ok, detail)
        self.assertEqual([r["clause_id"] for r in source], [r["clause_id"] for r in sample])
        self.assertEqual({r["seed"] for r in sample}, {"20261029"})

    def test_counterexample_replacing_one_id_same_seed_and_count_fails(self):
        source = csv_rows(ROOT / "work/data_staging/p15/C_QA/P15_C_HUMAN_REVIEW50.csv")
        sample = [dict(r) for r in source]
        sample[17]["clause_id"] = "REPLACED-ID-SAME-SEED"
        sample[17]["seed"] = "20261029"
        self.assertEqual(len(sample), 50)
        self.assertEqual({r["seed"] for r in sample}, {"20261029"})
        ok, detail = gate.exact_sample_check(source, sample)
        self.assertFalse(ok)
        self.assertIn("first_order_mismatch=18", detail)

    def test_sample_freeze_binds_source_bytes_and_ordered_ids(self):
        freeze = json.loads((OUT / "P16_C_SAMPLE_FREEZE_V4.json").read_text(encoding="utf-8"))
        source_path = ROOT / "work/data_staging/p15/C_QA/P15_C_HUMAN_REVIEW50.csv"
        sample_path = OUT / "P16_C_MACHINE_SAMPLE_INDEX.csv"
        source = csv_rows(source_path)
        self.assertEqual(freeze["p15_sample_sha256"], gate.sha(source_path))
        self.assertEqual(freeze["sample_export_sha256"], gate.sha(sample_path))
        self.assertEqual(freeze["sample_ids_sha256"], hashlib.sha256("\n".join(r["clause_id"] for r in source).encode()).hexdigest())
        self.assertEqual(freeze["official_jsonl_sha256"], gate.sha(ROOT / "upstream/05_提交区/clauses.jsonl"))

    def test_review_union_stays_90_and_48_50_42_42_counters_are_distinct(self):
        register = csv_rows(OUT / "P16_C_MACHINE_REVIEW_SCOPE90.csv")
        self.assertEqual(len(register), 90)
        self.assertEqual(len({r["clause_id"] for r in register}), 90)
        self.assertEqual(sum(int(r["change_cell_count"] or 0) for r in register), 73)
        self.assertEqual(sum("RANDOM50" in r["review_scopes"] for r in register), 50)
        self.assertEqual(sum("CHANGED42" in r["review_scopes"] for r in register), 42)
        self.assertEqual(sum(r["overlap_random_and_change"] == "YES" for r in register), 2)

    def test_machine_fail_dominates_human_blocked_and_statuses_are_separate(self):
        checks = [{"status": "BLOCKED"}, {"status": "FAIL"}]
        self.assertEqual(gate.machine_status(checks), "FAIL")
        self.assertEqual(gate.human_threshold_status(0, 50, 0, 42, False, False), "BLOCKED")
        self.assertEqual(gate.combined_status("FAIL", "BLOCKED"), "FAIL")
        self.assertEqual(gate.combined_status("PASS", "FAIL"), "FAIL")
        self.assertEqual(gate.combined_status("BLOCKED", "BLOCKED"), "BLOCKED_PENDING_HUMAN_REVIEW")

    def test_47_of_50_blocks_and_48_of_50_without_all_42_blocks(self):
        self.assertEqual(gate.human_threshold_status(47, 50, 42, 42, True, True), "BLOCKED")
        self.assertEqual(gate.human_threshold_status(48, 50, 41, 42, True, True), "BLOCKED")

    def test_48_of_50_and_42_of_42_still_require_verified_identity_and_owner(self):
        self.assertEqual(gate.human_threshold_status(48, 50, 42, 42, False, True), "BLOCKED")
        self.assertEqual(gate.human_threshold_status(48, 50, 42, 42, True, False), "BLOCKED")
        self.assertEqual(gate.human_threshold_status(48, 50, 42, 42, True, True), "PASS")

    def test_invalid_counts_or_wrong_scope_totals_fail(self):
        self.assertEqual(gate.human_threshold_status(51, 50, 42, 42, True, True), "FAIL")
        self.assertEqual(gate.human_threshold_status(48, 50, 42, 41, True, True), "FAIL")
        self.assertEqual(gate.human_threshold_status(48, 50, 42, 42, True, True, conflicts=1), "BLOCKED")

    def test_review_signature_text_without_trust_material_is_not_identity_verification(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            event = base / "events.jsonl"
            event.write_text('{"reviewer_identity":"Someone","signature_b64":"looks-signed"}\n', encoding="utf-8")
            summary = gate.verified_review_summary(["r1"], ["c1"], event, base / "identity.json", base / "owner.pem", base / "approval.json")
            self.assertFalse(summary["identity_verified"])
            self.assertEqual(summary["verification_status"], "BLOCKED")
            self.assertIn("trust material missing", summary["reason"])

    def test_two_independent_temp_fixture_signers_count_48_and_42_but_only_in_temp(self):
        # Fake identities/signatures are isolated under TemporaryDirectory and
        # the verifier is stubbed. Nothing is written to project review files.
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            random_ids = [f"r{i}" for i in range(50)]
            changed_ids = [f"c{i}" for i in range(42)]
            registry = {"reviewers": {"test-a": {"public_key_pem": "fixture-a"}, "test-b": {"public_key_pem": "fixture-b"}}, "owner_signature_b64": "fixture-owner"}
            write_json(base / "identity.json", registry)
            freeze_hash = "fixture-freeze-sha"
            event_rows = []
            write_json(base / "approval.json", {"sample_ids_sha256": hashlib.sha256("\n".join(random_ids).encode()).hexdigest(),
                                                   "changed_ids_sha256": hashlib.sha256("\n".join(changed_ids).encode()).hexdigest(),
                                                   "freeze_sha256": freeze_hash,
                                                   "review_events_sha256": "filled-after-events",
                                                   "owner_signature_b64": "fixture-owner"})
            events = []
            reviewed_random = random_ids[:48]
            for scope, ids in (("RANDOM50", reviewed_random), ("CHANGED42", changed_ids)):
                for cid in ids:
                    for reviewer in ("test-a", "test-b"):
                        events.append({"event_id": f"{scope}-{cid}-{reviewer}", "clause_id": cid, "scope": scope,
                                       "decision": "PASS", "reviewer_identity": reviewer, "reviewed_at": "fixture-time",
                                       "freeze_sha256": freeze_hash, "source_pdf_sha256": "fixture-pdf",
                                       "render_sha256": "fixture-render", "signature_b64": "fixture-signature"})
            events_path = base / "events.jsonl"
            events_path.write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
            approval_path = base / "approval.json"
            approval = json.loads(approval_path.read_text(encoding="utf-8"))
            approval["review_events_sha256"] = gate.sha(events_path)
            write_json(approval_path, approval)
            (base / "owner.pem").write_text("fixture", encoding="utf-8")
            with patch.object(gate, "_verify_ed25519", return_value=True):
                result = gate.verified_review_summary(random_ids, changed_ids, events_path, base / "identity.json", base / "owner.pem", approval_path, gate.sha(base / "owner.pem"), freeze_hash)
            self.assertEqual((result["random_pass"], result["random_total"]), (48, 50))
            self.assertEqual((result["changed_pass"], result["changed_total"]), (42, 42))
            self.assertEqual(result["verification_status"], "PASS")
            self.assertTrue(all(str(p).startswith(td) for p in base.iterdir()))

    def test_same_reviewer_twice_does_not_satisfy_independent_cross_review(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            ids, changed = [f"r{i}" for i in range(50)], [f"c{i}" for i in range(42)]
            write_json(base / "identity.json", {"reviewers": {"same": {"public_key_pem": "fixture"}}, "owner_signature_b64": "sig"})
            freeze_hash = "fixture-freeze"
            write_json(base / "approval.json", {"sample_ids_sha256": hashlib.sha256("\n".join(ids).encode()).hexdigest(), "changed_ids_sha256": hashlib.sha256("\n".join(changed).encode()).hexdigest(), "freeze_sha256": freeze_hash, "review_events_sha256": "pending", "owner_signature_b64": "sig"})
            events = [{"event_id": f"{cid}-{n}", "clause_id": cid, "scope": "RANDOM50", "decision": "PASS", "reviewer_identity": "same", "reviewed_at": "fixture", "freeze_sha256": freeze_hash, "source_pdf_sha256": "pdf", "render_sha256": "png", "signature_b64": "sig"} for cid in ids[:48] for n in (1, 2)]
            events_path = base / "events.jsonl"
            events_path.write_text("".join(json.dumps(x) + "\n" for x in events), encoding="utf-8")
            approval = json.loads((base / "approval.json").read_text(encoding="utf-8")); approval["review_events_sha256"] = gate.sha(events_path); write_json(base / "approval.json", approval)
            (base / "owner.pem").write_text("fixture", encoding="utf-8")
            with patch.object(gate, "_verify_ed25519", return_value=True):
                result = gate.verified_review_summary(ids, changed, events_path, base / "identity.json", base / "owner.pem", base / "approval.json", gate.sha(base / "owner.pem"), freeze_hash)
            self.assertEqual(result["random_pass"], 0)
            self.assertEqual(result["verification_status"], "BLOCKED")

    def test_pdf_page_index_bounds_are_exclusive_at_page_count(self):
        self.assertTrue(gate.valid_page_index(0, 1))
        self.assertTrue(gate.valid_page_index(9, 10))
        self.assertFalse(gate.valid_page_index(-1, 10))
        self.assertFalse(gate.valid_page_index(10, 10))

    def test_preparation_rerun_does_not_touch_human_owned_csv(self):
        paths = [OUT / "P16_C_HUMAN50.csv", OUT / "P16_C_HUMAN_REVIEW90.csv"]
        before = [gate.sha(p) for p in paths]
        cp = subprocess.run([sys.executable, "-B", "-m", "scripts.p16_c_prepare_human50"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(cp.returncode, 0, cp.stderr)
        self.assertEqual([gate.sha(p) for p in paths], before)

    def test_real_gate_reports_fail_precedence_and_persists_separate_states(self):
        cp = subprocess.run([sys.executable, "-B", "-m", "scripts.p16_c_machine_gate"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(cp.returncode, 2, cp.stdout[-3000:] + cp.stderr[-1000:])
        result = json.loads((OUT / "P16_C_MACHINE_GATE.json").read_text(encoding="utf-8"))
        self.assertEqual(result["machine_integrity_status"], "BLOCKED")
        self.assertEqual(result["human_release_status"], "BLOCKED")
        self.assertEqual(result["status"], "BLOCKED_PENDING_HUMAN_REVIEW")
        self.assertFalse(result["release_merge_performed"])
        self.assertEqual(result["human_review_counts"]["random_pass"], 0)
        self.assertEqual(result["human_review_counts"]["changed_pass"], 0)


if __name__ == "__main__":
    unittest.main()
