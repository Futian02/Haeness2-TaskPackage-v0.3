"""SHA-256 inventory of every tracked blob materialized from upstream HEAD."""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT / "upstream"
OUT = ROOT / "docs" / "audits" / "upstream_head_manifest.jsonl"


def classify(path: str) -> tuple[str, bool]:
    p = path.replace("\\", "/")
    if p.startswith("04_接口文档/reference_code/"): return "third_party_reference", False
    if any(x in p.lower() for x in ("cache", "runs/", "render", "_cache", ".cache")): return "historical_cache_or_run", False
    if p.startswith(("01_RBI标准/", "02_损伤机理参考/", "03_案例样例/")): return "official_source_or_sample", False
    if p in {"README.md", "04_接口文档/工具接口规范.md", "04_接口文档/技术指标验证方法.md", "任务包问题答复.docx", "资料获取与摘录表填写指南.md"}: return "frozen_teacher_contract", False
    if p.startswith("05_提交区/") or p.startswith("04_接口文档/"): return "teacher_deliverable_or_schema", False
    return "upstream_tracked_other", False


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    head = subprocess.check_output(["git", "-C", str(REPO), "rev-parse", "HEAD"], text=True).strip()
    names = subprocess.check_output(["git", "-C", str(REPO), "ls-files", "-z"])
    paths = [x.decode("utf-8", "surrogateescape") for x in names.split(b"\0") if x]
    records = []
    for rel in paths:
        p = REPO / rel
        if not p.is_file(): raise SystemExit(f"tracked file not materialized: {rel}")
        role, editable = classify(rel)
        records.append({"path": rel, "size_bytes": p.stat().st_size, "sha256": sha256_file(p),
                        "role": role, "origin": f"upstream@{head}", "editable": editable})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("".join(json.dumps(r, ensure_ascii=True) + "\n" for r in records), encoding="utf-8")
    pdfs = [r for r in records if r["path"].lower().endswith(".pdf")]
    excels = [r for r in records if r["path"].lower().endswith((".xlsx", ".xls"))]
    print(f"HEAD={head} tracked={len(paths)} inventoried={len(records)} pdf={len(pdfs)} xlsx_xls={len(excels)}")
    print(f"MANIFEST={OUT.relative_to(ROOT)} manifest_sha256={sha256_file(OUT)}")
    print(f"pdf_sha256={json.dumps([{k:x[k] for k in ('path','size_bytes','sha256')} for x in pdfs], ensure_ascii=False)}")
    print(f"spreadsheet_sha256={json.dumps([{k:x[k] for k in ('path','size_bytes','sha256')} for x in excels], ensure_ascii=False)}")


if __name__ == "__main__": main()
