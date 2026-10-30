# Aetheris V2 需求定案与架构规格（Owner，2026-10-29）
状态：**DESIGN_APPROVED_IN_PRINCIPLE / IMPLEMENTATION_NOT_STARTED / NO_RELEASE**。用户已回答12个主要需求问题。本文件作为Codex任务的设计合同；工程实现必须先读当前磁盘、AGENTS及PROJECT_STATUS_CURRENT，文档未覆盖教师硬合同时以上游合同为准。

## 1. 冻结产品决策（记录用户真实选择）
1. **泛化优先**：即使用户未详细给出材料/介质/温压，系统也应在已知范围内开展有据初步专业调查、提出可区分假设与补证清单；不能简单“缺工况→一律不分析”。不能把一般先验写成现场确定事实。
2. 混合问题做**任务分解→子任务执行→证据合并**，独立解释/标准查证/设备研判/整理写作，有安全决定时专业子任务优先。
3. **模型主导意图识别**，采用结构化输出；确定性规则为权限、合同、危险结论等硬门禁。允许模型不确定或解析失败时进入保守路径；规则不是用关键词代替语义理解。
4. 专业执行采用**模式C且偏B**：保留RULE_DEMO确定性基线与LLM Agentic可选/默认发展路线；逐渐将动态规划、查询改写、工具选择、证据反思交给大模型，执行参数/来源/结论仍受程序约束。不要混淆单模型多角色与多独立模型。
5. DM82改革目标是**设备适用性判定**，不是只提高词法检索。官方老师Excel/JSONL/enum/工具原封不动，自有版本化派生语义条件库试点再扩。
6. 不足证据使用**分层候选**：SUPPORTED_WITH_CONDITIONS / POSSIBLE_NEEDS_EVIDENCE / EXCLUDED_WITH_CONFIRMED_CONTRADICTION / NOT_ASSESSED，展示支持、反证、未知、需要的关键现场参数，禁止伪确诊。
7. 目前处于开发测试；机器审核、Owner独立审计可做候选质量审查，但**不得替代老师要求的不同真人抽取/交叉签核**。正式发布仍受P16 gate。
8. 前端只显示自然回答、必要证据、默认折叠的**公开“思维过程/判断依据”**；打开后显示经脱敏的阶段摘要、工具名、可核查的输入/输出与出处。SSE仍用于传输/恢复，原始事件JSON仅受控本地数据库；不能展示模型私有CoT。教师演示要求的真实工具过程必须能核对，不能为了隐藏SSE连工具输入输出都藏掉。
9. 每个对话独立存储空间和有限上下文，考虑按阈值凝练，不把所有聊天无限送模型；普通聊天下文与设备证据隔离。
10. 默认简洁答复，按需生成专业完整报告；导出功能之后按审批实现，不能伪装正式工程鉴定。
11. 优先**不漏关键危险机理**，但不得把未经证据约束的宽召回直接写成机理适用/已发生。评估关键危险召回、候选精度、排除安全、无依据断言率，公开不能声称专家认证。
12. 保留老师上游和老目录；只进行安全小重构，移动历史代码必须依赖核查/备份/单独批准。

## 2. 当前实测基线（不是假想架构）
- LangGraph 1.1.2，langchain-core 1.2.19（本机2026-10-29实测）。`orchestration/r9_industrial_candidate.py`有StateGraph、MAX_INVESTIGATIONS=3、MAX_REVIEW_RETRIES=2、MAX_TOOL_CALLS=8、3冻结教师工具。现有`_selected_tools`是规则方案，Graph的investigator**没有LLM自主function call**，一般聊天也会经过graph.run。
- `backend/api.py`负责任务创建、同会话上下文、SQLite/SSE/DeepSeek；`backend/deepseek.py::generate_chat`当前限制同会话24条消息、16000字符及最近12轮，**没有持久化压缩摘要**。`backend/store.py`单SQLite WAL，conversations/messages/runs/agent_events/attachments已按conversation_id关联，另有独立LangGraph checkpoint。
- 65条困难路由样本现阶段48一致/17错误，工程→一般8例危险。旧离线R10 20例回归与当前P13有失败断言；不能借历史绿灯认定改造成功。
- DM正式82条：八段式非空82/82，material74/82，medium26/82，equipment_type81/82，temperature_c23/82，pressure_mpa0/82，verified_by0/82。参见`docs/data_quality/DM_APPLICABILITY_ROOT_CAUSE_AND_REFORM_20261029.md`。这不是业务正确率。
- P16真人交叉人审仍0/50（42改动0/42），老师554/554 schema与工具17/17 PASS只是程序合同。不可读写老师原资料或盖机器签。

