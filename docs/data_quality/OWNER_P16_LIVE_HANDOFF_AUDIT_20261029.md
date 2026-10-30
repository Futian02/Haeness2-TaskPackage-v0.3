# Aetheris P16 | Owner 当轮实时独立复核与收口裁决（2026-10-29）

**状态：EVIDENCE_PACKAGE_ACCEPTED / TEACHER_CONTRACT_MACHINE_PASS / DATA_CONTENT_BLOCKED / C_GATE_DESIGN_FAIL / FULL_SUITE_ENV_FAIL / OFFICIAL_RELEASE_FORBIDDEN**

## 0. 本报告的新增证据与边界
本报告基于当前 DevSpace 真实工作树，实际读取根 AGENTS、P16 A/B/C、P15、Owner 报告、教师技术验证方法与填写指南，执行下述测试/源码审查。仅新增本报告；不修改老师上游、P15/P16 A/B/C 文件、正式数据、数据库、服务或模型凭据。当前无法在此通道直接观看私人原标准图片像素，GB/T 30579 的具体字符差异仍待独立原图视觉复核；没有将已有机器视觉报告冒充本次独立人工签字。

## 1. 当前独立复测结果
- `.venv-langgraph/Scripts/python.exe -B -m scripts.owner_p16_independent_readonly_audit` 实跑：A 42条，73格；机器结果 MATCH 28、AMBIGUOUS 13、CONTRADICTS 1；随机50+定向42，重合2，唯一90、人签0；剩余表格211、DM字段1312、补充标准56、建议11；预览554条，修改42、无增删。
- `python -B -m scripts.owner_p16_target_pdf_readonly_smoke` 实跑：TSG21源PDF index78文本含8.2.3而无8.3.12；index83包含8.3.12与“安全附件检验”。这是独立PDF文字层证据，页脚印刷79仍待视觉审核。GB/T 30579原始PDF中文文字层乱码，index14/15/38/57无法用get_text确认5Cr或注氢文字。
- 教师正式库原版 `validate.py --final`：554/554 clauses、200/200 trajectories PASS。
- 教师P16预览库原版 `validate.py --final --clauses work/data_staging/p16/merged/P16_CLAUSES_PREVIEW_ONLY.jsonl --trajectories upstream/05_提交区/trajectories.jsonl`：554/554+200/200 PASS。
- 正式工具 `upstream/05_提交区/_selftest_tools.py` 与 P16候选独立probe的相同自测：各17/17 PASS。
- 系统Python `python -B -m pytest -q tests/test_p16_a_evidence42.py`：5 passed；主venv `unittest tests.test_p16_b_fidelity_retrieval tests.test_p16_c_human50_gate -q`：10 tests OK。
- 主venv `unittest discover -s tests -q`：**230 tests / 1 ERROR / 3 skip**，约62.5秒，P16-A测试顶层`import fitz`因主venv缺 PyMuPDF 失败；不是全量绿。
- 实际`scripts/p16_b_fidelity_retrieval.py:222-230`的`expand_case(cid,q)`依赖五个已知测试case_id的专用扩词；37/42→42/42是in-sample实验值，不代表未知用户query的检索泛化。部分gold存在相关性争议。

