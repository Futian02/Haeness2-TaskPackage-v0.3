# P15-C 独立数据 QA、候选集成与教师终验报告

日期：2026-10-29  
状态：**READY_FOR_OWNER_REVIEW**（集成与机器门禁完成）  
正式发布：**BLOCKED / 不具备发布条件**（真人交叉复核和 PDF 原文准确性门禁未完成）

## 1. 范围与边界

已先阅读 `AGENTS.md`、P15 字段闭环总计划、Owner 字段审计、P15-C 任务书、教师填表指南、原版 `convert.py` / `validate.py`、P14 数据质量审计。C 仅写 `scripts/p15_c_*.py`、`tests/test_p15_c_*.py`、`work/data_staging/p15/C_QA/**`、`work/data_staging/p15/merged/**` 与本报告；未改 A/B 输出、上游原始 Excel/PDF、正式 JSONL、教师工具、P13 应用代码。没有提交、部署、清理或移动数据。

**冻结合同**：教师工具仍只有 `damage_mechanism_query`、`rbi_lookup`、`standard_clause_search`；原 `tools.py`、`convert.py`、`validate.py` 均未改。候选工具回归在独立 staging 副本中进行，副本 `tools.py` SHA-256 与冻结教师文件一致：`4ea2eee633b7cf6988a6c6aaeff328ff8347dc12bbfbc0f7bdbce4c7f6a8e80d`。

## 2. A/B 候选独立核对与真实差异

对源表和 A/B 候选按 Excel 行、列独立逐格对照，并要求每个变化恰有一个台账条目，且 `old_value/new_value` 与实际源/候选值完全一致：

| 输入 | 源数据行 | 实际差异单元格 | 台账精确匹配 | 结论 |
|---|---:|---:|---|---|
| A RBI | 485（含 13 条未签草稿） | 64 | 64/64 | 无漏记/多记 |
| B DM | 82 | 9 | 9/9 | 无漏记/多记 |
| **合计** | 567 | **73** | **73/73** | 逐单元格范围一致 |

实际变更构成：

- A：26610.3 §7 图1矩阵 25 行的 T/W 两列归位与页码追溯，共 50 格；26610.5 表2/表3 原文摘录 10 格；TSG 21 四条适用条件 4 格。矩阵 G/H 与原始/统一风险等级通过教师映射表逐格核对，25/25 一致。表2的 CA 面积阈值、单位及边界按行展开。
- B：30579 §5.6 四格（原文/描述/温度上限/其他条件）；§5.23 三格（清空 49–66℃的通用温区并重写条件对象）；§6.7 两格（清空通用温度上限并将 H₂S 分压与设备总压力分开）。
- **新增正式知识记录 0 条**；B 的五份补充标准分类 84 个章节/附录，直接补入两张教师表及正式 JSONL 的候选 0 条。变更是既有记录的纠错/语义归位，非扩充记录规模。
- C 对 A/B 两份变更台账计数：73/73 有 `printed_page`、`pdf_page_index`、定位描述和非空 `evidence_quote`；A 4 格是非表格语义变更，故无 `table_id`，但有 PDF bbox/文字定位。所有 73 格仍标记人审待核。

所有源定位、引文和复核状态由 A/B 台账提供并由 C 核对了单元格差异；机器截图/OCR/台账不等于真人 PDF 逐字复核。A/B 报告状态均为 `REVIEW_BLOCKED`，其 `review_required/reviewer_status` 仍指向人工待核。C 未将它们升级为 HUMAN_VERIFIED。

## 3. 独立字段质量门

`P15_C_FIELD_LEDGER.csv` 及 `rbi_P15_C_FIELD_LEDGER.csv`、`dm_P15_C_FIELD_LEDGER.csv` 为原始源表逐字段基线；`candidate_rbi_P15_C_FIELD_LEDGER.csv` 与 `candidate_dm_P15_C_FIELD_LEDGER.csv` 为候选复核。每格附字段分类、标准 PDF 路径是否存在、印刷页、原文摘录、`pdf_page_index`/bbox 空位及待核状态。`REQUIRED / CONDITIONAL_SUPPORTED / SOURCE_UNSPECIFIED / REVIEW_NEEDED` 分类不把非空率当准确率。

