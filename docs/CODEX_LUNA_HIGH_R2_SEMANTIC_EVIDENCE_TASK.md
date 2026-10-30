# Luna High R2｜标准PDF驱动的工程语义机理知识层（独立于R1，须待R1验收）
目标：把工程师自然语言中的现象转成候选机理、已知/反证/未知证据、鉴别问题，而非只做PDF向量聊天。
路径与阅读：先AGENTS.md、docs/PROJECT_STATE.md、老师接口规范、资料填写指南、原始PDF/XLSX与上游tools.py；必须先完成全仓Git同步。只写 knowledge/、evals/、docs/，不直接改老师01/02标准及正式clauses.jsonl。

交付过程：
1. 逐章梳理 GB/T 30579-2022 14个优先机理（5.1/5.19/5.23/5.24/6.7/5.21/5.22/5.6/9.3/6.1/5.11/5.5/6.4/6.12），加标注和参考：机理名、别名（别名只能做查询映射）、适用材质、介质、温压限定、可观察症状、反证条件、必须询问的现场数据、推荐验证检测方式、同类区分、条款ID与标准页。不能把未在标准明确给出的工程推断说成原文；补充网络资料必须记录url、发布日期、许可证、证据层级，仅作背景或外部旁证，不能注入官方clauses.jsonl。
2. 输出人工可核查的json/yaml知识卡schema，字段 evidence.type=observation|hypothesis|standard_rule|exclusion，certainty=observed_true|observed_false|unknown，source{clause_id,page,standard_code,confidence,verified_by}，缺失时verified_by为空。不要自动标人工核验。
3. 构造≥40条自然语言题集：同义描述、现场叙述、相互矛盾观测、数据缺失、多介质、多设备、域外，以及≥10条“铁离子升高/水样pH下降/未测厚”组合。所有真值由人工复核后才可进入Gold；未审核标provisional，不混到正式准确率。
4. 测官方baseline/FTS5/可选embedding+RRF+rereank，分离冷建索引、检索、远程向量、模型、reviewer与完整应答的P50/P95。不可从短小术语8/8直接推出语义准确率。
5. 编写可跑的结构化差别诊断规则和多Agent状态单元测试：未知不会变False；同一观察可同时支持和否定不同候选但必须保留来源；冲突状态显式存在；非标外部信息不得被视为标准证据。
6. 新增面向前端的 mechanism evidence graph 节点边和卡片字段，支持候选对比表、证据缺口列表、引用点击回标准摘录；提供真实样例与失败案例。
产物 docs/audits/R2_MECHANISM_KNOWLEDGE_AUDIT.md、knowledge/mechanisms/、evals/semantic_gold_draft.jsonl、docs/SEMANTIC_EVIDENCE_MODEL.md，要求人工审核标注、不得编造PDF内容。R1中原三工具及正式官方验收必须保持全部通过。

终验必须包括：规范条款真实ID、可回源PDF、条件适用、unknown三值；至少10个有对照的自然语言用例；无API时embedding标BLOCKED，不得只用模型直觉当证据。
