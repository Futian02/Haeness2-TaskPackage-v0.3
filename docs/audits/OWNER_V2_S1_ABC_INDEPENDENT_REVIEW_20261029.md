# OWNER｜Aetheris V2 S1-A/B/C 独立复核与S2接线门禁（2026-10-29）

**总判定：S1_OWNER_REVIEW_ACCEPTED_WITH_CONDITIONS / S2_PREP_ALLOWED / DEFAULT_V2_CUTOVER_NO_GO / TEACHER_BUSINESS_RELEASE_BLOCKED。**
本报告是真实本地源码+实际运行的独立复核；未提交、部署、重启运行服务、调用付费LLM、修改上游正式条款/人工签名/真实SQLite。不能把S1专项PASS外推为真实模型规划、设备专业正确率或教师最终验收。

## 1. 当前实测（本轮重新运行）
| 范围 | 实际复验 | 说明 |
|---|---|---|
| S1-A 新路由 | **11/11 PASS** | 结构化路由可注入mock，默认仍本地规则，真实router provider未接线 |
| S1-B AgentGraph候选 | **16/16 PASS** | Fake Planner、合成条款、隔离工具；未接入默认API |
| S1-C 会话记忆 | **9/9 PASS** | 临时SQLite，memory service未接入API/Graph |
| 原R9 | 最初**1 FAIL+2 ERROR**；兼容修正后**19/19 PASS** | 新V2策略错误把部分原R9输入判general，详见第2节 |
| S1 A/B/C+R9专项 | **55/55 PASS** | 修正后合并运行 |
| 新Owner安全边界 | **4/4 PASS** | 上下文短问题、标准编号、普通文本变换、高风险子任务不得藏GENERAL |
| S1-A+P13/R10专项 | **25/25 PASS** | 不包括历史R10完整矩阵脚本 |
| Owner原65条自拟困难题 | **65/65一致** | 与既定人工预期一致，非独立盲标、非线上路由准确率 |
| 整仓Python unittest discover | **275 tests, 0 FAIL, 1 ERROR, 3 SKIP** | 本轮修复后实际运行耗时101.72s；唯一ERROR是P16-A顶层import fitz环境缺包，不是P16内容断言失败；再加4项Owner专项后尚未重跑新的整仓分母 |
| P16-A独立pytest | **5/5 PASS** | 系统Python有pytest与fitz，命令`python -B -m pytest -q -p no:cacheprovider tests/test_p16_a_evidence42.py`；不等于全部人工核验 |
| 前端 | **118/118 Vitest、TypeScript PASS、Vite build PASS** | 用本机node.exe直调；主index bundle 614.49KB有chunk警告，真实移动端Edge截图尚未核验 |
| 教师程序合同 | `validate.py --final` **554/554条款、200/200轨迹 PASS**；原工具selftest **17/17 PASS** | 不表示老师50人审、LLM原生100解析、专业适用性认证 |
| 100 run临时本地负载 | 随全仓测试c=1/4/8各100，errors 0 | 与Owner独立更高压100c8出现27个429队列的脚本条件不同，不可相互抵消或宣称背压完全解决 |

## 2. 已修复的阻塞回归（只改自有路由）
本轮最初复跑`tests.test_r9a_industrial_candidate`出现：
- `test_low_quality_retrieval_rewrites_and_retries_with_traceable_source` FAIL：原标准工具调用计数由预期至少2变成0；
- `test_identical_query_zero_information_gain_stops_loop` ERROR：`gate_decisions`为空；
- `test_transient_tool_failure_retries_and_records_attempt_count` ERROR：没调用`standard_clause_search`。
**查明根因**：S1-A用V2 LocalIntentPolicy替换旧`classify_intent`语义，令带上一轮设备材料/介质上下文的“设备腐蚀”“请问帮我设备情况可能是什么”变`general_chat`；“GB/T-DEMO 标准第4.1条”无查询动词，旧图也被送`general_chat`，没有进入investigator。
**实际最小修复**：
- `backend/intent_router_v2.py`：明确“第x.y条”即使无查询动词仍视为标准查证；对模型Proposal附带`DEVICE_DIAGNOSIS/RBI_ASSESSMENT/MECHANISM_EXPLORATION`或HIGH风险子任务却申报GENERAL/非安全路线的结构化JSON直接拒绝，禁止子任务风险与主route冲突。
- `orchestration/intent.py`：当同会话已提供设备条件、当前短问题又明确涉及设备腐蚀/情况/裂纹等，保留原R9专业意图；问候、翻译、科普、代码等明确普通请求不继承旧设备条件。
- 新建`tests/test_owner_v2_routing_regressions.py`4项可持续复现用例。
**复测证据**：R9 19/19、S1-A+P13/R10 25/25、Owner65 65/65、新Owner4/4、A/B/C+R9 55/55 PASS。没有通过放宽断言、skip测试或修改老师三工具实现。

## 3. A/B/C评审质量与剩余缺口
### S1-A：模块GO，模型真实路由NO-GO
优点：strict Pydantic/DAG、安全floor、真实FastAPI worker通用路径可跳graph.run，并保留原SQLite run lease/SSE；明确STANDARD和MIXED仍过渡R9。问题：`router_from_environment()`没有真实结构化远端Provider（只支持注入），默认`V2A_LLM_ROUTER_ENABLED=0`；所以65/65与120/120是**确定性/Mock语义**，不是LLM分类能力测量。混合子任务DAG只是元数据快照，未执行真正的子任务拆分/结果合并。已实修旧R9兼容回归与高风险子任务一致性漏洞。

