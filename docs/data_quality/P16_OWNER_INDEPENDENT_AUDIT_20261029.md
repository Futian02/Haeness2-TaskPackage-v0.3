# P16 Owner严格独立验收报告（2026-10-29）
项目根目录：D:\作业\竞赛\计算机设计智能体\机械智能体
审查状态：**EVIDENCE_PACK_PASS / MACHINE_CONTRACT_PASS / CONTENT_REVIEW_BLOCKED / FULL_SUITE_ENV_FAIL / NO_RELEASE_AUTHORIZATION**

## 1. 独立实际执行，不是转述Codex
- 直接读P16-A/B/C报告、A42证据卡审签CSV及73格台账、B211表格风险台账及1312字段风险台账/11条提案、C50随机/90去重审签CSV、P16-C门禁JSON、P16预览JSONL。新增只读审计脚本 `scripts/owner_p16_independent_readonly_audit.py`。
- 运行该脚本：P16-A42条：28 MATCH / 13 AMBIGUOUS / 1 CONTRADICTS；73格关联一致。随机50 + 变更42（交叉2）=90个唯一真实人审对象，签核**0**。剩余RBI表格211条、DM G–N/O–V字段1312项、补充标准待核章节56项、P16-B提案11项。P16实际预览554条，对正式554修改42条（44 JSON字段变更）、新增0、删除0，SHA256=`7efebc07786fd6232da05d21c43323486f3b15d1ff4edd731075755fe419d196`。正式JSONL SHA256=`a8151797ba15a6a7452dd83aaec9fab4c0a815724ca45062eb1e2bac7b4d49ef`。机器结构PASS、人审发布BLOCKED。
- P16 A专项：系统Python `python -B -m pytest -q tests/test_p16_a_evidence42.py` → **5 passed**。
- P16 B/C专项：`.venv-langgraph/Scripts/python.exe -B -m unittest tests.test_p16_b_fidelity_retrieval tests.test_p16_c_human50_gate -q` → **10 tests OK**。
- 全量统一解释器 `.venv-langgraph/Scripts/python.exe -B -m unittest discover -s tests -q` → **230 tests, ERROR=1, skipped=3**；唯一错误在A测试模块顶层`import fitz`：`.venv-langgraph`缺少PyMuPDF，而系统Python安装了。A系统Python单独过，不能宣传“单环境全量通过”；修复方式是明确测试依赖、用隔离env安装所需包，或将测试外部工具依赖移入针对测试并提供明确skip条件，**不能直接删除或掩盖测试**。
- 原正式资料 `validate.py --final`：554/554条款、200/200轨迹PASS；P16预览 `validate.py --final --clauses work/data_staging/p16/merged/P16_CLAUSES_PREVIEW_ONLY.jsonl --trajectories upstream/05_提交区/trajectories.jsonl`同样PASS。
- 原本老师`_selftest_tools.py`与P16候选隔离副本各自重新跑：均17/17 PASS。
- `git status --short -- upstream/01_RBI标准 upstream/02_损伤机理参考 upstream/05_提交区/clauses.jsonl` 无输出；脚本打印的正式JSONL哈希与C冻结一致。未改上游、正式DB、主应用、老师工具，未调用任何真实计费模型。