## 2. 额外发现的P0级 C 门禁设计失效（此前Owner报告未独立列为硬缺陷）
**P0-C1：人工审查后门禁反而报错。** `scripts/p16_c_machine_gate.py` 的 `human_signatures_not_fabricated` 只允许登记表`reviewer_identity/signature/decision`全部空白，并要求manifest `human_signed == 0`才 PASS。真实审签写入任何字段时`no_signature=False`使检查 FAIL，即使来源可信、42条已核签也不可能得到当前宣称的成功路径。
**P0-C2：发布门禁不计算真人通过数。** 同脚本 `human_release_gate`只判断冻结manifest中的`human_signed == 0`，否则显示PENDING；未从50条随机审查计算>=48通过及42条变更审签/纠错；最终JSON `human_review_signed: 0`被写为常量。脚本不具备正式判定真实人审95%条件的能力。
**P0-C3：重新生成可能清空人审结果。** `scripts/p16_c_prepare_human50.py`直接以`open("w")`重建`P16_C_HUMAN_REVIEW90.csv`，把reviewer_identity、签名、时间、decision全部写成空值；同时`P16_C_PREP_MANIFEST.json`固定重写`human_signed:0`。**一旦人审开始，不可再次运行该准备脚本写同一路径**；必须分离不可变机器快照与append-only/审核人拥有的审签数据，备份原件并保护覆盖。
**P1-C4：门禁PDF图片检查仍主要是文件存在/来源哈希/索引非负，不核索引<实际页数、图片内容真属该索引，也无法代替人眼确认页脚；`official_files_modified:false`写死，不能由这一字段证明正式文件没变。** 应比较源PDF真实页数与image哈希/渲染manifest，正式文件哈希绑定开工冻结baseline，人工验签独立门禁。

以上是静态源码的确定性设计问题，不是已经有人签署被抹掉：**当前确实仍是0人工签字**。禁止试图通过填假签名调绿。此类漏洞使“机器审核合格”与“能够放行”之间缺乏可信状态转换。

## 3. 内容风险与审查优先级
- P0：TSG21 §8.3.12 错页定位index78→83只出修正提案，不写旧台账。
- P0：30579 §5.6 的材料牌号3Cr/5Cr、烃相/轻相、注氢/注氨、焦化蜡油遗漏、5.6 F/H引用范围均须核原页；现为机器候选而非人工确证。
- P0：30579 §5.23的49–66℃局部NH4HS气相条件、材料耐蚀性分类；§6.7湿H2S气相分压/溶液浓度与不同子型温区，不得误设为通用过滤条件。
- P1：26610.5表2/3共10行数值及单位、26610.3图1共25格颜色虽机器MATCH，尚无人签；211条表格缺逐格真值，其中20条OCR仅作导航；82模式G-N/O-V共1312字段、56补充章都不能标成人工完成。
- C端固定50随机样本来自seed20261029，50中42变更仅2条，因此总共90唯一对象须真实人审；随机50至少48条通过，42条需全部裁决；缺签时通过率**未知**。

## 4. 最短收工路线：P16内修补，不创建P17
1. **先修门禁状态机和审签数据防覆盖**，使用独立且不可变的machine review index；signed review ledger放隔离目录，保持人审手工字段在任何脚本重跑后原封不动；审签可信度由审核人/Owner在外部授权核实，机器不能只看字符串是否非空。编写临时伪输入的离线正反测试（禁止伪造正式审签）模拟 47/50 FAIL、48/50且42通过/待改修正 PASS、签名缺失FAIL、双人冲突BLOCKED；无Owner批准仍必须RELEASE_BLOCKED。
2. **小范围校验真实PDF**：TSG两页索引对照后更新仅P16工作副本定位，30579 5.6/5.23/6.7逐字段原图裁决，将source quote、bbox、数值条件对象写进proposal；人工未签则不合并正式。
3. **检索去case_id**：查询扩展只依赖query语义、结构化索引与冻结领域词典；>=30全新盲测及相关负例，单独计算Recall/MRR/NDCG，保留baseline、成本与失败明细；不得改教师工具或偷看gold。
4. **测试环境统一**：在测试依赖锁中明确PyMuPDF的隔离环境配置；不改生产依赖、不直接跳过强制PDF专项；使主venv全量0 ERROR，再实跑原版teacher validate（正式和候选各554/200）、17工具自测、P16专项。
5. **真实人工签核**：50随机、42改动逐项独立交叉审核；不强行补空字段、TSG周期、材料/温度阈值；现有0签时保持PREVIEW_ONLY。任何正式发布须Owner再次书面授权，独立执行者备份、原版转换、校验、哈希锁定和验证后才写正式层。
6. 老师真实100组模型原生工具解析、至少5轮连续真实工具调用、ModelScope可访问演示是独立最终交付门。P16数据Gate绿后仍不得宣称整个项目验收完成。

