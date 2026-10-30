"""P15 Owner read-only field coverage across teacher Excel and JSONL; OOXML reader, no workbook modification."""
from __future__ import annotations
import collections
import json
from pathlib import Path
from scripts.audit_rbi_source_workbook import ROOT, workbook
P={
"RBI":ROOT/"01_RBI标准"/"条款摘录表_RBI.xlsx",
"DM":ROOT/"02_损伤机理参考"/"条款摘录表_损伤机理.xlsx"
}
def report(name,path):
    blocks=dict(workbook(path))
    source=blocks["摘录表"]
    hd=source[0][1]
    colids=[chr(ord("A")+i) for i in range(23 if name=="RBI" else 25)]
    hdr={c:hd.get(c+"1","") for c in colids}
    records=[(i,vals) for i,vals in source[1:] if str(vals.get("A"+str(i),"")).strip()]
    counts={}
    for c in colids:
        n=sum(bool(str(v.get(c+str(i),"")).strip()) for i,v in records)
        counts[c]={"header":hdr[c],"nonempty":n,"empty":len(records)-n,"percent":round(100*n/max(1,len(records)),1)}
    groups=collections.defaultdict(list)
    for i,vals in records:groups[str(vals.get("B"+str(i),"")).strip()].append((i,vals))
    per_standard={}
    for std,rows in sorted(groups.items()):
        per_standard[std]={"n":len(rows),"nonempty":{c:sum(bool(str(v.get(c+str(i),"")).strip())for i,v in rows)for c in colids[6:]}}
    mandatory_cols="ABCDEF"+("G"if name=="DM" else "")+("W"if name=="DM" else "U")
    special={
       "required_field_blank_rows":{c:sum(not str(v.get(c+str(i),"")).strip() for i,v in records)for c in mandatory_cols},
       "expected_not_applicable_fields": ["风险等级 G-J 仅涉及定性风险分级/矩阵的行","K检验周期只适用于标准明确给出无歧义周期的条款"]if name=="RBI" else ["O/P只填规范枚举,不包含所有受影响材料","Q-T仅标准明确阈值时填"]
    }
    print("### "+name+" RECORDS",len(records),"SHEETS",list(blocks))
    for c,d in counts.items():print(c,d["header"],d["nonempty"],"/",len(records),d["percent"],"%")
    print("BY_STANDARD",json.dumps(per_standard,ensure_ascii=False))
    print("SPECIAL",json.dumps(special,ensure_ascii=False))
if __name__=="__main__":
    for name,path in P.items():report(name,path)
