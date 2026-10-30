# Owner 独立审核｜RBI 6 PDF / 23列Excel / 正式数据与语义知识库（2026-10-28）

**裁决：FORMAL_FORMAT_AND_TOOL_PASS / CONTENT_HUMAN_REVIEW_BLOCKED。禁止写“6份PDF 100%核证”或“全部23列填满”。**
执行环境：本地DevSpace只读核验、阅读PDF与标准OOXML，不修改原Excel/PDF/老师JSONL/正在由Codex操作的前后端。只新增审计脚本和本报告、人工复核空模板。
原 Excel：`upstream/01_RBI标准/条款摘录表_RBI.xlsx`，当前90842B，SHA256=`e43f7b0d3381a38fa648c2505e27d1c87893af5aea89aa119097dbfc49c6b7bf`，有效485行；表格预格式化行保留至602，不代表有602条内容。

## 1. 四轮实际核验（均已执行）
**I OOXML源表/知识库一致性**
- 4 sheets/23列，原472行 + 26610.1新增13条=485。抽样前的472行逐单元格值**0差异**，相对于原始backup只有`xl/worksheets/sheet2.xml`改变，其余17个OOXML组件不变。
- 原472条A编号、B标准、C条号、D页、E标题、F摘录，与正式JSONL **0核心字段不一致、0缺ID**。全表重复ID=0、畸形ID=0、非法数字字段=0、F超过300字=0。
- 老师风险映射独立读`risk_level_mapping.xlsx`：25个 G/H成对矩阵格，**25/25组合唯一、25/25与映射一致、无孤立I或J**。图1在原PDF第13张图像页已实际渲染检查。
- **这些只是结构和映射一致，不证明F每句话等于PDF原文。**

**II 原PDF来源、表格视觉**
- 六PDF共461页：GB/T26610.1=34，.2=25，.3=14，.4=164，.5=53，TSG21=171；索引中449页needs_visual_review/12页needs_human_review，0页正式签署完成。OCR曾全页执行，但OCR不能成为真人审核证据。
- 正式472条的Unicode/去空格全文匹配：.2 0/134、.3 exact38 prefix92 no11、.4 0/139、.5 exact1 prefix4 no21、TSG exact17 prefix14 no1。**.2/.4 PDF文字层乱码，该项不能换算为真实错误率**。
- GB/T26610.1 第474–486行新增的13条PDF页码与短原文都通过机器定位**13/13**（印刷页+`4`=该PDF索引，U/V均空）。尚未真人视觉审核标题或设备适用性，不能算正式来源E2/E3。
- 本轮实际打开原PDF视觉页面：26610.3图1风险矩阵，26610.5表2面积后果等级，26610.4表2失效概率；26610.5的5级面积边界（9.29/92.9/279/929）与Excel第144–148行数值一致；.4表2的储存容器行第169行数值与可见表格初步对应，但未对全部孔径、设备类型、单位和科学计数法作双人逐格核对，**不可宣布整表通过**。
- **高度关注F列定义违规风险**：至少`GBT26610.5-2022-表2-a`（Excel144行）的F为“面积后果等级划分见表2。表2中等级A对应……”；PDF实际将5.4正文、表头与表格单元格分开显示，并无该句连续原文。该记录数值一致，但F属于**解释性结构化转写**而非忠实逐字原文，应将原表格内容作为可核的原文摘录，转写说明另进W备注/结构化字段。全表约**210条含‘表X中，’等转述特征**（.3 78、.4 102、.5 25、.2 5）；这只是机器排查范围，不是210条已定错。

**III 字段填充与业务语义**
- 485行每行A–F都有值；G30/H45/I25/J25/K0/L54/M0/N0/O0/P0/Q0/R0/S32/T472/U472/V0/W485。
- 现有472行U为自然姓名“代航”，并非指南示范的“学号_姓名”；另外13行U空、全485行V空。老师转换器仅硬校验U非空，**格式PASS不能替代真实抽取身份和独立审核**。
- K（检验周期）0并不允许随意给每行填同一个值；TSG21 8.1.6.1内确有首次/定期、不同安全状况等级对应的条件性周期：若要结构化K，必须按“设备/状态/等级/适用条件”拆具体行，同时不能把TSG状况等级转成RBI统一风险L1–L4。
- 适用材质M/介质N/温度压力O–R全空，可能有部分标准只给一般原则，但**不能因此认为所有PDF已抽全**。应对.2检验策略、.4失效概率表、.5后果阈值、TSG21周期逐条制定“适用/不适用/缺失”覆盖清单，而不是盲填所有23列。
- 原文F中22条提到年数/周期但K仍空，有些是**服役年限、设计年限或停车次数**，不是检验周期；不得机械转入K。
- `scripts.preflight_source_tables`返回340条**启发式复核提示**（RBI推荐方法1项，其余大多为损伤八段中的中文顿号/列表），无确定性强错，不应自动批量改写。

