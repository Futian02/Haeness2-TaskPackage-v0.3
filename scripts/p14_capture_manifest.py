"""Capture hashes/status for P14 audit boundaries; reads upstream only."""
from __future__ import annotations
import hashlib,json,subprocess
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]; UP=ROOT/'upstream'; STAGE=ROOT/'work'/'data_staging'/'p14'
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()
def rel(p):return p.relative_to(ROOT).as_posix()
def main():
    src=sorted([*(UP/'01_RBI标准').rglob('*.pdf'),*(UP/'02_损伤机理参考').rglob('*.pdf')])
    src += [UP/'01_RBI标准'/'条款摘录表_RBI.xlsx',UP/'02_损伤机理参考'/'条款摘录表_损伤机理.xlsx',UP/'05_提交区'/'clauses.jsonl',UP/'05_提交区'/'trajectories.jsonl']
    status=subprocess.check_output(['git','-C',str(UP),'status','--short','--branch'],text=True,encoding='utf-8',errors='replace')
    head=subprocess.check_output(['git','-C',str(UP),'rev-parse','HEAD'],text=True).strip()
    files={rel(p):{'sha256':sha(p),'bytes':p.stat().st_size} for p in src}
    payload={'captured_at_utc':datetime.now(timezone.utc).isoformat(),'upstream_head':head,
      'upstream_git_status_read_only':status.splitlines(),'source_files':files,
      'candidate_files':{p.name:{'sha256':sha(p),'bytes':p.stat().st_size} for p in [STAGE/'条款摘录表_RBI_candidate.xlsx',STAGE/'条款摘录表_损伤机理_candidate.xlsx',STAGE/'clauses_candidate.jsonl']},
      'scope_status':'REVIEW_BLOCKED','writes_outside_p14_scope':False,'formal_sources_modified_by_this_task':False}
    out=STAGE/'P14_RUN_MANIFEST.json';out.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(out)
if __name__=='__main__':main()
