# Haeness2 机械智能体状态（持续状态源）

> **历史资料标记（2026-10-28）**：本文主体记录的是 2026-10-27 状态，不再作为当前运行真源。当前状态、已验证结果和未决事项请先看 [`PROJECT_STATUS_CURRENT.md`](PROJECT_STATUS_CURRENT.md) 与 [`audits/FINAL_LOCAL_INTEGRATION_ACCEPTANCE.md`](audits/FINAL_LOCAL_INTEGRATION_ACCEPTANCE.md)。保留本文原文用于历史追溯，不在最终集成中重写旧记录。

最近复核：2026-10-27
项目路径：D:\作业\竞赛\计算机设计智能体\机械智能体
远端：Futian02/Haeness2-TaskPackage-v0.3
上游 HEAD：d7877bf387482b2fa9b148d30860da59ccad48b3
状态：`upstream/` 为独立 Git 工作树，`master...origin/master` 且干净；当前使用 sparse-checkout。外层项目处于另一个父级Git树下，其它路径的历史脏状态不得触及。

## 已验证（本轮独立执行，非旧报告转述）
- `python -B upstream/04_接口文档/validate.py --final`：554/554 条款、200/200 轨迹 PASS；DM 82、RBI 472、多步144、三类特殊各15。
- `python -B upstream/05_提交区/_selftest_tools.py`：17/17 PASS。
- `python -B upstream/04_接口文档/harness_skeleton/run_guardrail_tests.py`：报告尾部显示异常拦截36/36、误拦0，达标。
- `python -B upstream/05_提交区/_check_harness_sync.py`：两份Harness一致，SHA256前16为`63fa7082ac3f216d`。
- `python -B -m unittest discover -s tests -v`：新增产品层/检索实验与真实Harness集成测试13/13 PASS；未运行Gradio。
- `python -B -m evals.benchmark_retrieval`：8条显式机理术语各30次热查询，官方和FTS5均Recall@5=1/MRR@5=1；官方热均值0.2134ms，FTS5热均值0.0258ms；官方初始化约183.25ms，FTS5建索引约19.553ms。仅此机器微基准，含义见 `docs/RETRIEVAL_R0_RESULT.md`。
- `python -B -m evals.benchmark_agent_latency`：新增3场景×12轮规则Harness热执行：各3次调用；HCl P50 2.53ms/P95 3.15ms，湿H2S 3.18/3.47ms，多介质2.59/3.00ms；未含LLM/UI/network，不能拿来冒充真实响应。
- 通过只读python-docx直接读取 `upstream/任务包问题答复.docx`：121段+2表，关键限制摘要在 `docs/TEACHER_QA_CONSTRAINTS.md`。
- 本轮完成教师规格精读与总规划，见 `docs/MASTERPLAN_V1_TEACHER_FIRST_20261027.md`、`docs/TEACHER_REQUIREMENTS_AND_GAPS_20261027.md`、`docs/OSS_REUSE_DECISION_V1_20261027.md`、`docs/COURSE_02_AGENT_TOOLS_RAG_SYSTEMS_20261027.md`；完成Luna High首轮本地执行任务书，见 `docs/CODEX_LUNA_HIGH_R0_EXECUTE_20261027.md`。

## 已落实的目录 / 代码 / 文档
- `AGENTS.md` 已初始化：固定阅读顺序、数据合同、层边界、测试和学习原则。
- `README.md`、`.gitignore`；`app/runtime.py` + `app/web.py`：不修改老师工具签名的规则/LLM演示原型。
- `knowledge/lexical.py`：SQLite FTS5 trigram + 内置BM25，**旁路实验**，不注册为第四个老师工具。
- `evals/retrieval_gold.json`、`evals/benchmark_retrieval.py`：8题基准与读-only性能计时；`tests/` 13测全绿。
- 文档：`docs/ROADMAP.md`、`ARCHITECTURE.md`、`DOCS_INDEX.md`、`CONTRACT_LOCK.md`、`DATA_LINEAGE.md`、`RETRIEVAL_LEARNING.md`、`RETRIEVAL_R0_RESULT.md`、`TEACHER_QA_CONSTRAINTS.md`、`LEARNING_PLAN.md`、`LEARNING_01.md`。
- `scripts/check_sources.py`：只读检查19个重要文档/数据，当前**9 PRESENT / 10 MISSING**；MISSING均为 `01_RBI标准/`、`02_损伤机理参考/`、`03_案例样例/` 的稀疏未检出文件，不代表GitHub上不存在。

