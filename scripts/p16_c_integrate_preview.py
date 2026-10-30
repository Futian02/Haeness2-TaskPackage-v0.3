from __future__ import annotations

"""Create P16-C PREVIEW_ONLY staging workbooks and run original teacher gates.

No reviewer-pending A/B correction is applied. Inputs and teacher code are
read-only; all copies and generated files stay under work/data_staging/p16/merged.
"""

import csv
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MERGED = ROOT / "work/data_staging/p16/merged"
IN_RBI = ROOT / "work/data_staging/p15/merged/条款摘录表_RBI_P15_A_convert_eligible.xlsx"
IN_DM = ROOT / "work/data_staging/p15/merged/条款摘录表_损伤机理_P15_B_candidate.xlsx"
A_ROOT = ROOT / "work/data_staging/p16/A_CHANGED_42"
B_ROOT = ROOT / "work/data_staging/p16/B_REMAINDER"
UPSTREAM = ROOT / "upstream"
TEACHER = UPSTREAM / "04_接口文档"
TEACHER_SUBMIT = UPSTREAM / "05_提交区"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def csv_data(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def run(args: list[str], log: Path, cwd: Path = ROOT) -> subprocess.CompletedProcess:
    p = subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=False)
    log.write_text("$ " + " ".join(f'"{x}"' if " " in x else x for x in args) + "\n" + p.stdout + p.stderr, encoding="utf-8")
    return p


