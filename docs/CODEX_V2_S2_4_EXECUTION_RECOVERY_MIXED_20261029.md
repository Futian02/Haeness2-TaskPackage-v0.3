# Codex S2.4｜Aetheris 运行恢复/幂等与真实混合DAG候选实现
项目：`D:\作业\竞赛\计算机设计智能体\机械智能体`
**阶段状态**：S2已作为本地离线候选验收；S2.4目标是闭合运行协议和混合业务DAG，**不得将V2设为默认、不得改正式业务DB、不得真实调用LLM或修改upstream/教师工具/人审记录，不得部署或重启在线服务**。

## 必读（按顺序）
`AGENTS.md`
`docs/PROJECT_STATUS_CURRENT.md`
`docs/audits/V2_S2_OWNER_INTEGRATION_20261029.md`
`docs/audits/OWNER_V2_S2_REVIEW_20261029.md`
`docs/AETHER_V2_REQUIREMENTS_ARCHITECTURE_20261029.md`
`docs/AETHER_V2_MODEL_POLICY_GUARDRAILS_20261029.md`
`docs/CODEX_V2_S2_OWNER_HANDOFF_20261029.md`
当前真实源码：`backend/api.py`, `backend/store.py`, `backend/conversation_memory.py`, `backend/intent_router_v2.py`, `orchestration/agentic_v2.py`, `orchestration/agentic_contracts.py`, `frontend/src/trace-events/model.ts`, `tests/test_v2_s2_integration.py`，以及所有相关测试与现有test runner。先检查git状态和可能并行修改，保护尚未提交的用户文件。

## 冻结方向
只在**受控临时SQLite、Fake/Mock模型、只读教师工具**范围内实施。保持`AETHER_V2_AGENTIC_ENABLED`默认0和R9默认执行不变。已有S2-A/B/C状态、Owner修好的R9路由兼容、S2全量282/3skip和R10 mock20/20是历史基线，不可删除/放宽测试造绿。真正的安全门禁（模型不可能越权、完整风险参数不足不能给等级、E0来源不能冒人审）继续由确定性代码实现。

### Gate 0：真实现状确认
1. 打印项目Git快照并说明父仓/独立upstream区别，不碰现有RBI Excel M和候选备份。
2. 确定`backend/api.py`创建run、分配lease/CAS、SQLite event/tool-call记录、SSE replay、run终态、直接general与agentic候选的真实接口；画一个**时序图**，明确提交点和重试后何处可能重复执行工具。
3. 选择成熟的LangGraph/SQLite现有checkpoint能力；禁止额外写一个简陋任务调度器替代成熟runtime。明确哪一部分为LangGraph执行状态，哪一部分为业务执行账本。给出试验/修复后每一个Gate的实际命令、环境、数据、日志与回滚。
4. 当前`ReplayLedger`仅进程内，`_invoke` FutureTimeout不杀线程；**不得因checkpoint list有数据而声称durable exactly-once/cancellation已经完成**。

### Gate 1：持久执行账本与恢复（优先，只实现完这一Gate再进入下一Gate）
- 定义`run_id,subtask_id,step_id,tool_name,args_digest`稳定动作身份；与`conversation_id`关联、schema/foreign key/unique/状态转换，有必要使用事务与CAS提交。提议迁移只用于临时SQLite并给出回滚/备份策略，现有表不可删/破坏。
- 运行至少区分`INTENT_RECORDED`, `STARTED`, `SUCCEEDED`, `FAILED`, `UNCERTAIN`, `CANCEL_REQUESTED`等可观测状态；结果及来源hash受约束，工具前先登记、执行后原子提交结果/事件。重新进入同run已完成动作必须重用真实持久结果，不重新调用。崩溃在STARTED且无result的情况标记UNCERTAIN，**老师工具只读**可在限额内有审计地重试，记录是否可能重复查询，不可谎称物理exactly-once。
- 检查点必须能在**独立Python新进程**恢复，不只是同一候选对象新invoke一次。谨慎使用LangGraph`thread_id`与`checkpoint_ns`按run隔离，结合现有FastAPI run状态和lease，防止跨会话/跨run污染。单run只产生一个assistant终态，不能把已完成run变成再次执行。
- 真正的timeout需要底层调用有界、可取消或隔离；`Future.cancel()`只处理尚未开始的future，不是强制杀已运行线程。若进程隔离成本过高，可明确仅支持本地只读工具的软超时，但相关Gate保留FAIL，**不可移除超时预算保护**。
- 统一`tool_attempt`、模型请求、SSE事件与UI投影的调用计数含义；已记的事件不可回滚重编号。不把模型Fake usage当真实Token成本。

