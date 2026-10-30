"""Read-only source quote candidate assertions against GB/T 26610.1-2022 PDF.
This checks machine extraction matching only; PDF visual/printed-page human audit
remains mandatory before adding rows to teacher XLSX.
"""
from __future__ import annotations
from pathlib import Path
import fitz
import re
import unicodedata

PDF = Path(__file__).resolve().parents[1] / "upstream" / "01_RBI标准" / "GBT26610.1-2022_基本要求和实施程序.pdf"
# printed_page, clause_no, parent_title, short quote copied from original PDF
CANDIDATES = [
 (4, "5.1.1", "风险", "ＲＢＩ以相对风险确定装置、单元、系统、设备或组件的等级。"),
 (4, "5.2.1", "风险分析的类型", "ＲＢＩ中的风险分析分为定性风险分析、定量风险分析、半定量风险分析三种类型。"),
 (4, "5.2.2", "风险分析的类型", "定性风险分析要求输入描述性信息（通常为一定的数据范围），并给出定性的结果。定性分析一般能够在缺乏具体定量数据条件下完成风险评估。"),
 (7, "6.2.4.1", "工艺单元中的腐蚀回路筛选", "根据拟进行ＲＢＩ评估的工艺单元中各设备工艺介质的化学性质、操作压力、操作温度、材质和运行历史等条件将工艺单元划分为若干腐蚀回路。"),
 (7, "6.4.1.2", "确立评估工况的通用要求", "ＲＢＩ评估中使用的运行工况指运行中的极端工况，在运行中应对关键工艺参数进行监控以确保其在评估工况内运行。"),
 (9, "7.1.2", "RBI评估需要的数据", "ＲＢＩ评估应采用一致的原则对所有基础数据进行采集和记录。"),
 (9, "7.2.2", "数据质量", "重要数据资料的缺失可能会严重影响ＲＢＩ评估结果。数据提供单位应保证数据真实性，尽量确保数据完整性，评估中使用的数据应经过验证。"),
 (11, "8.1.2", "通则", "当同一设备或部件存在多种工艺条件（不同的温度、压力或介质），ＲＢＩ评估时宜识别出不同工艺条件下可能存在的损伤类别和损伤模式。"),
 (11, "8.2.1.2", "损伤类别的识别", "识别损伤类别应了解设备运行及其与化学、机械环境的相互作用。"),
 (13, "9.1.2", "失效可能性分析", "失效可能性分析应研究设备已知的全部损伤模式，并主要关注易发生多种损伤模式的设备。"),
 (20, "12.1.1", "通过检验降低风险管理的不确定度", "检验本身并不能改变或降低损伤模式的发生可能性。"),
 (23, "13.8.1", "建立完整性操作窗口（IOWs）", "通过制定完整性操作窗口，建立适当工艺操作边界，可以避免或减缓设备损伤的发生，降低失效可能性。"),
 (25, "14.3.2", "实施RBI再评估的时机", "评估周期到期之后。细小变化的长时间积累也会引起ＲＢＩ评估的重大变化。应设定实施ＲＢＩ再评估的最长时间间隔。"),
]
def key(s):
    return re.sub(r"\s+","",unicodedata.normalize("NFKC", s))
def audit():
    document=fitz.open(PDF)
    for printed,clause,title,quote in CANDIDATES:
        index=printed+4
        extracted=key(document[index].get_text(sort=True))
        exists=key(quote) in extracted
        print(("MATCH" if exists else "NOT_EXACT"),clause,"printed=",printed,
              "pdf_idx=",index,"len=",len(quote),"title=",title)
        if len(quote)>300: print("  TOO_LONG")
    print("TOTAL",len(CANDIDATES),"PDF_PAGE_COUNT",len(document))
if __name__=="__main__":audit()
