# Codex Window A｜R8-A 全量PDF逐项核对→原RBI Excel直接填充｜执行提示词
STATUS: READY_TO_SEND_TO_LOCAL_CODEX。你是唯一拥有`upstream/01_RBI标准/条款摘录表_RBI.xlsx`写权限的执行窗口；Window B同时只负责`frontend/`及必要`backend/`，双方严格不碰对方目标文件。

项目根目录：`D:\作业\竞赛\计算机设计智能体\机械智能体`

**第一步必须完整读取并遵守**
- `AGENTS.md`
- `docs/OWNER_R8A_RBI_PDF_EXHAUSTIVE_XLSX_DESIGN_20261028.md`（本次唯一详细合同）
- `docs/audits/RBI_RISK_FIELD_DIRECT_EDIT_20261028.md`
- `docs/audits/P2_RBI1_LANGGRAPH_EVIDENCE.md`
- `upstream/README.md`
- `upstream/04_接口文档/convert.py`、`validate.py`、`enums.json`与`risk_level_mapping.xlsx`
- `upstream/01_RBI标准/条款摘录表_RBI.xlsx`所有sheet头/格式，唯一允许写入`摘录表`。
- `scripts/audit_pdf_rbi_coverage.py`、`scripts/audit_rbi1_quote_candidates.py`、此前13条P2候选。

## 任务
1. 对本地RBI目录**6份PDF（共461页）逐章、逐节、逐表、逐公式、逐适用条款**扫描，建立章节/表格/附录覆盖台账，不能仅基于搜索几个关键词和已有472条推断完整。每个相关标准子项必须映射到已存在行、新增行，或说明为何不录。PDF的GB/T26610.2/.4中文提取乱码，必须以页面视觉/矢量文本及表格复核为准，乱码文本不可写入Excel。遇到读不清的数字、单位、不等式、脚注→needs_human_review，禁止猜测与自动虚假签审。
2. 用户要求**直接更新原始**`upstream/01_RBI标准/条款摘录表_RBI.xlsx`，并且只准修改其中`摘录表`，既有472行、23列字段与其他3sheet的格式/公式/数据验证均保持不变；追加新条款并在确认实际PDF有遗漏时修旧行，每项修正都留下原值、原文和印刷页。13个P2候选从GB/T26610.1开始核证并合并，后续按覆盖台账继续追加有价值条款，不止13条。工作开始前记录原件SHA、备份、排查另一个Excel写者；任何格式不一致立即停止并回滚。
3. **23列必须逐一按教师字段合同填充**：A编号、B标准、C文本条号、D印刷页、E原始准确标题、F逐字原文≤300字，G/H/I/J风险条件与映射按GB/T26610.3及risk_level_mapping核算，K只有具有具体设备条件的单值年数才填，L检验方法，M/N材质介质枚举，O/P温度℃，Q/R压力MPa，S设备枚举，T剩余原文条件，U/V真实人员抽取与独立复核，W问题/版本/待审核说明。**不允许为了“填满”而把不适用空列瞎填**，尤其不能把TSG21安全状况等级1-5映射成L1-L4、不能把“最长9年”无条件写成建议年限，也不能把说明性AI改写写入“原文摘录”。
4. 输出各PDF覆盖台账和单元格变更ledger、数值/公式/表格随机二次核验清单，现有行哈希与其它3sheet的XLSX OOXML差异证据，记录每份PDF检出的独特条款、仍未检完的章节。不得用“PDF文字不匹配”直接证明摘录错误，也不能因为机器字符串匹配就宣布准确率100%。
5. **人审签名不可伪造**。抽取人U如果没有真实学号姓名，新增条款如实标DRAFT并在原表保存候选，明确convert会失败且官方JSONL继续保留既有554条；绝不能借用旧行署名或填“AI/待审核”来骗过强制校验。V仅独立真人看过PDF后填，未验证保持空。将需真实抽取人/复核人的行列出，停止于待Owner签署，不向我问重复问题。
6. 对全部满足真实身份/来源约束的数据，使用老师原`convert.py`隔离输出完成读表，检查条号文本、ID唯一、枚举、原始风险→统一映射、负/开区间、周期和错误日志；批准后再正式输出`05_提交区/clauses.jsonl`，运行原`validate.py --final`、3工具自测、guardrail/normal与现有Python回归。**不修改教师脚本以绕过错误，不直接改JSONL**。若因U/V真人身份缺口无法合法完成则明确BLOCKED，不伪报通过。
7. 交付`docs/audits/R8A_RBI_PDF_COVERAGE_LEDGER.csv`、`R8A_RBI_CELL_DELTA.csv`、`R8A_RBI_FINAL_AUDIT.md`（六份标准覆盖率/原Excel已填条数/各字段有依据的填写率/错误/待审核/原始命令/文件SHA），原工作簿与回滚备份的真实路径。不要删除任何上游PDF、已有Excel、reference_code或历史证据，不执行git reset/clean，不提交或部署。

**停止条件**：所有可识别的相关章节/表格已形成覆盖台账；原Excel按证据已补全；对无法确认的内容明确留下待审核清单；老师转换与终验分别真实PASS或因合法人审缺口明确BLOCKED。最终状态`READY_FOR_OWNER_REVIEW`，待ChatGPT下一轮独立审计。不要只给“新增了几十条”的文字汇报，一定提供可核查的PDF源、页码、单元格diff和实际终验命令。
