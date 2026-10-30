"""Owner's read-only evidence audit of RBI XLSX, canonical JSONL and GB/T 26610.1.

Only stdlib OOXML; never writes or modifies any spreadsheet or PDF.
This is a structural/source-text diagnostic, not human sign-off.
"""
from __future__ import annotations
import collections
import hashlib
import json
import random
import re
import unicodedata
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

from scripts.audit_rbi_source_workbook import ROOT, workbook

XLSX = ROOT / "01_RBI标准" / "条款摘录表_RBI.xlsx"
BAK = ROOT / "01_RBI标准" / "条款摘录表_RBI.xlsx.bak_owner_before_rbi1_20261028"
JSONL = ROOT / "05_提交区" / "clauses.jsonl"
RISK = ROOT / "04_接口文档" / "risk_level_mapping.xlsx"
SOURCE = ROOT / "01_RBI标准" / "GBT26610.1-2022_基本要求和实施程序.pdf"
ABC = "ABCDEFGHIJKLMNOPQRSTUVW"

def norm(s):
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(s))).replace("，", ",").replace("（", "(").replace("）", ")")

def read_xlsx(path, target="摘录表"):
    for name, rows in workbook(path):
        if name == target:
            return [{c: vals.get(c+str(num), "") for c in ABC} | {"_row": num} for num,vals in rows]
    raise ValueError("missing sheet "+target)

