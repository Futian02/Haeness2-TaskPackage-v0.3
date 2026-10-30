# P2 RBI1 + LangGraph 执行证据

日期：2026-10-28  
状态：`READY_FOR_OWNER_REVIEW`（工作树交付，未签核；RBI 新摘录仍为 draft）

## 1. RBI1 独立工作副本与 PDF 核验

### 工作簿边界

- 原始教师表：`upstream/01_RBI标准/条款摘录表_RBI.xlsx`。本轮只读；SHA-256：`38cf71bf9f9868cfa531729cda70dea2e2857b3a788ec1a67f56d27ef01512f9`；教师仓库 `HEAD=d7877bf387482b2fa9b148d30860da59ccad48b3`，对应 tracked 文件差异检查通过。
- 已存在的独立候选副本：`upstream/01_RBI标准/RBI_GBT26610_1_13candidates_for_review.xlsx`（教师表之外的另一个文件；本轮未改写该 XLSX）。SHA-256：`d292a20f1487b3cedcc67d6b36ea192df15f79e3e360905f946252970e818853`。23列、13条候选、ID唯一；`clause_no` 为文本；U「抽取人」、V「复核人」13行均为空；风险、周期、材质、介质、温压和设备字段没有默认填值。
- PDF：`upstream/01_RBI标准/GBT26610.1-2022_基本要求和实施程序.pdf`，SHA-256：`af4a2b2aebe3b792635e9e14aff6b4255bcc0e20627c59bb656fae1721522c57`，共34页。脚本索引换算为 `PDF 0-based index = 印刷页 + 4`。
- `scripts/audit_rbi1_quote_candidates.py` 只读运行得到 `MATCH=13/13`。另逐页渲染印刷页 4、7、9、11、13、20、23、25，视觉检查页脚印刷页码、条款层级/标题、原文位置及适用语境；联系表为 `docs/audits/p2_candidate_pdf_contact_sheet.png`，逐页全尺寸渲染保存在 `docs/audits/p2_pdf_visual_pages/`。再逐条将副本中的页码、条款号、标题、原文与对应 PDF 页提取文本比对：13/13 条款原文在正确页面通过 NFKC+去空白规范化匹配；标题在页面上逐条视觉核对。
- PDF 字体映射导致部分标题的文本抽取使用 `犚犅犐` 等替代字符；其中 `7.1.2`、`13.8.1`、`14.3.2` 的候选标题字符串不能直接用 Unicode 规范化命中 PDF 文本。已在上述渲染页视觉核对为对应小节标题；机器抽取差异不冒充人工校验记录。

### 逐条校对与适用条件

| clause_no | 印刷页 | 标题（工作副本） | 原文/语境核验 | 条款明确条件或边界 | 结构化字段处理 |
|---|---:|---|---|---|---|
| 5.1.1 | 4 | 风险 | 正确页、条款号与引文匹配 | RBI按相对风险对装置/单元/系统/设备/组件分级；不定义特定设备参数 | 具体适用对象、风险级别留空 |
| 5.2.1 | 4 | 风险分析的类型 | 正确页、条款号与引文匹配 | 定性、定量、半定量三类方法 | 不从方法分类推定风险级别 |
| 5.2.2 | 4 | 风险分析的类型 | 正确页、条款号与引文匹配 | 定性方法使用描述性信息并形成定性结果；定量数据不足时可开展，但不能据此编造现场输入 | 不补设备、温压或风险字段 |
| 6.2.4.1 | 7 | 工艺单元中的腐蚀回路筛选 | 正确页、条款号与引文匹配 | 回路划分考虑介质化学性质、操作压力/温度、材质和运行历史；这些是方法考量，不是特定设备默认值 | 条件留在方法说明，不填材质/介质/温压边界 |
| 6.4.1.2 | 7 | 确立评估工况的通用要求 | 正确页、条款号与引文匹配 | 评估工况指运行极端工况，并需监控关键工艺参数使其保持在评估工况内 | 无通用数值限值，温压边界留空 |
| 7.1.2 | 9 | RBI评估需要的数据 | 正确页、条款号与引文匹配；PDF 字体 ToUnicode 映射使文字抽取含替代字形，使用页面视觉核对标题 | 基础数据按一致原则采集和记录 | 不推定具体数据值或材料/介质限制 |
| 7.2.2 | 9 | 数据质量 | 正确页、条款号与引文匹配 | 数据缺失影响评估；提供方应保证真实性、尽量完整，使用数据应验证 | 不填虚构验证状态/审核人 |
| 8.1.2 | 11 | 通则 | 正确页、条款号与引文匹配 | 同一设备存在温度、压力或介质等多工况时，识别各工况可能的损伤类别和模式 | 不把其解释为具体适用介质列表 |
| 8.2.1.2 | 11 | 损伤类别的识别 | 正确页、条款号与引文匹配 | 识别需了解运行及其与化学、机械环境的相互作用 | 不映射为设备已有损伤事实 |
| 9.1.2 | 13 | 失效可能性分析 | 正确页、条款号与引文匹配 | 研究已知全部损伤模式，关注易发生多种模式的设备 | 不生成可能性等级 |
| 12.1.1 | 20 | 通过检验降低风险管理的不确定度 | 正确页、条款号与引文匹配 | 检验本身不改变/降低损伤模式发生可能性 | 不生成检验周期或可能性变化值 |
| 13.8.1 | 23 | 建立完整性操作窗口（IOWs） | 正确页、条款号与引文匹配；IOWs 字体映射差异以页面视觉核对标题 | 建立适当工艺操作边界可避免/减缓设备损伤并降低失效可能性；边界具体值不在该条给定 | 不编温度/压力范围 |
| 14.3.2 | 25 | 实施RBI再评估的时机 | 正确页、条款号与引文匹配；RBI 字体映射差异以页面视觉核对标题 | 周期到期后再评估；细小变化积累也可能造成重大变化，应设最长间隔，但该条未给统一数值 | 检验周期留空 |

