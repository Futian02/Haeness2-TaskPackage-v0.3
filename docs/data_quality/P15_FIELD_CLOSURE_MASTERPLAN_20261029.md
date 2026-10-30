# P15｜标准数据集字段质量收口总计划（Owner核查版，2026-10-29）

状态：**PLAN_READY / ORIGINALS_FROZEN / PILOT_REVIEW_BLOCKED**。本文件是独立现场核查后的Codex执行规格，不表示所列数据已修好。主项目：`D:\作业\竞赛\计算机设计智能体\机械智能体`。

## 一、Owner逐字段实测——不是猜的
使用只读OOXML解析器 `scripts/owner_p15_field_coverage_readonly.py` 对 **upstream原本** 读取真实数据行（不把格式化空白行计入）。源：`upstream/01_RBI标准/条款摘录表_RBI.xlsx`（485行=472已入库+13未签草稿）、`upstream/02_损伤机理参考/条款摘录表_损伤机理.xlsx`（82行）。这不是候选Excel数目。

### RBI（485行）
A-F ID/标准/条款/印刷页/标题/原文均485/485；G失效可能性30；H后果45；I原始风险25；J统一风险25；K检验周期**0**；L检验方法54；M适用材质**0**；N介质**0**；O-P温度上下限**0**；Q-R压力上下限**0**；S设备32；T“其他适用条件”472；U抽取人472；V复核人**0**；W备注485。
按标准：26610.1草稿13；.2 134（L42）；.3 141（G30/H35/I,J25）；.4 139（G-J全空）；.5 26（H10）；TSG21 32（L12/S32）。13草稿 U/V皆空。
**解释**：G–J不是普通记录必填项。比如.4是定量失效概率/因子，不等于直接失效可能性“等级”。26610.2检验时间常依风险条件动态决定，不可擅自填K固定年数。TSG安全状况1-5≠RBI统一L1-L4。M/N/O-R也只在条款明确设备适用对象/边界时填；真空值应保留并标NOT_APPLICABLE或SOURCE_UNSPECIFIED。
**真问题**：T虽然472/485非空，样例含“25格拆行顺序”等管理性解释，不一定是适用条件；应把非条件文字移到W备注。F“表2中，某类别对应数值”存在**解释性转述**，与教师要求`content_raw`逐字摘录冲突风险极高。P14 B线启发式标**221条**（不是221条已判错），其中.3 78、.4 103、.5 25、.2 15；P14原生PDF文字匹配58 exact/19片段/408 no-match因PDF编码/跨栏/表格存在大量假阴性，不能拿这些数算准确率。

### 损伤机理（82行，全部GB/T30579-2022）
A–F 82/82；**G–N八段式 8×82字段全非空**；O枚举材质74；P枚举介质26；Q温度下限20；R温度上限13；S/T压力上下限0；U设备81；V其他条件82；W抽取人82（当前姓名“代航”，须本人确认真实归属及教师学号_姓名格式）；X复核人0；Y备注82（含AI辅助、待人工核对说明）。
**好消息**：GB/T30579附录A第5–9章模式编号29+16+16+11+10=82，82个主模式编号已齐全；现阶段是**八段式内容及每个适用条件真实性、边界**，不是缺损伤模式主条目。
**高风险语义**：5.23“酸性水腐蚀(碱式酸性水)”Q/R当前49/66℃，V解释此区间为硫氢化铵气相析出温度；不能**未经PDF复核**直接等同整个机理适用温度，否则误排其它工况。5.6“环烷酸腐蚀”Q/R=177/242℃，V却含另一个218～400℃的轻相介质条件；需要辨别多物理场景、温区与金属温度，不能任选一个覆盖。6.7“湿硫化氢破坏”V含0.0003MPa**H2S分压**，不能写成S/T“设备操作总压力”。5.23 O列含“300系列/双相”但I列表述为“耐蚀性较强”；条件表中的材料候选不能被误认为全都**高易感**，要保存susceptibility vs resistant语义到分层受控属性（若教师25列无字段则写有据V条件，不改合同）。
**结论**：有数字不等于具备同一语义的数值边界；将“某子现象发生窗口”强填为整个机理过滤区间会导致工具错误拒绝，P15必须对DM82所有Q–T与V做专项审查。

