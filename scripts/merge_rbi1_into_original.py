"""Merge 13 P2 audited RBI1 candidate clauses into the EXISTING teacher XLSX.

Uses only stdlib ZIP/XML to preserve all XLSX archive members except the single
'摘录表' worksheet XML, and existing rows in that worksheet. No new sheet/columns.
Safety:
* Original SHA gate, 13 exactly, unique ids, source quote checks already in P2.
* Backup before atomic swap; verify all unaffected ZIP members byte-identical.
* Preserve row styles, workbook relationships, formatting and validation.
* Extractor and verifier MUST be real people. No invented names.
* If extractor omitted, drafts are written with U empty; official convert FAILS
  as designed, until a genuine extractor signs and re-runs the converter.

Run in project root:
  python -B -m scripts.merge_rbi1_into_original --check
  python -B -m scripts.merge_rbi1_into_original --apply --unsigned-draft
  python -B -m scripts.merge_rbi1_into_original --apply --extractor 2024xxxx_真实姓名

WARNING: never run this concurrently with another workbook writer. The user
has authorized modifying this specific original source file only.
"""
from __future__ import annotations
import argparse
import hashlib
from pathlib import Path
import re
import shutil
import tempfile
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape
import zipfile

from scripts.audit_rbi_source_workbook import ROOT, workbook
from scripts.audit_rbi1_quote_candidates import CANDIDATES, key

SOURCE = ROOT / "01_RBI标准" / "条款摘录表_RBI.xlsx"
DRAFT = ROOT / "01_RBI标准" / "RBI_GBT26610_1_13candidates_for_review.xlsx"
PDF = ROOT / "01_RBI标准" / "GBT26610.1-2022_基本要求和实施程序.pdf"
BASE_SHA = "38cf71bf9f9868cfa531729cda70dea2e2857b3a788ec1a67f56d27ef01512f9"
DRAFT_SHA = "d292a20f1487b3cedcc67d6b36ea192df15f79e3e360905f946252970e818853"
PART = "xl/worksheets/sheet2.xml"
FIELDS = "ABCDEFGHIJKLMNOPQRSTUVW"
SHEET_NAME = "摘录表"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def data_rows(path: Path):
    found = [(n, v) for name, rows in workbook(path) if name == SHEET_NAME for n, v in rows]
    if not found:
        raise RuntimeError("missing 摘录表")
    first = [found[0][1].get(c + "1", "") for c in FIELDS]
    expected = [
        "clause_id", "standard_code", "clause_no", "page", "title", "原文摘录",
        "失效可能性等级", "失效后果等级", "风险等级(原始)", "风险等级(统一)",
        "检验周期(年)", "推荐检验方法", "适用材质", "适用介质",
        "温度下限", "温度上限", "压力下限", "压力上限",
        "适用设备类型", "其他适用条件", "抽取人", "复核人", "备注",
    ]
    if first != expected:
        raise RuntimeError("teacher header changed or missing")
    return [(row, {c: v.get(c + str(row), "") for c in FIELDS}) for row, v in found[1:]]