def audit():
    import fitz
    arr = read_xlsx(XLSX)
    header, items = arr[0], [r for r in arr[1:] if r["A"]]
    print("Workbook bytes", XLSX.stat().st_size, "SHA256", hashlib.sha256(XLSX.read_bytes()).hexdigest())
    print("RBI record count", len(items), "last", items[-1]["_row"], "headers", [(c,header[c]) for c in ABC])
    fields={c:sum(bool(r[c]) for r in items) for c in ABC}
    print("NONEMPTY_FIELDS",json.dumps(fields,ensure_ascii=False))
    groups=collections.defaultdict(list)
    for r in items: groups[r["B"]].append(r)
    for code,rows in sorted(groups.items()):
        print("STANDARD",code,"rows",len(rows),"with_GH",sum(bool(x["G"]) and bool(x["H"]) for x in rows),
            "with_K",sum(bool(x["K"]) for x in rows),
            "with_L",sum(bool(x["L"]) for x in rows),
            "with_MNS",sum(bool(x["M"]) or bool(x["N"]) or bool(x["S"]) for x in rows),
            "missing_U",sum(not x["U"] for x in rows),"missing_V",sum(not x["V"] for x in rows))
    ids=collections.Counter(r["A"] for r in items)
    duplicate=[(k,v) for k,v in ids.items() if v>1]
    malformed=[r["_row"] for r in items if r["A"]!=re.sub(r"[/\s]","",r["B"])+"-"+r["C"] and not re.fullmatch(re.escape(re.sub(r"[/\s]","",r["B"])+"-"+r["C"])+r"-[a-z]{1,2}",r["A"])]
    numeric_issues=[(r["_row"],c,r[c]) for r in items for c in ("D","K","O","P","Q","R") if r[c] and not re.fullmatch(r"-?\d+(?:\.\d+)?",r[c])]
    bad_quote=[(r["_row"],len(r["F"])) for r in items if len(r["F"])>300]
    print("STRUCTURAL_ERRORS duplicates",duplicate[:10],"bad_ids",malformed[:12],"nonnumeric",numeric_issues[:10],"quotes_over_300",bad_quote[:10])
    mapping=[]
    for name,rows in workbook(RISK):
        if name=="GBT26610.3-2014":
            for num,vals in rows:
                if num<2:continue
                a,b,c,d=(vals.get(f"{col}{num}","") for col in "ABCD")
                if a and b:mapping.append((a.upper(),b.upper(),c,d))
    m={(a,b):(c,d)for a,b,c,d in mapping}
    matrix=[r for r in items if r["B"]=="GB/T 26610.3-2014" and r["G"] and r["H"]]
    mismatches=[]
    for r in matrix:
        expect=m.get((r["G"].upper(),r["H"].upper()))
        if expect!=(r["I"],r["J"]):mismatches.append((r["_row"],r["G"],r["H"],r["I"],r["J"],expect))
    print("MATRIX mapping",len(m),"records",len(matrix),"unique_pairs",len(set((r["G"],r["H"]) for r in matrix)),
          "errors",mismatches[:25])
    risk_orphans=[r["_row"] for r in items if (bool(r["I"])!=bool(r["J"])) or ((r["I"] or r["J"]) and (not r["G"] or not r["H"]))]
    print("RISK_PAIR_INVALID",risk_orphans[:20])
    intervals=[(r["A"],r["F"][:90]) for r in items if not r["K"] and (re.search(r"\d+(?:\.\d+)?\s*(?:年|个月)",r["F"]) or "周期" in r["E"])]
    print("POSSIBLE_INTERVALS_IN_TEXT_WITH_EMPTY_K",len(intervals),"samples",json.dumps(intervals[:11],ensure_ascii=False))
    with zipfile.ZipFile(BAK) as za, zipfile.ZipFile(XLSX) as zb:
        common=set(za.namelist()) & set(zb.namelist())
        changed=[p for p in sorted(common) if za.read(p)!=zb.read(p)]
        print("OOXML_SAME_COMPONENTS",len(common)-len(changed),"changed",changed,"missing",sorted(set(za.namelist())-set(zb.namelist())))
    old=read_xlsx(BAK)
    old_items=[r for r in old[1:] if r["A"]]
    delta=[(old_r["_row"],c,old_r[c][:20],new_r[c][:20]) for old_r,new_r in zip(old_items,items) for c in ABC if old_r[c]!=new_r[c]]
    print("EXISTING_472_ROWS_CHANGED",len(delta),delta[:12])
    official=[json.loads(line)for line in JSONL.read_text(encoding="utf8").splitlines()if line.strip()]
    off={x["clause_id"]:x for x in official if x["knowledge_type"]=="rbi"}
    mismatch=[]
    missing=[]
    for r in old_items:
        x=off.get(r["A"])
        if not x:missing.append(r["A"]);continue
        for c,key in (("B","standard_code"),("C","clause_no"),("D","page"),("E","title"),("F","content_raw")):
            if norm(r[c])!=norm(x.get(key,"")):
                mismatch.append((r["_row"],c,r[c][:30],str(x.get(key))[:30]))
    print("CANONICAL_RBI",len(off),"SOURCE_ROWS_NOT_IN_JSONL",len(missing),"CORE_FIELD_MISMATCH",len(mismatch),
          "mismatches_sample",mismatch[:10])
    from scripts.audit_rbi1_quote_candidates import CANDIDATES
    doc=fitz.open(SOURCE)
    new=items[len(old_items):]
    candidate_matches=[]
    for i,(printpage,clause,title,quote) in enumerate(CANDIDATES):
        row=new[i]
        p_idx=printpage+4
        ok=norm(row["F"])==norm(quote) and norm(quote) in norm(doc[p_idx].get_text(sort=True))
        candidate_matches.append((row["_row"],clause,ok, row["C"]==clause,row["D"]==str(printpage),row["U"]=="",row["V"]==""))
    print("RBI1_13_MACHINE_CHECK",candidate_matches)
    print("RBI1_all_text_matches",sum(x[2] for x in candidate_matches),"no_human_U",sum(x[5] for x in candidate_matches))
    sample=random.Random(20261028).sample(official,50)
    print("OFFICIAL_RANDOM50_COUNTS",dict(collections.Counter(x["standard_code"] for x in sample)),
          "IDs",json.dumps([x["clause_id"] for x in sample],ensure_ascii=False))
    print("AUDIT_NOTE: 50 samples drawn, NOT human-reviewed or E2/E3.")
if __name__=="__main__":
    audit()
