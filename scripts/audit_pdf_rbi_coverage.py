"""Read-only PDF-vs-RBI clause coverage probe; NOT a human verification.
Only the six source PDFs in upstream/01_RBI标准 are searched.
Normalizes Unicode and whitespace. Exact matches and prefix matches are
diagnostic; absence can arise from PDF tables/OCR/extraction, not necessarily
from a wrong Excel record. No source files are changed.
"""
from __future__ import annotations
import collections, json, pathlib, re, unicodedata
import fitz

ROOT=pathlib.Path(__file__).resolve().parents[1]/"upstream"
FOLDER=ROOT/"01_RBI标准"
DOCS={
 "GB/T 26610.1-2022":FOLDER/"GBT26610.1-2022_基本要求和实施程序.pdf",
 "GB/T 26610.2-2022":FOLDER/"GBT26610.2-2022_基于风险的检验策略.pdf",
 "GB/T 26610.3-2014":FOLDER/"GBT26610.3-2014_风险的定性分析方法.pdf",
 "GB/T 26610.4-2022":FOLDER/"GBT26610.4-2022_失效可能性定量分析方法.pdf",
 "GB/T 26610.5-2022":FOLDER/"GBT26610.5-2022_失效后果定量分析方法.pdf",
 "TSG 21-2016":FOLDER/"补充规范"/"TSG21-2016_固定式压力容器安全技术监察规程.pdf"
}
def norm(s):
    s=unicodedata.normalize("NFKC",str(s))
    s=re.sub(r"\s+","",s)
    return s.replace("，",",").replace("（","(").replace("）",")").replace("：",":").replace("；",";")

def main():
    entries=[json.loads(t) for t in (ROOT/"05_提交区"/"clauses.jsonl").read_text(encoding="utf8").splitlines() if t.strip()]
    records=[c for c in entries if c.get("knowledge_type")=="rbi"]
    by=collections.defaultdict(list)
    for x in records: by[x["standard_code"]].append(x)
    for name,path in DOCS.items():
        doc=fitz.open(path)
        pages=[norm(pg.get_text(sort=True)) for pg in doc]
        exact=[]; prefix=[]; no=[]
        for c in by.get(name,[]):
            quote=norm(c.get("content_raw",""))
            if quote and any(quote in page for page in pages):
                exact.append(c)
            elif len(quote)>=26 and any(quote[:26] in page for page in pages):
                prefix.append(c)
            else:
                no.append(c)
        print("STANDARD",name,"pages",len(doc),"entries",len(by.get(name,[])),
              "exact_text_matches",len(exact),"prefix_only",len(prefix),
              "no_simple_text_match",len(no),"pages_with_text",sum(len(p)>50 for p in pages))
        print("SAMPLE_NEED_MANUAL",[(r["clause_id"],r.get("page"),r.get("content_raw","")[:66]) for r in no[:3]])
        doc.close()
    print("NOTE: Text-match diagnostics only; no matched quote is automatically certified for clause number, printed page or device applicability.")
if __name__=="__main__":main()