**IV 工具/检索与知识草稿回归**
- 老师`validate.py --final`官方**554/554 clauses,200/200 trajectories PASS**（正式RBI472+DM82）；RBI第1部分新增13候选**不在**正式JSONL中。鉴于13行U空，官方convert运行会报13个必填字段错误，保留草稿不绕过门禁。
- 老师`_selftest_tools.py` **17/17 PASS**；source check 19/19；Python测试`unittest discover -s tests -q` **145 tests OK, 3 optional skips**。
- 6个针对性老师调用：风险矩阵→ok/5出处；后果面积→ok/5出处；损伤机理湿硫化氢→ok/6出处；RBI具体材料→ok/16出处且**没有虚造风险L级或年限**；泛化词“基于风险的检验策略”→not_found；GB/T26610.1新增数据质量短语→not_found（新13未入正式库）。这些是召回覆盖缺口，不能用结构化总条数掩盖。
- `knowledge.lexical.SqliteLexicalRetriever` FTS5载入554条：能找到湿硫化氢、氯化铵、风险矩阵、检验周期和后果等级；“数据质量”查询0命中；检索排序≠专业正确。
- `knowledge/semantic_drafts.jsonl`机理卡10/10：有对应正式DM来源和quote_span，**全部E0、reviewed=false、draft_needs_review**；目前不是核证的专家结论。
- 机器用固定seed `20261028`在正式554条中随机抽50条（包括损伤机理9、RBI41），见`OWNER_RBI_RANDOM50_HUMAN_REVIEW_TEMPLATE_20261028.csv`，**只完成抽样，人工页码、逐字、条件复核均待两个人独立签署，不得冒充≥95%条款引用准确率通过**。

## 2. 最小修复路径（效率优先）
P0. 保持原Excel及官方JSONL冻结：无真人签名不能将新增13条直接convert进正式知识库，也不应回滚历史有效数据；Owner安排真实抽取人签U、独立复核人逐条核F/条号/印刷页/适用性后再填V。
P1. 对**表格转述风险最高的约210候选**按来源排序：先.5表2/3面积与经济后果，再.4表2失效频率和各表，最后.3/.2数值因子；将F忠实原文与W解释性记录分离。特别审单位、指数、区间上下界、设备类别。
P2. 对K=0和M/N/O–R=0做**按标准的适用性覆盖审查**：有明确适用条件的逐条补录，无来源的合法空值保留；对TSG21条件检验周期应拆行后填写，不等于所有K应非空。
P3. 真实双人核对50条固定样本；≥48/50通过（老师要求≥95%，50条的离散验收至少48条，原则上错≤2）。不通过先修数据再随机重新抽；签名不能由AI补。工具方面再为.2泛化检索、26610.1缺数建立少量回归题，不扩展老师3个工具签名。
P4. 仅在P0–P3核证后运行原老师`convert.py`隔离转换→diff→`validate.py --final`→三工具与知识库回归；新条款数变化时记清source→JSONL→索引版本，避免Excel/JSONL长期分叉。
**达标即收工**：必要条款原文/数值/适用性已交叉核证，合法真实U/V，老师转换+终验通过；不要为了让23列均非空而编造任意设备风险、温压、周期。

## 3. 复现命令（只读）
```
python -B -m scripts.audit_rbi_owner_deep_readonly
python -B -m scripts.audit_pdf_rbi_coverage
python -B -m scripts.audit_rbi1_quote_candidates
./.venv-langgraph/Scripts/python.exe -B -m scripts.audit_rbi_source_workbook
./.venv-langgraph/Scripts/python.exe -B upstream/04_接口文档/validate.py --final
./.venv-langgraph/Scripts/python.exe -B upstream/05_提交区/_selftest_tools.py
./.venv-langgraph/Scripts/python.exe -B -m unittest discover -s tests -q
```
注：`fitz/PyMuPDF`在全局`python`存在、主`.venv-langgraph`不包含；PDF只读两脚本必须使用全局Python。多窗口Codex正在修改前端；本轮未修改其文件。