## 3. 目标路径与混合编排
```text
React Chat / attachments
  -> FastAPI run creation, conversation ACL, input snapshot, audit event
  -> Deterministic safety and permission precheck
  -> LLM Structured Intent + Task Decomposition  [可对绝对简单的问候走不增加调用的fast path]
  -> Policy Gate (validated schema, hard safety priority, model cannot override)
     -> general_chat: DeepSeek direct; zero LangGraph; no teacher tool
     -> standard_lookup: light teacher standard_clause_search -> relevance/provenance -> synthesis
     -> engineering: bounded agentic LangGraph
     -> mixed: bounded subtask DAG, engineering first if safety-related, merge verified results
  -> Answer Contract checker -> complete_run atomically -> SSE back-end replay
  -> UI final answer + sourced cards + default-collapsed public decision summary
```
子任务类型至少支持 GENERAL_EXPLANATION, STANDARD_LOOKUP, MECHANISM_EXPLORATION, DEVICE_DIAGNOSIS, RBI_ASSESSMENT, WRITING_SYNTHESIS, CLARIFICATION_REQUIRED; 最终路由三主路径，不能把具体风险判定改成普通写作。普通“什么是应力腐蚀开裂”无需强制查标准；明确“按GB/T解释”查标准；给设备工况/现场故障则工程。含安全内容的混合问题拆分，写作子任务只能读取工程门禁批准的最终结论与状态。
**模型路由返回规范建议**：version, primary_route, subtasks[{id,kind,user_goal,requires,facts_refs,task_risk}], safety_relevance, confidence, reasons_public, needs_clarification, model_usage, provider_request_id。严格Pydantic/jsonschema、长度、枚举、最多4子任务、DAG无环、最大总调用和时间，失败或低置信转受限工程探索/澄清。**模型“安全”标签不能授权风险等级/批准来源/伪造老师审核**。
对非常简单闲聊可用严格短路，一次generate_chat；其他LLM路由可能额外一次模型调用，必须实测次数、TTFT和费用，不假称一般问题始终一次。后续可考虑单次LLM同时给route+general answer，但只在不破坏policy gate/质量时做A/B。模型配置不可用时RULE_DEMO低置信、安全保守；真实收费调用仅经Owner明确授权。

## 4. 工程LangGraph V2（动态规划、模型能力与执行器权限分离）
节点建议：
```text
prepare_case(context facts, provenance)
  -> planner(LLM JSON subgoals/queries/tool proposals)
  -> validate_plan(policy: tool allowlist/args/schema/rate, no unapproved docs)
  -> execute_teacher_tool(only exact 3 names; read-only, attempt trace)
  -> ground_sources(provenance, official SHA, identity, relevance)
  -> applicability_check(three-valued predicates and missing facts; pilot only)
  -> evidence_reflection(LLM compares competing hypotheses and asks targeted next question)
    -> (bounded revise_plan -> tool) OR independent_review(auditor + skeptic)
  -> gate_and_answer(grounded claim schema) -> publish public activity projection
```
每节点单一职责，state存**原始可复核数据**：conversation_id, run_id, source_sha, user_facts[provenance,observed/negated/unknown,unit,scope,updated_at], hypothesis[{claim_id,probability?禁止无校准的数值概率, evidence_links, conditions, contradictions, unknowns, status}], plan, tool_history, retrieved_sources, disagreements, budget, final_contract。
- **只给模型决策权**：对用户意图、查询改写、调用顺序与取舍、下一步缺失信息选择、候选解释。**执行器不可逾越**：三工具白名单、严格schema、原PDF/JSONL来源、禁止人工签名伪造、无完整风险因素不得L1–L4、无标准出处不得逐字引用。任何模型对系统规则的请求当不可信文本。
- 缺材料或介质时允许先调用`standard_clause_search`和做一般失效模式调查；只有`damage_mechanism_query`必需合法枚举材料/介质时才跳过它，不准给它硬造默认值，也不准把实际非枚举词偷偷映射成错误枚举。不得因信息不全把整个Graph跳过。
- 只把**真实用户检测/台账**作为现场观察；模型假设、文献一般规律、历史摘要不能填充现场字段。所有温度/压力阈值必须指定对象（壁温、介质温、H2S分压、系统总压等）、局部/全局范围和证据来源。
- 独立审查：auditor检查条款来源、证据级别和引用；skeptic寻找反例/错误适用条件/不完整性。可调用模型，但“不同prompt的同一个模型”不等于真人独立交叉审签；不能让审查者只读上游planner的结论而无源材料。
- 最大3调查回合、8次**实际工具attempt计费**、至多2次重审（可先沿用R9界限）；LLM分类/规划/反思/复核分别给预算，限流/时间，超预算返回保留不确定性的部分结果，不虚报完整。
- 使用现有run级幂等与SQLite唯一终态，LangGraph thread_id可按(conversation_id,run_id)隔离单次checkpoint；跨轮会话由会话记忆服务喂state，而不是错把run级checkpoint当用户记忆。需验证resume中断重试和重复tool调用行为。

