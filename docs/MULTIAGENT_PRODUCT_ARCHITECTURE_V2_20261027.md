# Haeness2 多智能体企业化工程平台 V2｜产品和技术设计

日期2026-10-27。用户明确选择**多智能体是学习和产品硬目标**；教师单Agent原Harness只作为提交兼容基线，不把“教师可调用工具仅3个”误读成“平台内部只能3个角色”。本文属于设计，非宣称已上线。

## 一、用户故事
机械专业朋友交付符合老师合同的三个Tool、证据轨迹数据与ModelScope网页；我们计算机主线则开发工程风险研判工作台：类似豆包的聊天交互，历史会话持久化、持续事件流、可展开的Agent分工与工具轨迹、可点到原文的证据、多个工作模式、可重放和对照评价。

## 二、架构选择
优先在业务外层独立LangGraph StateGraph。保留原教师 `Harness.run` + 三工具为单体兼容模式。多体采用真实子图/节点（独立状态输入、system role、输出 schema、独立评测）；平台内部角色不注册成老师的第四个tool。初始5个角色：
1. Supervisor / Triage：任务理解、完整性/成本预算、条件路由、需求缺口，输出可审计的plan摘要；
2. Mechanism Analyst：症状→假设/支持/反证/区分证据；调用damage_mechanism_query和standard_clause_search；
3. RBI Specialist：风险等级与检验依据、实际缺失因子提示；调用rbi_lookup，缺信息则`risk_level=null`；
4. Evidence Critic：可独立审查检索与前两代理的假设，反证和来源E0–E3核对，支持二次检索/退回；
5. Reporter：综合强证据与未解问题，结构化输出与用户可读解释；不得臆造quote/页码/风险数字。
真实多LLM模式与Mock RuleDemo必须明确区分，不要只把单LLM输出切成五段就称多智能体通过。

## 三、状态协议（数据和控制分离）
`WorkflowState`包括 conversation_id/run_id/user_input/normalized_observations/hypotheses/tool_observations/source_refs/missing_information/reviewer_findings/decision_status/cost_budget/next_agent/iterations；每角色只修改自己持有的字段。每个可审计事件必须包含seq、run_id、agent_id、phase、status、started_at/ended_at、source和error。所有节点接收同一schema，避免agent互相传任意自然语言导致的“悄悄偏移”。
迭代上限/超时/重试/环路预算：例如Supervisor最高两次重规划，单问题最多8次工具调用；超过则停止并列出未决问题，不能硬答或假装没有错误。这里是工程初始建议，非教师要求。

## 四、工程语义与标准PDF RAG双链
- 原始PDF/Excel由教师源保持原样（上游当前仍未全量检出）；建立`DocumentRegistry`记录sha、年份、标准版次、PDF页码与印刷页码。
- `ClauseRecord`仍读teacher `clauses.jsonl`（554）；不改原文。
- **新语义层** `Observation`(name, value, unit, polarity, observed_at, status=observed|unknown|not_measured, provenance, confidence)；
- `Hypothesis`(mechanism_id, supporting_evidence[], opposing_evidence[], needed_evidence[], applicable_constraints[], source_clause_ids[]);
- 数据模式：原文硬约束（材质/介质/温压/标准现行性）先过滤，随后BM25/FTS5+embedding混合召回，RRF排序、rerank精排，再按E0–E3与现场约束过滤。避免在输入“未测厚”时把unknown误编码为false。
- PDF自动抽取仅生成`draft_semantic_rule`，保留page, quote_span, extraction_tool, validation_state=needs_human_review；对照原PDF逐页确认前不得升级为`verified`或自动用于硬性风险定级。
- 外部资料（标准网站、公开论文）保留URL、发表日期、版权许可和“参考背景”级别，**不混写为国标原文**。

## 五、数据库选择
**SQLite WAL作为默认开箱可运行存储**，因为朋友无需安装MySQL，且本地单机演示有足够用；SQLAlchemy/SQLModel定义models并把MySQL作为配置适配器。数据库表：users(演示可不设账号)、conversations、messages、runs、agent_events、tool_calls、evidence_links、knowledge_sources、semantic_drafts、feedback、eval_runs。建索引run_id+seq、conversation_id+created_at；SSE断线重连读seq事件重放。
线上多实例/高并发和多进程竞争时迁移到托管MySQL/PostgreSQL，不为学习数据库而增加朋友启动成本。SQLite并不等于JSON日志；JSONL只可作为append-only审计导出，事务、检索和消息索引用数据库。

## 六、实时网站与思考链
推荐独立React/Next.js + assistant-ui（或CopilotKit/AG-UI）+ FastAPI。页面：左历史会话；中间消息流/模型输出；右执行时间线、引用证据与角色拓扑；底部输入/工况引导。事件层优先采用AG-UI已有事件（RUN_STARTED,STEP_STARTED,TOOL_CALL_START,TOOL_CALL_RESULT,TEXT_MESSAGE_CONTENT,STATE_DELTA,RUN_FINISHED）+项目自定义`EVIDENCE_FOUND`,`REVIEW_FINDING`，避免全新协议。
可视化“思考链”=可审计**决策摘要、执行计划、角色交接、查询理由、参数和结果、分歧与复核**。不承诺显示模型私有隐藏推理链或把内部CoT存库。
老师交付ModelScope Gradio作为第二个入口，可以同一个FastAPI/Agent核心适配官方流程，不能只交自建域名代替老师要求。

## 七、初期性能与可靠性原则
`T_total ≈ T_parse + max(T_parallel_agents) + T_tool + T_critic + T_report + T_stream`，实际依赖图中有串行边，准确预算要按关键路径统计。目标是第一token尽快流出、用户可见活动流，不是让不确定诊断更快硬答；多Agent增加模型往返，须对照单体质量/成本/P95。
缓存仅用于静态条款索引和已验证文档解析，不能缓存跨用户未脱敏工况；数据库持久化要带事务、idempotent event seq，关闭/取消后有可解释状态。

## 八、部署分阶段
第一阶段：localhost FastAPI+SQLite+React，单命令启动并自测；
第二阶段：ModelScope Gradio按老师要求单独发布，不携带收费完整PDF/密钥；
第三阶段：自定义域名+合法支持动态后端和HTTPS的平台；Cloudflare Pages等静态托管可放前端，但动态FastAPI/数据库需要单独运行服务；免费实例通常有睡眠、限制、无永久磁盘、出网和流量配额。**任何公网暴露需鉴权、限流、脱敏和密钥管理**，不能把本地SQLite直接映射公网。不保证存在任意持续免费的完整服务器，具体选平台时再验证条款。

## 九、学习每一层
Agent：LangGraph状态机、路由/仲裁、恢复和checkpoint；
语义：数据库NULL的三值逻辑、实体归一化、RAG hybrid和因果假设；
系统：SSE事件流、幂等、事务、调度、服务延迟、监控；
机械：腐蚀机理、材料分类、RBI风险矩阵和标准引用边界。
