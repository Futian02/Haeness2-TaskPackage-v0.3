# 交给本地 Codex｜Luna High / Fast｜P0-P1 企业级多智能体纵切版
日期 2026-10-27。用户明确要求：把机械标准RBI任务当企业级技术实习项目，多智能体平台是核心学习目标；现有教师3个工具必须合规；本地豆包式网站、会话存储、结构化诊断与可追溯证据。**本任务不是重写老师原项目，而是外部新增多智能体产品层。**

## 工作目录与执行规则
唯一工作区：`D:\作业\竞赛\计算机设计智能体\机械智能体`。
首先读取 `AGENTS.md`、`docs/PROJECT_STATE.md`、`docs/MASTERPLAN_V1_TEACHER_FIRST_20261027.md`、`docs/TEACHER_REQUIREMENTS_AND_GAPS_20261027.md`、`docs/TEACHER_QA_CONSTRAINTS.md`、`docs/FULL_SYNC_AUDIT_PLAN_20261027.md`、`upstream/README.md`、`upstream/04_接口文档/工具接口规范.md`、`upstream/04_接口文档/技术指标验证方法.md`。 
对教师数据为只读：不得改名/改签名三个 `damage_mechanism_query`,`rbi_lookup`,`standard_clause_search`；五键返回 `status,in_domain,result,source,message` 与八段式、Schema、枚举、XLSX原文不动；不得硬给无依据风险值。禁止`git clean/reset`、删除用户文件、对父级竞赛目录批量git操作；API密钥一律本机环境变量，不输出或提交。
若Luna High Fast profile可选使用，无法启用时正常Luna High，禁止虚报。

## Sprint A — 完整文件与签名核对（先做，有阻塞就报告）
1. `git -C upstream status --short --branch`，确认独立仓库干净；清点剩余磁盘容量。然后**完整检出**上游Git HEAD的全部追踪文件：`git -C upstream sparse-checkout disable`，不可只补01/02/03。若网络不足记录失败，绝不能假装完成。
2. 核实`python -B -m scripts.check_sources` 19/19及PDF/XLSX、案例、老师DOCX、参考代码目录真实落盘；记录真实文件数、总大小和SHA256抽样至 `docs/audits/P0_REPO_SYNC.md`。不要重复clone reference_code。
3. 跑官方终验、17工具测试、护栏、两份Harness一致性及我们的`python -B -m unittest discover -s tests -v`。保留命令、退出码、stdout精简结果、相应git diff。人审/真实LLM/公网部署不能伪报PASS。

## Sprint B — 先做可运行、可交互的多智能体“纵向一刀”
原则：先一个完整场景端到端再扩展，不要建一堆空类。**至少出现真实的多节点协作、状态变化与可观察事件**，规则本地模式无API也能演示；真实API模式在密钥缺失时标`blocked`/demo，不得把规则替代算作模型完成。

