"""Owner read-only mixed-intent stress matrix for Aetheris.
No keys, no network, no source modifications, no LLM usage.
Human-authored expected categories are an initial adversarial routing audit,
not a validated annotation set or model accuracy claim.
"""
from __future__ import annotations

import json
from collections import Counter
from orchestration.intent import classify_intent

CASES = [
    ("general", "你好"), ("general", "早上好，最近怎么样？"),
    ("general", "你是谁"), ("general", "你是什么模型？"),
    ("general", "帮我写一首深秋的诗"),
    ("general", "帮我用 Python 写一个排序算法"),
    ("general", "什么是 HTTP 协议？"),
    ("general", "讲讲图灵机的历史"),
    ("general", "今天上海天气怎么样？"),
    ("general", "给我写一篇求职自我介绍"),
    ("general", "怎样制定英语六级复习计划？"),
    ("general", "解释一下矩阵求导"),
    ("general", "帮我写一篇关于腐蚀机理的科普文章"),
    ("general", "把这段腐蚀报告翻译成英文"),
    ("general", "为压力容器企业写一句广告语"),
    ("general", "帮我写一个RBI培训课程大纲"),
    ("general", "给我讲一个关于工程师的笑话"),
    ("general", "帮我写一首包含损伤机理四个字的诗"),
    ("general", "请把这段设备检查文字改成正式公文语气"),
    ("general", "计算机操作系统中的失效恢复机制是什么"),
    ("standard", "GB/T 30579-2022 第5.6条写了什么"),
    ("standard", "查GB/T 26610.3第7条的5×5风险矩阵"),
    ("standard", "TSG21-2016 第8.3.12条在哪一页"),
    ("standard", "帮我查GB/T 26610.5-2022 表2面积后果等级"),
    ("standard", "GB/T 26610.4-2022 表10寿命周期次因子"),
    ("standard", "查询标准第5.2条原文"),
    ("standard", "标准中的失效可能性等级是怎么定义的？"),
    ("standard", "GB/T 30579-2022 中湿硫化氢破坏对应条款"),
    ("standard", "检索损伤机理的第5.23条款"),
    ("standard", "标准条款规定安全阀如何检验"),
    ("standard", "请检索RBI标准中的腐蚀机理条款"),
    ("standard", "GB/T 26610.2-2022 检验策略的实施"),
    ("standard", "我只是想查标准第7条，不需要设备研判"),
    ("standard", "你可以干什么？顺便查 GB/T 30579 第5.6条"),
    ("engineering", "碳钢管道介质湿硫化氢，可能有哪些损伤机理？"),
    ("engineering", "这台容器的RBI风险等级是多少？"),
    ("engineering", "依据GB/T 26610.3评估这台压力容器的风险等级"),
    ("engineering", "碳钢换热器接触氯化氢后出现减薄，分析原因"),
    ("engineering", "该管道出现严重腐蚀，下一步检查什么？"),
    ("engineering", "这台压力容器出现裂纹，该如何处理？"),
    ("engineering", "分析这台设备的失效可能性"),
    ("engineering", "判断这个储罐的失效后果等级"),
    ("engineering", "我检测到容器壁厚明显减薄，是否安全？"),
    ("engineering", "设备出现氢鼓泡，应该核查什么？"),
    ("engineering", "现场发现裂纹，接下来应该检测哪些参数？"),
    ("engineering", "近三年测厚数据下降，容器还能安全运行吗？"),
    ("engineering", "这台换热器的局部腐蚀形态如何判断？"),
    ("engineering", "碳钢容器在湿硫化氢条件下是否会发生HIC"),
    ("engineering", "用上次的材质继续判断这台设备的腐蚀原因"),
    ("engineering", "高温下这台设备发生开裂是什么原因？"),
    ("engineering", "你是什么模型？顺便判断这台容器的风险等级"),
    ("engineering", "介绍一下你自己，并分析碳钢管道的损伤机理"),
    ("engineering", "你可以帮我做什么，同时评估这台设备的风险"),
    ("engineering", "帮我判断这个容器还能否安全运行"),
    ("engineering", "在管道H2S环境下，0.0003MPa代表什么条件？"),
    ("engineering", "给这台设备建议检验周期，现场数据尚未提供"),
    ("engineering", "氯离子升高对这台不锈钢换热器有什么影响"),
    ("engineering", "设备有盐沉积和压降增大，如何区分损伤机理"),
    ("engineering", "你好，请分析这台管道的腐蚀"),
    ("engineering", "刚才那个设备怎么进一步做风险分析？"),
]
STALENESS = [
    ("general", "帮我写一首诗"),
    ("general", "今天天气好不好"),
    ("general", "继续写上面的 Python 代码"),
    ("standard", "GB/T30579-2022 第5.6条全文位置"),
    ("engineering", "刚才那台管道的损伤机理还能怎么验证？"),
]

def coarse(route: str) -> str:
    if route == "general_chat":
        return "general"
    if route == "standard_lookup":
        return "standard"
    return "engineering"

def main():
    rows=[]
    for expected,q in CASES:
        route=classify_intent(q,{})
        rows.append({"expected":expected,"actual":coarse(route),"subroute":route,"question":q,"stale":False})
    stale={"material":"碳钢","medium":["湿硫化氢"],"equipment_type":"管道"}
    for expected,q in STALENESS:
        route=classify_intent(q,stale)
        rows.append({"expected":expected,"actual":coarse(route),"subroute":route,"question":q,"stale":True})
    misses=[r for r in rows if r["actual"]!=r["expected"]]
    counts=Counter(r["expected"]for r in rows)
    mistakes=Counter(r["expected"]for r in misses)
    print(json.dumps({
       "kind":"OWNER_READONLY_CURATED_ROUTE_AUDIT", "total":len(rows),
       "expected_categories":dict(counts),"misrouted":len(misses),
       "by_expected_missed":dict(mistakes),
       "note":"hand-curated challenging questions; not a random population accuracy estimate",
       "mismatches":misses
    },ensure_ascii=False,indent=2))
if __name__=="__main__":
    main()
