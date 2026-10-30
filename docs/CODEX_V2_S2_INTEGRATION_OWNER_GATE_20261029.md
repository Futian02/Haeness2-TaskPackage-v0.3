# CODEX S2｜三窗口联合集成验收与可控切换（只有S1 A/B/C验收后才执行）
项目根：D:\作业\竞赛\计算机设计智能体\机械智能体
**请先确认S1三个窗口交付真实源码与实测，不得现在提前执行S2。**
先读`AGENTS.md`，`docs/PROJECT_STATUS_CURRENT.md`，`docs/AETHER_V2_REQUIREMENTS_ARCHITECTURE_20261029.md`，`docs/AETHER_V2_MODEL_POLICY_GUARDRAILS_20261029.md`，`docs/CODEX_V2_S1_A_ROUTER_GATEWAY_20261029.md`、`docs/CODEX_V2_S1_B_AGENTGRAPH_20261029.md`、`docs/CODEX_V2_S1_C_MEMORY_UI_20261029.md`及三份`docs/audits/V2[A-C]*.md`，复查git状态、各分支依赖和本机测试，列出未完成项后再接线。

## 目标与任务
- 只允许一个集成窗口在验收后编辑共享接线点：`backend/api.py`、`backend/deepseek.py`、`backend/store.py`、`orchestration/agentic_v2.py`、前端公开投影文件及整合测试；**禁止自动覆盖S1窗口持续写入的文件**。先协调文件所有权/必要时临时worktree，保持原方案作为fallback。禁止upstream、正式Excel/JSONL、真实数据、签核、在线重启、真实paid API。
- 使用`feature_flag=V2_AGENTIC`默认off，RULE_DEMO原R9保持可复现；当用户选V2时FastAPI结构化router、agentic V2图、会话记忆服务、前端ActivityTrace有统一schema、相同run_id、同一真实事件序列与单个原子assistant回答。
- 纯普通聊天必须zero Graph calls；标准查询不需要材质；工程任务缺字段时仍进行标准级差别分析但不伪确认；混合请求独立规划/合并；上下文保护和设备事实纠错；教师工具恰好3个。
- 任何模型的规划/工具策略/建议不得穿透policy gate。E0/E1、E2/E3、风险L1-L4、真人签核、错误压力对象、弱相关机理需要各自positive/negative evidence。没有真人审核不能成为正式业务结论。
- SSE只内部传输/replay；用户看自然答复＋证据卡＋默认折叠的可公开步骤/脱敏输入输出，不显示raw SSE JSON/密钥/内部思维链。测试回放和真实tool event一致。
- 旧R10 mock回放、本轮P16-B/R8B fallback失败、100c8排队429和当前旧服务PID/磁盘差异先按当前状态诊断，不得借别的版本历史跑分虚报修复。更改排队模式须保留queued任务生命周期、429 Retry-After、前端有界重试与终态。
- 对照S1 gates与当前`docs/AETHER_V2_REQUIREMENTS_ARCHITECTURE_20261029.md`全部验收项：官方 validate554/200、老师tools17/17、至少165路由case、≥30专业fake反例、会话隔离/摘要、UI测试+build、隔离c1/c4/c8含pending终态。所有详细命令、计数、环境、超时和残余FAIL写文档。
- 做新旧R9 vs V2在同一冻结离线题库的差分报告（路由、重要危险召回/错误断言、Tool调用数、LLM模拟调用数、API性能、SSE回放），不得以LLM模拟作真实付费模型效果；若没有真实gold只能明确工程正确性尚未量化。
- 集成代码和报告交`docs/audits/V2_S2_INTEGRATION_OWNER_GATE_20261029.md`，以实测GO/NO_GO决策。仅当回归/业务门禁合格且Owner另行批准，方可讨论把V2从默认off改为on；本次不发布/不开公网/不更改老师数据。