建议架构（允许发现成熟OSS适配问题时做技术调整并在ADR解释）：
- `backend/`：FastAPI + Pydantic v2 + SQLAlchemy/SQLModel + SQLite WAL，数据库默认 `data/haeness.db`（被git忽略）。MySQL留`DATABASE_URL`接口，朋友不用装MySQL即可运行。
- `agents/`：LangGraph StateGraph **作为多智能体编排层**（不是取代教师Harness），节点 `triage`(识别用户意图、校验)、`evidence`(调原三工具/证据查找)、`diagnostician`(排除式机理与现场差异分析)、`verifier`(条款与适用范围审查)、`reporter`(写保守结论与待补信息)；只有必须的节点参与，不能默认每问都5轮LLM。沿用`app.runtime`与原3工具Registry作为工具服务边界；外部四五个Agent是编排角色，不要注册新的教师工具。
- `web/`：优先 **React + Vite + TypeScript**（本地轻量、前后端分离），加Tailwind/shadcn/ui与[assistant-ui](https://github.com/assistant-ui/assistant-ui) 预制聊天控件；CopilotKit AG-UI只是替代方案，**只选一套**并记下选择原因与锁定依赖。不是一屏Gradio JSON，目标是类似豆包的三栏：左侧会话/案例、中央流式对话、右侧Agent协作时间线/工具节点/标准原文来源与适用性；支持深色/浅色、响应式。老师Gradio `app/web.py` 仍保留作为可独立上交的兼容Demo。
- 事件流：Backend以SSE传递 `run_started, agent_started, decision_summary, tool_called, tool_result, source_attached, verification, text_delta, run_completed, error`；仅展示**可公开的行动/证据/决策摘要**，不得输出模型隐藏CoT、私密原始提示词或密钥。
- 持久化：Session/Message/AgentRun/RunEvent/EvidenceRef这5张业务表；保留用户输入、模型公开回复、用户可见工具轨迹、来源条款、成本/耗时。SQLite WAL迁移用Alembic；跨进程重连后能完整恢复会话，不允许仅留React state；数据库输出不提交Git。避免无限存用户隐私和收费PDF。
- **工程语义模型**：`EvidenceFact` 包括 field, raw_text, normalized_value, unit, observation_state=`observed_true|observed_false|unknown`, source_kind=`user|standard|external|inferred`, source_ref, support_clause_ids, confidence_type, conflicts；至少实现`未做测厚`→unknown，`测厚无减薄`→observed_false，`测厚确认减薄`→observed_true 的隔离测试。禁止把`未提到裂纹`当false。
- P0建议选**一个**真实演示场景：碳钢常压塔顶+氯化氢/湿硫化氢+pH降低/Fe升高/测厚未知。流程自动得到候选机理、证据状态、缺失现场字段、可公开条款出处、条件不足的保守结论；能显示各Agent分别做了什么。不能把硬编码prompt当专家真实判断。
- `GET /api/health`、`POST /api/sessions`、`GET /api/sessions`、`GET /api/sessions/{id}`、`POST /api/sessions/{id}/runs` SSE；要求本机CORS仅允许本地web开发源，输入长度限制、异常脱敏、请求超时，非模型模式可完全离线运行。
- 验证端到端“创建会话→输入工况→Agent流事件→3工具→拒判及证据→保存消息→重启API→历史仍在”。至少集成测试覆盖这条链、模型缺key告警、并发错误的隔离、无来源拒答和3值逻辑。
- 所有现有`tests/`仍绿，老师 `validate.py --final` 仍绿；不得为赶速度删除现有测试。需要新增依赖锁文件/版本与README一键启动命令。轻量demo可只用SQLite+FastAPI本地，后续MySQL迁移测试非本Sprint要求。

## Sprint C — 机理文档生成设计（本轮只建契约/小样本，不批量虚构）
- 仔细看教师PDF和现有`clauses.jsonl`八段式：原文 `content_raw` 是不可修改的事实来源。其他公开文献/网页只能作为“外部参考”，不与国家标准同级。
- 设计只读输入 `clause_id→standard_code,clause_no,page,mechanism_detail,applicable_conditions` 到 `MechanismCard`，含：机理、现象关键词/同义词、可证成/排除的现场证据、尚缺变量、适用边界、条款ID和出处、外部公开资料链接。不得随意生成正文伪装标准原话；每个card增`evidence_grade` E0~E3和`reviewed`状态。
- 做 2-3 张人工可校的Demo卡（盐酸腐蚀、湿硫化氢破坏、氯化铵腐蚀），未人工核原PDF的E2/E3不得直接标PASS。不编辑 `upstream/05_提交区/clauses.jsonl`。
- 形成`docs/SEMANTIC_MECHANISM_CARD_SPEC.md`与`docs/EVIDENCE_SCOPE_SECURITY.md`。后续用于Hybrid检索训练与展示。

## 验收、停止点和成果
本次最重要的是**有用的纵切**而非空壳：无API模式浏览器能看到三代理以上轮流产生公开可查动作/事件，3工具真实可读、有标准依据、缺现场要明确拒绝硬判、刷新页面会话仍在（允许更简化首版）。
交付 `docs/audits/P1_MULTIAGENT_E2E.md`、`docs/ADR_001_STACK_DECISION.md`、所有单元/集成测试命令、如何本机启动API/UI、哪些点为`BLOCKED`、提交文件列表和第三方开源许可记录。
如网络/Node/包安装阻塞：优先实现backend+SQLite+事件流+测试，前端只交具备正确协议的局部可运行代码，不把未启动UI说成PASS。
绝不部署到公网、不添加域名DNS、不上传商业私密PDF、不发邮件、不篡改源数据。
任务完成停止并返回 `READY_FOR_CHATGPT_REVIEW`；不要擅自开始第二个独立大任务。
