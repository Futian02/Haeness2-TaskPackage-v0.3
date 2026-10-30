# ADR-002｜企业级多智能体产品层：边界、状态、选型

**决定（2026-10-27）**：用户确认多智能体平台属于核心项目目标，**不再是老师交付内的可选装饰项**。但任务包要求单Agent+3冻结Tool，所以创建两套边界：
- Teacher-compatible plane：原 `upstream/05_提交区/harness.py` + 原三工具 + 官方schema + Gradio/ModelScope验收，现存数据不可破坏。
- Product-learning plane：`agents/` LangGraph协作网络 + `backend/` API + `web/`聊天网页 + `knowledge/`标准来源与审计 + `evals/`企业级对照。
**所有子Agent复用同一冻结 ToolRegistry；内部Agent角色不是新增老师工具。** 公开模式先以标准辅助研判为主，不执行设备操纵指令。

## 1. 为什么不用从零手搓所有Agent框架
已有Harness可以作为教学样本学习for-loop、ToolRegistry、schema、异常和轨迹；多Agent编排的checkpoint、跨节点状态合并、interrupt、重复运行恢复、安全注入，是成熟LangGraph擅长的核心。参考 https://reference.langchain.com/python/langgraph/overview 。决定：**老师Harness保留，LangGraph用于上层有状态角色编排**。如果独立LangGraph适配因版本受阻，允许先实现小状态机保持同一事件协议，再在第二轮替换；不可只有5个空节点冒充多智能体。

## 2. 至少5个节点、3个实质上独立的角色
A. Supervisor（路由/预算）：理解问题、分解需要的证据与剩余预算，按任务难度决定是否启用反证审查，保护最大模型调用数。
B. Evidence Agent（事实/标准）：将自然现象转成结构化字段，调用老师的 `damage_mechanism_query` 和 `standard_clause_search`；不能使用收费标准外部正文冒充国家标准。
C. Diagnosis Agent（机理诊断）：结合工况与返回证据，对候选进行支持/反证/unknown追踪，调用 `rbi_lookup` 读取判级路径；不得擅自将 unknown→false 或风险`null`→L1-L4。
D. Skeptic/Verifier Agent（证据审计/反证）：每条最终断言要求匹配来源clause_id、source、适用材料/介质/温度区间；发现缺失时反驳并提取补测点；默认仅对高不确定性/高安全影响/新颖工况启动昂贵LLM，可先有确定性checker基线。
E. Reporter/Advisor Agent（报告）：可复核的结论、候选差分表、现场需补字段和下一步检查建议，给标准条款与页码；对未取得依据的设备等级/检验周期必须留空。

关键：不是每个节点都调用LLM，避免5x延迟；至少3个拥有独立职责/不同提示策略的真实模型子Agent模式需在R1中被实测。离线demo可以使用确定性节点展示流程，但UI必须标记DEMO，不得伪称多模型完成。不同角色之间传递**结构化状态**而非拼接长篇自然语言“自言自语”。

## 3. GraphState合同（建议Pydantic）
```text
SessionState = {
  session_id, run_id, turn_id, mode, locale,
  input_raw, normalized_context,
  facts: EvidenceFact[],
  candidates: MechanismCandidate[],
  retrieved_clauses: EvidenceRef[],
  tool_calls: ToolEvent[],
  disagreements: VerificationIssue[],
  missing_information: MissingFact[],
  final_assessment: Assessment | null,
  budget: {token_cap, llm_calls_max, elapsed_ms_max, max_tool_calls},
  event_ids: []
}
EvidenceFact = {
  field, raw_span, value, unit,
  observation_state: observed_true|observed_false|unknown|not_applicable,
  source_kind: user_observation|official_standard|public_reference|model_hypothesis,
  source_ref, confidence_evidence, conflicts: [],
}
MechanismCandidate = {
  mechanism_id, name, supporting_clauses: [],
  contradicting_clauses: [], assumptions: [], unknowns: [],
  disposition: candidate|excluded|unresolved, disposition_basis: []
}
EvidenceRef = {clause_id, standard_code, clause_no, printed_page, pdf_page_index?,
               content_raw_exact, applicable_conditions, verification_level:E0|E1|E2|E3}
```
`raw_span` 是从输入直接摘录可回放；`model_hypothesis` 不能升级为用户已观测事实。

## 4. 并行、同步、条件审查
- 设备条件归一化 → Evidence/检索（可并行执行词法与实验向量，但不是新增Teacher Tool）→ Diagnosis。
- Evidence Agent与诊断意见状态合并后，Verifier审查。low risk且证据一致时通过程序校验快速进入Reporter；证据矛盾/缺关键因子时升级LLM Skeptic或者人工。
- 若核查失败：最多1次“寻找反证/补问”修补；失败后生成“不能定级+缺失字段清单”。不允许无限 Agent ping-pong。
- 日志/事件可显示公开的`why_next_step`决策摘要、所选工具、输入、返回、来源、延迟；不显示未公开的内部链式思考。

## 5. 前端开源优先
候选A： [assistant-ui](https://github.com/assistant-ui/assistant-ui) MIT，React模块化对话UI、会话/消息、渲染工具调用、LangGraph适配，可复刻豆包型聊天体验；可与我们自己FastAPI SSE事件协议做轻适配。
候选B： [CopilotKit](https://github.com/CopilotKit/CopilotKit) + AG-UI，同一事件流支持协作、流式状态、human-in-loop，可与LangGraph/FastAPI结合；优势是协议集成，复杂度比轻chat前端高。
**决策默认A**（优先实现完整聊天UI和会话存储），若需要中断/动态节点UI，再升级AG-UI/ CopilotKit；不得把两套重框架同时投入首个Sprint。

## 6. 状态与企业运维
本地默认SQLite WAL+SQLAlchemy/Alembic；Friends机器无需独立MySQL服务。用DATABASE_URL抽象支持未来MySQL 8/PostgreSQL，部署时才迁移。为 message、run_event、tool_call、evidence 和 agent_cost分别建表，可做可重放/异常审查；SQLite checkpoint与业务表分别管理，杜绝内存会话成为唯一真相。
SSE schema 版本化：run_started, agent_started, decision_summary, tool_called, tool_result, verification, reference_added, token_delta, run_completed, error。
P50/P95和成本按session/run/agent/tool分拆。活动状态、取消、超时、用户断联重连都是后续真实企业能力。

## 7. 质量门禁
产品层每个新角色必须有可验证行为 + 契约单测 + 冻结样本。老师原工具、Schema、风险映射、原PDF/XLSX无变动。
除了schema correctness，还要由复核人确认E2原PDF文字和E3适用条件，保证“标准出处→判断”的链路。
