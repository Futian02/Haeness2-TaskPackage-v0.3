# 第3课预习：机械风险标准知识库如何搭建（RAG底层原理）

## 1. 不同于“扔PDF进向量数据库”
这不是任意文档聊天。现有 554 条记录已经结构化：`clause_id`、`standard_code`、`page`、`title`、`content_raw`、`applicable_conditions`、`mechanism_detail`、`rbi_detail`。优先利用字段精确过滤，不允许embedding越过适用性约束。
每条是“条款/图表行级单位”，不是“每300字硬切chunk”。一个title同名的25个RBI风险矩阵格必须靠clauses ID区分，不能丢失坐标。

## 2. 当前真实链路
官方 `standard_clause_search` 将搜索词分词、计算IDF、再按标题0.6+正文0.4覆盖率混合加权，返回带来源的hits。因只有554条，直接扫描完全可能已经满足时延；先测，不假设向量一定更快。

## 3. 实验升级路线（每一级都必须在冻结题上赢过上一级）
V0：原生结构化筛选+官方词法检索；测Recall@5、MRR@10、无结果正确率、P50/P95。
V1：SQLite FTS5 `trigram` 中文子串词法检索；BM25排序。**SQLite为内存索引，只作旁路基线，不改源文件。**
V2：用Embedding编码`[标准号+条款号+标题+知识类别+适用材质/介质+正文]`，建立Faiss或Qdrant Local索引。对于小样本，向量建索引时长/推理时长是重要代价，数据更新需带版本。
V3：按材质/介质/标准先过滤，词法BM25 + dense embedding双路召回，用RRF融合，再在最多10-30条候选上cross-encoder或ColBERT rerank；不足证据时回退检索或拒判，不让向量距离充当证据真实性。

## 4. 数学直觉
向量方法：`e_q=Enc(q), e_d=Enc(d)`；`sim(q,d)=e_q·e_d/(||e_q||||e_d||)`。语义近≠材料与温度适用。
BM25：对查询词q_i，综合`IDF(q_i)`与文档词频 `tf`、文档长度 `|d|`、全库平均长度 `avgdl` 排名：
`score(d,q)=Σ_i IDF(q_i)·tf_i(k1+1)/[tf_i+k1(1-b+b|d|/avgdl)]`。
RRF：对不同召回路径的排名取 `Σ_r 1/(k+rank_r(d))`。它不用跨算法比较绝对分数，能将关键词精确与语义召回综合。

**速度瓶颈不是一个固定常数**：粗筛与小库词法一般很便宜；若QueryEmbedding每次远程调用+CrossEncoder几十条重排，会引入显著网络/模型推理延迟。哪一级最佳，要在本机和真实API上测P95。

## 5. 最重要的质量保障
RAG只负责“拿到候选证据”，不能直接做设备安全判级。高风险决策用程序检查适用性：材质/介质映射正确，操作温度和压力符合条文给出的边界，有效现场因子齐备。输入缺失 != boolean false；查不到证据 != 没有风险。

## 6. 前沿但有依据
- 2024 Anthropic *Contextual Retrieval*：嵌入/词法索引之前增加原文上下文，减少chunk脱离标准/章节时造成歧义；适合我们给每个条款拼标准号、章号、适用范围，不是让LLM改写content_raw。
- Qdrant Hybrid Search / Reranking：BM25、dense embedding双路，晚期交互或cross-encoder重排小候选集；随着语料增大再引入。
- Long-context LLM不等于不需要检索：完整标准体积、版本溯源、适用条件校验、引用可重复性都是检索层的职责。

参考：https://www.anthropic.com/research/contextual-retrieval
https://qdrant.tech/documentation/tutorials-basics/reranking-hybrid-search/

## 7. 我们本轮实际代码
`knowledge/lexical.py`：使用Python标准库sqlite3的 FTS5+trigram，内存建库，返回真实 `clause_id`、页码和类别。它不创建第四个老师工具。
`evals/benchmark_retrieval.py`：同题对照official/fts5，打印Recall@K、MRR、时间分布。先从8条**显式术语**查询开始，再人工标注模糊现场叙述题；一张小表不能证明V1已经优于V0。