## 二、PDF是真用多少，不是看解析页数
12 PDF共1385页：01 RBI六份共461页；02机理与补充六份共924页。P14逐页清单1385/1385，无人逐字签核；Pilot Tesseract 30579标题6/8、正文有错漏，未达正式提取质量Gate。
正式clause 554=RBI472+DM82。RBI正式覆盖.2/.3/.4/.5/TSG21共5份；26610.1只有额外13条草稿未入库。DM正式只包含30579；GB/T150.1/.3/.4、151、21447共5份PDF未按教师条款转入正式JSONL。**“没入库”≠“应该全塞进RBI/DM表”**：设计/制造标准不自动是RBI风险或腐蚀机理。须列每章节`usable_as_mechanism / risk_inspection / auxiliary_background / out_of_scope`，确有可入教师两类时才写候选，否则输出受控辅助索引、不污染教师数据。
P14候选RBI472+DM82和正式554逐字段相同：仅证明旧数据转换链正确，没有数据增量。新P15不能继续只做影子复制，必须交机器可核的真实修正差异（或因来源不可核而明确阻塞）。

## 三、教师数据字段分类规则（绝不可用“非空越高越好”评分）
每个cell都要产出`field_class`之一：
1. REQUIRED：A–F + U/W抽取人（必须真实归属），DM G描述不得空，风险矩阵G–J按真实表格单元，具体要求以teacher convert为准；
2. CONDITIONAL_SUPPORTED：来源原文明确、且与列语义一致时填写。例如`process_temperature_min`与`NH4HS气相析出温度`不能混为一谈；
3. NOT_APPLICABLE：标准没给这种类型的属性，明确空；
4. SOURCE_UNSPECIFIED：该条可能需要但原文没提供（非编造），明确空；
5. REVIEW_NEEDED：原文/OCR/表格/术语/页码未充分核对，不可发布；
6. PROPOSED_CORRECTION：新值附`standard_code, printed_page, pdf_page_index, bbox/table_row_cell, evidence_quote, method, reviewer_status`，只在stage中写，不直接覆盖正式表。

`field_completion_recall = 已有来源证据且正确填写的字段数 / 来源已明确支持该字段的字段数`；单纯空值率仅用于定位工作，不能作为达标分。
F摘录必须逐字且≤300字；G-N可结构化忠实转述，但不能伪造假设；原文中的“较耐蚀”与“易腐蚀”不得互换。数值单位、上下限、开闭边界、条件对象、证据表格行列100%审查。
真人抽取/复核身份不得伪造；模型互审不是教师要求的真人交叉复核。未知保持空，AI机器核查标机器身份。

## 四、三个Codex窗口并行职责与写入边界
- **A RBI Field Repair**：独占`work/data_staging/p15/A_RBI/**`、`docs/data_quality/P15_A_*.md/csv`、`scripts/p15_a_*.py`、`tests/test_p15_a_*.py`，读01 PDF及RBI模板/P14候选。对485原记录优先221高风险转述，T非适用条件混放、G-J/TSG分级与检验方法/周期审查、13待签草稿。输出可比较的修复候选xlsx + per-cell source ledger+变更/未决清单。不改原上游。
- **B DM+Supplementary**：独占`work/data_staging/p15/B_DM/**`、`docs/data_quality/P15_B_*.md/csv`、`scripts/p15_b_*.py`、`tests/test_p15_b_*.py`，读02 PDF与DM模板。全部82模式八段式和温压/敏感材料条件审查，补充五标准逐章语义分类并抽取确有价值的候选，输出候选xlsx + 辅助索引 + 来源 ledger。不得对源PDF或老师正式库写。
- **C independent QA+integration**：独占`work/data_staging/p15/C_QA/**`、`work/data_staging/p15/merged/**`、`docs/data_quality/P15_C_*.md/csv`、`scripts/p15_c_*.py`、`tests/test_p15_c_*.py`，先独立建立字段规则和冻结teacher source真值/teacher convert对照样例，检查 baseline；A/B提供候选后唯一集成进入merged、使用原官方convert.py在staging生成候选clauses.jsonl、teacher validate官方校验、工具/Graph检索回归，生成固定seed50条**待真人签核**样本。不能自称独立真人审核。
三窗口同一worktree可以协作但**文件独占不可冲突**；A/B都不可写C合并区、C不可写A/B候选；不能全局Git清理/commit/改upstream/git sparsecheckout/覆盖同一xlsx。

