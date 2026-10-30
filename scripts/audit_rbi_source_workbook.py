"""Read-only RBI source/workbook inventory using OOXML and official clauses output.

No openpyxl, no writes, no workbook changes. Intended to distinguish formatted
empty rows from unpopulated source records and identify genuine metadata gaps.
"""
from __future__ import annotations
import collections
import json
import pathlib
import zipfile
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parents[1] / "upstream"
NS = {
    "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "p": "http://schemas.openxmlformats.org/package/2006/relationships",
}
def decode_cell(cell, shared):
    kind = cell.get("t", "")
    if kind == "inlineStr":
        return "".join(e.text or "" for e in cell.findall(".//m:is/m:t", NS))
    v = cell.find("m:v", NS)
    if v is None: return ""
    if kind == "s":
        return shared[int(v.text)]
    return v.text or ""

def workbook(path):
    with zipfile.ZipFile(path, "r") as z:
        strings = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in root.findall("m:si", NS):
                strings.append("".join(t.text or "" for t in si.findall(".//m:t", NS)))
        root = ET.fromstring(z.read("xl/workbook.xml"))
        relroot = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        relmap = {x.get("Id"): x.get("Target").lstrip("/") for x in relroot}
        for sh in root.findall(".//m:sheets/m:sheet", NS):
            name = sh.get("name")
            part = relmap.get(sh.get("{"+NS["r"]+"}id"))
            if not part: continue
            if not part.startswith("xl/"): part = "xl/" + part
            doc = ET.fromstring(z.read(part))
            rows = []
            for row in doc.findall(".//m:sheetData/m:row", NS):
                values = {c.get("r"): decode_cell(c,strings) for c in row.findall("m:c",NS)}
                if values: rows.append((int(row.get("r")),values))
            yield name, rows

def run():
    p = ROOT / "01_RBI标准" / "条款摘录表_RBI.xlsx"
    print("WORKBOOK:",p.name,p.stat().st_size,"bytes")
    for name,rows in workbook(p):
        print("SHEET",name,"XML_NONEMPTY_ROWS",len(rows),"MAX_XML_ROW",max((r for r,_ in rows),default=0))
        if name == "填写示例":
            for rn,vals in rows[:7]:
                print(" EXAMPLE_ROW",rn,json.dumps(vals,ensure_ascii=False)[:2400])
        if name == "摘录表":
            head=dict(rows[0][1])
            print(" HEADER",json.dumps(head,ensure_ascii=False)[:3500])
            samples=[rows[1],rows[2],rows[-3],rows[-2],rows[-1]]
            for rn,vals in samples:
                print(" DATA_ROW",rn,json.dumps(vals,ensure_ascii=False)[:2800])
            cols=collections.Counter()
            actual=0
            for rn,vals in rows[1:]:
                if not (vals.get("A"+str(rn),"").strip()):continue
                actual+=1
                for k,v in vals.items():
                    if v and not k.startswith("A"):cols["".join(x for x in k if x.isalpha())]+=1
            print(" NONEMPTY_KEY_DATA_ROWS",actual)
            print(" POPULATED_COLUMNS",dict(cols))
    clauses=[]
    with (ROOT / "05_提交区" / "clauses.jsonl").open(encoding="utf-8") as f:
        for s in f:
            if s.strip():
                c=json.loads(s)
                if c.get("knowledge_type")=="rbi":clauses.append(c)
    print("RBI_RECORDS",len(clauses),"BY_STANDARD",dict(collections.Counter(c["standard_code"] for c in clauses)))
    fields=["page","content_raw","extractor","verified_by"]
    for fld in fields:print("FIELD",fld,"EMPTY",sum(not c.get(fld) for c in clauses))
    for f in ["likelihood","consequence","risk_level","risk_level_unified","inspection_interval_year","inspection_methods"]:
        count=sum(c.get("rbi_detail",{}).get(f) not in [None,"",[]] for c in clauses)
        print("RBI_DETAIL",f,"NONEMPTY",count,"BLANK",len(clauses)-count)
    print("RAW_LENGTH_MAX",max(len(c.get("content_raw","")) for c in clauses))
    print("UNVERIFIED_SAMPLES",[(c["clause_id"],c.get("title")) for c in clauses if not c.get("verified_by")][:10])
if __name__=="__main__":run()
