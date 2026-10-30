# V2-B 模型主导 AgentGraph 候选审计报告

**状态：** `READY_FOR_OWNER_REVIEW`（独立候选实现与隔离测试完成；不代表集成验收或生产批准）  
**范围：** S1-B，仅候选编排、假模型、隔离 fixture、专项测试和评估案例。  
**基线：** R9 原运行图和默认路由保留，候选未被接入默认 API / Runtime。  
**真实模型/计费服务：** 未调用、未加载 API Key、未做外部网络请求。

## 1. 交付内容

| 文件 | 内容 |
|---|---|
| `orchestration/agentic_v2.py` | LangGraph 候选：准备输入、模型规划、策略校验、工具执行、来源落地、候选条件整理、模型反思、并行 Auditor/Skeptic、结论门禁、报告 |
| `orchestration/agentic_contracts.py` | 规划/反思/工具参数/审查的严格 Pydantic 合约（extra=forbid、strict），含 teacher `evidence` 六个子字段 Schema |
| `backend/agentic_provider.py` | 注入式 `StructuredPlanner` 边界和离线脚本化 Fake Planner；没有远端 Provider、Key 读取或计费回退 |
| `tests/test_v2b_agentic_graph.py` | 16 个专项测试，Fake 工具、合成条款和异常 Fixture |
| `evals/v2b_professional_cases.jsonl` | 31 个合成专业评测案例；`gold_truth=NOT_ASSERTED`，不冒充标准真值或人工标注 |

## 2. 图与责任边界

`prepare_case → model_plan → policy_validate → execute_tool → source_ground → candidate_conditions → reflect → model_plan（有界）→ review_dispatch → [auditor ∥ skeptic] → merge_reviews → review_gate（最多2次有条件再计划）→ claim_gate → report`

- 模型通过结构化输出决定工具、改写查询、提出调查目标，拿到来源证据摘要、竞争候选和复核反馈后反思是否继续。Fake Planner 只用于 S1 测试，实际模型未接入。
- 程序独立约束工具集合、参数 Schema、枚举、调用预算、事实来源、条款来源元数据和最终结论等级。
- 三个工具必须与冻结名完全一致：`damage_mechanism_query`、`rbi_lookup`、`standard_clause_search`。工具 registry 多一个或少一个都拒绝构造。
- User prompt、检索条款正文中的指令都不改变程序策略；不存在“工具计划即可执行”的信任路径。
- 非枚举材料/介质/设备条件不做别名猜测；候选计划会被策略层改道为原问题文本检索，保留输入字符串与未知状态。
- Auditor 和 Skeptic 作为 LangGraph fan-out 并发执行，各自只写独立状态字段；结论门禁再检查引用是否属于同一 Run 的已验证来源。

## 3. 缺工况行为

缺材料/介质/温度时不终止。Fake Planner 对“换热器裂纹”走标准条款检索，输出来源支持的可能方向、尚未确认的适用性和定向补证清单。缺材料或介质时，结构化损伤机理工具不会被调用；温度和设备只从调用方显式输入取值。数据缺失保留为 `unknown`，不当作“不存在”或排除证据。

结果中固定含 `confirmed_engineering_conclusion=false`、`human_review_completed=false` 和 `risk_level=null`。条款来源只支持进一步调查方向；不根据模型假设形成工程确认结论。补证建议分别指向材质（含复层/堆焊层）、腐蚀性组分与水相、局部/启停温度、系统压力与必要时 H2S 分压、设备分类及部位。

## 4. 来源与预算门禁

- 成功工具返回必须为冻结的五键外壳，`status=ok` 要求 `source` 非空且 `in_domain=true`。
- 每个来源 ID 必须存在于本地 `clauses.jsonl`；`standard_code / clause_no / page` 必须与规范记录逐字段相符。
- 输出以规范记录计算 SHA-256，并记录整库文件 SHA-256。老师工具当前返回字段不含 hash，因此该值标记为 `canonical_record_sha256_calculated`，不伪称老师签名或原始 PDF hash。若返回可选 `source_sha256` / `record_sha256` 则必须匹配，否则整组来源拒绝。
- 同一线程、同一 Run、同一工具与参数使用 `ReplayLedger` 防止重复执行；新 Run 或新线程不复用。重复动作仍消耗调查轮数，但不增加实际工具尝试数，避免重复计划造成无限循环。
- 每次工具操作最多 2 次执行尝试；全程最多 8 次真实工具尝试、3 个调查轮次；结构化 Provider 请求最多 12 次，候选端账面 Token 预算 12,000，运行墙钟默认 30 秒。规划失败、工具超时/异常、来源错误都保留可见状态。
- `rbi_lookup` 仅作只读查询；无 PoF/CoF 与完整审批证据时输出风险等级始终为 null，即使底层 fixture 或工具返回等级也不提升为报告结论。风险问题补证还列出 PoF 检测/损伤数据、CoF 介质/库存/后果边界及风险矩阵版本。
- 只读默认 adapter smoke 已成功实例化 `CompiledStateGraph`，从 `app.runtime.load_harness()` 读取到冻结三工具，加载本地 554 条条款并计算运行语料指纹；该 smoke 不执行任何正式教师工具。

