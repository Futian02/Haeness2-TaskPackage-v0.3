# 多智能体企业平台 R1：Supervisor设计裁决
日期2026-10-27。用户要求项目主目标升级为**真实企业项目式多智能体平台**；老师单Agent只是交付最低线，三工具协议必须继续兼容。

## 总体形态
浏览器React/Vite/TS（chat thread + 过程时间线 + 标准证据侧栏 + 多agent图）
→ FastAPI（REST写会话、SSE逐步推送，OpenAPI版本化）
→ Agent Runtime（LangGraph可选选型：StateGraph+SQLite checkpointer）
→ Coordinator / EvidenceAgent / CriticAgent / ReportAgent
→ TeacherCompatAdapter（只调用 upstream/05_提交区原有3个工具与Harness）
→ 原始554结构化条款（clause_id/standard_code/page/version）及只读PDF参考
→ SQLite（默认）/MySQL（作为可替换存储层） + 原始轨迹/证据表。

建议 Agent 节点如下：
1. Coordinator：解析意图，把设备/材质/介质/工况/现场观测中的缺失与否定区分，选择下一个节点及结束条件。
2. EvidenceAgent：只经三个官方工具查询；输入/输出严格Schema；返回候选机理、正反证据、来源列表、未解决的差别诊断问题。
3. CriticAgent：优先规则审查E0/E1 E2/E3，不依赖“第二模型觉得合理”；不具备标准原文/实测信息时拒给定级。
4. ReportAgent：将可核证来源、当前结论、待补证据、适用边界组织成用户易读表格；不创造专业事实。
5. 可选 KnowledgeCurator 离线节点：从PDF生成**未验证草案**，需要人类核实后才能进入检索主库。它是离线数据管道不是老师第四个在线Tool。

节点由工作流编排者按证据状态、轮次预算与风险决定启用，不是每个问题都强制4个模型顺序调用；并行审查也必须按成本收益对照。系统默认允许独立rule baseline供老师验收。

## 必备技术合同
Pydantic：`EquipmentContext`, `EvidenceState`, `MechanismCandidate`, `AgentStep`, `GroundedClaim`, `ReviewVerdict`。具体字段：
- `EvidenceState.value` 可为number/string/bool/null；`observed`三值：known_true/known_false/unknown。没有测厚是unknown，不是false。
- 每个`GroundedClaim`带 `clause_ids[]`, `source_quote_hash`, `applicability_checks`, `verification_status`（draft/machine_checked/human_verified/rejected）。
- `AgentStep`: `node_id`, `seq`, `start/end`, `public_decision_summary`, `tool/args/response`, `latency`, `error`, `sourceIds[]`；绝不声称输出模型隐式chain-of-thought。
- `ReviewVerdict`: `supported/insufficient/contradicted` + `missing_fields[]` + `reasons[]`。
- 最终仍导出老师固定`trajectory.schema.json`的字段，不添加自定义字段污染官方数据；产品事件单独存数据库。

## 数据库
SQLite优先：无需安装服务、易迁移、朋友可开箱即跑；通过SQLAlchemy/Repository抽象预留MySQL。基础6表：
`sessions(id,title,created_at,...)`、
`messages(id,session_id,role,content,ts,...)`、
`runs(id,session_id,status,model,started,ended,latency_ms,...)`、
`steps(id,run_id,seq,agent,tool_name,args_json,result_json,public_summary,latency_ms,...)`、
`evidence_refs(id,run_id,clause_id,standard_code,page,support_state,verified_by,...)`、
`feedback(id,run_id,quality_label,comment,...)`。
可选`checkpoints`/ `knowledge_drafts`，不存密钥明文，不把人工未验标成human_verified；提供迁移版本与索引。

## 前端用户体验
左侧：新建会话、历史、最近实验；中间：聊天/生成中/SSE分段/步骤卡片/多个Agent头像和转交；右侧：准确显示标准号、章号、页码、引用短片、E0-E3状态。
对话结论区使用`可确认`/`待确认`/`不在覆盖范围`三段式；证据不足时给需要采集的字段和鉴别下一步，不用“胡乱置信度百分数”冒充概率。
用户允许保存本地会话，默认SQLite文件位于`data/local/`（Git ignore），后台启动无需MySQL。
UI可以借鉴Dify/Doubao的**信息架构**，不要抄品牌图标/受保护资产或宣称开放隐藏思考内容。

## 技术选型来源及目前观察
Qwen-Agent(https://github.com/QwenLM/Qwen-Agent)：专注Qwen模型的tool calling、planning和RAG；适合学function call层。
LangGraph(https://reference.langchain.com/python/langgraph/overview)：当前支持StateGraph、多角色、SQLite/Postgres检查点与supervisor/swarm形式；适合多Agent核心编排。
OpenAI Agents SDK(https://developers.openai.com/api/docs/guides/agents/sdk)：handoff、guardrail、trace，适合学运行时与可观察性；
Dify(https://github.com/langgenius/dify)：可视化流程+RAG+agent+模型管理，参考UI与工作流，不宜为了本项目直接自托管整个Dify。
Langfuse(https://langfuse.com/self-hosting)：trace/eval观测参考，完整自托管代价高；本项目先SQLite追踪，不起复杂基础设施。
公开框架功能与License版本可能变化，采用前检查最新文档与依赖。

## 首轮开发判据
A. 本机可以新建会话，发送3种设备样例，至少从真实官方Tool得可追溯证据。
B. SSE正常/断开/重连状态有日志，sqlite重启后读会话与步骤。
C. 多角色工作流至少一个真的可执行的coordinator→evidence→review→report链，不靠固定静态动画。
D. 不能使用老师合同以外的第四个tool；能够切rule baseline；真实LLM凭据不可用时显示Not Configured。
E. 负例：未测厚、材质不支持、工况越界不得硬填等级；审查器阻止无出处引用。
F. 每个功能附≥1个自动测试；与官方validate --final等测试并行保留。