结论：候选页码、节号和引文的页面核验可复现，标题与条款语境经本轮视觉检查；未获得真实抽取人及独立复核人的身份/签核，因此工作簿继续保持 `draft_needs_review`，不作为人工已签核数据或并入官方 JSONL。`convert.py` 的隔离探针按预期因13行「抽取人」为空而退出1，未生成输出；真实日志 `P2_convert_draft_gate.log`；官方 JSONL 仍为 RBI 472 条、总 554 条。需真人填写 U/V 并经 Owner 批准后再走正式转换与字段 diff。

## 2. 隔离 Python 环境与兼容性

- 原 Python 3.11.9 环境确实存在 `langgraph==1.1.2`、`langchain-core==1.2.19`、旧 `tenacity==5.1.5` 的冲突。直接 `python -B -m scripts.langgraph_state_routing_demo` 的异常为 `AttributeError: module 'asyncio' has no attribute 'coroutine'`，由旧 Tenacity 导入触发。
- 未更改全局 Python、未 monkey patch。建立 `.venv-langgraph`，安装项目依赖及 `langgraph==1.1.2`、`langchain-core==1.2.19`、`tenacity==9.1.2`、`langgraph-checkpoint-sqlite==3.1.2`。完整解析锁见 `requirements-langgraph.lock.txt`。
- 初始化命令：`py -3.11 -m venv .venv-langgraph`；` .\.venv-langgraph\Scripts\python.exe -m pip install -r requirements.txt langgraph==1.1.2 langchain-core==1.2.19 tenacity==9.1.2 langgraph-checkpoint-sqlite==3.1.2`。后续可用 `python -m pip install -r requirements-langgraph.lock.txt` 复现本机完整解析结果。
- `pip check`：`No broken requirements found.`；`python -B -m scripts.langgraph_state_routing_demo` 实际打印 `CASE missing_context` 与 `CASE has_context` 的不同条件路由，最后 `STUDY_DEMO_PASS`。

## 3. 六节点 StateGraph 迁移

- 修改 `orchestration/graph.py`：以 LangGraph `StateGraph(GraphState)` 驱动原有 Supervisor、Evidence、Diagnosis、RBI Specialist、Evidence Auditor、Reporting 六节点；`add_conditional_edges` 负责按状态选择后继，节点只注册条件出边，没有并存的固定+条件重复路径。
- 保留 `RunState` 字段、同步 `AgentGraph.run(state, emit)` API、扩展 `add_node` 行为及既有 SSE 事件类型/顺序。Missing context、OOD 从路由边跳过 Evidence/Diagnosis/RBI 工具节点；RBI Specialist 仍检查温度、压力、投用年限及候选机理，不足时只形成信息缺口。标准查询仍只调用教师 `standard_clause_search`。
- 当前图是顺序执行，无并行写同一 State，因此不需要 reducer；未来若启用 fan-out，需先给并发字段显式 reducer。模式仍为 `RULE_DEMO`，没有模型凭据，不宣称真实多 LLM。
- LangGraph checkpoint 使用 `data/langgraph_checkpoints.sqlite3` 和 `langgraph-checkpoint-sqlite`；业务日志维持 `Store` 的 SQLite WAL 数据库，两者职责及文件分开。API、SQLite 业务事件、SSE 首跑和 replay 协议不变。
- 测试新增真实 `StateGraph` 类型及独立 checkpoint 文件检查。首次集成测试发现：构造后动态插入节点未重建图，以及测试读取 checkpoint 后未关闭 SQLite reader；两处均已修正并复测通过。