## 2. 明确技术正确性与真实性风险
- A的42卡引用19张原PDF页图。机器判定28/13/1不等于28真人通过。**TSG21 §8.3.12 来源定位矛盾已独立二次确认**：Owner额外运行 `python -B -m scripts.owner_p16_target_pdf_readonly_smoke`，原PDF的PyMuPDF文字层显示index78包含§8.2.3、不含§8.3.12；index83包含§8.3.12和“安全附件检验”。P15-A登记index78确属错误证据页；index83条文定位有独立文字证据，但印刷79页脚、完整图文仍待真人目视核准。此为定位缺陷，并未证明候选条文正文错误；C门禁正确阻断。GB/T30579原PDF文字层乱码，5.6材料牌号/注入点疑点仍只能归机器视觉提案，不能冒充独立文本核真。
- GB/T30579 §5.6 本轮候选F只含§5.6.1；旧版F包含部分§5.6.2形态，H仍存形态。新F的摘录范围与教师原文口径需要定向审核，不能简单说“修完”。
- P16-B源图机器观察提出**较高优先级的潜在真实错录**：§5.6 受影响材料I的`3Cr-0.5Mo`可能应是`5Cr-0.5Mo`；J字段“轻相”可能应作“烃相”；K字段“注氨点”可能应为“注氢点”，且部分焦化轻重蜡油回路遗漏。§5.23铝合金/镍基合金的“耐蚀vs易感”语义可能被O枚举遗漏；§6.7局部H₂S分压、浓度、各子型温区不可混。**这些目前只是P16-B机器视觉提案，尚未完成真人第二人逐字确认、尚未写入P16预览**；若得到真人证实才形成修复数据。
- RBI 221表格高风险基线，P15曾10条图像候选，P16余211条仍缺可靠双人单元格核对。P16-B定向20条只是页面OCR导航，不等于20条核真。DM82个模式的G–N 656格+O–V 656格=1312项列队，不是1312新条款或全数错误。五份补充PDF的56个待审章节暂分类成52设备设计制造辅助、4外腐蚀控制辅助，但具体章节标题/页界仍待核。
- 本轮所谓“数据蒸馏改进”没有再生成新正式条款：P16预览继承P15候选42条修改，其SHA与P15候选一致，P16-B的6个材料/语义提案、5个检索提案全留隔离清单。
- P16-B的46合成查询：38个有gold、42个相关ID判断；teacher/tool旧索引37/42，应用层新全字段+query-plan+RRF为42/42，MRR@20 0.816→0.952。它**未接入正式服务**，gold是合成未审核，且likelihood_method、matrix_mapping两题的gold scope本身不可靠；不可称“专业检索准确率100%”或把应用新策略当老师原工具通过验收。
- 本轮50随机样本中与42修改只有2重合，因此未来真人需覆盖两套：随机50条至少48通过（真正独立交叉核验）+定向42条逐条结果；唯一审核对象90，人工签字0不是正确率0%。
- 数据缺陷关系到后续Agent：错误合金名称→工况材质匹配偏差；烃相/轻相、注氢/注氨混淆→检索依据和设备场景变形；分压与总压/局部温区混用→错误排除候选；错误PDF索引→引用追溯失效。应先解决可靠内容再部署/宣称风险诊断。

## 3. 下一轮动作（不要再搞P17无界工程）
**P0 机器层约束闭环**：
(1) 在P16独立目录修复TSG证据locator候选，确认PDF index83与印刷79真实对应，并使审签卡同步，不动正式数据；
(2) 先以局部PDF原图对§5.6所有疑似字词、§5.23材料、§6.7分压逐字段出一份`proposed_fix + raw_pdf_quote + bbox/table + independent human verification pending`对照，人工批准后由唯一候选整合者生成P16-next preview；不能静默把11条建议合入已审候选；
(3) 统一测试环境：固定PyMuPDF开发/测试依赖或者清晰明确可选图像专项测试，与全套230项unittest兼容，不掩盖错误；
(4) 将应用层检索方案作为独立候选，先重新核两条有争议的gold，加入材料/介质反例与领域专家测试，不直接改冻结老师三工具。
**P1 人工层硬门**：准备42张已有卡+50张随机卡，安排真实审核人至少独立两人交叉核对页码、原文、适用条件、风险矩阵、数值表、与关键变更。随机50至少48条通过、42定向全部给出通过或纠错后重核、任何明确错误不能带入发布；合成AI图片卡不是人审。221/1312高风险字段按来源/数值优先级滚动核实，合法空值保留。
**P2 唯一发布**：人工批准后专人备份/哈希/事务方式替换源表及正式JSONL，老师原版convert→validate 554/200→工具17/17→全项目回归→真实检索回放。未取得Owner批准不写upstream。教师另外要求100组真实LLM原生工具解析、5轮连续调用、ModelScope公开演示，P16数据无权替代。

## 4. 交接建议
新窗口优先读取：`docs/data_quality/P16_OWNER_INDEPENDENT_AUDIT_20261029.md`、`docs/data_quality/P16_{A_CHANGED_RECORDS_REVIEW,B_SOURCE_FIDELITY_AND_RETRIEVAL,C_FINAL_RELEASE_GATE}.md`；实际磁盘与教师合同高于摘要/聊天记忆；运行`python -B -m scripts.owner_p16_independent_readonly_audit`。