## 5. 对话存储：**每会话一个逻辑空间，不每会话一个db文件**
`conversation_id`是消息/附件/工具/报告/摘要/设备上下文的强隔离键。继续单个SQLite WAL+索引、外键、事务；`run_id`隔离单次轨迹和checkpoint；`tenant_id`/user ACL上线前补齐，没有账号认证时保持loopback demo和APP_ENV=production fail-closed。未来物理多库只在容量/合规数据隔离需要时再迁移，不提前造轮子。
建议添加自有表（迁移必须幂等且先对隔离临时DB执行）：
- `conversation_memories(conversation_id, memory_version, summary, covered_until_message_id, source_message_ids_json, source_hash, model_id, generation_kind, verified_state, created_at, PK(conversation_id,memory_version))`；
- `conversation_fact_assertions(conversation_id, assertion_id, field, value_json, unit, object_scope, provenance_type, source_message_id, confidence_label, confirmation_state, superseded_by, updated_at)`；
- `conversation_route_events(conversation_id, run_id, policy_version, llm_route_json, validated_route_json, reason_codes, model_call_count)` 可合并现有runs JSON若无新表收益；
- memory与Graph checkpoints不是权威设备事实；源消息和审计事件永不被摘要覆盖。
窗口组成：system/固定规则 + 当前请求 + 最近可见完整N轮(先沿用12轮上限) + **可选**已覆盖旧历史的摘要 + 经来源确认的设备事实 + 当前相关证据引用；不带跨会话数据、全部附件和模型隐藏推理。超token预算或历史达到阈值才触发增量摘要；先实现可运行无模型的bounded-history baseline，再实现**显式可选、可mock、可验签**的模型摘要。摘要要附覆盖范围/hash，增量只处理新消息；失败时用截断历史仍可回答，不得自行伪造旧消息、设备参数或签名。
事实冲突：用户当轮明确纠正旧值→旧断言标superseded，保留变更历史；“用户只问某参数会不会变化”不视作测量数据；助手建议永不写为用户已确认事实。普通聊天仅最近普通交互上下文，专业输入默认不外传通用模型；除非用户在当前轮明确授权并只传有界最小必要内容。
上下文压缩计费单独记账（摘要模型额外请求次数），不可每轮无脑请求；允许用户清空本会话设备工况、查看/纠正已确认事实（开发版先接口和mock验收）。

## 6. 知识适用性与专业正确性契约
老师正式源只读，Owner派生层以source PDF/JSONL SHA、具体条款+印刷/物理页、原文短摘录定位，`predicate`包含subject/object/unit/op/range/polarity/role/scope/evidence_state/reviewer_status。E0/E1证明检索与映射来源，**不等于PDF人工逐字核对或工况适用**。
候选必须记录：查到的知识源、支持条件、已确认矛盾、尚未询问或测量的条件、自动排除理由、是否需要人审。即便弱相关机理有可能，也不能直接删除全部候选以换虚高Precision：给主候选与待排查候选两个层级，比较危险召回和误报。
开发期Owner/模型审阅只生成MACHINE_CANDIDATE或OWNER_TECHNICAL_REVIEW的技术意见，**不可填老师人工交叉核验列、不可改实物真实签名或宣称真人独立复核**。
先做10–15个高风险试点+至少30–50独立正/反/缺信息gold；再扩大82条。设计详见`docs/data_quality/DM_APPLICABILITY_ROOT_CAUSE_AND_REFORM_20261029.md`。

## 7. 前端公开追踪与专业报告
- Chat bubble: 最终答复 + 重要证据卡 + 一个默认收起的“思维过程 · N步”。过程内按阶段显示任务拆分→工具检索→证据检查→假设鉴别→复核→结果；点击阶段二次展开**经脱敏可核查的参数/返回摘要及原标准来源**，不展示原始SSE帧、JS JSON dump、隐私信息和模型内在CoT。简单闲聊可以没有复杂步骤，不用捏造N。
- 实际`ActivityTrace.tsx`使用工具group与`argsText:JSON.stringify(step.tool.args)`；需要改成可信`public_trace_projection`接口/前端schema，默认用户层无原始JSON，教师本地审核模式才经权限控制查看详细逐步工具信息。开发版没有真实鉴权，不实现伪admin令牌或公网debug endpoint。
- 专业结论默认简洁，支持“生成完整分析报告”的后续显式子任务（报告包含问题、已知、候选、标准出处、反例、尚需补测与责任边界），报告不是正式工程设备安全证书。