## 5. 任务分工建议及唯一写入域
- 当前P16-C Codex后续只修 `scripts/p16_c_*.py`、`tests/test_p16_c_*.py`、`work/data_staging/p16/C_GATE/**` 和 `docs/data_quality/P16_C_*.md`，优先P0-C1~C3；不可触碰任何真人签署文件，先备份后审计修改。严禁在生产/上游写数据。
- 当前P16-B Codex后续只修B独有脚本/测试/隔离检索评测，删除对case_id的专用扩词并建立盲测；保留旧in-sample报告为历史结果。
- A负责源图定位/5.6等人工裁决提案；不绕过C审批。Owner独立审计文件单独归Owner写。

## 6. 结论
**教师Schema和工具自测通过；内容专业真实性尚被锁；C人审Gate当前逻辑尚不能支持实际验收转换。** 最优解不是继续增加框架或扫1385页，而是先修C门禁保护已审结果、复核少量高危源图、去检索先验、最后由真人完成签核。项目保持NOT_READY_FOR_RELEASE。

## 7. 15:20+ 再次交付后的增量核验
用户报告A REVIEW_BLOCKED、B PREVIEW_ONLY、C READY_FOR_OWNER_REVIEW。DevSpace核验到A/B/C报告最后写入时间分别约12:22/13:01/13:02；三个原P16窗口没有出现较上一轮Owner报告更新的修补稿，尚未执行 `docs/CODEX_P16_FINAL_BOUNDED_CORRECTIONS_20261029.md` 中的C门禁、B去测试ID先验及A可疑语义修复。本轮只读跑 `owner_p16_independent_readonly_audit` 仍返回42/73/90/0、211/1312/56、554/42、同一TSG定位错误；B/C十项unittest实跑10/10 PASS；源PDF文本复核TSG index78无§8.3.12、index83有§8.3.12，GB/T30579文字层仍乱码。这是当前状态的延续，不是新一轮人审完成。

**新增P0-C5：机器FAIL会被BLOCKED覆盖。** `scripts/p16_c_machine_gate.py`当前优先选择任何BLOCKED作为总状态，再选择FAIL。即使随机50抽样被意外改变、渲染图片丢失、审核身份检查失败，若真人签核还没完成，根状态仍报`BLOCKED_PENDING_HUMAN_REVIEW`，而非`FAIL`。应以FAIL优先，分开报告`machine_integrity_status`与`human_release_status`，禁止把数据损坏归因为正常待人审。

**新增P1-C6：抽样冻结校验不足。** `fixed_seed_sample`当前只核50行和seed字符串，不逐个比对P15冻结50条的clause_id、顺序、来源JSONL哈希。必须绑定freeze manifest/ID清单和原始数据哈希，反例测试替换一个ID但保持seed与行数应FAIL。

**Git污染边界**：`git -C upstream status --porcelain`实际返回跟踪RBI原表`M`、一份13条候选未跟踪、一份历史备份未跟踪；RBI Excel相对Git HEAD二进制文件大小89233→90842字节。因此本轮只能声明“当前官方源SHA与P16 C记录的快照一致”，不能声明“upstream Git工作树干净/与HEAD逐字节相同”。这些改动属于历史状态，未做reset/覆盖/归因；后续冻结需同时记录`HEAD blob`和当前`working tree SHA`，确定Owner认可的源基线。

**Owner最终复审**：A证据导航交付PASS、B隔离数据审查队列PARTIAL、C隔离预览PASS但**release gate implementation FAIL**；专业原文审核和发版均BLOCKED。下一次Codex最优先只继续C任务：保持所有既有签名字段/原始输入只读，修复P0-C1/C2/C3/C5和P1-C6，新增带伪签名的独立临时fixture测试，勿把fixture写入真人审签表。
