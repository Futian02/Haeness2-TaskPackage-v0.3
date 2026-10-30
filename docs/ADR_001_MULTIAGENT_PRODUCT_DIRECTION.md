# ADR-001｜企业级多智能体机械风险诊断平台（用户方向已确定）
日期 2026-10-27。状态：**Decision accepted by user, implementation planned / NOT COMPLETE**。

## 目标相对于老师最低要求升级
老师要单Agent+三Tool+Harness+数据；我们要完成可交付客户的多Agent产品与可学的全栈工程：多角色协作、工程语义与结构化约束、可信引用、主动追问、流式对话、本地持久会话、API、部署和可审计质量门禁。教师三工具是兼容接口，不限制外部产品的Agent数量与内部服务模块。

## 主技术栈
- Agent编排：LangGraph StateGraph，图结构与checkpointer支持多角色、状态恢复/人审；老师原 RulePlanner/Harness 作为基线与工具适配，**不重写老师Schema**。
- 应用后端：Python FastAPI + Pydantic / SSE；统一事件 `run_started/agent_enter/tool_started/tool_result/evidence_selected/review_finished/run_finished/error`，前端只消费类型化事件。
- 存储：本地SQLite + SQLAlchemy/Alembic；用户朋友电脑零部署成本。后续迁移MySQL需明确 `DATABASE_URL` 与迁移回归；不要从一开始要求MySQL服务。Graph checkpoint使用支持SQLite的实现，业务会话/审计记录与checkpoint概念分离。
- 网站：React + TypeScript + Tailwind/shadcn/ui；可对照 CopilotKit/AG-UI模式，先看其开源组件和License是否兼容；若只需要项目专有的轨迹卡，自写小量UI比引入整套Open WebUI更易维护。
- 模型：通过兼容OpenAI格式的provider adapter调Qwen等模型，密钥仅从环境变量，后续按失败与成本选型号；规则回退显式标识而非伪“LLM成功”。
- 知识库：上游 `clauses.jsonl` 和三工具不可改变，内部可使用现有SQLite FTS5实验为检索基线，先从人工金标准再考虑Embedding/RRF/Rerank；标准原文保留不改写，相关条款强制结构化适用性过滤。

## 模块拆分（约束职责）
1. IntakeAgent：自然语言事件提取（equipment/material/medium/temp/pressure/field_evidence）、单位与同义词归一化；每字段 {value,provenance,confidence,missing_reason}；对布尔现场观测采用 tri-state `true/false/unknown`。
2. DifferentialDiagnosisAgent：既有`damage_mechanism_query`与`standard_clause_search`检索候选、支持证据、相反证据、待补采样；不输出最终等级。
3. RbiAgent：既有`rbi_lookup`，场景因子不齐仅返回根据标准的计算路径、`risk_level=null`；绝不因模型自信就给L3/周期。
4. EvidenceAuditAgent：先确定性校验clause_id E0/E1与参数适用性，再视需要由独立模型审查E2/E3；可退回上一环节最多一次。
5. ReportAgent：形成外显逻辑摘要、标准来源列表、可操作的“需要补的现场观测”清单；把不确定性保留下来。
6. Supervisor Router：根据请求与证据判断哪些Node必须调用，限制最大LLM/工具调用轮次，保证简单请求不被多体堆Token拖慢。

## 流式网站交互
左边历史会话、中央对话气泡、右边过程/证据审查抽屉：展示过程状态、关键工具、实参、返回摘录与时间、条款出处、风险未定的原因、待补充现场信息。不要展示模型不允许公开的隐藏推理链；“思维链”替换为**公开决策摘要+可回放事件轨迹+引用来源**。
支持会话管理、查看旧诊断的输入与工具输出、导出脱敏审计报告、比较补充一个证据后的前后研判变化。

## 开源项目候选（已核公开资料，采纳前复核许可与版本）
- LangGraph： https://reference.langchain.com/python/langgraph/overview （SQLite checkpoint/supervisor/swarm 官方支持）
- CopilotKit + AG-UI: https://docs.copilotkit.ai/langgraph-python （流式多agent聊天界面、HITL、共享状态）
- Open WebUI: https://github.com/open-webui/open-webui （仅借鉴UI，会话、历史数据库架构；新版品牌条款需仔细确认）
- Langfuse: https://langfuse.com/self-hosting （观测性很强，但自部署要求Postgres/ClickHouse/Redis/S3；对免费小服务器过重，不推荐首轮上）
- ModelScope Gradio：官方验收另行保留Gradio简版页面，商业对外产品与教学演示可共享后端。

## 接口设计准则
开放自有产品API，不修改老师所规定三个工具对外合同；所有Agent共享的只有结构化状态与引用ID，不互相写长篇自然语言当作状态；runtime不能隐藏规则 fallback；Trace每步有UTC时间戳、耗时、模型/工具标识、有效来源与脱敏策略。

## 最小反例
“未做测厚” = observation.value unknown，绝不是 wall_thinning=false；
“钢的腐蚀形态看起来很像某标准” != 现场适用；
“工具查到一条风险矩阵” != EF/IF/MCF/PF/MDF和后果完整，因此不能给数值风险与检验周期。
