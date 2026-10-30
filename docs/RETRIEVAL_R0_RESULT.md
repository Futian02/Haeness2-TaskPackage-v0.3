# RAG词法检索对照实验 R0（2026-10-27）

环境：用户本机 Python+SQLite3 3.45.1；词法索引用标准库 `sqlite3 FTS5(trigram)`，数据为上游 `05_提交区/clauses.jsonl` 中554条。

命令：`python -B -m evals.benchmark_retrieval`

## 本轮测得
- 8题，均为GB/T 30579标准机理的**完整准确名称**，每题30轮热查询。
- 官方原始词法检索：Recall@5=1.0000、MRR@5=1.0000、warm mean 0.2134ms；
- SQLite FTS5+BM25：Recall@5=1.0000、MRR@5=1.0000、warm mean 0.0258ms；
- 官方初次加载和内存初始化≈183.25ms；FTS5读取JSONL并建立索引≈19.553ms。

## 如何解读
**只证明8个精确术语在当前运行机器中的热查询与语法性能**；没有统计并发、P95端到端、语义改写、工况参数适用性、模型时延。初始化口径不同（原工具加载与初始化 vs FTS读取并建索引），不可当作绝对优化比率。尤其不应凭 8/8 达标宣称生产RAG完成。

## 下一步实验设计（冻结20-50人工金标）
- exact term (8)：现已完成；
- field evidence paraphrase (10+)：例如“塔顶水样铁离子升高、pH下降”，由工程标准原文复核哪些条款相关；
- disambiguation (10+)：湿硫化氢/氯化氢与氯化铵等易混场景；
- negative/OOD (5+)：没有适用条款或超出枚举，不许只因向量相似就“强匹配”；
- RBI matrix row (10+)：title完全相同但不同图1格，必须核具体clause_id；
- 测Recall@k、MRR、nDCG、无结果率、误答/误拒率、索引刷新时延，以及模型端到端P50/P95。

## 决策
暂不把 FTS5 替换上游 `standard_clause_search`，仅在 `knowledge/lexical.py` 保留可比较的实现。当前554条规模下，查询本身已很快；更值得研究的是**语义召回、引用真实性、检索后属性约束和LLM执行时间**。