def prepare(source: Path, draft: Path, extractor: str):
    if sha(source) != BASE_SHA:
        raise RuntimeError("SOURCE_HASH_CHANGED: existing workbook is no longer P2 baseline; re-audit first")
    if sha(draft) != DRAFT_SHA:
        raise RuntimeError("DRAFT_HASH_CHANGED: P2 reviewed draft differs; re-audit first")
    orig = data_rows(source)
    filled = [(n, r) for n, r in orig if r["A"]]
    if len(filled) != 472 or filled[-1][0] != 473:
        raise RuntimeError("the original 472 teacher rows changed; refuse to overwrite")
    target = [(n, r) for n, r in orig if 474 <= n <= 486]
    if len(target) != 13 or any(r["A"] for n, r in target):
        raise RuntimeError("target A474:W486 is not all available")
    candidates = data_rows(draft)
    if len(candidates) != 13:
        raise RuntimeError("expected exactly 13 candidate rows")
    from_pdf = {clause: (page, title, quote) for page, clause, title, quote in CANDIDATES}
    existing = {r["A"] for _, r in filled}
    edits = []
    for i, (_, rec) in enumerate(candidates):
        clause = rec["C"]
        if clause not in from_pdf:
            raise RuntimeError("Unexpected clause " + str(clause))
        page, title, quote = from_pdf[clause]
        rid = "GBT26610.1-2022-" + clause
        if rec["A"] != rid or rec["B"] != "GB/T 26610.1-2022":
            raise RuntimeError("candidate has unexpected id/code: " + str(rec["A"]))
        if str(page) != str(rec["D"]) or key(quote) != key(rec["F"]):
            raise RuntimeError("candidate page/quote mismatch for " + clause)
        if rec["E"].strip() != title.strip():
            raise RuntimeError("candidate title mismatch for " + clause)
        if rid in existing:
            raise RuntimeError("duplicate teacher id " + rid)
        for c in "GHIJKLMNOPQRS":
            if rec[c]:
                raise RuntimeError("P2 candidate unexpectedly filled risk/conditions " + clause + ":" + c)
        # T holds a P2 editorial/generalized note and is not pasted as a
        # standard applicability constraint. Preserve the exact standard quote.
        edits.append({
            "A": rid, "B": rec["B"], "C": str(clause),
            "D": int(page), "E": rec["E"], "F": rec["F"],
            "U": extractor,
            "W": "DRAFT；AI辅助条款摘录待核：原标准印刷p." + str(page)
                 + "；PDF页(0起始)=" + str(page+4)
                 + "；需真实抽取人/独立复核人确认；不构成设备风险定级",
        })
    if len({e["A"] for e in edits}) != 13:
        raise RuntimeError("duplicate candidate ids")
    return edits


def xml_text_cell(col, row, content, style=None):
    style_attrib = (' s="' + str(style) + '"') if style is not None else ""
    return (f'<c r="{col}{row}"{style_attrib} t="inlineStr"><is><t>'
            + escape(content) + "</t></is></c>")


def new_row(num: int, rec: dict):
    # Only new data rows are constructed. Reuse the exact A/C/G/H blank styles
    # of the already-preformatted template rows.
    cells = [
        xml_text_cell("A", num, rec["A"], 12),
        xml_text_cell("B", num, rec["B"]),
        xml_text_cell("C", num, rec["C"], 12),
        f'<c r="D{num}" t="n"><v>{rec["D"]}</v></c>',
        xml_text_cell("E", num, rec["E"]),
        xml_text_cell("F", num, rec["F"], 17),
        f'<c r="G{num}" s="12" t="n" />',
        f'<c r="H{num}" s="12" t="n" />',
    ]
    if rec.get("U"):
        cells.append(xml_text_cell("U", num, rec["U"]))
    cells.append(xml_text_cell("W", num, rec["W"]))
    return f'<row r="{num}">' + "".join(cells) + "</row>"


def modify_xml(original: bytes, edits: list[dict]) -> bytes:
    src = original.decode("utf-8")
    for index, rec in enumerate(edits):
        row = 474 + index
        pattern = re.compile(r'<row r="' + str(row) + r'"[^>]*>.*?</row>')
        result = pattern.search(src)
        if result is None:
            raise RuntimeError("Cannot locate preformatted row " + str(row))
        if not re.fullmatch(
            r'<row r="' + str(row) + r'"[^>]*>'
            r'(?:(?:<c r="(?:A|C|G|H)' + str(row)
            + r'"[^>]*\s*/>))*</row>', result.group()
        ):
            # Verify via conservative XML structure rather than reformatting
            # the workbook if the empty template differs from expectations.
            root = ET.fromstring(result.group())
            if any(child.find("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v") is not None
                   or child.find("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}is") is not None
                   for child in root):
                raise RuntimeError("row has nonempty cell, abort " + str(row))
        src = src[:result.start()] + new_row(row, rec) + src[result.end():]
    modified = src.encode("utf-8")
    ET.fromstring(modified)
    return modified


