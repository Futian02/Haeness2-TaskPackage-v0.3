# 给本地 Codex Luna High（Fast若支持）｜R1 企业级多智能体产品首轮任务
日期：2026-10-27。路径：D:\作业\竞赛\计算机设计智能体\机械智能体
用户明确决定：项目训练目标是计算机专业企业级多智能体平台，不仅满足老师最低单Agent指标。上游三工具/Schema/教师原始资料仍视为不可破坏合同。
**先读** AGENTS.md、docs/PROJECT_STATE.md、docs/MASTERPLAN_V1_TEACHER_FIRST_20261027.md、docs/TEACHER_REQUIREMENTS_AND_GAPS_20261027.md、upstream/README.md、upstream/04_接口文档/工具接口规范.md、docs/CODEX_LUNA_HIGH_R0_EXECUTE_20261027.md。
如果上轮全量Git同步尚未完成，优先执行 scripts/SYNC_ALL_UPSTREAM.ps1（仅在upstream干净及足够空间的前提下），确认PDF、XLSX、样例与reference_code全部检出。不能删/改标准PDF和两份XLSX。

## 设计目标：首轮完整可运行的多智能体后端，而非空壳
采用 LangGraph 为**自有产品层**运行时（不用替换上游教师Harness）；Python FastAPI 提供HTTP+SSE流；SQLite默认持久化会话/消息/决策审计（以后Repository adapter可替换MySQL/PostgreSQL），尽可能复用成熟库，不手写JSON数据库并发写入层。
最小实际Graph节点：
(1) 工况抽取/归一化 Agent（把自然语言转成字段、证据三值{true,false,unknown}及units，保留原文与置信度；不能将“未检测”当成false）；
(2) 机理鉴别 Agent（严格只通过既有 damage_mechanism_query/standard_clause_search，输出候选、支持/反证/缺失、待核条款）；
(3) RBI评估 Agent（只调用既有 rbi_lookup；缺EF/IF/MCF/PF/MDF或后果时risk_level和interval为null）；
(4) 审查 Agent（独立复核clause_id是否真实/本轮调用过、工况适用、是否超域、是否编造结论；自动评分与纠错最多1轮；不能仅凭模型自评给“合格”）；
(5) 总结 Agent（组装可读结论、下一步现场测量清单、引用与结构化卡片）。
Graph路由按需调用，场景简单可跳过部分步骤，支持并行准备与有限回退，最大总轮次/LLM calls固定上限，成本和延迟可计量。节点之间使用严格 Pydantic State 和类型化事件，不将自由文本作为跨Node唯一数据。
**三个官方Tool的名字、参数、五键返回及正式data files禁止修改**；自有Graph适配层可以调用它们，不新增老师可调用工具。

## 数据与网页的R1最小交付
- app/api/（FastAPI），app/agents/（state、nodes、graph、registry adapter），app/storage/（SQLAlchemy + SQLite默认、会话与审计events；支持DATABASE_URL可换MySQL的迁移设计，先不依赖MySQL），web/（React/Next.js或Vite，借鉴CopilotKit AG-UI的流式交互；不要把整套Open WebUI源码复制进项目）。
- 本地网站有类似现代聊天产品的会话列表、消息输入、多轮可恢复聊天、案例模板；右侧/抽屉显示 **过程轨迹**：现在执行哪个Agent、调用工具参数、返回摘要、证据条款、原始标准编号页码、耗时、最终结论；支持审查结果卡和“需要补采的现场参数”。
- UI展示的是审计可公开的决策摘要，而非模型隐藏私有chain-of-thought。前端可以用demo/mock标识数据预览，但交付验收必须对接真实运行Graph和上游工具。
- 确保朋友电脑不安装MySQL也能 `docker compose up` 或最小 `uvicorn` + `npm run dev` 启动；端口、密钥环境变量配置示例；部署前默认只绑127.0.0.1，不向公网开放。
- 预留 `app/web.py` 的Gradio作为老师ModelScope快速兼容演示，不移除。

## R1先完成的有界分步
1. 检索完整源与确立ADR：直接检查 LangGraph、CopilotKit/AG-UI、FastAPI、SQLAlchemy 版本及许可证。只引入必要包。生成 docs/ADR_001_MULTIAGENT_STACK.md。
2. 完成 typed state、5节点（RBI和Reviewer可以规则/接口优先，LLM凭据缺失标记API_BLOCKED；不得伪称真实LLM）、受控路由、最大步数、来源核查。
3. FastAPI最小接口 /health, /sessions, /sessions/{id}/messages, /runs/{id}/events (SSE) 和本地SQLite存储，若拆分接口以contract为准。不得在SQLite存密码、API密钥。
4. 简洁现代化前端初版（会话/消息/工具轨迹/证据卡/证据不足），至少三例可真实调用现有工具；无API时明确规则回退。
5. 独立单元/集成测试，至少20项新测试覆盖三值证据、工具合同、被拒调用、错误引用、数据库存取、会话隔离、SSE排序及截断、Graph终止、安全缺省。
6. 产出 docs/R1_EVIDENCE.md、docs/R1_NEXT_GATES.md。每条PASS附本机命令与退出码；没起来的服务标BLOCKED，禁止声称真实部署。

## 暂不做
不做收费标准全文外发、联网抓企业装置台账、不上传隐私设备数据；不立刻自建分布式向量库；不做零证据的大模型推理能力宣传；不改变L1-L4风险映射；不部署公网，也不购买服务器或绑定域名（须另行授权和确认DNS/安全）。
既有父仓库下其他项目有本地变更，不得git clean/reset；改动尽量留在我们自己的产品层，不覆盖老师上游成果。
交付末尾输出实际改动文件、运行步骤、性能和失败记录，停止在 READY_FOR_SUPERVISOR_REVIEW。
