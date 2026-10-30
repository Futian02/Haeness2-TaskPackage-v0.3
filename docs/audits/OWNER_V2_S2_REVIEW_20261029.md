# Owner S2独立审核与下一阶段准入判定（2026-10-29）

**结论：S2_ACCEPTED_AS_OFFLINE_CANDIDATE / S2_4_ENGINEERING_APPROVED / V2_DEFAULT_NO_GO / TEACHER_FINAL_BLOCKED。**

## 1. 依据与本轮复验

主记录：`docs/audits/V2_S2_OWNER_INTEGRATION_20261029.md`，状态：`docs/PROJECT_STATUS_CURRENT.md`，真实代码：`backend/api.py`、`orchestration/agentic_v2.py`、`backend/conversation_memory.py`、`frontend/src/trace-events/model.ts`。

- Codex报告（**未全部由Owner重跑**）：统一`scripts/test_s2.py`中282 unittest 0 FAIL、0 ERROR、3可选SKIP；P16-A pytest 5/5；R10 20/20 mock replay；前端118 Vitest+TS/Vite build；正式教师 validate 554/200、tools17/17。运行依赖本机base-site-packages混合，不是洁净重建。
- Owner独立重跑（本轮）：`./.venv-langgraph/Scripts/python.exe -B -m unittest tests.test_v2_s2_integration -v` **4/4 PASS**，覆盖显式V2 feature off、fake candidate适配、SQLite checkpoint存在、同会话工程事实复用和普通聊天不继承工程事实。这**不是**重跑全部282项，也不是崩溃恢复实验。
- Owner独立核对上游三件SHA-256：
  - `upstream/05_提交区/clauses.jsonl`：`a8151797ba15a6a7452dd83aaec9fab4c0a815724ca45062eb1e2bac7b4d49ef`
  - `upstream/05_提交区/条款抽样核对报告.md`：`a063d3e7ccea90e13fce38c40554b68de3293d569adc58a6168f6fd9bc1b81be`
  - `upstream/01_RBI标准/条款摘录表_RBI.xlsx`：`e43f7b0d3381a38fa648c2505e27d1c87893af5aea89aa119097dbfc49c6b7bf`
  上游Git原先Excel M、13候选/备份untracked保持不动，不归因S2工作。

## 2. 源码确认

### S2.0 PASS（本机）
`scripts/test_s2.py`以项目venv优先、追加系统Python base-site-packages补PyMuPDF/pytest，并有OpenTelemetry可选命名空间隔离，证明“这台机器可以完整测试”，**未证明从零按照lock文件重建成功**。R10离线20测试已修Mock/Profile兼容。只能称本机PASS。

### S2.1 PARTIAL
`backend/api.py`当前由显式`AETHER_V2_AGENTIC_ENABLED`开关控制；`V2_AGENTIC`仅在SQLite地址位于系统临时目录时获准。候选实例默认`ScriptedFakePlanner()`，未连接真实LLM。API adapter把候选工具/来源/阶段转为既有事件和消息协议。混合任务`MIXED_SUBTASKS_DEFERRED_CHECKPOINT_GATE`仍只是状态标记，不是真正的DAG子任务执行。

### S2.2 PARTIAL / 核心阻塞
`AgenticV2Candidate.graph.compile(checkpointer=...)`和`run(... checkpoint_ns=f"aetheris-v2:{run_id}")`存在，单次运行可写checkpoint。**但`run`目前仍是对初始输入直接`graph.invoke(state,...)`，没有实现按数据库终态/检查点恢复与补偿的入口**。
`ReplayLedger.get_or_execute`只是进程内dict，且在锁内执行工具；进程中止后内存账本消失。“checkpoint存在”既不能证明工具结果已持久提交，也不能证明重新调用不会重复查询。
`_invoke`超时用`future.result(timeout)`与`shutdown(wait=False)`，这不会确保正在运行的底层线程已停止。不能称具备强制取消、真正端到端超时和资源清理。
教师三工具都是只读，正确的协议应先记意图/尝试，在未知结果时明确标记UNCERTAIN，并只对幂等只读查询有限重试。**不宣称跨进程物理exactly-once执行**。