def check_inputs() -> dict:
    if not IN_RBI.is_file() or not IN_DM.is_file():
        raise SystemExit("P15 convert-eligible RBI and P15 B DM workbook inputs must be present")
    a = csv_data(A_ROOT / "P16_A_REVIEW42.csv")
    cells = csv_data(A_ROOT / "P16_A_CELL_AUDIT.csv")
    p_b = B_ROOT / "P16_B_CHANGE_PROPOSALS.jsonl"
    b_summary = json.loads((B_ROOT / "P16_B_RUN_SUMMARY.json").read_text(encoding="utf-8"))
    if len(a) != 42 or len({r["clause_id"] for r in a}) != 42 or len(cells) != 73:
        raise SystemExit(f"P16-A artifact integrity failed: review rows={len(a)}, cells={len(cells)}")
    if any((A_ROOT / r["card_path"]).is_file() is False for r in a):
        raise SystemExit("P16-A review card missing")
    if any(r.get("human_result", "").strip() or r.get("human_signature", "").strip() for r in a):
        raise SystemExit("P16-A unexpectedly contains human decisions/signatures; require Owner review before proceeding")
    proposals = [json.loads(line) for line in p_b.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(proposals) != 11 or b_summary.get("table_risk_rows_remaining") != 211 or b_summary.get("dm_total_cells") != 1312:
        raise SystemExit(f"P16-B artifact integrity failed: proposals={len(proposals)} summary={b_summary}")
    data_proposals = [p for p in proposals if p.get("proposal_type") == "source_fidelity_review_candidate"]
    retrieval_proposals = [p for p in proposals if p.get("proposal_type") == "isolated_application_retrieval_candidate"]
    return {"a_review_rows": len(a), "a_cell_audit_rows": len(cells), "b_proposals": len(proposals), "b_source_fidelity_proposals": len(data_proposals), "b_application_retrieval_proposals": len(retrieval_proposals), "b_remaining_table_rows": b_summary["table_risk_rows_remaining"], "b_dm_field_cells": b_summary["dm_total_cells"], "human_review_complete": False}


def main() -> int:
    MERGED.mkdir(parents=True, exist_ok=True)
    audit = check_inputs()
    rbi_out = MERGED / "P16_RELEASE_CANDIDATE_PREVIEW_RBI.xlsx"
    dm_out = MERGED / "P16_RELEASE_CANDIDATE_PREVIEW_DM.xlsx"
    jsonl_out = MERGED / "P16_CLAUSES_PREVIEW_ONLY.jsonl"
    shutil.copy2(IN_RBI, rbi_out)
    shutil.copy2(IN_DM, dm_out)

    official_rbi = UPSTREAM / "01_RBI标准/条款摘录表_RBI.xlsx"
    official_dm = UPSTREAM / "02_损伤机理参考/条款摘录表_损伤机理.xlsx"
    official_clauses = TEACHER_SUBMIT / "clauses.jsonl"
    official_trajectories = TEACHER_SUBMIT / "trajectories.jsonl"
    pre_hashes = {str(p.relative_to(ROOT)): sha(p) for p in (official_rbi, official_dm, official_clauses)}

    convert = run([sys.executable, "-B", str(TEACHER / "convert.py"), "--inputs", str(rbi_out), str(dm_out), "--output", str(jsonl_out)], MERGED / "P16_C_CONVERT_PREVIEW.log")
    if convert.returncode != 0:
        (MERGED / "P16_C_INTEGRATION_STATUS.json").write_text(json.dumps({"status": "BLOCKED_CONVERT_FAILED", "returncode": convert.returncode, "input_audit": audit}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(convert.stdout, convert.stderr)
        return convert.returncode or 1

    validate = run([sys.executable, "-B", str(TEACHER / "validate.py"), "--final", "--clauses", str(jsonl_out), "--trajectories", str(official_trajectories)], MERGED / "P16_C_VALIDATE_FINAL_PREVIEW.log")
    # Compare canonical JSON records by ID/field against the frozen official JSONL.
    def load_jsonl(p: Path) -> dict[str, dict]:
        with p.open("r", encoding="utf-8") as f:
            return {r["clause_id"]: r for r in (json.loads(line) for line in f if line.strip())}
    old, new = load_jsonl(official_clauses), load_jsonl(jsonl_out)
    added, removed = sorted(new.keys() - old.keys()), sorted(old.keys() - new.keys())
    diff_rows = []
    field_count = 0
    for cid in sorted(old.keys() & new.keys()):
        for field in sorted(old[cid].keys() | new[cid].keys()):
            if old[cid].get(field) != new[cid].get(field):
                field_count += 1
                diff_rows.append({"clause_id": cid, "field": field, "old_value": json.dumps(old[cid].get(field), ensure_ascii=False), "preview_value": json.dumps(new[cid].get(field), ensure_ascii=False), "human_review": "PENDING"})
    with (MERGED / "P16_C_PREVIEW_JSONL_DIFF.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["clause_id", "field", "old_value", "preview_value", "human_review"]); w.writeheader(); w.writerows(diff_rows)

    # Isolated copy of the original teacher tools and supporting schemas.
    probe = MERGED / "candidate_tool_probe"
    p4 = probe / "04_接口文档"
    p5 = probe / "05_提交区"
    p4.mkdir(parents=True, exist_ok=True); p5.mkdir(parents=True, exist_ok=True)
    for rel in [Path("enums.json"), Path("material_family.json"), Path("risk_level_mapping.xlsx"), Path("schema/tool_response.schema.json")]:
        dest = p4 / rel; dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(TEACHER / rel, dest)
    for name in ["tools.py", "_df_rules.py", "_selftest_tools.py"]:
        shutil.copy2(TEACHER_SUBMIT / name, p5 / name)
    shutil.copy2(jsonl_out, p5 / "clauses.jsonl")
    tool_test = run([sys.executable, "-B", str(p5 / "_selftest_tools.py")], MERGED / "P16_C_TEACHER_TOOL_SELFTEST.log")

    post_hashes = {str(p.relative_to(ROOT)): sha(p) for p in (official_rbi, official_dm, official_clauses)}
    status = "BLOCKED_PENDING_HUMAN_REVIEW"
    result = {
        "status": status, "candidate_type": "PREVIEW_ONLY_NOT_RELEASE", "input_audit": audit,
        "preview_workbooks": {"rbi": {"path": str(rbi_out.relative_to(ROOT)), "sha256": sha(rbi_out)}, "dm": {"path": str(dm_out.relative_to(ROOT)), "sha256": sha(dm_out)}},
        "preview_jsonl": {"path": str(jsonl_out.relative_to(ROOT)), "sha256": sha(jsonl_out), "count": len(new)},
        "jsonl_diff_vs_official": {"added": len(added), "removed": len(removed), "modified_clause_ids": len({r["clause_id"] for r in diff_rows}), "changed_fields": field_count, "added_ids": added, "removed_ids": removed},
        "convert_exit_code": convert.returncode, "validate_final_exit_code": validate.returncode, "teacher_tool_selftest_exit_code": tool_test.returncode,
        "teacher_tool_selftest_pass_expected_count": 17,
        "official_hashes_before": pre_hashes, "official_hashes_after": post_hashes,
        "official_hashes_unchanged": pre_hashes == post_hashes,
        "reviewer_signatures": 0, "release_marker": False,
        "p16_a_review_status_counts": {s: sum(1 for r in csv_data(A_ROOT / "P16_A_REVIEW42.csv") if r["review_status"] == s) for s in sorted({r["review_status"] for r in csv_data(A_ROOT / "P16_A_REVIEW42.csv")})},
        "p16_b_retrieval_integration": "NOT_APPLIED_APPLICATION_ONLY_PROPOSALS",
    }
    (MERGED / "P16_C_INTEGRATION_STATUS.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if validate.returncode != 0 or tool_test.returncode != 0 or pre_hashes != post_hashes:
        return 1
    return 2  # expected pending-real-human gate


if __name__ == "__main__":
    raise SystemExit(main())
