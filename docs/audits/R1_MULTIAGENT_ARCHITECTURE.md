# R1 多智能体平台架构与审计边界

日期：2026-10-27。产品侧独立于 `upstream/` 教师交付面；禁止把内部角色注册进官方 ToolRegistry。

## 执行图

`SupervisorAgent → (route) → EvidenceAgent → DiagnosisAgent → RbiSpecialistAgent → EvidenceAuditorAgent → ReportingAgent`

Router branch is live: missing material/medium goes to ask-for-context and bypasses teacher tools; standard/clause query calls only `standard_clause_search`; mechanism/risk query calls structured damage query + fallback search; unrelated text is marked out-of-domain and bypasses tools. RBI is still a separate conditional specialist.

| Node | 可替换职责 | 写入状态 | Teacher 工具调用 |
|---|---|---|---|
| Supervisor | 工况/标准查询/上下文不足路由 | `route`, `observations` | 无 |
| Evidence | 结构化观测到参数；复用 frozen registry | `tool_results`, `candidates`, `evidence_refs` | `damage_mechanism_query`, `standard_clause_search` |
| Diagnosis | 候选/未知/缺证据整理 | `gaps` | 无 |
| RBI Specialist | 明确温度、压力、年限且有候选后才继续 | `rbi_results`, `gaps` | `rbi_lookup`（条件满足时） |
| Evidence Auditor | 条款 ID 存在/当前调用来源检查；E2/E3留给人工 | `issues`, `verification_level` | 无 |
| Reporting | 报告可核证内容与缺项 | `answer` | 无 |

图是实际可运行的 `AgentGraph`，节点以 `AgentNode.run(state)` 依赖注入；可单独替换/单测节点。该轻量状态图是 ADR-002 允许的 LangGraph 受阻回退，避免首轮引入 checkpoint/框架依赖而掩盖实际状态/事件合同。本轮节点实现是确定性 RULE_DEMO Agent 节点，**不是多LLM协作，也没有证明多Agent质量增益**。`mode`、API、网页、报告一致显式标记 `RULE_DEMO`。

## 不变量

- `upstream/` 老师 ToolRegistry 只能有 `damage_mechanism_query`、`rbi_lookup`、`standard_clause_search`；Agent 角色不是额外工具。
- 官方 tool 接口、五键外壳、Schema、八段式、风险映射和原始 PDF/XLSX 均只读。
- RBI 节点要求实际温度、压力、投用年限和非空机理候选。缺一就记录 gap，不调用 `rbi_lookup`；工具结果中风险为空也不推导。
- 对外 trace 只含 `decision_summary` / tools / args / results / evidence / timing slot，不展示隐藏 CoT。
- Evidence 等级：E0=条款ID候选/存在性未能确认；E1=ID存在且由本轮冻结工具返回；E2=标准原文支持断言；E3=材料/介质/温压/现场条件适用。自动化只做到 E1，不能冒充人工 E2/E3。

## 扩展点

`AgentNode` 协议、共享 `RunState`、`AgentGraph.add_node` 和可观测事件构成 provider 边界。接真实 LLM 时应在 Evidence/Diagnosis/Verifier 分别注入 provider client 与结构化输出 schema；先跑相同冻结问题的 RULE / single-LLM / multi-agent 配对集，分开报告 native parse、fallback、E0-E3、token/cost、TTFT、P50/P95。此轮 API key 与真实 LLM评测未配置。

## 选型权衡

Python 状态对象与顺序执行优先保证确定性、可测性、事件幂等序号和教师调用复用；成本是尚无 LangGraph checkpoint/interrupt/失败恢复、循环图需手动编排。SQLite 是本轮会话持久层；后续引入图 checkpoint 时应单独存图状态，不把业务事件表当作 checkpoint 替代品。
