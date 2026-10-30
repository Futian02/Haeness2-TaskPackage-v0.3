# 第3课｜为什么术语检索100%，一句工程话却0/5？

本课不是一般RAG科普，而是复盘`python -B -m evals.semantic_probe`在上游554条标准上的实际结果：5个自然语言长句，老师原检索与当前FTS5均返回空。这组是**无专家标注的查询可用性测试**，不能把0/5当语义模型准确率。
上一轮8个标准机理**准确术语**测试二者均Recall@5=100%（也是很小的特定样例）。两组并不矛盾：检索器能找到已经标准化的术语，未必理解现场口语。

## 一、揭示导致0/5的机制
老师 `standard_clause_search` 凭分词、覆盖度和IDF打分，但命中存在“至少有一个词完整出现在title/content_raw”的门槛；FTS5实现采用trigram全词组短语查询，长句不能匹配完整原文时就没有结果。
比如`「铁离子升高，pH下降，尚未测厚」`，并非一条标准术语；我们的 FTS5 `_match_query` 把整句当一个引号包围的短语。这主要是**查询改写/分解策略不足**，而不是数据库失灵，不能用0/5推导“必须上向量模型”。

## 二、先设计工程事实表示层（比embedding更重要）
输入：`常压塔顶碳钢管道，塔顶铁离子升高、pH下降、未做测厚。能否判高风险？`
抽象:
```text
equipment=pipe, location=tower_overhead, material=carbon_steel
Fe: observation_trend=increased, quantitative_value=unknown
pH: observation_trend=decreased, quantitative_value=unknown
wall_thinning: observation_state=unknown (not tested)
possible_damage: hypothesis, not confirmed
RBI_required_factors: absent/unknown
```
**状态区分**：`unknown != observed_false`。还要区分 `unmentioned` 与 `explicitly_not_tested`，二者作为元数据不同，虽然都是unknown。
Boolean证据用`Truth3={True,False,Unknown}`；数值证据用 `value: float|null` + unit + trend + measurement_status，不宜简单套用True/False。
断言状态 `hypothesis|supported|contradicted|unresolved` 与 `raw_span`和`source`绑定。

## 三、从句子到检索计划（三个候选策略）
A. 词典 + 规则（快）：根据领域词典提取`pH, 铁离子, 减薄, 塔顶`，扩展“湿环境、腐蚀、碳钢”等**候选**术语，然后逐词检索，取合并候选。局限：同义词覆盖和多义词歧义。
B. 小LLM结构化抽取（灵活）：返回Pydantic对象 `{entities, evidence, missing, uncertainty, candidate_query_terms}`；约束只能标可见的input span为observed。失败时规则回退，计入LLM失败，不能误记解析成功。
C. Embedding + rerank（适于口语语义）：对机理卡用章节+材料+影响因素等字段构建检索文本，而不是仅把`content_raw`切300token；dense用于提升召回，最终由标准适用条件做硬过滤。

推荐：A作为离线强基线，B改善自然语言结构化输入，C只有实测确实改善困难集才加入产品。对于材料牌号/标准编号，精准词法通常保留为一路。

## 四、数学：对多路召回排序融合
官方检索得序列R1，向量得R2。每篇候选文档d的RRF：
```
RRF(d) = 1/(k + rank_lexical(d)) + 1/(k + rank_dense(d))
```
其中k是平滑参数，不是TopK。这个公式组合不同算法的相对名次，不假设lexical score与cosine similarity同尺度。
检索质量：
```
Recall@K = |Relevant∩TopK| / |Relevant|
MRR@K = (1/N)Σ_i [1/rank_i]  (首个相关结果名次)
```
没有专家标注Relevant时，**不能**声称Recall。语义相似度 0.92 也不能推断某条标准适用于现有设备。

## 五、要做的最小实验
1. 固定本轮5个自然长句，保存语料版本、模型版本与查询策略。
2. 先让事实抽取器标识在文本中直接出现的信息，禁止凭标准知识猜不存在的数值。
3. 记录 `raw query→rewritten queries→tool hits→mechanism candidates`；打印标准ID和排除条件，避免仅看自然语言总结。
4. 让知晓标准的人工核对哪些候选具有E2原文与E3适用性，形成小金标；
5. 对比对同一组题的 V0整句、V1关键词拆分、V2结构化/语义扩展、V3混合检索，报告精度/召回与延迟。

## 六、跨学科关联
- **数据库**：NULL和三值逻辑。SQL的`IS NULL`不是`=FALSE`，与`尚未测厚`一致。
- **概率与诊断**：假设集合`H_i`、证据`E`，观测是更新候选信念的输入，而不是把缺失当负证据。
- **可靠性工程**：失效模式与效应分析(FMEA)用于思考潜在失效、观测与后果，但不等同于GB/T26610的RBI数值框架。
- **计算机工程**：由统一JSON状态及事件日志使Agent决策可追溯、可重放；不是展示模型不可得的内部思考链。

### 思考题
如果设备“未做测厚”，Verifier发现Diagnosis Agent已经因为`wall_thinning=false`排除了某机理，应该怎样修复？
正确做法应拒绝这个排除证据，要求更新为unknown并重新查鉴别条件；再将“需要测厚”作为用户可执行补测信息，而不是继续给肯定结论。
