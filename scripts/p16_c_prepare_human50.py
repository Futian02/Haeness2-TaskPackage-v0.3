from __future__ import annotations

"""Build P16-C's fixed-seed human review package without editing official inputs.

All writes are confined to work/data_staging/p16/C_GATE. Page locators are
machine candidates from the pre-existing P14 native-page inventory; a human
must still compare each rendered original PDF page with the clause.
"""

import csv
import hashlib
import html
import json
import re
import subprocess
import unicodedata
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "work/data_staging/p16/C_GATE"
SAMPLE = ROOT / "work/data_staging/p15/C_QA/P15_C_HUMAN_REVIEW50.csv"
DIFF = ROOT / "work/data_staging/p15/merged/P15_C_CANDIDATE_JSONL_DIFF.csv"
CELL_LEDGER = ROOT / "work/data_staging/p15/merged/DIFF_LEDGER.csv"
A_REVIEW = ROOT / "work/data_staging/p16/A_CHANGED_42/P16_A_REVIEW42.csv"
P16_A = ROOT / "work/data_staging/p16/A_CHANGED_42"
CANDIDATE = ROOT / "work/data_staging/p15/merged/clauses_candidate.jsonl"
NATIVE = ROOT / "work/data_staging/p14/page_cache/native_pages.jsonl"
IMAGE_DIR = OUT / "pdf_pages"
CARD_DIR = OUT / "cards"
FREEZE = OUT / "P16_C_SAMPLE_FREEZE_V4.json"
MACHINE_SAMPLE_INDEX = OUT / "P16_C_MACHINE_SAMPLE_INDEX.csv"
MACHINE_SCOPE_INDEX = OUT / "P16_C_MACHINE_REVIEW_SCOPE90.csv"
SEED = 20261029


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def clause_token_present(text: str, clause_no: str) -> bool:
    token = unicodedata.normalize("NFKC", str(clause_no or "")).strip()
    if not token:
        return False
    # Avoid matching 5.1 inside 5.10; native text often carries fullwidth digits.
    return re.search(rf"(?<![\d.]){re.escape(token)}(?![\d.])", unicodedata.normalize("NFKC", text)) is not None


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_candidate() -> dict[str, dict]:
    result = {}
    with CANDIDATE.open("r", encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            result[row["clause_id"]] = row
    return result


def load_native_pages() -> dict[str, list[dict]]:
    pages: dict[str, list[dict]] = defaultdict(list)
    with NATIVE.open("r", encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            pages[row["source_pdf"].replace("\\", "/")].append(row)
    return pages


def source_path(source_pdf: str) -> Path:
    p = (ROOT / source_pdf).resolve()
    if not p.is_file() or not p.is_relative_to(ROOT / "upstream"):
        raise ValueError(f"PDF source must resolve inside upstream: {source_pdf}")
    return p


def locate(row: dict[str, str], pages: list[dict]) -> tuple[int | None, str, str]:
    clause = row.get("clause_no", "")
    token_matches = [p for p in pages if clause_token_present(p.get("text", ""), clause)]
    wanted = str(row.get("printed_page", "")).strip()
    # First use an explicit footer page label when the native page record retains
    # it. This is especially useful for TSG pages with duplicated TOC mentions.
    footer_matches = []
    if wanted:
        for p in pages:
            tail = "\n".join(unicodedata.normalize("NFKC", p.get("text", "")).splitlines()[-10:])
            if re.search(rf"[—–-]\s*{re.escape(wanted)}\s*[—–-]", tail):
                footer_matches.append(p)
    token_footer = [p for p in token_matches if p in footer_matches]
    if len(token_footer) == 1:
        p = token_footer[0]
        return int(p["pdf_page_index"]), "MACHINE_CLAUSE_TOKEN_AND_EXPLICIT_FOOTER", wanted
    if len(footer_matches) == 1:
        p = footer_matches[0]
        return int(p["pdf_page_index"]), "MACHINE_EXPLICIT_FOOTER_UNIQUE", wanted
    if len(token_matches) == 1:
        p = token_matches[0]
        return int(p["pdf_page_index"]), "MACHINE_CLAUSE_TOKEN_UNIQUE", str(p.get("printed_page_guess") or "")
    # Printed page is an independent page label; use it only if inventory has a
    # unique exact match (never apply a guessed constant offset).
    page_matches = [p for p in pages if str(p.get("printed_page_guess") or "").strip() == wanted and wanted]
    if len(page_matches) == 1:
        p = page_matches[0]
        return int(p["pdf_page_index"]), "MACHINE_PRINTED_PAGE_UNIQUE", str(p.get("printed_page_guess") or "")
    if len(token_matches) > 1:
        return None, "AMBIGUOUS_CLAUSE_TOKEN", ""
    if len(page_matches) > 1:
        # If the clause token narrows the set, use that intersection.
        intersection = [p for p in page_matches if clause_token_present(p.get("text", ""), clause)]
        if len(intersection) == 1:
            p = intersection[0]
            return int(p["pdf_page_index"]), "MACHINE_TOKEN_AND_PRINTED_PAGE", str(p.get("printed_page_guess") or "")
        return None, "AMBIGUOUS_PRINTED_PAGE", ""
    return None, "UNRESOLVED_NO_VERIFIED_PAGE_MAP", ""


def offsets_from_native(pages_by_source: dict[str, list[dict]]) -> dict[str, int]:
    offsets: dict[str, int] = {}
    for source, pages in pages_by_source.items():
        deltas = [int(p["pdf_page_index"]) - int(p["printed_page_guess"])
                  for p in pages if isinstance(p.get("printed_page_guess"), int)]
        if len(deltas) >= 3 and len(set(deltas)) == 1:
            offsets[source] = deltas[0]
    # P14 pilot OCR filenames record independently paired physical/printed
    # locators for GB/T 30579; require a consistent multi-page offset.
    pilot_dir = ROOT / "work/data_staging/p14/agents/A/page_cache"
    pilot = []
    for p in pilot_dir.glob("GBT30579-2022_pdfindex_*_printed_*_pilot_ocr.txt"):
        m = re.search(r"pdfindex_(\d+)_printed_(\d+)", p.name)
        if m:
            pilot.append(int(m.group(1)) - int(m.group(2)))
    if len(pilot) >= 3 and len(set(pilot)) == 1:
        offsets["02_损伤机理参考/GBT30579-2022_承压设备损伤模式识别.pdf"] = pilot[0]
    return offsets


def render_page(pdf: Path, page_index: int) -> Path:
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"{sha256(pdf)[:12]}_page_{page_index:04d}"
    target = IMAGE_DIR / f"{stem}.png"
    if not target.exists():
        exe = "pdftoppm"
        proc = subprocess.run(
            [exe, "-f", str(page_index + 1), "-l", str(page_index + 1), "-singlefile", "-png", "-r", "120", str(pdf), str(IMAGE_DIR / stem)],
            capture_output=True, text=True, check=False,
        )
        if proc.returncode != 0 or not target.exists():
            raise RuntimeError(f"pdftoppm failed for {pdf.name} page {page_index}: {proc.stderr[-1000:]}")
    return target


def write_card(row: dict[str, str], record: dict | None, locator: dict, img_rel: str | None, index: int) -> None:
    CARD_DIR.mkdir(parents=True, exist_ok=True)
    card = CARD_DIR / f"{index:02d}_{re.sub(r'[^A-Za-z0-9_.-]', '_', row['clause_id'])}.html"
    rec = record or {}
    fields = {
        "clause_id": row.get("clause_id"), "standard_code": row.get("standard_code"),
        "clause_no": row.get("clause_no"), "title": row.get("title"),
        "printed_page": row.get("printed_page"), "pdf_page_index_zero_based": locator.get("pdf_page_index"),
        "locator_status": locator.get("locator_status"), "locator_basis": locator.get("locator_basis"),
        "content_raw_F": rec.get("content_raw", row.get("evidence_quote", "")),
        "applicable_conditions": rec.get("applicable_conditions", row.get("conditions_to_verify", "")),
        "source_pdf": row.get("source_pdf"), "source_pdf_sha256": locator.get("pdf_sha256"),
        "review_status": "PENDING_REAL_HUMAN_REVIEW", "reviewer_identity": "", "reviewer_signature": "",
        "reviewed_at": "", "decision": "", "correction_note": "",
    }
    data = html.escape(json.dumps(fields, ensure_ascii=False, indent=2))
    image_html = f'<img src="../{html.escape(img_rel)}" alt="Original PDF page, not OCR" />' if img_rel else '<div class="missing">原始页图尚未定位：不可审签，先由人核定物理页索引。</div>'
    page_html = f"<p>印刷页：{html.escape(str(row.get('printed_page') or ''))} ｜ PDF 物理页（0-based）：{html.escape(str(locator.get('pdf_page_index') if locator.get('pdf_page_index') is not None else '未定位'))} ｜ 定位：{html.escape(locator.get('locator_status',''))}</p>"
    body = f"""<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>{html.escape(row['clause_id'])}</title>
<style>body{{font:15px/1.55 system-ui,sans-serif;margin:24px;color:#17212b}}h1{{font-size:22px}}.grid{{display:grid;grid-template-columns:minmax(0,2fr) minmax(330px,1fr);gap:22px}}img{{width:100%;height:auto;border:1px solid #aaa}}pre{{white-space:pre-wrap;background:#f2f5f7;padding:14px;border-radius:8px}}.missing{{padding:30px;background:#fee;color:#900}}.sign{{min-height:100px;border-bottom:1px solid #333}}@media(max-width:900px){{.grid{{grid-template-columns:1fr}}}}</style>
<h1>固定随机抽样 #{index}: {html.escape(row['clause_id'])}</h1><p>随机种子 {SEED}；此卡仅为机器定位与原图供审，未完成真人复核。</p>{page_html}
<div class="grid"><section><h2>原始 PDF 页图（只读上游渲染）</h2>{image_html}</section><section><h2>候选记录与适用条件</h2><pre>{data}</pre><h3>实际审核人填写</h3><p>姓名/身份核验：<span class="sign"></span></p><p>签名（本人手写或可追溯电子签名）：<span class="sign"></span></p><p>日期、结论、页码、错误类型与修订意见：<span class="sign"></span></p></section></div></html>"""
    if card.exists():
        if card.read_text(encoding="utf-8") != body:
            raise SystemExit(f"Existing evidence card differs (possibly human annotations); refusing overwrite: {card}")
        return
    with card.open("x", encoding="utf-8") as f:
        f.write(body)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    sample = load_csv(SAMPLE)
    if len(sample) != 50 or {int(r["seed"]) for r in sample} != {SEED}:
        raise SystemExit(f"Expected exactly fixed seed {SEED} 50-row P15 sample; got rows={len(sample)}")
    if len({r["clause_id"] for r in sample}) != 50:
        raise SystemExit("P15 sample has duplicate clause_id")
    # Human-authored sheets are append-only/owner-controlled. This preparation
    # script must never rewrite them, even when they currently look blank.
    if FREEZE.exists():
        frozen = json.loads(FREEZE.read_text(encoding="utf-8"))
        source_sha = sha256(SAMPLE)
        ordered_ids_sha = hashlib.sha256("\n".join(r["clause_id"] for r in sample).encode()).hexdigest()
        if frozen.get("p15_sample_sha256") != source_sha or frozen.get("sample_ids_sha256") != ordered_ids_sha:
            raise SystemExit("Frozen P15 source/sample binding changed; refusing regeneration without Owner review")
    changes = load_csv(DIFF)
    cells = load_csv(CELL_LEDGER)
    ids = sorted({r["clause_id"] for r in cells})
    if len(ids) != 42:
        raise SystemExit(f"P15 diff expected 42 clause IDs, got {len(ids)}")
    if len(cells) != 73:
        raise SystemExit(f"P15 A/B cell ledger expected 73 changed Excel cells, got {len(cells)}")
    cell_counts: dict[str, int] = defaultdict(int)
    for row in cells:
        cell_counts[row["clause_id"]] += 1
    overlap = sorted(set(ids) & {r["clause_id"] for r in sample})
    union = sorted(set(ids) | {r["clause_id"] for r in sample})
    if len(overlap) != 2 or len(union) != 90:
        raise SystemExit(f"Expected 2 overlap and 90 unique review objects, got {len(overlap)} and {len(union)}")
    records = load_candidate()
    pages_by_source = load_native_pages()
    offsets = offsets_from_native(pages_by_source)
    loc_rows = []
    cards = []
    for i, row in enumerate(sample, 1):
        source = source_path(row["source_pdf"])
        rel_source = source.relative_to(ROOT / "upstream").as_posix()
        pages = pages_by_source.get(rel_source, [])
        index, basis, printed_guess = locate(row, pages)
        if index is None and rel_source in offsets and str(row.get("printed_page", "")).isdigit():
            # Offset is accepted only when supported by >=3 independent page
            # locators all agreeing for this exact source PDF.
            index = int(row["printed_page"]) + offsets[rel_source]
            if not (0 <= index < len(pages)):
                index = None
                basis = "PRINTED_PAGE_OFFSET_OUT_OF_RANGE"
            else:
                basis = f"MACHINE_CALIBRATED_CONSTANT_OFFSET_{offsets[rel_source]}"
                printed_guess = row["printed_page"]
        status = "LOCATED_MACHINE_CANDIDATE_REQUIRES_HUMAN_VISUAL_CHECK" if index is not None else basis
        image_rel = None
        image_sha = ""
        if index is not None:
            img = render_page(source, index)
            image_rel = img.relative_to(OUT).as_posix()
            image_sha = sha256(img)
        locator = {
            "sample_no": int(row["sample_no"]), "seed": SEED, "clause_id": row["clause_id"],
            "source_pdf": row["source_pdf"], "pdf_sha256": sha256(source),
            "printed_page": row.get("printed_page", ""), "inventory_printed_page_guess": printed_guess,
            "pdf_page_index": index, "locator_status": status, "locator_basis": basis,
            "pdf_page_count": len(pages), "render_sha256": image_sha,
            "machine_page_is_not_human_verification": True, "render_path": image_rel or "",
        }
        loc_rows.append(locator)
        write_card(row, records.get(row["clause_id"]), locator, image_rel, i)
        cards.append({"sample_no": i, "clause_id": row["clause_id"], "path": f"cards/{i:02d}_{re.sub(r'[^A-Za-z0-9_.-]', '_', row['clause_id'])}.html", "locator_status": status})

    with (OUT / "P16_C_MACHINE_PAGE_LOCATORS.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(loc_rows[0]))
        w.writeheader(); w.writerows(loc_rows)
    with MACHINE_SAMPLE_INDEX.open("w", encoding="utf-8-sig", newline="") as f:
        fields = list(sample[0]) + ["pdf_sha256", "resolved_pdf_page_index", "locator_status", "evidence_card"]
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for row, loc, card in zip(sample, loc_rows, cards):
            w.writerow({**row, "pdf_sha256": loc["pdf_sha256"], "resolved_pdf_page_index": loc["pdf_page_index"], "locator_status": loc["locator_status"], "evidence_card": card["path"]})
    # Unified review register: random sample and changed-record scope both remain
    # explicit. Human identity, timestamp, status, and signature are blank.
    by_id = {r["clause_id"]: r for r in sample}
    a_reviews = load_csv(A_REVIEW) if A_REVIEW.is_file() else []
    a_by_id = {r["clause_id"]: r for r in a_reviews}
    with MACHINE_SCOPE_INDEX.open("w", encoding="utf-8-sig", newline="") as f:
        columns = ["clause_id", "review_scopes", "random_sample_no", "seed", "change_cell_count", "change_cells", "overlap_random_and_change", "source_pdf", "printed_page", "pdf_page_index", "locator_status", "evidence_card", "change_evidence_card", "change_machine_conclusion", "change_machine_review_label", "reviewer_identity", "reviewer_2_identity", "signature_1", "signature_2", "review_timestamp", "decision", "disagreement_resolution", "status"]
        w = csv.DictWriter(f, fieldnames=columns); w.writeheader()
        card_map = {c["clause_id"]: c for c in cards}
        for cid in union:
            s = by_id.get(cid)
            changes_for = [d for d in cells if d["clause_id"] == cid]
            c = card_map.get(cid)
            a = a_by_id.get(cid)
            a_card = ("../A_CHANGED_42/" + a["card_path"] if a and a.get("card_path") else "A_CARD_PENDING_P16_A")
            w.writerow({
                "clause_id": cid,
                "review_scopes": ";".join(x for x, yes in [("RANDOM50", s is not None), ("CHANGED42", bool(changes_for))] if yes),
                "random_sample_no": s.get("sample_no", "") if s else "", "seed": SEED if s else "",
                "change_cell_count": len(changes_for), "change_cells": ";".join(sorted({d["field"] for d in changes_for})),
                "overlap_random_and_change": "YES" if s and changes_for else "NO",
                "source_pdf": s.get("source_pdf", "") if s else (a.get("source_pdf", "") if a else ""),
                "printed_page": s.get("printed_page", "") if s else (a.get("printed_page", "") if a else ""),
                "pdf_page_index": next((x["pdf_page_index"] for x in loc_rows if x["clause_id"] == cid), "") if s else (a.get("pdf_page_index_0based", "") if a else ""),
                "locator_status": c.get("locator_status", "A_CARD_PENDING_P16_A") if c else ("A_MACHINE_CANDIDATE_REQUIRES_HUMAN_VISUAL_CHECK" if a else "A_CARD_PENDING_P16_A"),
                "evidence_card": c.get("path", "A_CARD_PENDING_P16_A") if c else ("" if a else "A_CARD_PENDING_P16_A"),
                "change_evidence_card": a_card,
                "change_machine_conclusion": a.get("machine_conclusion", "") if a else "",
                "change_machine_review_label": a.get("machine_review_label", "") if a else "",
                "reviewer_identity": "", "reviewer_2_identity": "", "signature_1": "", "signature_2": "",
                "review_timestamp": "", "decision": "", "disagreement_resolution": "", "status": "PENDING_REAL_HUMAN_REVIEW",
            })
    index_html = "<!doctype html><meta charset='utf-8'><title>P16-C human review 50</title><h1>P16-C 固定随机50条原图核验卡</h1><p>seed=20261029，50条原抽样保留；页图是上游原始PDF渲染，定位仍需审核人视觉确认。不得由Codex代签。</p><ol>" + "".join(f"<li><a href='{html.escape(c['path'])}'>{html.escape(c['clause_id'])}</a> — {html.escape(c['locator_status'])}</li>" for c in cards) + "</ol>"
    (OUT / "index.html").write_text(index_html, encoding="utf-8")
    locator_path = OUT / "P16_C_MACHINE_PAGE_LOCATORS.csv"
    a_inventory_path = P16_A / "P16_A_PAGE_INVENTORY.csv"
    a_page_rows = load_csv(a_inventory_path) if a_inventory_path.is_file() else []
    a_evidence = []
    for item in a_page_rows:
        source = (ROOT / item.get("src", "")).resolve()
        indices = [x.strip() for x in item.get("indices", "").split(";") if x.strip()]
        images = [x.strip() for x in item.get("images", "").split(";") if x.strip()]
        pages = []
        for index, image_name in zip(indices, images):
            image = P16_A / "pages" / image_name
            pages.append({"pdf_page_index": index, "image_name": image_name,
                          "image_sha256": sha256(image) if image.is_file() else ""})
        a_evidence.append({"clause_id": item.get("clause_id", ""), "pdf_sha256": sha256(source) if source.is_file() else "",
                           "pages": pages})
    a_evidence_bytes = json.dumps(a_evidence, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    manifest = {
        "status": "PREVIEW_ONLY_PENDING_HUMAN_REVIEW", "seed": SEED,
        "p15_sample_sha256": sha256(SAMPLE),
        "sample_export_sha256": sha256(MACHINE_SAMPLE_INDEX),
        "sample_ids_sha256": hashlib.sha256("\n".join(r["clause_id"] for r in sample).encode()).hexdigest(),
        "p15_candidate_jsonl_sha256": sha256(CANDIDATE),
        "official_jsonl_sha256": sha256(ROOT / "upstream/05_提交区/clauses.jsonl"),
        "machine_sample_index_sha256": sha256(MACHINE_SAMPLE_INDEX),
        "locator_manifest_sha256": sha256(locator_path),
        "p16_a_inventory_sha256": sha256(a_inventory_path) if a_inventory_path.is_file() else "",
        "changed42_evidence_sha256": hashlib.sha256(a_evidence_bytes).hexdigest(),
        "changed42_evidence": a_evidence,
        "human_ledger_path": "P16_C_HUMAN_REVIEW_EVENTS.jsonl",
        "machine_preparation_does_not_author_human_review": True,
        "random_sample_n": len(sample), "changed_unique_clause_ids": len(ids), "changed_cells": len(cells),
        "random_change_overlap": overlap, "deduplicated_review_objects": len(union),
        "page_locator_resolved": sum(r["pdf_page_index"] is not None for r in loc_rows),
        "page_locator_unresolved": sum(r["pdf_page_index"] is None for r in loc_rows),
        "human_signed": 0, "release_authorized": False,
    }
    # Freeze is created once; reruns may refresh machine indexes, but cannot
    # silently replace an established source binding.
    if FREEZE.exists():
        prior = json.loads(FREEZE.read_text(encoding="utf-8"))
        stable_fields = ("p15_sample_sha256", "sample_ids_sha256", "p15_candidate_jsonl_sha256", "official_jsonl_sha256", "sample_export_sha256", "locator_manifest_sha256", "p16_a_inventory_sha256", "changed42_evidence_sha256")
        if any(prior.get(k) != manifest.get(k) for k in stable_fields):
            raise SystemExit("Existing P16-C freeze does not match current inputs; refusing overwrite")
    else:
        with FREEZE.open("x", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
