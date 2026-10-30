# Codex S3-A｜正式82条损伤机理的只读来源扫描与10–15条条件候选
工作根：`D:\作业\竞赛\计算机设计智能体\机械智能体`
本机 Codex 在当前本地工作区使用文件读写与PowerShell/终端。不使用任何远程连接器来操作同一台电脑；不能直接读取D盘就报告LOCAL_EXECUTION_ENV_MISMATCH。

**先读**：`AGENTS.md`、`docs/PROJECT_STATUS_CURRENT.md`、`docs/S3_DM82_APPLICABILITY_RESEARCH_AND_ENGINEERING_SPEC_20261029.md`、`docs/data_quality/DM_APPLICABILITY_ROOT_CAUSE_AND_REFORM_20261029.md`、`docs/DATA_LINEAGE.md`、`docs/data_quality/TEACHER_SAMPLE50_EVIDENCE_STATUS_20261029.md`、老师三工具和标准原PDF/两份Excel/JSONL血缘文档。查看当前工作树并保护上游脏文件。

**独占可写**：`knowledge/applicability/candidates/**`、`scripts/s3_dm82_*.py`、`docs/data_quality/S3_*.md`。不要修改同阶段B负责的schema/判定引擎，或任意`upstream/**`、正式Excel/PDF/JSONL/教师脚本、P16人审表、生产SQLite、运行服务或AGENTS。

1. 真实只读加载正式`upstream/05_提交区/clauses.jsonl`的全部82条damage mechanism，检查八段式、材料/介质/设备/温压、`other`、影响因素文本；导出逐条字段覆盖+原文/枚举冲突归类，区别“未提及”“原文有但超出老师枚举”“值的作用对象不明”“子机理条件”等；每一条结果含clause_id和来源SHA。不得为了填充率给空字段填模型猜测。
2. 建立`source_manifest.jsonl`：只使用真实存在的PDF和JSONL，SHA256、clause ID、文献标题、页图索引、印刷页等如实定位；文本PDF页错位/乱码/OCR模型猜测另标NEEDS_PDF_CHECK。来源检索不得在本机路径中接入公网收费文档发布，也不能把整篇付费标准上传模型。
3. 按真实82条标题与clause ID选择10–15个危害高、语义易混淆的机理试点（例如烟气露点/燃灰/湿H2S/氯化铵/盐酸/酸性水/微生物/环烷酸等；先搜索真实标题，找不到标UNAVAILABLE），为每条生成**候选**谓词：property, operator, value, unit, target_object, role, polarity, scope, origin, source_excerpt_locator, review_state；同时给1个正证据、1个UNKNOWN缺项、至少1个不该误判的负例。不能把示例算真实标准结论。
4. 数据自动蒸馏可以先用严格词法/结构规则、再可选LLM生成“建议草稿”，但输出默认PROPOSED/NEEDS_PDF_CHECK，保留原文句与原PDF位置、来源校验结果，禁止伪签核/伪造纸面原文。用户当前明确授权机械智能体开发，不等于可以披露付费标准全文。
5. 新建`scripts/s3_dm82_inventory_readonly.py`（只读）+ 自动重复执行测试；候选总表应区分82条都被扫描与实际有可靠适用性谓词的数量。记录无来源/不确定的每条mechanism ID。
6. 专业测试种子≥30候选反例，明确这是**作者合成待审**而不是独立专家gold；重点区分湿H2S分压vs系统总压、介质温vs壁温、耐蚀vs易感、烟气侧vs常规酸管道；禁止模型输出L1-L4设备风险。
7. 交付`docs/data_quality/S3_DM82_SOURCE_CANDIDATES_AUDIT_20261029.md`：所有source hash、扫描分母、候选数量、文献不确定性、真实测试命令与输出、给B的字段契约。不得声称专业准确率已验证。

**停止条件**：任意老师正式源需要修改/创建新枚举/人工签名、页码无证据或跨窗口同文件冲突，立即标BLOCKED并保留证据。只完成自有候选，不切换线上V2。
