# CODEX S1-A｜模型意图路由 + 确定性安全门禁 + FastAPI普通直连
项目根：D:\作业\竞赛\计算机设计智能体\机械智能体
状态：**授权开发自有代码，非发布授权**。本任务是设计/实现的独立窗口A，禁止改教师上游和正式库。
开始前完整读取：`AGENTS.md`、`docs/PROJECT_STATUS_CURRENT.md`、`docs/AETHER_V2_REQUIREMENTS_ARCHITECTURE_20261029.md`、`docs/audits/OWNER_DATA_ROUTING_TEACHER_STRESS_AUDIT_20261029.md`；再检查本机`backend/api.py`、`orchestration/intent.py`、`backend/deepseek.py`、`backend/store.py`及现有测试。禁止根据任务单覆盖新磁盘变更，先git status。

## 唯一文件所有权
允许：`backend/api.py`、`orchestration/intent.py`、新建`backend/intent_router_v2.py`、`tests/test_v2a_router_gateway.py`、`evals/v2a_router_gold.jsonl`、`docs/audits/V2A_*.md`。
不得：`backend/store.py`、`backend/deepseek.py`、`orchestration/r9_industrial_candidate.py`、`frontend/**`、`upstream/**`、任何真实SQLite、.env.local、既有人工审核记录。不得修改项目外parent Git/全量git reset。不要占用/重启现有8000进程。

## 目标
实现可注入/可mock的`LLMStructuredIntentRouter`（模型结构化JSON、schema/枚举校验和策略校验），FastAPI内按任务分流；日常general在worker层**不调用graph.run**而调用已有`deepseek.generate_chat`，保持同会话有界历史和SQLite/SSE/失败反馈一致。纯标准lookup可先复用老路径（标注TRANSITIONAL，禁止谎称已独立轻量路径），或在自有薄封装只调用正式`standard_clause_search`并做现有来源相关性门禁。专业路径暂继续复用老R9 Graph，等待B完成再接新图。混合问题解析为有界子任务DAG和策略快照，允许第一轮实现安全保守降级而非假装各子任务已独立执行。

## 细则
1. 入口守卫：当前用户确实在询问设备安全/风险等级/现场故障/标准硬性结论时，**优先专业**，不能被前置“你好/你是什么模型/写篇文章”截断。64/65测试等自带样本不能专门训练后虚报泛化。用户没填材料/介质，仍允许专业探索，不把所有问题返回missing_context。
2. LLM路由可返回`primary_route`、`subtasks`、`needs_clarification`、`confidence`、公开理由；Pydantic严格验证；只能用模型来**建议**，不能让模型JSON单独授权teacher调用、规避白名单、对设备确定评级或修改数据。模型不可用、JSON坏、timeout/too many tasks时，使用无模型的安全保守回退，记录原因，不凭空向用户输出模型成功。
3. 对纯问候允许fast path，真实普通聊天不进入Graph；对非平凡请求LLM route可能增加一次模型调用，必须明确model_request_count，不能宣称general均仅1次。**默认禁真实模型调用**，可通过注入mock演示，不读key不发收费HTTP。真实LLM接线需有单独ENV feature flag默认off。
4. API重用现有run snapshot、worker lease CAS、event sequence、SSE回放及原子terminal；不能把两段assistant插入同一个run；不能因为直连跳过错误态。不能把密钥、提示词、CoT、原始SSE事件打印到用户正文。
5. 有限并发仍可能429/queued；本轮先诊断并设计backpressure回退测试，不在未经测试的情况下删除限流器。要报c8老测试和新测试差异。避免因全局module import创建/修改正式SQLite，测试patch临时DB。
6. 专业引用/工况未确认不得写“已诊断”“风险L1–L4”“已人工交叉核对”。模型输出仅为解释和规划；教师3工具入参schema不可改。

## 强制测试
- 原65困难用例（可读`evals/owner_mixed_intent_route_audit.py`）逐例分类并输出差异；新建≥100独立盲测用例，按普通/标准/专业/混合/改口/缺参数/提示注入/坏JSON分组（盲测不能仅复制65的句式）。专业→general在冻结集中0、普通→专业误路由单独统计；记录没有实测线上分布。
- Mock LLM: valid route; invalid JSON; malicious route; timeout; wrong tool name; permission claims; mixed question; no context; fail-to-safe. 真实FastAPI TestClient至少一般/标准/专业三路验证run_id及SQLite终态一致，一般入口graph.run调用次数=0。
- 复查`tests.test_p13_router_hypotheses`、`tests.test_r10_casual_chat`、R10离线20矩阵本次已知历史FAIL，能归因则记录，不为过绿改老预期/跳过测试。
- 执行`python -B upstream/04_接口文档/validate.py --final`应继续554/200通过，旧selftest不变。

## 交付
代码+独立测试+真实命令/输出/分母/耗时/错误清单+实现变化表+明确TEMP/READY_FOR_OWNER_REVIEW状态。`docs/audits/V2A_ROUTER_GATE_REVIEW_20261029.md`说明每个route的LLM调用成本、有无Graph、fail-safe行为、尚未接线B功能、已知冲突及需要Owner审批的后续工作。不得制造PASS；对当前磁盘未解决问题如实BLOCKED。