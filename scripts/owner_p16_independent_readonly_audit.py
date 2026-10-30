"""P16 Owner strictly read-only acceptance cross-check. Does not change source XLSX, PDFs or JSONL."""
from __future__ import annotations
import csv
import json
import collections
import hashlib
from pathlib import Path

R=Path(__file__).resolve().parents[1]
A=R/"work/data_staging/p16/A_CHANGED_42"
B=R/"work/data_staging/p16/B_REMAINDER"
C=R/"work/data_staging/p16/C_GATE"
M=R/"work/data_staging/p16/merged"
D=R/"work/data_staging/p15/merged"

def rows(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def jlines(p):
    with p.open(encoding="utf-8") as f:return [json.loads(x) for x in f if x.strip()]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

a=rows(A/"P16_A_REVIEW42.csv")
cell=rows(A/"P16_A_CELL_AUDIT.csv")
sample=rows(C/"P16_C_HUMAN50.csv")
union=rows(C/"P16_C_HUMAN_REVIEW90.csv")
loc=rows(C/"P16_C_HUMAN50_PAGE_LOCATORS.csv")
p15diff=rows(D/"P15_C_CANDIDATE_JSONL_DIFF.csv")
btable=rows(B/"P16_B_PRIORITY_TRIAGE.csv")
bdm=rows(B/"P16_B_DM_FIELD_REVIEW.csv")
bchapter=rows(B/"P16_B_SUPPLEMENT_REVIEW.csv")
bchanges=jlines(B/"P16_B_CHANGE_PROPOSALS.jsonl")
baseline=rows(B/"P16_B_RETRIEVAL_BASELINE_46.csv")
candidate=rows(B/"P16_B_RETRIEVAL_CANDIDATE_46.csv")
official=R/"upstream/05_提交区/clauses.jsonl"
preview=M/"P16_CLAUSES_PREVIEW_ONLY.jsonl"
old=jlines(official);new=jlines(preview)
o={x["clause_id"]:x for x in old};n={x["clause_id"]:x for x in new}
changed=[k for k in o if o[k]!=n[k]]
failed_signed=[x for x in union if any(x.get(k,"").strip() for k in ("reviewer_identity","reviewer_2_identity","signature_1","signature_2","review_timestamp","decision"))]
assert len(a)==42 and len(cell)==73 and len(sample)==50 and len(loc)==50 and len(union)==90
assert len({x["clause_id"] for x in union})==90
assert len(changed)==42 and len(old)==len(new)==554
assert set(o)==set(n)
assert len(p15diff)==44
assert len(btable)==211 and len(bdm)==1312 and len(bchapter)==56 and len(bchanges)==11
assert not failed_signed
assert sha(preview)=="7efebc07786fd6232da05d21c43323486f3b15d1ff4edd731075755fe419d196"
assert sha(official)=="a8151797ba15a6a7452dd83aaec9fab4c0a815724ca45062eb1e2bac7b4d49ef"

for name,rr in [("baseline",baseline),("candidate",candidate)]:
    assert len(rr)==46
    judged=[x for x in rr if x.get("expected_clause_ids","")]
    hits=sum(int(x["relevant_ids_retrieved"]) for x in judged)
    relevant=sum(int(x["relevant_id_count"]) for x in judged)
    print("RETRIEVAL",name,"judged",len(judged),"hits",hits,"relevant",relevant,"recall",round(hits/relevant,4))
assert len([x for x in baseline if x["case_id"] in {y["case_id"] for y in candidate}])==46

missing_img=[x["clause_id"] for x in a if not (A/x["card_path"]).exists()]
missing_c=[x["clause_id"] for x in sample if not (C/x["card_path"]).exists()] if "card_path" in sample[0] else []
assert not missing_img and not missing_c
machine=collections.Counter(x["machine_conclusion"] for x in a)
print("A_MACHINE",dict(machine))
print("UNION",{"unique":len(union),"overlap":len([x for x in union if x["overlap_random_and_change"]=="YES"]),"signed":len(failed_signed)})
print("BACKLOG",{"RBI_tables":len(btable),"DM_fields":len(bdm),"supp_chapters":len(bchapter),"proposals":len(bchanges)})
print("PREVIEW",{"official":len(old),"preview":len(new),"changed_ids":len(changed),"added_or_removed":len(set(o)^set(n)),"sha":sha(preview)[:16]})
print("OFFICIAL_HASH",sha(official)[:16])
print("TSG_LOCATOR_CONFLICT",[x["clause_id"] for x in a if x["machine_conclusion"]=="CONTRADICTS"])
print("RESULT MACHINE_STRUCTURE_PASS HUMAN_RELEASE_BLOCKED")
