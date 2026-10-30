"""Read-only Markdown inventory + stale-status + local-link audit.
Only prints report; no project files modified.
"""
from __future__ import annotations
from pathlib import Path
import collections,json,re
root=Path(__file__).resolve().parents[1]
skip={".git",".venv-langgraph","node_modules","dist","_rendered","_render","__pycache__","reference_code","test_deps","_pages"}
docs=[]
for base in [root/"docs",root/"upstream"]:
    for p in base.rglob("*.md"):
        if any(x in skip for x in p.relative_to(root).parts):continue
        if "upstream" in p.parts and p.parent.name not in {"upstream","05_提交区","04_接口文档"}:continue
        docs.append(p)
metrics=collections.Counter()
signals=[]
broken=[]
for p in docs:
    text=p.read_text(encoding="utf-8-sig",errors="replace")
    rel=p.relative_to(root).as_posix()
    metrics["doc_count"]+=1
    for tag,pattern in [
      ("100_percent",r"50/50|100(?:\.0)?%|100％"),
      ("legacy_current",r"唯一当前|当前稀疏未检出|尚未检出|CONTRACT_LOCK"),
      ("release_status",r"READY_FOR_OWNER_REVIEW|PREVIEW_ONLY|HUMAN_REVIEW|REVIEW_BLOCKED"),
      ("raw_sse_ui",r"前端.*SSE|展示.*SSE|执行记录|思维链")
    ]:
        found=re.findall(pattern,text,flags=re.I)
        if found:
            metrics[tag]+=1
            if tag in {"100_percent","legacy_current"}:signals.append({"path":rel,"tag":tag,"matches":found[:5]})
    for target in re.findall(r"(?<!\!)\[[^\]]+\]\(([^)]+)\)",text):
        clean=target.split("#")[0].split("?")[0].strip()
        if not clean or "://" in clean or clean.startswith("mailto:") or clean.startswith("#"):continue
        clean=clean.replace("%20"," ")
        d=(p.parent/clean).resolve()
        if not d.exists():broken.append({"from":rel,"link":target})
print(json.dumps({"counts":dict(metrics),"stale_or_metric_claims":signals[:70],"broken_local_links":broken[:70],"broken_count":len(broken)},ensure_ascii=False,indent=2))