## 五、OCR/文档解析选型（只需一个主方案+一个独立复核）
首选把**已渲染的标准页**送给本地PaddleOCR PP-StructureV3（表格/公式/版面），困难样本另用MinerU或PDF视觉模型独立核对，不要把三个大包全部装进主生产Python环境。先在隔离虚拟环境处理P14冻结20页，比较**准确文字+表格单元结构+读序+页脚页码**，人工不合格则继续调整方法，不拿标题6/8当达标。成熟工具： https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/algorithm/PP-StructureV3/PP-StructureV3.en.md；https://github.com/opendatalab/MinerU；https://docling.org/formats 。
本地标准PDF/截图不上传公开在线转换服务；大规模候选优先基于已存1385页P14 cache增量、不重新盲跑所有页；OCR仅疑难页。若使用大模型看图，人工reviewer仍是必需。

## 六、一轮后的实际目标、硬Gate和交付顺序
目标是**机器可核任务收敛且生成真正修正的两份候选xlsx**，不是伪称全部标准100%真人签名。
A: 485行完整逐字段triage台账；221条表格风险全部定位原PDF或者加入需人工原图队列；M/N/O-R真正来源有据才填；RBI T错误归位有源修正；13草稿单独。
B: 82模式×8段共656个字段都有对应标准子条款的可定位证据或明确REVIEW_NEEDED；所有81+设备、材质与介质枚举、Q–T过程温压进行语义审计，尤其5.6/5.23/6.7；五补充标准做章节级入库/辅助/排除分类。
C: 官方Excel模板原样、冻结老师三个工具签名、所有更改记录带来源（机器定位≥100%，不能达的保持待核），老师convert/validate/17工具/100条合成检索回归；正式JSONL与候选差异显式标新增/修改/删除并解释，零静默删行。50条随机样本独立抽签模板供真人交叉核验，≥48/50才能宣布老师指标达标。
禁止“AI复核已签/95%人工准确率/全PDF入两表”。P14的20页无ground truth是硬Gate未消失；无法确认的F、数值、适用性不发布。不要把这类限制变成对可机器可核工作的停工理由，先将有来源证据的候选和缺口列表全部完成。
Owner正式批准后另安排**唯一发布窗口**核算真实签核、转换并备份正式源表，避免并发修改老师文件。真实LLM100组解析和ModelScope公开部署另属教师终验线，不能因数据蒸馏而声称通过。

## 七、Owner优先看这些可视化交付
`docs/data_quality/P15_OWNER_FIELD_AUDIT_20261029.md`（初始事实）；
`P15_A_FIELD_CHANGELOG.csv`/ `P15_B_FIELD_CHANGELOG.csv`：每个cell old/new/action/证据定位/status；
`P15_C_INTEGRATION_ACCEPTANCE.md`：候选 Excel/JSONL 差异、0错误记录、覆盖提升、风险未决、抽样50条与人审状态；
`work/data_staging/p15/merged/`：两个真正带修正的候选xlsx及clause候选，不覆盖原文件。
