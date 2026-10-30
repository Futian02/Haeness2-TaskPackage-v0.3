# P14 标准数据蒸馏阶段审计

**状态：`REVIEW_BLOCKED`**（机器可验证基线收敛；20页内容精度 gate 未通过；等待真人逐页/逐字段复核）。  
日期：2026-10-29。  
边界：全部源 PDF、两份源 Excel、教师工具、正式 clauses/trajectories 均只读；所有候选仅写 `work/data_staging/p14/`。没有修改 P13 的 backend/frontend/orchestration，没有提交或部署。

## 1. 执行结论

本轮完成 12 份 PDF 的 1,385 页原生文本/页面结构机器盘点，输出逐页 `P14_SOURCE_COVERAGE_MATRIX.csv` 与章节/条款覆盖 `P14_CHAPTER_COVERAGE_MATRIX.csv`；建立 20 页分层 pilot（8页 30579、8页 26610.2/.4/.5、4页 TSG/补充标准），生成页面图像、原生文本页缓存和 Tesseract 诊断 OCR；完成两份教师模板的隔离副本；用教师原版 `convert.py --inputs ... --output ...` 生成候选 JSONL，并用原版 `validate.py --final` 验证。

**精确性 Gate 没过**：P14-A 的 8 个 30579 样本页 OCR 标题精确命中 6/8，正文 OCR 有可见错漏；本轮 20 页 OCR 没有真人逐字 ground truth，因此准确率不能计分。PDF 原生 CMap 对部分标准出现乱码/字符映射失真。没有资格扩批新条款，也没有把任何内容标为 `visual_checked` 或 `human_verified`。这是按“20页先核精度再批量”的任务门禁暂停，不把自动校验冒充人工审查。

当前可交付的两个候选 Excel 仅为**冻结基线的隔离复制件**：RBI 采用 upstream Git HEAD 472 条稳定版本（排除工作树中新添的13条未签候选），DM 为现有82条副本；未添加、改写、补签任何记录。用这些副本转换所得554条候选 JSONL 在所有字段上与当前正式554条 JSONL 完全一致（0 ID 差异、0记录字段差异），所以这验证了转换链路/模板基线，不等于完成新蒸馏或内容真实性核验。

## 2. 输入盘点与机器证据

| 文件组 | PDF页数 | 本轮内容 |
|---|---:|---|
| GB/T 26610.1-2022 | 34 | PDF SHA、页索引/文本、条款表记录匹配提示 |
| GB/T 26610.2-2022 | 25 | 同上；文本层布局/编码问题显著 |
| GB/T 26610.3-2014 | 14 | 同上；矩阵/表格行仅作为待核条目 |
| GB/T 26610.4-2022 | 164 | 同上；数值表格需要视觉逐格核验 |
| GB/T 26610.5-2022 | 53 | 同上；面积/经济后果阈值不得从 F 列转述直接入库 |
| TSG 21-2016 | 171 | 同上；条件周期须区分安全状况等级与 RBI 风险等级，并核对修改单 |
| GB/T 30579-2022 | 163 | 82 条既有记录字段/页码索引筛查，五章计数 |
| GB/T 150.1/.3/.4-2024、GB/T 151-2026、GB/T 21447-2018 | 761 | 机器章节覆盖与适用性分类；非 DM 条款不强塞入库 |
| **合计** | **1,385** | 12 份 PDF，只读 |

机器页缓存 `work/data_staging/p14/page_cache/native_pages.jsonl` 覆盖 1,385 个唯一 `(source_pdf, pdf_page_index)`，记录 PDF SHA-256、PyMuPDF 原生文本、文字块 bbox、页尺寸、短文本/可疑编码提示、机器检测章节/图表标记。该缓存是定位证据，不是原文准确性的判定。页码均保留 `pdf_page_index`；印刷页码仅记录为 `unverified_guess`，没有确认的留空。

章节层：`P14_CHAPTER_COVERAGE_MATRIX.csv` 共99行，包含 GB/T 30579 第5–9章及附录A待核项、RBI 摘录中实际出现的条款前缀、补充标准扫描到的37个章/附录范围。RBI 章节名/边界不能从损坏的原生文本自动稳定解出；该矩阵明确把现有工作簿前缀统计标成不完整的机器覆盖，不宣称六份 RBI PDF 的章级内容全覆盖。

## 3. 20 页 pilot 与错误回放

重现：

```powershell
python scripts/p14_inventory_pilot.py inventory
python scripts/p14_inventory_pilot.py pilot --render-scale 2
python scripts/p14_ocr_pilot.py
```

