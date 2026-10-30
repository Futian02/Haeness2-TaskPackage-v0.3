"""Read-only target-page smoke, PDF visual truth still needs independent human confirmation."""
from pathlib import Path
import fitz
p=Path("upstream/01_RBI标准/补充规范/TSG21-2016_固定式压力容器安全技术监察规程.pdf")
if not p.exists():
    matches=list(Path("upstream/01_RBI标准").glob("*TSG*pdf"))
    if not matches:raise RuntimeError("TSG source absent")
    p=matches[0]
d=fitz.open(p)
print("TSG",p.name,"pages",len(d))
for i in (78,83):
    t=d[i].get_text("text",sort=True)
    print("INDEX",i,"chars",len(t),"token_8.3.12",("8.3.12" in t or "8．3．12" in t),"8.2.3",("8.2.3" in t),"safe_attachment",("安全附件检验" in t),"head",repr(t[:130].replace("\n"," ")))
d.close()
p=Path("upstream/02_损伤机理参考/GBT30579-2022_承压设备损伤模式识别.pdf")
d=fitz.open(p)
for i in (14,15,38,57):
    t=d[i].get_text("text",sort=True)
    print("DM_INDEX",i,"chars",len(t),"has5Cr",("5Cr-0.5Mo" in t),"has3Cr",("3Cr-0.5Mo" in t),"注氨点",("注氨点" in t),"注氢点",("注氢点" in t),"head",repr(t[:100].replace("\n"," ")))
d.close()
