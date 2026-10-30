# 工程语义知识库设计 V1 — Evidence-first

目标：从现场自然语言（如塔顶水样pH下降、铁离子升高、尚未测厚）抽出工况、正反证据和未知项，找到符合标准适用条件的机理候选；不能仅凭向量相似得出风险级别。

## 数据层
- 标准事实：现有 clauses.jsonl 的 clause_id、standard_code、clause_no、page、content_raw、八段式与适用条件；这部分只读。
- 现场观测：原文片段、字段名称、数值/单位、观测状态、采样时间、可信来源。
- 机理卡：从八段式派生的机理名称、相关现象、影响因素、鉴别问题、排除线索、来源条款与审核状态。
- 外部参考：公开论文或可靠工程网站，另存 source_type/public_url/date/license；不充当老师规定的标准依据。

## 关键语义：未观察到不等于观察结果为否
对于测厚：
- “未做测厚”：wall_thinning = unknown；
- “实测确认没有减薄”：wall_thinning = observed_false；
- “实测确认有减薄”：wall_thinning = observed_true。
对于pH/铁离子等连续变量，区分定量读数与“偏低/升高”的定性描述；未提供数值不能杜撰5.8等读数。设备材质和介质可用教师官方枚举归一化，但不得扩充老师枚举值。

## MechanismCard最小字段
mechanism_id、official_name、source_clause_ids、applicable_conditions、mechanism_eight_fields、term_aliases、supporting_evidence、contradictory_evidence、missing_facts、discriminator_questions、evidence_level、reviewed、source_file_sha、card_version。
aliases只是产品层检索字段；未人工审查的卡记reviewed=false，E0/E1不能冒称E2/E3。

## PDF到卡的流程
1. 优先读取两份XLSX+现有JSONL，标准条款已经结构化，避免重复造OCR流水线。
2. 原PDF页或表格疑似乱码时，用Docling或MinerU离线提取候选内容，记录实际PDF页码和标准印刷页号的差异。
3. 生成模型只负责别名和鉴别问题候选；每条新断言绑定原始 clause_id、原文短证据以及适用条件。没有依据的归为“未经证实假设”，不可用来判定设备风险。
4. 规则审查 + 人工抽样审核后再进入可用于用户判断的索引；保留原稿来源、提取工具版本、编辑记录。
5. 对比官方关键词、FTS5、embedding、融合加rerank，金标至少覆盖明确术语、自然现象、容易混淆的机理、缺少信息与域外案例。

## 查询服务边界
标准三工具外部签名不变；产品层允许增添私有EvidenceStore、KnowledgeIndex、DocInspector模块，不向老师定义的工具注册第四个Tool。检索候选不等于安全适用：需要检查材料、介质、温压、现场因子及出处的逻辑支持。
