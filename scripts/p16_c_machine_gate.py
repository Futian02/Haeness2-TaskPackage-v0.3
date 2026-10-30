from __future__ import annotations

"""P16-C integrity and human-release gate. Human claims require signed trust evidence."""

import csv
import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "work/data_staging/p16/C_GATE"
P16_MERGED = ROOT / "work/data_staging/p16/merged"
P16_A = ROOT / "work/data_staging/p16/A_CHANGED_42"
P16_B = ROOT / "work/data_staging/p16/B_REMAINDER"
SOURCE_EXCEL = ROOT / "upstream/01_RBI标准/条款摘录表_RBI.xlsx"
SOURCE_JSONL = ROOT / "upstream/05_提交区/clauses.jsonl"
SAMPLE = OUT / "P16_C_HUMAN50.csv"
P15_SAMPLE = ROOT / "work/data_staging/p15/C_QA/P15_C_HUMAN_REVIEW50.csv"
LOCATORS = OUT / "P16_C_HUMAN50_PAGE_LOCATORS.csv"
REGISTER = OUT / "P16_C_HUMAN_REVIEW90.csv"  # legacy display sheet; never authoritative for signed review
MANIFEST = OUT / "P16_C_PREP_MANIFEST.json"
FREEZE = OUT / "P16_C_SAMPLE_FREEZE_V4.json"
EVENTS = OUT / "P16_C_HUMAN_REVIEW_EVENTS.jsonl"
IDENTITIES = OUT / "P16_C_REVIEWER_IDENTITY_REGISTRY.json"
OWNER_APPROVAL = OUT / "P16_C_OWNER_RELEASE_APPROVAL.json"
OWNER_TRUST = OUT / "P16_C_OWNER_TRUSTED_PUBLIC_KEY.pem"
EXPECTED_RBI_SHA256 = "e43f7b0d3381a38fa648c2505e27d1c87893af5aea89aa119097dbfc49c6b7bf"
EXPECTED_OFFICIAL_JSONL_SHA256 = "a8151797ba15a6a7452dd83aaec9fab4c0a815724ca45062eb1e2bac7b4d49ef"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def record(name: str, status: str, expected: str, actual: str, detail: str) -> dict[str, str]:
    return {"gate": name, "status": status, "expected": expected, "actual": actual, "detail": detail}


def exact_sample_check(source_rows: list[dict[str, str]], sample_rows: list[dict[str, str]], seed: int = 20261029) -> tuple[bool, str]:
    """Check exact ordered IDs and seed, not just cardinality/seed metadata."""
    source_ids = [r.get("clause_id", "") for r in source_rows]
    sample_ids = [r.get("clause_id", "") for r in sample_rows]
    source_seeds = {r.get("seed", "") for r in source_rows}
    sample_seeds = {r.get("seed", "") for r in sample_rows}
    ok = (len(source_rows) == 50 and len(set(source_ids)) == 50 and
          len(sample_rows) == 50 and sample_ids == source_ids and
          source_seeds == {str(seed)} and sample_seeds == {str(seed)})
    if not ok:
        first_diff = next((i for i, (a, b) in enumerate(zip(source_ids, sample_ids), 1) if a != b), None)
        return False, f"source={len(source_rows)} rows/{len(source_ids)} unique; sample={len(sample_rows)} rows; first_order_mismatch={first_diff}; source_seed={sorted(source_seeds)} sample_seed={sorted(sample_seeds)}"
    return True, f"exact ordered 50 IDs match frozen P15 list; seed={seed}"


def machine_status(checks: list[dict[str, Any]]) -> str:
    """Integrity failures always dominate pending-human blockers."""
    states = {str(x.get("status", "")) for x in checks}
    if "FAIL" in states:
        return "FAIL"
    if "BLOCKED" in states:
        return "BLOCKED"
    return "PASS"


def combined_status(machine_integrity_status: str, human_release_status: str) -> str:
    if "FAIL" in {machine_integrity_status, human_release_status}:
        return "FAIL"
    if machine_integrity_status != "PASS" or human_release_status != "PASS":
        return "BLOCKED_PENDING_HUMAN_REVIEW"
    return "PASS"