- 基线 RBI：485×23 = 11,155 个字段槽；DM：82×25 = 2,050 个字段槽。候选结构同为 13,205 个槽（含 RBI 13 条未签草稿）。
- PDF 文件路径可读存在；工作簿页码数字门禁通过。完整打印页→PDF 物理页 index / bbox / 表格行列映射仍未全量确认；不将打印页数值误称为 PDF 页面核准。
- F 原文栏只执行长度、存在性、来源登记等机器检查，逐字准确性没有全量 ground truth。机器无法确认的字段留在 `REVIEW_NEEDED`，没有用空值率推断正确性。
- 枚举字段按教师 `enums.json` 检查；别名和非法值进入审查；官方 converter 对可转换合并副本实际执行，0 error / 0 warning。
- `P15_C_OFFICIAL_SEMANTIC_CHECKS.json`：正式数据风险矩阵 25/25 配对完整，教师风险映射不一致 0；26610.5 表2五个边界均通过机器字符串/数值一致性检查；5.23、5.6、6.7 三项仍显式 `REVIEW`，没有宣称原 PDF 事实已被 C 独立目视验证。
- `P15_C_CANDIDATE_SEMANTIC_AUDIT.json`：候选矩阵 25 格、26610.5 表2 A–E 五边界、DM 三个高风险语义检查共 **9/9 机器断言通过**。5.23 温度边界为空；5.6 通用温区 177–427℃、218–400℃作为轻相介质子条件；6.7 总压力上下限均空，0.0003 MPa 留在 H₂S 分压条件语义中。报告状态字段仍为 `human_pdf_fidelity: NOT_VERIFIED`。

## 4. staging 合并、教师转换和 JSONL 字段差分

候选文件位于 `work/data_staging/p15/merged/`：完整 A preview（仍含 13 条草稿）、去除 13 条未签行后的 convert-eligible RBI、B DM 副本及候选 JSONL。原 A/B 候选保持未改。

1. 用教师原版 converter 对完整 preview 的门禁探针返回码 **1**，恰有 13 条“抽取人为空”，且未产生 JSONL。这是防止伪签名的预期结果。日志：`P15_C_UNSIGNED_PREVIEW_CONVERT_GATE.log`。
2. convert-eligible 副本排除上述 13 条未签草稿（没有补造抽取人/复核人），其余 RBI 472 + DM 82 输入教师原版 `convert.py`：**554 条、0 error、0 warning**。
3. 教师原版 `validate.py --final --clauses <staging候选> --trajectories <只读正式轨迹>`：554/554 条款通过、200/200 轨迹通过；multi-step 144、三类特殊轨迹各15，退出码0。
4. 候选 JSONL 对照正式 554 条：**added 0 / modified 42 / unchanged 512 / removed 0**；44 个逐字段 JSON 差异记录在 `P15_C_CANDIDATE_JSONL_DIFF.csv`。零静默删除。RBI 草稿 13 条仍在 `preview_full_unreleased`，不进入候选 JSONL。
5. 以字节复制的冻结 `tools.py`、官方 schema/枚举和候选 JSONL 建独立 probe package；教师原始 17 项 selftest 对候选副本运行 **17/17 PASS**。官方正式库独立 selftest 亦 **17/17 PASS**。

主要复现命令及完整 stdout/stderr：

```powershell
python -B scripts/p15_c_prepare_review_and_merge.py merge --rbi work/data_staging/p15/A_RBI/条款摘录表_RBI_P15_A_candidate.xlsx --dm work/data_staging/p15/B_DM/条款摘录表_损伤机理_P15_B_candidate.xlsx
python -B upstream/04_接口文档/validate.py --final
python -B upstream/05_提交区/_selftest_tools.py
```

`work/data_staging/p15/merged/P15_C_INTEGRATION_RUN.log`、`P15_C_CANDIDATE_TOOL_SELFTEST.log`、`P15_C_SHA256_MANIFEST.json` 保存转换、校验、工具副本与各关键输入输出哈希。

## 5. 检索与适用条件实测

冻结 **46** 道检索题：38 道有正式条款 ID 的来源连接题（问题文本仍为合成、未获专家确认），8 道无金标判断题；每题分别标记 `query_origin` 与 `gold_evidence_status`，负题不被当成专家真值。另有 5 道条件过滤 adversarial probes。重点包括 26610.5 表2 CA 面积 A–E、26610.3 5×5 风险格、30579 5.23 / 5.6 / 6.7、条件错误过滤、TSG、补充标准无正式知识等。

| 数据集 | 正例相关判断 | micro Recall@20 | MRR@20 | 条件过滤可测试结果 |
|---|---:|---:|---:|---|
| 原正式 JSONL + 原工具 | 37/42 | 0.881 | 0.816 | 2 PASS / 2 FAIL / 1 NOT_TESTABLE |
| convert 候选 + 原样教师工具副本 | 37/42 | 0.881 | 0.816 | 4 PASS / 0 FAIL / 1 NOT_TESTABLE |