## 尚未完成，不得宣称PASS
1. 用户现在明确要求**HEAD全仓文件**同步（包括参考源代码与缓存），但原始PDF/XLSX尚未从稀疏Git检出；本轮全同步**未完成**。优先执行项目根目录 `scripts/SYNC_ALL_UPSTREAM.ps1`，或 `git -C upstream sparse-checkout disable`，它会检出所有被Git追踪的HEAD文件，并检查关键19件。
   然后跑 `python -B -m scripts.check_sources` 确认19/19；用户已要求全部文件，本轮会一并包含 `04_接口文档/reference_code` 的现有追踪资产（不重复clone外部远程仓库）。
2. Gradio未安装：`app/web.py` 尚未实际运行/截图；ModelScope尚未发布外网可访问链接。
3. 真实LLM API 10/100题未配置与评估；不存在 BFCL AST 评估证据，fallback不计原生解析成功。
4. 原 `tools.py` 仍有 `from _df_rules import` 导入路径风险，外层adapter的sys.path使普通流程可跑，但**没有修上游缺陷**。
5. 8条确切名称只验证基本检索，尚未有充足的自然语义描述、拒答和来源真实性金标；也未证明现有200条轨迹为自主模型生成或真人交叉复核。
6. PDF逐页人工审查未在本轮进行（用户原仓库过去的审查报告只能作历史证据）。
7. 本轮尝试连接本地 `dorqinspace__codex_bind_workspace` 至 D:\\ 项目与原始沙箱C:\\工作区，均返回工具内部错误；**未实际启动Luna执行，不能称为Codex完成。**

## 下一轮优先级
- 首先补全01/02/03，并查看标准PDF/XLSX字段及校验一致性；
- 在冻结20~50题金标上比较官方词法、FTS5与embedding+BM25+rerank，按质量/延迟选择而非按框架流行度；
- 真实LLM联通10题、原生解析/回退统计、前端Gradio本机启动；
- 之后100题+BFCL、ModelScope公开演示、再讨论LangGraph与多agent增益实验。

## 本轮新增（设计/任务，非实测功能）
- 用户战略改为**必须做多智能体企业化平台**；设计已写 `docs/MULTIAGENT_PRODUCT_ARCHITECTURE_V2_20261027.md`。
- Codex完整执行任务新稿：`docs/CODEX_LUNA_HIGH_R1_MULTIAGENT_PLATFORM_20261027.md`，本轮只写入文档，**未成功远程启动Codex**。
- 开源对标见 `docs/OSS_BENCHMARKS_MULTIAgent_V2_20261027.md`（Qwen-Agent、LangGraph、assistant-ui、CopilotKit/AG-UI、BFCL）。
- 数据库方案首选SQLite WAL + SQLAlchemy/SQLModel，MySQL可配置；网站计划FastAPI+React/assistant-ui，SSE/AG-UI事件持久化；**未实现网站或数据库，不得宣称上线**。
- 原始PDF/XLSX截至本轮检查仍未全量检出，HEAD完整同步任务等待本地执行器。

统一原则：学习第一；真实证据为本；不把工具召回当成风险判定。

---

## R1 多智能体产品垂直切片（2026-10-27 实测）

状态：`P0 FULL_TRACKED_HEAD_SYNC=PASS`；产品层 Agent/SQLite/API/单页站点/语义草稿已实现；真实LLM、MySQL和浏览器视觉验证仍未完成。完整过程、初始失败和审查路径见 `docs/audits/R1_EXECUTION_EVIDENCE.md`。

