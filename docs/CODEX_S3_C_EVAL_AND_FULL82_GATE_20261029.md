# Codex S3-C｜双基线专业判定评测与82条扩展门禁
本机项目：`D:\作业\竞赛\计算机设计智能体\机械智能体`。直接使用本机文件系统/终端；无法直接读取工作目录时报告环境不匹配，不自动接入远程连接器。

**启动条件**：S3-A已交付全82只读来源扫描与首批条件候选；S3-B已交付严格三值引擎及专项测试。未同时满足时先读取报告，只能准备评测协议，不假装批量结果。
读`AGENTS.md`、`docs/PROJECT_STATUS_CURRENT.md`、`docs/S3_DM82_APPLICABILITY_RESEARCH_AND_ENGINEERING_SPEC_20261029.md`、A/B各自审计、老师三工具合同和`docs/data_quality/TEACHER_SAMPLE50_EVIDENCE_STATUS_20261029.md`。

**独占可写**：`evals/s3/**`、`docs/audits/S3_C_*.md`；仅在A/B成果全都完成后，必要时添加`tests/test_s3_evaluation_protocol.py`。不要修改A/B文件、任何`upstream/**`、API、R9/V2默认图、正式DB、教师人审或源PDF。

工作合同：
1. 将候选来源与判定规则冻结成有SHA版本的数据集快照；旧教师三工具输出不改，新增层只作为`shadow`候选解释，同一输入旧/新成对比较。
2. 至少50条初始**合成开发集**，再提供空白独立人工盲标模板≥50条。记录支持/反证/未知/是否关键危险/材料角色/介质角色/环境作用侧/温压对象/来源等级/期望判定，按时间与来源去重拆分dev/holdout，避免将同场景复述既用于开发又用于独立检验。没有真人审核就不输出“专家金标准确率”。
3. 评估Critical Hazard Recall@K（尤其危害遗漏）、False Hard Exclusion、Precision@K、Unknown Calibration、Unsupported Assertion、来源覆盖率、p50/p95时延、AI新增请求数；每个指标列真实分母/未定数量，给错例聚类及置信区间范围。工程业务准确率与格式/工具测试分开呈现。
4. 至少覆盖烟气侧vs非烟气HCl管道、湿H2S分压vs系统压、壁温vs介质温、耐蚀材料被误当成易感、标准未给温度界、子机理适用性误扩大、腐蚀未发生vs仅有候选、缺少PoF/CoF被误标L等级、模型注入修改检索来源等负例。
5. 形成可复现CLI与机器报告，全部输入可追溯且不泄露收费标准全文；测试不读取真实用户会话/企业机密。
6. 前15试点至少人工核查引用与专业适用性前，不允许自动把全部82候选启用到生产检索；将每条状态列表为PROPOSED/PDF_CHECK_PENDING/REVIEWED/APPROVED等。若一条关键危险被无依据硬排除，Gate NO_GO。
7. 产出`docs/audits/S3_C_DM82_PAIRWISE_EVALUATION_20261029.md`与下一轮Owner验收清单。默认R9和关闭的V2全部保留，绝不部署、付费压测、修改上游标准或冒充真人审核。