## 8. 评估要求、阶段 Gate 与关键反例
- ROUTE：原65 hardcases+冻结≥100独立新案例（含缺材料/混合任务/普通创作/长上下文/模型JSON坏/模型有害策略建议），专业安全→general的漏判**在测试集为0**；必须报告样本构造和OOD泛化，不宣称现实事故漏判率为0。
- AGENT：官方tools 3个不变；无必需材料/介质时能够通过标准搜索产生有出处的**限定分析**；模型提出不存在工具、越权参数或未经核实来源时安全拒绝该动作；tool预算/重试/断点恢复正确。
- CORRECTNESS：Expert gold上关键危险Recall@k、False Exclusion、Unsupported Assertion、Missing Context Calibration、E0/E1/E2/E3不越级；对完整工况与缺工况正反例分别测，不拿schema通过当专业准确率。
- MEMORY：会话A和B多轮隔离、旧设备参数覆盖/纠正、摘要跨阈值不丢核心事实且不会把模型推测升格、摘要失败降级、SQLite迁移旧数据不丢、run checkpoint独立。
- UX：普通消息无raw SSE/JSON、展开有正确脱敏工具输入输出和真实来源、从DB回放一致、连续问答与移动端通过；后台完整事件未删减。
- SYSTEM：保留用户输入幂等、SSE sequence/单终态、SQLite WAL一致性和并发4/8；c8旧压测27 queued/429必须实测修复排队重试，而非吞失败。
- TEACHER：现行554/200、17/17、50真人、模型100原生解析、5步真实、guardrail、ModelScope分别计，不互相替代。
- 模型调用费用未授权之前一律fake/mock/RuleDemo，**绝不调用本地真实API key**；不得擅自部署、重启运行服务、写正式DB和upstream。

## 9. 工作分批与模块所有权（避免Codex互相覆盖）
阶段 S0 冻结本文件、测试金标和结构协议。S1三窗口**互不写同一文件**并行：
- **A Router/API** owns `backend/api.py`,`orchestration/intent.py`,new `backend/intent_router_v2.py` and its own tests;不可改store/deepseek/graph/frontend。先做structured LLM gateway**mockable**、policy；直连普通chat调用现有deepseek。Agentic新图由B交付后再接线。
- **B AgentGraph** owns new `orchestration/agentic_v2.py`,`backend/agentic_provider.py`,new tests;不直接编辑`r9_industrial_candidate.py`,`backend/api.py`,`backend/store.py`。基于三个教师工具的只读adapter，实现可注入planner和RULE_DEMO fallback。
- **C Storage/UI** owns `backend/store.py`,new `backend/conversation_memory.py`,`frontend/src/components/trace/ActivityTrace.tsx`,`frontend/src/trace-events/model.ts`,独立测试；不可改api/intent/graph和upstream。先做临时SQLite schema和公开投影，摘要模型默认不启用。
整合阶段 S2 单独Owner Gate，等待A/B/C都可审计后再由一个窗口接线；后做D：82条件语义层试点（自有knowledge/和gold），不得与上游人工审核合并。每阶段要求命令、日志、截图(UI)、哈希与FAIL清单；禁止借历史PASS。先新文件/依赖最小更改；无测试不宣称完成。

## 10. 仍需未来讨论但不阻挡S1的选项
- 专业风险高时是否允许**可配置**的第二模型交叉审核 vs同模型隔离prompt；要用盲评gold比较成本与价值，不先承诺多模型精度提高。
- 记忆摘要阈值默认使用tokens测量还是粗字符估算；首版保留有界历史，摘要触发由测试验证与预算确定，不在需求讨论阶段拍脑袋。
- 等有认证与老师批准后，再考虑公开ModelScope、跨用户协作、长期跨会话记忆与正式工程报告签章。上述均不属于当前安全可发布能力。

## 参考
本机源码：`backend/api.py`、`backend/store.py`、`backend/deepseek.py`、`backend/context_slots.py`、`orchestration/intent.py`、`orchestration/r9_industrial_candidate.py`、`frontend/src/components/trace/ActivityTrace.tsx`。
LangGraph官方：`https://docs.langchain.com/oss/javascript/langgraph/thinking-in-langgraph`（功能建模、state原始数据与thread/checkpointer/interrupt原则）；实现必须结合本机Python包1.1.2的API，而不是照搬JS样例。