### 完整同步与合同
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\SYNC_ALL_UPSTREAM.ps1` 最终重试通过；`upstream` HEAD=`d7877bf387482b2fa9b148d30860da59ccad48b3`，2535/2535 tracked files、2535/2535 HEAD tree entries、sparse=false、worktree clean；19/19官方关键件存在。
- `python -B -m scripts.build_upstream_manifest` 生成 `docs/audits/upstream_head_manifest.jsonl`（2535条；17 PDF + 3 XLS/XLSX），SHA=`85cda2745c343bbc2661c8337fa11f23c1f89c7383b4b7405e1c421bae95e3a2`。
- 教师合同/数据 `git -C upstream diff --exit-code HEAD -- ...` 退出0。教师 `validate.py --final` 实测554条款、200轨迹、144多步、特殊轨迹各15，PASS；三工具集成测试保持PASS。

### R1实现
- `orchestration/graph.py` 为真实可执行、节点协议可替换的六节点图：Supervisor / Evidence / Diagnosis / RBI Specialist / Evidence Auditor / Reporter。路由可分工况缺失、标准条款检索、机理研判、域外；缺上下文/OOD跳过工具，标准询问只调 clause search；Evidence节点复用上游三工具注册表，不加工具；RBI只在显式温度、压力、投用年限、候选俱全时调用。当前全部是确定性 RULE_DEMO 节点，不是多LLM实验结论。
- `backend/store.py` SQLite WAL七表：conversations、messages、runs、agent_events、tool_calls、evidence_refs、knowledge_documents；连接随session关闭，SSE事件有run内单调唯一sequence并可replay。
- `backend/api.py` FastAPI聊天/历史/运行/事件SSE；`web/index.html`三栏History+Chat+Trace/Evidence页面。`README.md`给出启动命令。API TestClient端到端通过、浏览器插件调用挂起未截图。
- `orchestration/semantics.py` 定义严格Pydantic `EngineeringObservation/Hypothesis/EvidenceLink/InformationGap`；unknown与false分离，简单单位与同义词归一化；10条来源候选卡、10个自然语言样例已生成，仍draft/non-gold。产品证据模型最高验证级别E1，E2/E3待人工审查。
- 新增审计文档：`R1_MULTIAGENT_ARCHITECTURE.md`、`R1_UI_EVENT_PROTOCOL.md`、`R1_ENGINEERING_SEMANTICS.md`、`R1_EXECUTION_EVIDENCE.md` 和模型JSON Schema。

### 最终实测命令
- `python -B -m unittest discover -s tests -v`：43/43 PASS；新增 API/SSE、语义schema与unknown、SQLite事件存储、可插拔图节点、Supervisor路由、RBI条件调用等30项测试。
- `python -B upstream\04_接口文档\validate.py --final`：PASS（上述结构/数量）。
- `python -B -m scripts.check_sources`：19/19。
- `TestClient`：GET `/`=200，`/api/health`=200；创建对话→创建run→SSE首跑→历史和事件重放全部通过。独立uvicorn+urllib live smoke：33 SSE帧、6 Agent节点事件、replay 33条、序列递增、run_completed。
- 本地 uvicorn绑定127.0.0.1:8000；浏览器视觉/console未验收；无域名/外网部署。

### 未完成 / Blocked
1. 真实模型API/模型key未配置，RULE_DEMO不能代替native LLM parse、single vs multi-agent质量/成本/耗时比较；没有对真实LLM宣称测试通过。
2. MySQL adapter/驱动/服务未实现；SQLite URL默认可用，其他数据库URL明确fail-fast。
3. Playwright视觉检查挂起；前端需后续在可用浏览器或React组件重构中验收。
4. 未执行PDF逐页人工原文核验，不能把候选卡升为E2/E3。
5. 父级Git树初始有其他项目脏改且本项目处于父仓未跟踪路径；本轮没 add/commit/reset/clean/branch。待审改动仍仅在本自有项目目录中。

### 下一步
先在同一冻结题集完成 RULE vs 有凭据single LLM 的基线，再决定是否接 LangGraph checkpoint / MySQL / React；先人工复核10条候选卡再冻结10条自然语言 gold cases。

---

## Owner 复核闭环（2026-10-28）

读取 `docs/OWNER_REVIEW_LAYOUT_AND_CONVERT_20261027.md` 后按其并发/归档约束处理：**本轮没有清理、移动或删除任何 upstream 文件**，清理留待当前开发阶段结束及带哈希的归档计划审批后再做。

- Owner 报告中观察到 `rbi_specialist` 缺注册。当前工作树复核时默认节点列表已经含 `RbiSpecialistAgent()`，完整图测试也通过；为防止节点表/执行路由以后再次漂移，在 `AgentGraph` 增加 `validate_routes()`，构造和执行前均 fail-fast 检查必需节点、注册表及顺序一致，并增加缺节点构造失败回归。
- Owner 提到的“38项”与当前磁盘测试集不一致：实际 `python -B -m unittest discover -s tests -q` 运行 **44项，全部通过**。SSE 单独复测 `python -B -m unittest tests.test_api_vertical_slice -v` 为3/3 PASS，覆盖首跑、消息持久化、事件 sequence 和 replay 幂等。
- `git -C upstream status --short --branch` 为 `master...origin/master` 干净；`git -C upstream diff --exit-code HEAD -- README.md 04_接口文档/工具接口规范.md 04_接口文档/技术指标验证方法.md 04_接口文档/enums.json 04_接口文档/risk_level_mapping.xlsx 05_提交区` 退出0；未改老师三工具或教师数据。
- 新增保护测试及实测命令记录见 `docs/audits/OWNER_REVIEW_RBI_REGISTRATION_20261028.md`。当前没有 Git add/commit/reset/clean 操作；清理仍 BLOCKED/DEFERRED，而非悄悄执行。

## P2 RBI1 + LangGraph StateGraph（2026-10-28）

状态：`READY_FOR_OWNER_REVIEW`。完整证据与真实日志见 `docs/audits/P2_RBI1_LANGGRAPH_EVIDENCE.md`。

- `upstream/01_RBI标准/RBI_GBT26610_1_13candidates_for_review.xlsx` 为独立13行工作副本；本轮只读核验，没有修改原 RBI 表。原表 SHA-256 `38cf71bf9f9868cfa531729cda70dea2e2857b3a788ec1a67f56d27ef01512f9`。候选保持抽取人/复核人身份、风险、周期及未经证明的现场条件字段为空；没有真人签核，不接入官方 JSONL。核验器 `scripts/verify_rbi1_candidate_workbook.py`，PDF逐条页码/标题/引文/条件记录见 P2 evidence。
- 原 Python 3.11.9 全局环境的 `tenacity==5.1.5` 导入因 `asyncio.coroutine` 已不存在而失败。没有修改全局环境；隔离 `.venv-langgraph` 固定 `langgraph==1.1.2`、`langchain-core==1.2.19`、`tenacity==9.1.2` 与 SQLite checkpoint 包，锁文件 `requirements-langgraph.lock.txt`。`pip check` 无依赖冲突，LangGraph 条件路由 demo 两种输入实际运行通过。
- `orchestration/graph.py` 现以真正的 LangGraph StateGraph 调度原六节点；conditional routing 对 missing-context/OOD 跳过工具。保留 `RunState`、`AgentGraph.run`、FastAPI、SQLite业务事件和SSE事件协议；checkpoint 单独存于 `data/langgraph_checkpoints.sqlite3`。当前为 `RULE_DEMO`，没有真实模型质量结论。新增 StateGraph/checkpoint 隔离回归。
- 最终隔离环境 `python -B -m unittest discover -s tests -q`：45/45通过；SSE/持久化/replay为3/3；官方 `validate.py --final` 通过（554 clauses / 200 trajectories）；`check_sources` 19/19。RBI draft convert 隔离探针因13条抽取人为空返回1且无输出，这是预期的人审门禁，不是正式数据回归失败。
- 未清理/移动/删除任何 upstream 文件，无 git add/commit/reset/clean。待 Owner 安排真实抽取人及独立复核人签核13条；批准后再进入转换、字段diff和正式合并。

## P3A 前端 + P3B 证据审查（2026-10-28）

状态：两条工程线均完成实现并停止在 `READY_FOR_OWNER_REVIEW`。独立验收报告：`docs/audits/P3A_FRONTEND_ACCEPTANCE.md`、`docs/audits/P3B_EVIDENCE_AUDIT.md`。

- P3A 新增 `frontend/` 的 React + TypeScript + Vite 应用，使用 assistant-ui runtime adapter、shadcn/ui 风格组件、Tailwind 与 React Flow；UI 是观测型事件图，对 SSE 增量事件和未知事件可容错，不改后端或 `web/index.html`。本机 Edge/Playwright 真实 UI→FastAPI→SSE→SQLite→回放链路通过：34条事件、5张引用卡，刷新恢复2条消息和34条事件，pageerror/alert=0。截图为 `frontend/evidence/p3a-e2e-desktop.png` (1280×900)、`frontend/evidence/p3a-e2e-mobile.png` (390×844)。Vitest 6/6、typecheck、production build、npm audit 0 vulnerabilities；根 `.gitignore` 已排除 `frontend/node_modules/` 与 `frontend/dist/`。
- P3B 在 `orchestration/`、`backend/` 增加结构化 Claim、E0/E1来源/条件核验、独立 Skeptic、SQLite claims/disagreements 与兼容 SSE 新事件。所有机器审核 Claim 保持 `unresolved/requires_human_review`；没有真实模型，不能将 RULE_DEMO称为多模型交叉审查。RBI旧工具调用回归按原样保留，但无独立失效可能性+后果证据时不生成/公开风险Claim，SSE副本会移除等级与周期字段；工具本体五键及三个工具不变。
- 评测草稿 `evals/p3b_unreviewed_scenarios.jsonl` 有20条 synthetic/unreviewed 场景，0个专家标签；E2原文蕴含、E3设备适用性、人工签核流程仍未实现。25次 RULE_DEMO 图基准：P50 63.91ms、P95 74.52ms、平均调用2个工具，unsupported risk claim=0。该数据不是专家金标或模型效果证据。
- 合并线：Owner 明确选择“不写，等待真实抽取人签名”。仅重新运行 `python -B -m scripts.merge_rbi1_into_original --check`，结果 `READY_TO_APPEND 13 A474:W486`、`EXTRACTOR_SIGNED False`、`CHECK_ONLY: no files modified`；未执行 `--apply`、未创建原件备份，原表SHA仍为 `38cf71bf9f9868cfa531729cda70dea2e2857b3a788ec1a67f56d27ef01512f9`，RBI 472条、官方 JSONL 554条继续不变。
- P3 合并后隔离环境完整测试 `python -B -m unittest discover -s tests -q`：54/54 PASS；官方 `validate.py --final`：554 clauses、200 trajectories，PASS；`scripts.check_sources`：19/19。三个老师工具、教师工作簿、标准 PDF 与官方 JSONL 均无差异。
- 未清理/移动/删除上游文件，未 git add/commit/reset/clean。下一步先由 Owner/真人处理13条源表签名与复核，再审核 Claim 判定/反证和人工复核状态产品契约；真实 LLM 联通及质量评测需单独批准模型凭据与基准题集。

## P4 API运行安全、Claim核验与UI完善（2026-10-28）

状态：A/B/C 三条线均停止在 `READY_FOR_OWNER_REVIEW`；未部署。详细报告及证据：`docs/audits/P4A_IDEMPOTENCE_SECURITY.md`、`docs/audits/P4B_INDEPENDENT_VERIFICATION.md`、`docs/audits/P4C_UI_EVIDENCE.md`、`docs/audits/P4C_EDGE_E2E.json`。

- **P4A**（`backend/` 与对应测试）：SQLite 原子 claim 保证 queued→running 单 worker；SSE 订阅/重放与执行解耦，终态 assistant 消息和 run 状态同事务提交；进程失联失败关闭，不自动重执行。API 输入/速率/并发有界，健康端点不泄露数据库绝对路径，生产模式无认证时 fail-closed，开发模式限制 loopback。P4A 定向测试 11/11 PASS。
- **P4B**（`orchestration/` 与 P4B 专属测试/evals）：独立 Claim 验证器明确区分 matched/missing/mismatch/unknown；缺少原始证据/必要元数据走 E0，不伪造 E2/E3 或语义蕴含。Skeptic 从原始观测独立检索；所有结论保留人工复核状态。定向测试 16/16 PASS；`evals.p4b_verify` 20 条合成旧用例+14条负例通过规则行为检查（不是专家金标）；官方来源检查 19/19。
- **P4C**（`frontend/`）：取消/epoch 防止旧会话响应串线；UI 展示可观测执行边、Claim 历史和来源，不将等待/跳过冒充执行；窄屏、长中文、深色及证据抽屉改进。Vitest 24/24、typecheck、Vite production build PASS。真实 Edge→FastAPI→SSE→SQLite 测试记录 16 个事件，序号5后 replay 11条，refresh 恢复16条，runs API 200，浏览器 console/page errors 0。
- **全量验证**：隔离 Python 环境 `python -B -m unittest discover -s tests -q` 共81项，80通过、1失败。唯一失败为旧 `tests/test_p3b_evidence_audit.py::test_explicit_condition_mismatch_is_not_applicable` 仍断言缺失 `content_raw` 的假 canonical fixture 应为 E1；新门禁按证据缺失正确返回 E0。该旧测试越出P4B写入边界，本轮未改旧 P3B 测试或放宽门禁。Owner 的 `evals/owner_p3_regression_probe.py` 同样保留P3旧预期：缺页应匹配，而新实现返回 missing/E0；脚本会在该首项断言失败，因此不能标记该历史探针全绿。
- 教师官方终验 `upstream/04_接口文档/validate.py --final`：554条 clauses、200条 trajectories PASS；工具来源 `python -B -m scripts.check_sources`：19/19 PASS。老师三个工具/五键合同未改。
- 没有启动部署，没有 add/commit/reset/clean。未对原始 RBI Excel / PDF 执行写入；13条补录继续等真实抽取人签名与复核。未绑定公网或域名。

### Owner 下一步
1. 审核是否将P3旧 E1 fixture/probe 预期迁移为显式的缺证 E0/missing，并确认旧行为测试仍覆盖“有完整原文元数据时的条件不适用”。
2. 复核生产认证/运行器恢复策略、SQLite 原子性与SSE重放证据，再决定部署门禁；本阶段未部署。
3. 由真实抽取人及独立复核人签署13条标准摘录后，另行审阅原表合并；当前继续保持原始工作簿不变。