def apply(edits: list[dict]) -> Path:
    backup = SOURCE.with_name(SOURCE.name + ".bak_owner_before_rbi1_20261028")
    if backup.exists():
        if sha(backup) != BASE_SHA:
            raise RuntimeError("backup exists with unexpected hash")
    else:
        shutil.copy2(SOURCE, backup)
    fd, tmp_path = tempfile.mkstemp(prefix="rbi1-patch-", suffix=".xlsx", dir=SOURCE.parent)
    import os
    os.close(fd)  # Windows cannot unlink an open tempfile; ZipFile(...,'w') truncates it
    tmp = Path(tmp_path)
    try:
        with zipfile.ZipFile(SOURCE, "r") as old, zipfile.ZipFile(tmp, "w") as new:
            if PART not in old.namelist():
                raise RuntimeError("Unexpected workbook sheet layout")
            original_sheet = old.read(PART)
            patched_sheet = modify_xml(original_sheet, edits)
            for meta in old.infolist():
                new.writestr(meta, patched_sheet if meta.filename == PART else old.read(meta.filename))
        with zipfile.ZipFile(SOURCE, "r") as old, zipfile.ZipFile(tmp, "r") as new:
            if new.testzip() is not None:
                raise RuntimeError("xlsx CRC validation failed")
            if old.namelist() != new.namelist():
                raise RuntimeError("xlsx part manifest altered")
            for part in old.namelist():
                if part != PART and old.read(part) != new.read(part):
                    raise RuntimeError("non-target workbook content changed: " + part)
            before = old.read(PART).decode()
            after = new.read(PART).decode()
            # Everything before/after the 13 editable row region unchanged.
            anchor_l = '<row r="474"'
            anchor_r = '<row r="487"'
            if before.split(anchor_l)[0] != after.split(anchor_l)[0]:
                raise RuntimeError("prior worksheet data changed unexpectedly")
            if before.split(anchor_r,1)[1] != after.split(anchor_r,1)[1]:
                raise RuntimeError("subsequent worksheet data changed unexpectedly")
        rows = data_rows(tmp)
        new_entries = [(n,r) for n,r in rows if 474 <= n <= 486]
        if len(new_entries) != 13 or any(
            r["A"] != edits[i]["A"] or r["F"] != edits[i]["F"] or r["C"] != edits[i]["C"]
            or r["G"] or r["H"] or r["I"] or r["J"] or r["K"]
            for i,(_,r) in enumerate(new_entries)
        ):
            raise RuntimeError("new data cell verification failed")
        os.replace(tmp, SOURCE)
    finally:
        tmp.unlink(missing_ok=True)
    return backup


def main():
    ap = argparse.ArgumentParser()
    grp = ap.add_mutually_exclusive_group(required=True)
    grp.add_argument("--check", action="store_true")
    grp.add_argument("--apply", action="store_true")
    ap.add_argument("--extractor", default="", help="verified real 2024xxxx_姓名; do not impersonate")
    ap.add_argument("--unsigned-draft", action="store_true", help="explicitly allow modifying original with U empty; official convert will FAIL")
    args = ap.parse_args()
    if args.apply and not args.extractor and not args.unsigned_draft:
        ap.error("no real extractor signed: require --extractor 学号_姓名 or explicit --unsigned-draft (convert blocked)")
    if args.extractor and args.unsigned_draft:
        ap.error("--extractor and --unsigned-draft are mutually exclusive")
    if args.extractor and (not re.fullmatch(r"[0-9]{6,}_[^_\\s]+", args.extractor)
                           or any(tag in args.extractor for tag in ("示范", "真实姓名", "待填", "xxxx", "XXXX"))):
        ap.error("extractor must have verified real 学号_姓名; placeholders are rejected")
    edits = prepare(SOURCE, DRAFT, args.extractor)
    print("READY_TO_APPEND", len(edits), "A474:W486")
    print("RISK_GHIJ_FIELDS", "all intentionally empty (no source-level risk matrix for RBI1)")
    print("EXTRACTOR_SIGNED", bool(args.extractor))
    if args.apply:
        backup = apply(edits)
        print("MODIFIED_ORIGINAL", SOURCE)
        print("BACKUP", backup)
        print("SHA256", sha(SOURCE))
        print("EXPECTED_CONVERT", "PASS only if extractor was genuine and provided; V verifier remains unsigned")
    else:
        print("CHECK_ONLY: no files modified")


if __name__ == "__main__":
    main()
