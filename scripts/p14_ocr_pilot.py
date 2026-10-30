"""Run diagnostic Tesseract OCR only on the frozen 20-page P14 pilot."""
from __future__ import annotations
import csv
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PILOT_DIR = ROOT / "work" / "data_staging" / "p14" / "pilot"
INPUT = PILOT_DIR / "pilot_20_pages.csv"
OUTPUT = PILOT_DIR / "ocr_text"

def main() -> int:
    exe = shutil.which("tesseract")
    if not exe:
        raise SystemExit("tesseract executable not found; no OCR was run")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with INPUT.open(encoding="utf-8-sig", newline="") as f:
        pages = list(csv.DictReader(f))
    metrics = []
    for row in pages:
        img = ROOT / row["render_path"]
        stem = img.stem
        outbase = OUTPUT / stem
        proc = subprocess.run([exe, str(img), "stdout", "-l", "chi_sim+eng", "--psm", "6"],
                              capture_output=True, text=True, encoding="utf-8", errors="replace")
        text_path = outbase.with_suffix(".txt")
        if proc.returncode:
            metrics.append({**row, "ocr_status":"error", "ocr_returncode":proc.returncode,
                            "ocr_chars":0, "ocr_exactness":"not_scored"})
            continue
        txt = proc.stdout
        text_path.write_text(txt, encoding="utf-8")
        metrics.append({**row, "ocr_status":"diagnostic_only", "ocr_returncode":0,
                        "ocr_chars":len(txt),
                        "ocr_text_path":text_path.relative_to(ROOT).as_posix(),
                        "ocr_exactness":"not_scored_against_human_transcription"})
    out = PILOT_DIR / "pilot_ocr_metrics.csv"
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(metrics[0]),extrasaction="ignore"); w.writeheader(); w.writerows(metrics)
    print(f"pages={len(metrics)} tesseract={exe} metrics={out}")
    print(f"diagnostic_only={sum(x['ocr_status']=='diagnostic_only' for x in metrics)} exactness_scored=0")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