def human_threshold_status(random_pass: int, random_total: int, changed_pass: int, changed_total: int,
                           identity_verified: bool, owner_approved: bool, conflicts: int = 0) -> str:
    """Release eligibility from *verified* review counts; no text-field shortcuts."""
    if random_pass < 0 or changed_pass < 0 or random_total != 50 or changed_total != 42:
        return "FAIL"
    if random_pass > random_total or changed_pass > changed_total:
        return "FAIL"
    if conflicts:
        return "BLOCKED"
    if random_pass < 48 or changed_pass != 42:
        return "BLOCKED"
    if not identity_verified or not owner_approved:
        return "BLOCKED"
    return "PASS"


def valid_page_index(index: int, page_count: int) -> bool:
    return 0 <= index < page_count


def _verify_ed25519(public_key_pem: bytes, message: bytes, signature_b64: str) -> bool:
    try:
        import base64
        from cryptography.hazmat.primitives.serialization import load_pem_public_key
        key = load_pem_public_key(public_key_pem)
        key.verify(base64.b64decode(signature_b64, validate=True), message)
        return True
    except Exception:
        return False


def _canonical_event(event: dict[str, Any]) -> bytes:
    payload = {k: v for k, v in event.items() if k != "signature_b64"}
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def verified_review_summary(expected_random_ids: list[str], expected_changed_ids: list[str],
                            events_path: Path, identities_path: Path, owner_trust_path: Path,
                            owner_approval_path: Path, expected_owner_key_sha256: str | None = None,
                            expected_freeze_sha256: str | None = None,
                            expected_evidence: dict[str, dict[str, str]] | None = None) -> dict[str, Any]:
    """Verify detached signatures against Owner-pinned identity registry and count distinct accepted objects.

    Missing crypto/trust material is BLOCKED, never inferred from nonempty signature strings.
    """
    result: dict[str, Any] = {"random_pass": 0, "random_total": len(expected_random_ids),
                              "changed_pass": 0, "changed_total": len(expected_changed_ids),
                              "verified_reviewers": [], "conflicts": 0,
                              "identity_verified": False, "owner_approved": False,
                              "verification_status": "BLOCKED", "reason": "trust material missing"}
    if not all(p.is_file() for p in (events_path, identities_path, owner_trust_path, owner_approval_path)):
        return result
    try:
        if not expected_owner_key_sha256 or sha(owner_trust_path) != expected_owner_key_sha256:
            return {**result, "verification_status": "BLOCKED", "reason": "Owner public-key fingerprint is not pinned out-of-band"}
        registry_doc = json.loads(identities_path.read_text(encoding="utf-8"))
        registry_signature = registry_doc.pop("owner_signature_b64")
        owner_pub = owner_trust_path.read_bytes()
        registry_bytes = json.dumps(registry_doc, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        if not _verify_ed25519(owner_pub, registry_bytes, registry_signature):
            return {**result, "verification_status": "FAIL", "reason": "reviewer registry Owner signature invalid"}
        reviewers = registry_doc.get("reviewers", {})
        accepted: dict[tuple[str, str], list[tuple[str, str]]] = {}
        verified_names: set[str] = set()
        for line in events_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            event = json.loads(line)
            required = ("event_id", "clause_id", "scope", "decision", "reviewer_identity", "reviewed_at",
                        "freeze_sha256", "source_pdf_sha256", "render_sha256", "signature_b64")
            if any(not event.get(k) for k in required):
                return {**result, "verification_status": "FAIL", "reason": "review event missing required signed evidence fields"}
            if expected_freeze_sha256 and event["freeze_sha256"] != expected_freeze_sha256:
                return {**result, "verification_status": "FAIL", "reason": "review event is bound to a different frozen sample"}
            expected_item = (expected_evidence or {}).get((event.get("clause_id", ""), event.get("scope", "")), (expected_evidence or {}).get(event.get("clause_id", "")))
            if expected_item and (event.get("source_pdf_sha256") != expected_item.get("source_pdf_sha256") or
                                  event.get("render_sha256") != expected_item.get("render_sha256")):
                return {**result, "verification_status": "FAIL", "reason": f"review evidence hash mismatch for {event.get('clause_id')}"}
            identity = event.get("reviewer_identity", "")
            reviewer = reviewers.get(identity)
            if not reviewer or not event.get("signature_b64"):
                continue
            pub = reviewer.get("public_key_pem", "").encode()
            if not _verify_ed25519(pub, _canonical_event(event), event["signature_b64"]):
                return {**result, "verification_status": "FAIL", "reason": f"invalid reviewer signature for {event.get('event_id', 'unknown')}"}
            verified_names.add(identity)
            cid, decision = event.get("clause_id", ""), event.get("decision", "")
            accepted.setdefault((cid, str(event.get("scope", ""))), []).append((identity, decision))
        conflicts = sum(1 for vals in accepted.values() if len({decision for _, decision in vals}) > 1)
        independently_reviewed = lambda vals: len({identity for identity, _ in vals}) >= 2 and len({decision for _, decision in vals}) == 1
        random_ok = {cid for (cid, scope), vals in accepted.items() if scope == "RANDOM50" and independently_reviewed(vals) and vals[-1][1] == "PASS"}
        changed_ok = {cid for (cid, scope), vals in accepted.items() if scope == "CHANGED42" and independently_reviewed(vals) and vals[-1][1] in {"PASS", "CORRECTED_AND_REVIEWED"}}
        random_n = len(set(expected_random_ids) & random_ok)
        changed_n = len(set(expected_changed_ids) & changed_ok)
        approval = json.loads(owner_approval_path.read_text(encoding="utf-8"))
        approval_sig = approval.pop("owner_signature_b64")
        approval_msg = json.dumps(approval, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        owner_ok = _verify_ed25519(owner_pub, approval_msg, approval_sig)
        if owner_ok and (approval.get("sample_ids_sha256") != hashlib.sha256("\n".join(expected_random_ids).encode()).hexdigest() or
                         approval.get("changed_ids_sha256") != hashlib.sha256("\n".join(expected_changed_ids).encode()).hexdigest() or
                         approval.get("review_events_sha256") != sha(events_path) or
                         (expected_freeze_sha256 and approval.get("freeze_sha256") != expected_freeze_sha256)):
            owner_ok = False
        state = "FAIL" if conflicts else "PASS" if random_n >= 48 and changed_n == 42 and verified_names and owner_ok else "BLOCKED"
        return {"random_pass": random_n, "random_total": 50, "changed_pass": changed_n, "changed_total": 42,
                "verified_reviewers": sorted(verified_names), "conflicts": conflicts,
                "verified_review_event_count": sum(len(v) for v in accepted.values()),
                "identity_verified": bool(verified_names), "owner_approved": owner_ok,
                "verification_status": state, "reason": "cryptographic event and Owner approval verification"}
    except Exception as exc:
        return {**result, "verification_status": "FAIL", "reason": f"malformed trust/review record: {type(exc).__name__}: {exc}"}


def pdf_page_count(pdf: Path) -> int | None:
    """Use PyMuPDF when installed; fallback to pdfinfo. Returns None on unreadable input."""
    try:
        import fitz
        with fitz.open(pdf) as doc:
            return len(doc)
    except ImportError:
        pass
    try:
        proc = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True, check=False)
        if proc.returncode == 0:
            import re
            match = re.search(r"^Pages:\s+(\d+)\s*$", proc.stdout, re.MULTILINE)
            if match:
                return int(match.group(1))
    except OSError:
        pass
    return None


def main() -> int:
    sample_path = OUT / "P16_C_MACHINE_SAMPLE_INDEX.csv"
    locator_path = OUT / "P16_C_MACHINE_PAGE_LOCATORS.csv"
    sample, p15 = rows(sample_path if sample_path.is_file() else SAMPLE), rows(P15_SAMPLE)
    locators, register = rows(locator_path if locator_path.is_file() else LOCATORS), rows(REGISTER)
    manifest_path = FREEZE if FREEZE.is_file() else MANIFEST
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    checks: list[dict[str, Any]] = []
    exact_ok, exact_detail = exact_sample_check(p15, sample)
    source_hash = sha(P15_SAMPLE)
    sample_hash = sha(sample_path if sample_path.is_file() else SAMPLE)
    checks.append(record("fixed_seed_sample_exact_order", "PASS" if exact_ok else "FAIL",
                         "exact 50 ordered clause_ids equal P15-C frozen list; seed=20261029",
                         f"source_sha256={source_hash}; sample_sha256={sample_hash}; {exact_detail}",
                         "ID order is compared row-by-row; same count/seed cannot mask a replacement ID."))
    locator_hash = sha(locator_path) if locator_path.is_file() else ""
    official_jsonl_hash = sha(SOURCE_JSONL)
    candidate_hash = sha(ROOT / "work/data_staging/p15/merged/clauses_candidate.jsonl")
    checks.append(record("source_manifest_binding", "PASS" if manifest.get("p15_sample_sha256") == source_hash and manifest.get("sample_ids_sha256") == hashlib.sha256("\n".join(r["clause_id"] for r in p15).encode()).hexdigest() and manifest.get("sample_export_sha256") == sample_hash and manifest.get("p15_candidate_jsonl_sha256") == candidate_hash and manifest.get("official_jsonl_sha256") == official_jsonl_hash and manifest.get("locator_manifest_sha256") == locator_hash else "FAIL",
                         "manifest binds P15 bytes, exported sample, ordered IDs and page locator manifest", f"source={source_hash}; sample={sample_hash}; locators={locator_hash}",
                         "Legacy manifest without the new hash fields fails closed; immutable freeze record is maintained separately."))
    official_matches = sha(SOURCE_EXCEL) == EXPECTED_RBI_SHA256 and official_jsonl_hash == EXPECTED_OFFICIAL_JSONL_SHA256
    checks.append(record("official_input_hash_guard", "PASS" if official_matches else "FAIL", f"RBI={EXPECTED_RBI_SHA256}; clauses={EXPECTED_OFFICIAL_JSONL_SHA256}", f"RBI={sha(SOURCE_EXCEL)}; clauses={official_jsonl_hash}", "Hash guard detects deviation from the recorded P16-C baseline; it does not write upstream."))
    checks.append(record("unique_review_union", "PASS" if len(register) == 90 and len({r["clause_id"] for r in register}) == 90 else "FAIL", "90 distinct clause_ids", f"{len(register)} rows / {len({r['clause_id'] for r in register})} unique", "50 random + 42 changed - 2 overlap."))
    checks.append(record("changed_cell_linkage", "PASS" if manifest.get("changed_unique_clause_ids") == 42 and manifest.get("changed_cells") == 73 else "FAIL", "42 clause IDs; 73 Excel cells", f"{manifest.get('changed_unique_clause_ids')} IDs; {manifest.get('changed_cells')} cells", "Read-only P15 merged DIFF_LEDGER.csv."))
    checked_images, invalid_images = 0, []
    for loc in locators:
        img = OUT / loc["render_path"] if loc.get("render_path") else None
        src = (ROOT / loc["source_pdf"]).resolve()
        try:
            idx = int(loc["pdf_page_index"])
        except (ValueError, TypeError):
            idx = -1
        count = pdf_page_count(src) if src.is_file() else None
        if not img or not img.is_file() or not src.is_file() or sha(src) != loc.get("pdf_sha256") or count is None or not valid_page_index(idx, count) or sha(img) != loc.get("render_sha256"):
            invalid_images.append(loc.get("clause_id", ""))
        else:
            checked_images += 1
    checks.append(record("original_pdf_page_images", "PASS" if checked_images == 50 and not invalid_images else "FAIL", "50 images; source SHA and 0 <= index < actual PDF page_count", f"{checked_images} verified; invalid={len(invalid_images)}", "Rendered image presence is only integrity evidence, not visual correctness."))
    a_page_rows = rows(P16_A / "P16_A_PAGE_INVENTORY.csv") if (P16_A / "P16_A_PAGE_INVENTORY.csv").is_file() else []
    a_invalid = []
    frozen_a = {r.get("clause_id"): r for r in manifest.get("changed42_evidence", [])}
    for item in a_page_rows:
        src = (ROOT / item.get("src", "")).resolve()
        count = pdf_page_count(src) if src.is_file() else None
        frozen_item = frozen_a.get(item.get("clause_id", ""), {})
        indices = [x.strip() for x in item.get("indices", "").split(";") if x.strip()]
        images = [x.strip() for x in item.get("images", "").split(";") if x.strip()]
        frozen_pages = frozen_item.get("pages", [])
        page_ok = len(indices) > 0 and len(indices) == len(images) == len(frozen_pages)
        for index_text, image_name, frozen_page in zip(indices, images, frozen_pages):
            try:
                index = int(index_text)
            except ValueError:
                index = -1
            image = P16_A / "pages" / image_name
            page_ok = page_ok and image.is_file() and count is not None and valid_page_index(index, count)
            page_ok = page_ok and frozen_page.get("pdf_page_index") == index_text and frozen_page.get("image_name") == image_name
            page_ok = page_ok and bool(frozen_page.get("image_sha256")) and sha(image) == frozen_page.get("image_sha256")
        if (not item.get("clause_id") or not src.is_file() or count is None or not page_ok or sha(src) != item.get("hash") or
                frozen_item.get("pdf_sha256") != sha(src)):
            a_invalid.append(item.get("clause_id", ""))
    a_evidence_bytes = json.dumps(manifest.get("changed42_evidence", []), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    a_freeze_ok = manifest.get("p16_a_inventory_sha256") == (sha(P16_A / "P16_A_PAGE_INVENTORY.csv") if (P16_A / "P16_A_PAGE_INVENTORY.csv").is_file() else "") and manifest.get("changed42_evidence_sha256") == hashlib.sha256(a_evidence_bytes).hexdigest()
    checks.append(record("changed42_page_evidence", "PASS" if a_freeze_ok and len(a_page_rows) == 42 and len({r.get('clause_id') for r in a_page_rows}) == 42 and not a_invalid else "FAIL",
                         "42 unique A records have valid source PDF/page bounds and image hash", f"inventory={len(a_page_rows)}/{len({r.get('clause_id') for r in a_page_rows})}; invalid={len(a_invalid)}",
                         "A images are checked read-only; this verifies locator integrity, not human visual correctness."))
    # Existing CSVs are human-owned. We neither interpret their text fields as verified identities nor write them.
    legacy_filled = sum(1 for r in register if any(r.get(k, "").strip() for k in ("reviewer_identity", "reviewer_2_identity", "signature_1", "signature_2", "review_timestamp", "decision")))
    checks.append(record("machine_did_not_autosign", "PASS" if manifest.get("human_signed", 0) == 0 else "FAIL", "machine preparation does not author human review fields", f"legacy human-field rows={legacy_filled}; manifest human_signed={manifest.get('human_signed')}", "Nonempty fields in legacy sheet are not accepted as identity proof; preparation scripts do not edit it."))
    p15_ids = [r["clause_id"] for r in p15]
    cells = rows(ROOT / "work/data_staging/p15/merged/DIFF_LEDGER.csv")
    changed_ids = sorted({r["clause_id"] for r in cells})
    expected_evidence: dict[Any, dict[str, str]] = {}
    for item in locators:
        if item.get("clause_id"):
            expected_evidence[(item["clause_id"], "RANDOM50")] = {"source_pdf_sha256": item.get("pdf_sha256", ""), "render_sha256": item.get("render_sha256", "")}
    if a_page_rows:
        for item in a_page_rows:
            source = (ROOT / item.get("src", "")).resolve()
            frozen_item = frozen_a.get(item.get("clause_id", ""), {})
            expected_evidence[(item.get("clause_id", ""), "CHANGED42")] = {
                "source_pdf_sha256": sha(source) if source.is_file() else "",
                "render_sha256": hashlib.sha256(json.dumps(frozen_item.get("pages", []), sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
            }
    freeze_sha = sha(FREEZE) if FREEZE.is_file() else ""
    human = verified_review_summary(p15_ids, changed_ids, EVENTS, IDENTITIES, OWNER_TRUST, OWNER_APPROVAL,
                                    os.environ.get("P16_OWNER_TRUSTED_PUBKEY_SHA256"), freeze_sha, expected_evidence)
    human_state = human_threshold_status(human["random_pass"], human["random_total"], human["changed_pass"], human["changed_total"], human["identity_verified"], human["owner_approved"], human["conflicts"])
    if human.get("verification_status") == "FAIL":
        human_state = "FAIL"
    checks.append(record("human_release_gate", human_state, ">=48/50 verified random PASS, 42/42 changed scope resolved, identity cryptographically verified, Owner approval signed", f"random={human['random_pass']}/{human['random_total']}; changed={human['changed_pass']}/{human['changed_total']}; reviewers={len(human['verified_reviewers'])}; Owner={human['owner_approved']}; reason={human['reason']}", "Human and Owner status are independent of machine integrity status."))
    p16_candidates = [P16_MERGED / "P16_RELEASE_CANDIDATE_PREVIEW_RBI.xlsx", P16_MERGED / "P16_RELEASE_CANDIDATE_PREVIEW_DM.xlsx", P16_MERGED / "P16_CLAUSES_PREVIEW_ONLY.jsonl"]
    integration = json.loads((P16_MERGED / "P16_C_INTEGRATION_STATUS.json").read_text(encoding="utf-8")) if (P16_MERGED / "P16_C_INTEGRATION_STATUS.json").is_file() else {}
    ready = all(p.exists() for p in p16_candidates) and integration.get("candidate_type") == "PREVIEW_ONLY_NOT_RELEASE"
    checks.append(record("p16_ab_candidate_integration", "PASS" if ready else "BLOCKED", "A/B preview candidates integrated only in isolated staging", "; ".join(f"{p.name}={'present' if p.exists() else 'absent'}" for p in p16_candidates), "No unreviewed proposal promoted into release."))
    a_reviews = rows(P16_A / "P16_A_REVIEW42.csv") if (P16_A / "P16_A_REVIEW42.csv").is_file() else []
    a_cells = rows(P16_A / "P16_A_CELL_AUDIT.csv") if (P16_A / "P16_A_CELL_AUDIT.csv").is_file() else []
    b_summary = json.loads((P16_B / "P16_B_RUN_SUMMARY.json").read_text(encoding="utf-8")) if (P16_B / "P16_B_RUN_SUMMARY.json").is_file() else {}
    linked = len(a_reviews) == 42 and len({r["clause_id"] for r in a_reviews}) == 42 and len(a_cells) == 73 and b_summary.get("table_risk_rows_remaining") == 211 and b_summary.get("dm_total_cells") == 1312 and b_summary.get("supplement_56_pending_chapters") == 56
    checks.append(record("p16_ab_independent_artifact_linkage", "PASS" if linked else "BLOCKED", "A:42 records/73 cells; B:211 risk rows/1312 fields/56 chapters", f"A={len(a_reviews)} records/{len(a_cells)} cells; B={b_summary.get('table_risk_rows_remaining')} risk rows/{b_summary.get('dm_total_cells')} fields/{b_summary.get('supplement_56_pending_chapters')} chapters", "A/B remain their owners' immutable deliverables."))
    contradictions = [r["clause_id"] for r in a_reviews if r.get("machine_conclusion") == "CONTRADICTS"]
    checks.append(record("unresolved_source_locator_contradictions", "BLOCKED" if contradictions else "PASS", "0 unresolved source-page contradictions", f"{len(contradictions)}: {', '.join(contradictions)}", "TSG locator contradiction remains pending independent human/Owner review."))
    machine = machine_status(checks)
    human_release = "PASS" if human_state == "PASS" else ("FAIL" if human_state == "FAIL" else "BLOCKED")
    status = combined_status(machine, human_release)
    result = {"status": status, "machine_integrity_status": machine, "human_release_status": human_release,
              "checks": checks, "human_review_counts": human, "invalid_image_clause_ids": invalid_images,
              "official_rbi_xlsx_sha256_read_only_snapshot": sha(SOURCE_EXCEL),
              "official_clauses_jsonl_sha256_read_only_snapshot": sha(SOURCE_JSONL),
              "candidate_preview_merge_performed": ready, "release_merge_performed": False,
              "human_review_signed": human.get("verified_review_event_count", 0),
              "official_files_modified": not official_matches}
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "P16_C_MACHINE_GATE.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(checks[0])); w.writeheader(); w.writerows(checks)
    (OUT / "P16_C_MACHINE_GATE.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if status == "FAIL" else (2 if status.startswith("BLOCKED") else 0)


if __name__ == "__main__":
    raise SystemExit(main())