原数据过滤失败：49–66℃的局部 NH₄HS 气相析出现象导致 80℃下 §5.23 返回 `out_of_domain`；§5.6 250℃轻相条件无法召回机理。候选把局部条件从通用温区分开后，两个病例在 staging 中均命中，显示**候选数据修复了已复现的误过滤**；该语义修复仍需真人标准复核。6.7 工具调用接口没有 `pressure_mpa` 输入，因此“总压不应与 H₂S 分压门槛互换”不能由该接口端到端断言，明确记 `NOT_TESTABLE`；结构审计确认候选 S/T 总压力字段为空。检索的 5 个正例未命中（似然方法、5E矩阵词面、矩阵综合问句、检验策略、5.6轻相词面）；候选未改善这些词面查询，未为了全绿改金标/放宽证据门禁。

机器检索题和候选/正式结果：`P15_C_OFFICIAL_RETRIEVAL_RESULTS.csv`、`P15_C_CANDIDATE_RETRIEVAL_RESULTS.csv`；条件探针各自的 `_CONDITION_FILTER_PROBES.csv`。这些题是 synthetic/unreviewed，结果不是教师“真实模型100题解析”或专家准确率。

## 6. 固定随机种子真人复核样本

`P15_C_HUMAN_REVIEW50.csv` 以 `seed=20261029`，从最终 convert-eligible 554 条候选 JSONL 确定性随机抽 50 条；复跑种子与样本 ID 完全一致。每项包含 clause_id、标准/条款/标题、PDF 文件路径、印刷页、原文与待核条件。PDF 物理页 index、bbox/表格格坐标及真人核验栏留空，要求审阅者现场填写。

状态：**50/50 `PENDING_HUMAN_REVIEW`；已签 0；通过 0；失败 0**。未签的结果不是“通过率0%”，而是尚未审阅。发布 Gate 要求 >=48/50 由独立真人核验通过；当前不满足。机器、A/B agent、C Codex 均未冒充教师要求的真人复核。

## 7. 验证结果、失败记录与发布裁定

- P15-C 专项测试：13/13 PASS（源表结构、风险映射、字段政策、PDF路径存在、A/B逐格差分、固定种子样本和检索用例定义）。日志：`work/data_staging/p15/C_QA/P15_C_UNIT_TESTS.log`。
- 项目全量 unittest：**219 项，216 PASS / 3 skipped / 0 failures**。日志：`work/data_staging/p15/C_QA/P15_C_FULL_UNIT_TESTS.log`。
- 教师官方正式库 `validate.py --final`：PASS，554 clauses + 200 trajectories。
- 教师正式库 `_selftest_tools.py`：17/17 PASS；候选 JSONL 下冻结工具副本：17/17 PASS。
- 已遇到并保留的工程失败：第一次 P15-C 风险映射测试错误地将教师映射返回 dict 当 tuple 索引，触发 `KeyError: 0`，已改为直接只读解析教师映射工作簿；第一次合并末尾缺少本地 `sha()` helper，在 converter/validator 已 PASS 后触发 `NameError`，补函数并从头复跑集成通过。未改教师程序掩盖失败。
- 正式发布**不通过 / BLOCKED**：0 条新增正式知识、42 条变更记录、PDF 原文与关键数值尚无完整独立真人核验；抽样 50 条尚未审阅；B 标注需要人工审查的 5.6/5.23/6.7仍待真人逐页核准；P14既有20页 OCR pilot 的精度 Gate 仍未解除。官方 schema/数量验收通过不能替代内容准确性和人审。

## 8. 最终交付文件

- 脚本：`scripts/p15_c_field_audit.py`、`scripts/p15_c_prepare_review_and_merge.py`、`scripts/p15_c_retrieval_eval.py`
- 专项测试：`tests/test_p15_c_field_audit.py`、`tests/test_p15_c_retrieval_eval.py`
- QA/字段/检索/抽样/日志：`work/data_staging/p15/C_QA/`
- staging 合并、候选 JSONL、逐格差异、semantic audit、工具副本回归、hash manifest：`work/data_staging/p15/merged/`

**结论**：P15-C 独立 QA、A/B 候选集成与教师机器终验交付至 `READY_FOR_OWNER_REVIEW`。正式发布门禁仍为 `BLOCKED_PENDING_HUMAN_REVIEW`；Owner 应安排非抽取人的 50 条真人审查、逐字/数字/矩阵核对后再决定发布。不得将本报告中的工具/schema PASS解释为标准原文已核真。
