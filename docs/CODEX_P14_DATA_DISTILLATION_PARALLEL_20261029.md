# 新Codex窗口｜P14 标准数据大规模蒸馏（独立于P13）
唯一根目录：D:\作业\竞赛\计算机设计智能体\机械智能体
立即开始，先读 AGENTS.md、upstream/README.md 第八部分、upstream/04_接口文档/技术指标验证方法.md、upstream/资料获取与摘录表填写指南.md、docs/P14_STANDARD_DATA_DISTILLATION_MASTERPLAN_20261029.md、docs/audits/OWNER_RBI_KNOWLEDGE_INDEPENDENT_AUDIT_20261028.md。

**你是P14数据Owner，可以派3个并行子智能体；不能与已有P13（backend/frontend/orchestration）窗口抢文件。**
只读源：`upstream/01_RBI标准/**`6 PDF+RBI.xlsx，`upstream/02_损伤机理参考/**`6 PDF+DM.xlsx，`upstream/04_接口文档/**`、正式`05_提交区/clauses.jsonl`。
只允许写：`work/data_staging/p14/**`、`docs/data_quality/P14_*.md/csv`、`scripts/p14_*.py`和`tests/test_p14_*.py`。禁止写原PDF/原Excel/正式JSONL/数据库/P13正在修改的任何backend/frontend/orchestration文件。不要误删任何缓存/备份。

**并行子Agent A: DM主标准**。对 GB/T30579 PDF 163页、当前DM表82条逐损伤模式核对章5–9、每条八段式G-N、F原文<=300字、条号、印刷页码与PDF索引、适用材质/介质/温压。检查82条是否覆盖标准中应该抽取的全部损伤模式及八子条款。自动定位、OCR仅针对乱码/表格页，涉及专业真值的图表逐页视觉复核。生成增量候选，不重造已对的旧行、不写假人工签名。
**并行子Agent B: RBI主标准**。对GB/T26610.1–.5和TSG 21六PDF共461页，优先复核既有210条“表X中…”类解释性F列、.3图1的25格风险矩阵、.4/.5数值表、.2检验策略、TSG条件周期、.1新增13条。风险表格行必须保留表头、单位、边界和印刷页原图定位。不得混淆检验周期/服役年限、TSG安全状况等级和RBI L1–L4。
**并行子Agent C: 其余5PDF补充标准**。GB/T150.1、150.3、150.4、151、21447累计761页，逐章节做适用性分类/标准号/章节范围的coverage ledger；只把合法且与损伤识别有直接关系的条款作为DM候选，其余标为辅助设备适用性索引或非本课题范围，不把所有文字强塞进25列。不许为了页数冲量。
**由你唯一合并者完成**：
1. 对全部12 PDF、1385页建立标准→章节→页→表/公式→候选/已有/排除/待复核的coverage矩阵。处理PDF原生文本乱码，使用PyMuPDF/pdfplumber+PP-StructureV3成熟工具（只选疑难页OCR，先20页pilot），PDF视觉复核数字/公式/表格；保存页索引与印刷页码，不擅自改文本。
2. 在`work/data_staging/p14`生成两份**与老师表头、sheet、枚举、样式一致的Excel副本**，只把可核条款放入候选；原文F不可润色，解释放备注，八段式G-N必须有原文依据；不符合枚举或无证据的字段留空并列待审。抽取者与复核者必须真人签名，AI只写机器核验备注，不能伪装人工签名。
3. 用**原始老师脚本**`upstream/04_接口文档/convert.py --inputs <two staged xlsx> --output work/data_staging/p14/clauses_candidate.jsonl`隔离试转，校验候选version和正式554条的diff；现有RBI.xlsx有13个U空，可使用开工前的472条合规基线副本做隔离转换对照，但不可伪造13条U填入正式库。
4. 至少先交20页pilot、来源覆盖表和质量报告（数字、原文字段、页码、enum、适用条件），如果pilot中存在系统性假原文/无法对上页码，不得全面无界跑；修算法后逐批10–30页增量执行。审计不是完成率宣称。
5. 老师随机>=50条交叉核对>=95%必须真人签核；你可以生成独立抽样/复核表与可导航PDF页的模板，但不可以把两个LLM审核当真人。正式数据流必须等Owner许可才覆盖，不能同时写上游。
6. 完整交付 `docs/data_quality/P14_SOURCE_COVERAGE_MATRIX.csv`、`P14_DATA_QUALITY_AUDIT.md`、staging候选Excel/JSONL、具体差异及待人工处理队列；没有足够证据即标`REVIEW_BLOCKED`，禁止虚报“100%标准已蒸馏”。
技术选择以现有工具复用、可学习和少文件为先，不要引入复杂新数据库/模型训练。执行直到机器可核项收敛，不必每10分钟征询。完整报告包含错误回放、复现命令、隔离转换结果、尚缺人审项和下一步。