### S1-B：Agentic候选GO，默认接线NO-GO
优点：确有`StateGraph` + model_plan→policy_validate→execute_tool→source_ground→reflect→两审→claim_gate，Fake Planner的工具名与参数可动态变化，不是简单旧规则改名；工具3名强制、参数Schema与source metadata/本地语料指纹可核。已完成16专项。
**关键阻塞**：
1. `graph.compile()`**没有持久化checkpointer**；`ReplayLedger`仅Python对象内存、还在持锁状态执行工具，跨进程崩溃后不能证明幂等/恢复。切换默认图前必须统一`conversation_id/run_id/thread_id`，实现断点恢复、可重复/可取消工具attempt记录和崩溃恢复测试。
2. `_invoke`的`Future.result(timeout)`只使等待线程超时，不能保证底层线程真正终止；`shutdown(wait=False)`后底层仍可能占用资源，真实远端Provider必须使用原生网络timeout、协作取消和并发预算。上限“30s/12K token”在Fake层只是本地估计/调用后检查，不等于真实API严格预算。
3. 设备适用条件尚无真人金标或全面语义验证；来源identity/hash是必要条件，不代表条文满足设备工况。没有真实provider、真实teacher tool E2E、PDF页级人审。

### S1-C：存储与隐私模块GO，产品UI准入部分NO-GO
优点：SQLite单库conversation_id隔离，事实断言显式确认、旧事实superseded，摘要有源消息hash/parent version，模型摘要默认关闭；临时DB9项和前端118项PASS。
**关键阻塞**：
1. MemoryService还没在`backend/api.py`/工程图调用；因此多轮摘要/确认事实管理功能不能称已上线。
2. `frontend/src/trace-events/model.ts`中`safeArgs`将material/medium/temp/pressure/equipment_type实际值**全部遮成固定文案**，且检索`keyword`不在参数白名单。这样的UI不能让老师核对真正输入何种工况/查询词。需要单独设计**授权可见的、具数据最小化与脱敏边界的tool输入/输出公开投影**，同时普通用户不得接收私有SSE整包JSON。没有生产鉴权的开发版不以伪admin标志替代安全身份。
3. 浏览器真实Edge移动viewport尚未重新执行；chunk614KB构建警告仍在。
4. Store迁移在构造时执行，未来接真实数据库需有可靠备份+迁移版本和失败回滚，当前仅临时SQLite验证。

## 4. 发现的独立环境/测试口径问题
- 项目`.venv-langgraph`缺`fitz`与pytest，系统Python则有PyMuPDF/pytest。`tests/test_p16_a_evidence42.py`是pytest风格而非unittest，默认unittest discover因顶层import fitz导致**导入ERROR**。系统Python用pytest跑真实5项PASS；需要统一依赖/测试发现策略，不能将旧报错说成业务数据失败或直接删测试使全绿。
- 根目录不是frontend package根；`npm run test --prefix frontend`本机脚本执行曾出现`"node" not recognized`，但`where node`有真实`D:\Program Files\nodejs\node.exe`，直接node运行Vitest 118/118、tsc PASSED、Vite build PASSED。需明确工具执行cwd/Node PATH并固定统一命令，不将shell路径异常归咎源码。
- 历史`evals/r10_offline_chat_matrix.py`本轮仍在`persisted["status"]=="completed"`断言FAIL：旧脚本Mock只patch`deepseek.settings/is_configured`并以tuple作为`generate_chat`返回，而当前API选用`model_profiles.safe_profile`和结构化`GenerationResult`，**可能存在旧mock失配**；目前尚未进行逐run身份/失败码诊断，不能既宣称生产回归又宣称已修。S2需新增以当前API合约为准的10×2隔离矩阵，与历史结果分开。
- `upstream/01_RBI标准/条款摘录表_RBI.xlsx`本轮末尾仍M，另有13候选及历史备份untracked；这都是之前已存在的状态，未改变或归因。教师文档、审核签名和正式JSONL未触碰。

## 5. S2准入顺序（只授权候选联调，不授权发布）
**Gate G0 技术基线**：规范Python依赖和运行器、P16-A pytest单独验收、R10当前合同离线回放、Git SHA与教师基线；先解决已知测试漂移，不能修改测试预期造绿。
**G1 API接线**：保留原R9默认，新增`V2_AGENTIC`显式且默认off；普通直连Graph=0；标准轻量路径与混合DAG确实有界执行而非仅存快照，无法完成须显式TRANSITIONAL不能虚报。
**G2 Provider与Budget**：真实Provider接口实现可mock、特性标志关闭、真实模型/收费需Owner另行明确允许；Planner JSON schema不可靠时fallback安全；原生usage与请求超时、tool循环预算独立计。
**G3 持久恢复**：LangGraph checkpointer与SQLite事实/运行事件一致、run级幂等、并发/失败/重连/崩溃重放；否则不可替换默认专业路径。
**G4 记忆与UI**：MemoryService按当前cid接入，系统事实与AI摘要分离；公开折叠步骤支持真实可核查的最小工具入参和标准来源，不泄raw SSE或隐藏CoT；本地Edge桌面/手机实拍核验。
**G5 专业适用性独立门**：82机制10–15试点/金标、负证据/未知场景、precision/recall/false exclusion，当前无E3认证；未签P16与老师LLM100/5轮/公开ModelScope仍BLOCKED。

### 文件与状态
- 完整原S2设计：`docs/CODEX_V2_S2_INTEGRATION_OWNER_GATE_20261029.md`；
- **新Owner专项S2提示词**：`docs/CODEX_V2_S2_OWNER_HANDOFF_20261029.md`；
- 最新状态：`docs/PROJECT_STATUS_CURRENT.md`。
本轮GO仅意味着**S1候选可进入受控S2联调**，不是默认V2上线、工程准确率、老师正式验收或外部发布。
