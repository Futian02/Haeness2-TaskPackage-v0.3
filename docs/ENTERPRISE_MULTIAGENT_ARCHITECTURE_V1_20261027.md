# Haeness2 Enterprise Agent Lab｜多智能体产品架构 v1
2026-10-27。定位：机械设备可信风险研判场景的多Agent全栈工程实训＋教师单智能体兼容路径。
本架构为计划，当前基线仅app/runtime.py、app/web.py和SQLite FTS5实验，尚未完成多Agent网站。

## 架构约束
- 向老师交付的唯一工具接口仍是 damage_mechanism_query、rbi_lookup、standard_clause_search，统一五键、八段式和原始JSONL保持。
- 多智能体是我们的**企业产品层**，不是通过篡改老师原三工具完成。产品层各agent通过同一个 tool adapter 获取可靠标准证据。
- 动作轨迹显示公开可审核的决定摘要/检索词/工具参数/结果/引用与耗时；禁止把模型不可访问的隐藏内部推理链伪造成“真实思维链”。
- 局部模型失败能降级，但UI与测评显式记录fallback，不当作LLM parse success。
- 原始标准层被视为证据，不将外网搜索说法冒充GB/T原文。

## 建议技术栈
Frontend：React + TypeScript + Vite (学习组件化、SSE、状态管理)；参考Open WebUI交互，但自建领域界面；第一阶段可保留Gradio作教师演示兼容备份。
Backend：FastAPI + Pydantic + SQLAlchemy + SQLite（默认零安装）；日后 MySQL 只需URL+migration即可切换。
Orchestrator：LangGraph state graph 优先，保留上游教师 Harness teacher-compatible；外部启用 Agent角色，按条件调度；学习Agent state、edges、checkpoint、handoff。对于流式事件，自建统一Trace协议，OpenTelemetry可后续加入。
LLM provider：OpenAI-compatible client→Qwen/DeepSeek等，接入密钥使用环境变量；本地无需凭据可mock演示并注明不是模型输出。
RAG：现有554条结构化 clause library；硬条件过滤→词法FTS5/BM25→按人工金标选增Dense Embedding→RRF→Reranker→E0-E3引用审查；不直接将标准PDF任意切chunk而丢条款号/章节。
部署：本地网站端到端先稳定；公网免费服务器/自有域名/HTTPS需要核实具体提供商配额与限制，免费不等于稳定，公网不得暴露付费token、敏感标准原文。

## 智能体角色和触发
1. Intake Agent：解析工况、标准化单位和同义词，将unknown与observed_false区分；触发条件=自然语言输入。
2. Retrieval Agent：把机理候选问题映射至三官方工具、解释适用性、收集clause ID；它不是新老师工具。
3. Mechanism Analyst：候选机理、支持与排除、提出缺失现场数据；可以调已有工具。
4. Adversarial Reviewer：查反证、查来源真实性E0/E1/E2/E3、拒绝错误确定性；当低置信/候选冲突/生成最终结论时触发（至少final前一审）。
5. RBI Agent：只有现场可能性与后果因子齐备才判级；缺失只说明因子与判定路径，不能臆造L1~L4和年数。
6. Report Agent：把已审议结论与来源生成用户可读安全报告，指出建议核验项。

**不要硬性六Agent顺序走满**。低风险简单查询走 Intaker→Retriever→Analyst→Reviewer→Report；复杂证据冲突才走迭代/更多审查；缺风险因子先追问而不是生成等级。模型调用次数设预算/最长路径。

## 核心数据契约（建议，未实施）
Case {equipment, material_normalized, medium[], temperature_c?, pressure_mpa?, evidence: map[string, {state: observed_true|observed_false|unknown, value?, unit?, origin}], question, normalized_aliases[]}
Hypothesis {mechanism_name, supports[], contradicts[], unresolved[], confidence_label?, source_clause_ids[]}
Evidence {clause_id, standard_code, clause_no, page, content_raw, applicable_conditions, match_verdict, provenance_type: standard|web_public|user_observation}
Review {claim_id, source_clause_ids[], validity: supported|contradicted|insufficient|out_of_domain, issues[], reviewer_method, manual_verified: bool}
Event {session_id, run_id, seq, kind, agent, public_summary, tool, sanitized_args, result_ref, elapsed_ms, timestamp}
保存这些结构至数据库时对证据ID建索引，trace事件按run_id+seq唯一，外网引用不可暴露数据库密钥。

## 图式
User Chat → Intake → Policy&Routing → Retrieval ↔ Analyst → [Review / Contradiction] → RBI (if sufficient) → Report → UI + DB
              ↘ teacher-compat Harness independent mode
每一个agent返回结构化产物；人可以点击每个evidence回看标准号/页码/原文摘录；Trace可以回放同一轮工具输入输出，不宣称相同LLM随机输出必然可复现。

## 实施Gate
M0 全仓同步/文档来源完整，老师最终验收继续通过；
M1 Backend DB Session/Run/Event SSE，前端本地聊天与mock流，单老师工具真实调用；
M2 Intake + Analyst + Reviewer + Report的真正agent协作，≥1真实LLM、可检查handoff，100组工具解析；
M3 工程语义知识卡、现象抽取、否证/缺失；冻结领域金标、混合检索；
M4 领域UI、可折叠Agent工作流、会话搜索、报告导出、并发超时；
M5 本地域名/免费公开托管试部署与ModelScope老师入口并行；通过真实访问与可用性验收；
M6 单agent/多agent准确率、误硬答、延迟、成本A/B，出产品技术报告与答辩演示。