### S2.3 PARTIAL
`ConversationMemoryService`确实进入`backend/api.py`，仅给工程路径读同CID确认事实；摘要生成尚无完整端到端接线，事实与用户修正流程也需要测多设备对象/后续冲突。
前端`model.ts`目前keyword、材质、介质、温压具体值一律用占位符替换，即使底层真正执行不同查询、不同工况，展开后仍无法区分。公开UI隐藏raw frame是正确方向，但**仅显示“已记录”不满足教师演示的工具参数/结果可核查性**。
需要：普通用户无敏感明文；在**真实授权、受控本地会话**内显示最小充分的真实参数（原字段单位/来源/必要的检索关键词）及对应工具结果。**无身份认证时禁止以URL query、localStorage或debug flag冒充Owner权限**。
另有运行数据协议：当前`/api/runs/{rid}/events`会给客户端原始事件JSON，前端遮盖不等于事件原文对有权调用此本地端点的客户端不可见；生产部署前必须服务端身份/访问控制+不同公开投影。项目当前生产模式仍fail-closed，不以视觉脱敏宣称完成服务端保密。
Edge真实桌面/移动E2E仍未见本轮通过证据。

## 3. 三个层面的GO/NO-GO

| 层面 | 当前结论 | 必须具备 |
|---|---|---|
| 接受S2作为本地开发成果 | **GO** | 现有源码/专项与报告可追溯、默认flag off、教师数据不动 |
| 启动S2.4本地受控工程联调 | **GO** | 只读工具/假模型/临时数据库；新增持久执行协议与故障注入测试 |
| 开启V2默认或真实模型 | **NO-GO** | 持久恢复、真实混合DAG、权限、可靠性/正确性、真实provider预算与盲标门禁 |
| 教师提交/正式人审 | **BLOCKED** | P16真实独立50交叉人审0/50（不能以AI Owner评审代替）、原生LLM100调用及教师发布要求待证 |

## 4. 建议执行顺序与验收指标

1. **S2.4-A 运行持久化协议**：将`run_id`+任务/工具`step_id`+tool name+args hash定义为稳定幂等键；在同一临时SQLite中写attempt ledger、状态转换、工具结果hash和可查来源；checkpoint和SQLite run终态协同。崩溃/重启后对已确认结果不得重做，对`started but no result`明确UNCERTAIN并仅幂等只读重试。分进程故障注入测试（杀进程/重开Store、不能只new同一个Python对象）。
2. **S2.4-B 串行混合DAG执行**：4子任务以内拓扑校验、实际运行、依赖完成/失败/跳过状态落库；专业子任务优先，最终写作只能合并已通过证据门禁的结论；不先追求并行，需做到安全、可回放、可恢复和不重复assistant消息。
3. **S2.4-C 接入真实工具与UI证据**：用原三老师只读工具+受控样例实际调用（仍无真实LLM）；公开阶段/工具输入/来源与SQLite run一致。服务端保留原事件，普通展示与本地审核展示分离，并明确当前无生产鉴权的边界。Edge桌面/手机真实截图与网络console验收。
4. **S2.5 Provider与盲标**：上述门禁过关后，再讨论真实模型adapter（默认off，独立授权才允许真实paid key）；专业测试集与独立人工盲标（非LLM自标）分离。使用provider原生timeout、max_tokens、schema和实际usage并区分规划与报告费用。
5. **S3 DM82业务正确性**：材料/介质/温压角色与适用条件派生层、10–15高风险机理正反例试点、候选危险召回/误排除统计；不碰老师正式数据和人审列。

## 5. Codex协作约定（今后）
Codex直接读取本地路径/文件/命令，任务书不要求它依赖额外桥接插件。当前网页端进行本地检查所用连接方式不需要写入Codex任务提示词或实施合同。以目录内`AGENTS.md`、最新磁盘、报告为准，且不得用历史假PASS覆盖最近FAIL。

详见执行提示词`docs/CODEX_V2_S2_4_EXECUTION_RECOVERY_MIXED_20261029.md`。