**故障注入验收**：
A. 已提交工具结果后kill worker→重启同run→实际工具次数不增、最终消息不重复；
B. 工具启动但结果未提交→kill worker→重启标UNCERTAIN，有明确允许的只读重试路径、attempt累计且不假装执行一次；
C. 工具异常/超时/坏JSON→持续记录错误而非hang；
D. 复用相同thread_id不同run_id→证据和checkpoint隔离；
E. worker lease过期、SSE断线/replay/重复`/stream`请求、queued任务→无事件乱序、无多终态、无幽灵任务；
F. 两条并发run相同和不同conversation_id→无数据串线。
必须使用真实独立子进程、临时SQLite和明确可观测调用计数。单元mock不能替代这些集成故障用例。

### Gate 2：真实混合子任务执行（先串行、不追求并行）
- 用户明确选择`MIXED`时，先保留不超过4个任务的`subtask DAG`与严格依赖。实现至少`GENERAL_EXPLANATION`, `STANDARD_LOOKUP`, `MECHANISM_EXPLORATION/DEVICE_DIAGNOSIS`, `WRITING_SYNTHESIS`四类子任务的**真实逐个调度**；不具备证据的写作不得形成新的现场断言或风险等级。
- 执行顺序由依赖拓扑+确定性安全规则控制，设备安全子任务不能被普通写作绕过；独立标准查询只调用冻结标准工具，不填假设备参数；专业工程分支调用候选Graph；普通解释使用本地离线Mock，不走老师图；写作只消费已通过输出门禁的结果，支持部分成功、失败、跳过和DEFERRED。
- 每个subtask的attempt、来源、依赖、状态写SQLite，意外中止后按Gate1恢复。不准只输出`MIXED_SUBTASKS_DEFERRED_CHECKPOINT_GATE`或者只保存DAG元数据，却报告“混合任务已完成”。
- 非混合一般、标准、工程仍保留低时延路径与既有Mock回归。若强安全条件尚不满足，禁用整合、返回已完成部分和缺失说明，禁止用写作补全缺证据。

**集成验收**：不少于15个混合正/反/异常用例，含“解释→查GB/T条款→研判换热器裂纹→报告”、“只翻译报告不研判”、“请直接确认风险等级但缺PoF/CoF”、“模型提出第四工具”、“标准无结果”“某子任务timeout”“中途kill后恢复”“上下文跨对话泄漏”“报告模型新增无源确诊”等；逐个检查真实工具次数、依赖状态、final message唯一、引用和SSE回放。若Gate1无成功证明，Gate2只能做隔离验证不可标GO。

### Gate 3：公开Trace与证据可核查性（在1/2完成后）
- 当前`frontend/src/trace-events/model.ts`将`keyword`与所有材料/介质/温压直接遮成“已记录”。请明确普通用户与教师审核者分别需要什么，设计`public_summary`、`public_tool_projection`、`restricted_owner_evidence`三个概念；**无真实认证时不要建立可任意切换的Owner debug入口**。真实运行参数只能在合法授权范围内展示，而且不能把原SSE帧、密钥、企业附件、PDF文本无条件推向客户端。
- 当前`/api/runs/{rid}/events`提供原事件，前端mask不是服务端权限隔离；正式上线需补真实认证/ACL/安全传输。开发版继续loopback-only、production fail-closed，并写出信任边界说明。
- 与老师三工具真实入参/返回source核对，页面步骤/来源/次数均必须来自已落SQLite记录；模型公开摘要不是内部CoT。Edge桌面及390×844移动视口做真实浏览器截图+console/network检查。无法拿到浏览器时标BLOCKED并保留源码专项测试，不虚报视觉E2E。

### Gate 4：回归/文档一致性
- 跑`./.venv-langgraph/Scripts/python.exe -B scripts/test_s2.py`，明确总数/skip；R10 20项回放、S1+S2专项、前端Vitest/TS/Vite、老师`validate.py --final`和17自测（全只读）。
- 独立路由65+120只是开发者整理样本，真实盲标缺口仍要写，不能自称准确率100%；DM82正式适用性/真人50证据/LLM原生100次仍待核。
- 固定`docs/audits/V2_S2_4_EXECUTION_DAG_REVIEW_20261029.md`记录每个Gate的真实命令、调用计数/崩溃log、成功失败、兼容性、修改文件和未通过项，并更新`docs/PROJECT_STATUS_CURRENT.md`最新标题。不要覆盖历史S2报告或回归文件，保留旧记录。
- Git项目父级大量未跟踪，任何删除/迁移/提交/clean/reset需另行审核。禁止上游变更、生产DB写入、付费API、在线服务重启/部署。

## 停止条件
如果实际数据/依赖/工具架构无法实现Gate1可靠恢复，保留有界候选和失败证据，**不要伪造恢复PASS后继续开默认V2**。若有真实Provider/公网/教师正式Excel/人审签名的需求，提出明确的Owner授权点，不执行。当前目标仅S2.4本地隔离工程验证。

最终答复必须给出：Gate0/1/2/3/4的分项状态、首次/复现命令、真实测试分母、并发/恢复计数、未解决失败、可回滚改动和下一步精确建议。**实现工作优先于重复规划，但不满足门禁时如实PARTIAL/BLOCKED。**