## 4. 实际验证命令与结果

在项目根目录执行：

```powershell
.\.venv-langgraph\Scripts\python.exe -m pip check
.\.venv-langgraph\Scripts\python.exe -B -m scripts.langgraph_state_routing_demo
.\.venv-langgraph\Scripts\python.exe -B -m unittest discover -s tests -q
.\.venv-langgraph\Scripts\python.exe -B -m unittest tests.test_api_vertical_slice -v
.\.venv-langgraph\Scripts\python.exe -B upstream\04_接口文档\validate.py --final
.\.venv-langgraph\Scripts\python.exe -B -m scripts.check_sources
```

| 验证项 | 实际结果 |
|---|---|
| `pip check` | PASS：无 broken requirements |
| LangGraph 条件路由 demo | PASS：缺材质/介质与字段完备路径不同，`STUDY_DEMO_PASS` |
| 单元测试 | PASS：45 tests，`OK` |
| SSE/持久化/replay | PASS：3 tests，创建 run、SSE、消息和事件落库、序号/replay 幂等、教师工具清单检查 |
| 官方 `validate.py --final` | PASS：554 clauses（RBI 472、损伤机理82），200 trajectories、144 multi_step、三类特殊轨迹各15；100%记录通过 |
| `scripts.check_sources` | PASS：19/19 |
| 教师合同/原始数据差异 | PASS：指定工具合同、验证方法、枚举、风险映射、原始 RBI XLSX、`05_提交区` 均 `git diff --exit-code HEAD` 干净 |
| 基准对照 | PASS（作为可比较基线）：8题、每题30次；官方/FTS5 Recall@5 与 MRR@5 均1.0；warm mean 0.1622ms / 0.0199ms。仅精确术语，不代表语义或安全有效性 |

真实 stdout/stderr 记录：`P2_langgraph_demo.log`、`P2_pip_check.log`、`P2_unittest.log`、`P2_sse_replay_test.log`、`P2_official_final_validation.log`、`P2_source_inventory.log`、`P2_retrieval_benchmark.log`、`P2_convert_draft_gate.log`、`P2_rbi1_candidate_machine_audit.log`。可复跑的只读 XLSX/PDF 核验器为 `scripts/verify_rbi1_candidate_workbook.py`；它只报告机器文本对照结果，并将标题标注 `VISUAL_REVIEW_REQUIRED`。

## 5. 变更 / 失败项 / 下一轮

本阶段变更：`orchestration/graph.py`、`tests/test_store_and_graph.py`、`scripts/verify_rbi1_candidate_workbook.py`、`requirements-langgraph.lock.txt`、`README.md`、`docs/PROJECT_STATE.md`、本证据报告及其日志/页码联系表。独立 RBI 候选工作簿和 PDF 均未改写；`upstream` 分支仍为 HEAD `d7877bf387482b2fa9b148d30860da59ccad48b3`，唯一 untracked 文件是原先已存在的独立候选工作簿。

仍待人工/Owner：真实抽取人及另一名复核人填 U/V；Owner 核最终标题、条件语义和并入计划；取得签核后才跑新增行合并、官方 convert 输出与逐字段对比。原环境不修全局 Tenacity；需使用隔离环境。本轮没有清理/移动/删除上游 PDF、XLSX、备份或 reference_code，没有 git add/commit/reset/clean。

状态：`READY_FOR_OWNER_REVIEW`。建议下一轮先由有资格的抽取人、独立复核人逐页签核13条并冻结工作簿；之后才转换/差异审查。LangGraph 后续在固定题集比较 RULE_DEMO 与有凭据的单模型/多智能体质量、成本、延迟，并审查并行 State reducer；不要以当前确定性路由或8题检索基准声称多 Agent 质量增益。