pilot 页清单：`work/data_staging/p14/pilot/pilot_20_pages.csv`；2×原页渲染在 `pilot/rendered_pages/`，导航接触表 `pilot/pilot_contact_sheet.png`，OCR 诊断文本与20行OCR计数在 `pilot/ocr_text/` 和 `pilot/pilot_ocr_metrics.csv`。8个30579页横跨第5–9章；8个RBI页取自26610.2/.4/.5；另4页取自TSG、150.1、151、21447。20页均未产生可入库断言，`candidate_count=0`。

| 方法/结果 | 观测 | 结论 |
|---|---|---|
| PyMuPDF 原生文本 | 1,228页≥80个非空字符，157页短/空；多份 PDF 的文本层有错字形/CID/表格读取顺序问题 | 字符数不是可读性/逐字准确率。保存全量原生文本和 bbox，仅机器定位 |
| 30579 8页 Tesseract | 子任务 A 测得标题命中6/8；另报告正文 OCR 替换/漏识。印刷页2→PDF第8页（0基index 7）只抽查一个锚点 | 只能辅助定位；不能用 OCR 回填F、G-N、印刷页映射或来源字段 |
| 本轮20页 Tesseract | 已对20张2×渲染执行 `chi_sim+eng --psm 6`，记录 OCR 文本长度；无人类逐字ground truth，精确度未评分 | 不构成 pilot precision pass；机器抽取 gate 保持关闭 |
| 图/表 | 接触表可见大量表格、公式与图，但没有对全部数字、单位、脚注做逐格双人对照 | RBI 数值/边界不入新增候选；需后续视觉审查 |

失败记录：第一版页面文本质量启发式把可打印字符权重错误，产生过度标记；已改为“字符可打印/文本长度”诊断且没有据此改写内容。B线逐页匹配中 `.2/.4` 等大量 no-match 可能源于编码/表格顺序，不能当作错误率。机器错误与改进记录保留在 `work/data_staging/p14/agents/{A,B,C}/`。

## 4. 原始记录与 Excel/JSONL 候选

### GB/T 30579-2022

- 原DM表：4 sheets、25列、82条；按章节统计 `5/6/7/8/9 = 29/16/16/11/10`，与任务书给定数量一致。只证明编号计数，不证明附录A或内容覆盖完整。
- G–N 八段式82/82非空、F列82/82不超过300字；复核人82/82空。抽取人字段虽有填写，但机器无法验证签署身份。
- A线将原82行整理为82个 `machine_located/unreviewed` 审计候选；内容保存为哈希和字段摘要，不把旧值冒充新抽取。起始页映射仅p.2→PDF物理页8（0基index 7）视觉确认，其他81条仍待核。

### RBI 六份标准

- 当前工作树 RBI 文件为485条（472个原基线 + 13个未签 `.1` 草稿）；当前 SHA-256 `e43f7b0d3381a38fa648c2505e27d1c87893af5aea89aa119097dbfc49c6b7bf`。开工时该文件已是 Git modified，另有两个既存 untracked 文件；本任务保持原状。
- staging 的 `条款摘录表_RBI_candidate.xlsx` 来自 Git HEAD `38cf71bf9f9868cfa531729cda70dea2e2857b3a788ec1a67f56d27ef01512f9`，4 sheets/23列/472条；排除13条未签草稿，不伪造抽取人/复核人。
- B线只读审计当前485行：复核人485/485为空；13条 `.1` 候选抽取人/复核人均空。机器匹配结果58条 exact normalized page、19条 fragment、408条 no-match，受 PDF 字体编码/跨页/表格影响，**不换算为正确率**。221条“表X中”等表达是启发式视觉复核队列，不是221条已判错（较Owner先前估计210条更宽的regex，多出的11条未裁定）。
- 当前485行统计：检验周期K=0、适用材质=0、介质=0、温度/压力范围=0；检验方法54、设备类型32；不因列空而猜填。

### 五份补充标准

C线逐页机器扫761页、记录37章/附录范围。GB/T150.1/.3/.4偏通用设计、制造和验收，GB/T151主要为换热器设计制造背景；不直接填25列DM。GB/T21447第4.3表1–4保留1个**空引文**的条件性机器候选，表格单元格/单位/适用性均未核，暂不进教师 Excel/JSONL；防腐层、阴极保护章节归辅助控制背景。

### 两份Excel与官方转换器

隔离候选文件：

- `work/data_staging/p14/条款摘录表_RBI_candidate.xlsx`：4 sheets，23列，472条，SHA如上。
- `work/data_staging/p14/条款摘录表_损伤机理_candidate.xlsx`：4 sheets，25列，82条，SHA-256 `8bb05d1d0dacbe542a1713a317a769f064a9c6c7ad34053417f0dbba01a0d62e`。
- 转换命令（从 `upstream/` 当前目录运行；输入/输出均为 staging 绝对路径）：