## 5. 隔离验证结果

命令：

```powershell
cd D:\作业\竞赛\计算机设计智能体\机械智能体
.\.venv-langgraph\Scripts\python.exe -B -m unittest tests.test_v2b_agentic_graph -v
```

结果：**16 tests passed**。覆盖完整与缺失工况、HCl 95°C/管道/烟尘误归因反例、无检索命中、RBI 等级限制、提示注入、非法工具与枚举、模型伪造温度、模型提供来源 ID、来源元数据/Hash/空 source 错误、工具失败与超时、重放隔离、调查及复核预算、模型反思可见竞争候选、评估集数量与结论未知标注。

所有工具调用测试均由本地 Fake Tool 返回合成条款 `T-1`；没有调用老师正式工具、真实知识库、生产 DB 或真实模型。评估 JSONL 是测试覆盖清单而非教师校验结果。

最终复测命令 `python -B -m unittest discover -s tests -q`：**275 tests，1 failure、3 errors、3 skipped**。失败项为既有 `test_r9a_industrial_candidate` 的 `test_low_quality_retrieval_rewrites_and_retries_with_traceable_source`；错误项为同文件的 `test_identical_query_zero_information_gain_stops_loop`、`test_transient_tool_failure_retries_and_records_attempt_count`，以及 `test_p16_a_evidence42` 导入错误。V2-B 专项 16/16 通过；S1-B 不拥有这些既有模块的写权限，因此将总体验收阻塞交给 A 窗口判定，不把全仓测试宣称为通过。早先同命令观测到更多旧 Router/P3B/P4A/R9A 失败，说明当前共享树全仓测试存在波动；最终状态以最新一次复测为准。全仓运行的本地压测中 P13 100-run concurrency=1/4/8 三档均 0 errors，但本任务不据此认领 P13 验收。

## 6. 已知限制 / S2 交接

1. 这是一条隔离候选；尚未并入 API、默认运行图、用户会话存储、生产日志或 UI。
2. 实际 LangGraph 候选默认使用 Fake Planner。S2 可注入实现 `StructuredPlanner` 的获批 Provider；要将剩余 Token 上限转为 Provider 的硬 `max_output_tokens` 控制，并为请求时长设置 Provider 原生 timeout。当前 S1 在假模型边界做请求次数、估算 Token 和墙钟预算检查，不宣称是真实模型 usage 计量。
3. 来源哈希是本地数据记录的规范化计算值及本地整库文件 SHA-256，不是逐条 PDF 页面哈希或签名来源验证。正式采信需保留 PDF 页级证据和人工审核流程。
4. 语义支持关系仍属候选关联：结构化结果与当次工具 source 绑定，但本实现不自动判定标准是否充分支持设备级结论，也不推断材料耐蚀性或工况包络。
5. 线程超时通过线程池 Future 超时记录失败。工具当前为只读查询；若后续注入外部 Provider 或长时工具，应加进程隔离/原生取消，避免底层调用在超时返回后继续占用线程。
6. 任务文档要求的进度状态文件不在本窗口的 S1-B 写权限内；由 A 窗口确认候选与测试结果后更新中心状态。

## 7. 非目标与保护

- 未修改 `upstream/`、R9 基线、默认 API / Runtime、store、意图识别、前端、`.env`、正式数据库或 P16 签收文件。
- 不自动把模型假设、工具查询候选、检索相似度或 `verified_by` 空字段表述成确认事实、教师验证、人工签字或现场结论。

**交接状态：** `READY_FOR_OWNER_REVIEW`；等待 A 窗口做文件权限核验、全量测试、配置与接线评审，S1-B 不自行部署、不替换 R9。