```powershell
python 04_接口文档/convert.py --inputs `
  "D:\作业\竞赛\计算机设计智能体\机械智能体\work\data_staging\p14\条款摘录表_RBI_candidate.xlsx" `
  "D:\作业\竞赛\计算机设计智能体\机械智能体\work\data_staging\p14\条款摘录表_损伤机理_candidate.xlsx" `
  --output "D:\作业\竞赛\计算机设计智能体\机械智能体\work\data_staging\p14\clauses_candidate.jsonl"
```

- 实测：教师转换器读取554条（DM82/RBI472）、0错误、0提示。候选 JSONL SHA-256 `0bf853460b60f51dc21f2d05a909479c00ad18abbf203be3081169cff2fb16e4`。
- 独立按 `clause_id` 对比正式 `clauses.jsonl`：candidate 554、official 554、candidate-only 0、official-only 0、记录字段diff 0。
- 候选校验：原版 `validate.py --final --clauses <staging clauses_candidate> --trajectories <只读 upstream trajectories.jsonl>` 退出0；554/554 clauses、200/200 trajectories、多步144、三特殊类型各15。它说明格式/规模门槛通过，不验证 PDF 原文真实性，也不升级人工复核证据。
- 原三教师工具 `upstream/05_提交区/_selftest_tools.py`：17/17通过，源工具只读。
- 另有L2聚合候选清单 `work/data_staging/p14/candidates/p14_source_candidates.jsonl`：82条DM既有记录 + RBI 485行源记录 + 1个补充标准辅助项，共568条唯一候选ID；其中221条RBI表格解释风险标记。所有候选仍是 `machine_located/unreviewed`，不表示正式可导入记录。

## 5. 自动化测试与复现入口

```powershell
python scripts/p14_inventory_pilot.py inventory
python scripts/p14_inventory_pilot.py pilot --render-scale 2
python scripts/p14_ocr_pilot.py
python work/data_staging/p14/agents/A/p14_dm30579_audit.py
python work/data_staging/p14/agents/B/audit_rbi_readonly.py
python work/data_staging/p14/agents/C/scan_supplementary_standards.py
python scripts/p14_merge_candidate_registry.py
python scripts/p14_finalize_coverage.py
python -m unittest tests.test_p14_pipeline_artifacts -v
```

P14新增 artifact tests：**5/5 PASS**（1,385页矩阵唯一性、Excel模板结构/记录数、转换字段级diff、L2候选非人审状态、20页pilot没有未评准确率候选）。原始 teacher selftest：**17/17 PASS**。官方转换、候选validate的完整控制台输出由运行日志在本地命令行复现。

项目全量 unittest 额外运行：**194 tests / 1 failure / 3 skipped**。失败为既有 `tests/test_p5a_lease_event_integrity.py::test_failed_and_completed_run_reject_old_worker`，终态 `failed` 分支观察到事件序列 `[1,2]`，测试期望 `[1]`；隔离重跑仍复现。该测试/实现位于本任务禁止修改的 P13 产品代码边界，本轮未改动处理。P14 专项5项和数据生成/teacher 回归均独立通过；整体状态仍为 `REVIEW_BLOCKED`，该项目全量失败也保留为 Owner 待处理项。

## 6. 未决与下一步

请查看 [`P14_UNRESOLVED_ITEMS.csv`](P14_UNRESOLVED_ITEMS.csv)。最小解除阻塞顺序：

1. 安排非抽取人的真人 reviewer，用来源页图逐项交叉核对 pilot 20页里的页码、条款号、F逐字、表格行列/单位/脚注及适用条件；记录真实姓名、字段级差错和复核意见。未签之前pilot不算通过。
2. 若视觉发现OCR或页码系统性错误，修复识别策略并重跑同一冻结pilot；如需 PaddleOCR PP-StructureV3，先验证本机环境与受控使用，仍以PDF视觉为准。
3. Pilot accuracy gate 达标后，才对30579已有82条做逐条核验，并分批10–30页扩展；RBI优先复核26610.5面积表、.4数值表、.3矩阵、.2检验策略、TSG条件周期和13条未签 `.1` 草稿。
4. 从准备提交的数据用固定seed随机抽≥50条，必须由独立真人签署，≥48/50准确；机器/AI不得签名或代核。
5. 人工核对完成后重新生成经核准候选 Excel→原convert→candidate validate，交Owner另行批准后才可安排正式源数据整合。本轮没有达到该批准门槛。

**最终阶段裁定：`REVIEW_BLOCKED`。** 交付候选、覆盖矩阵、质量审计、未决清单和可重复脚本；未宣称“已完成标准大规模蒸馏”或“正式数据正确”。
