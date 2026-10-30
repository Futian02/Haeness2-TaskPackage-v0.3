# Codex / Luna High Fast｜R1 企业级多智能体基础设施与工程语义
用户当前明确定位：本项目不仅为机械专业朋友交付老师作业，还作为计算机专业企业实训；**多智能体平台必须建设**，本轮建立可测试基础而不是一次性假装全部完成。

项目根：D:\作业\竞赛\计算机设计智能体\机械智能体
先读 AGENTS.md、docs/PROJECT_STATE.md、docs/MASTERPLAN_V1_TEACHER_FIRST_20261027.md、docs/TEACHER_REQUIREMENTS_AND_GAPS_20261027.md、docs/CONTRACT_LOCK.md、docs/DATA_LINEAGE.md 和 upstream/老师官方文档。
若 upstream 仍为 sparse checkout，先按 scripts/SYNC_ALL_UPSTREAM.ps1 的安全检查完成HEAD所有追踪文件检出。保护其它竞赛目录及父级Git；不得git clean/reset；不得破坏teacher v0.3三个Tool签名、五键外壳、八段式、枚举、Schema和原始PDF/XLSX。

## 交付范围（这一轮优先垂直切片）
1. 源码架构：保留 upstream 官方单智能体作为 teacher-compatibility path；外层新建平台 backend（FastAPI）、orchestration（建议LangGraph状态图）、agent roles（case intake、evidence retrieval、mechanism analyst、adversarial reviewer、RBI evaluator、report composer），但**只需把 analyst+reviewer+reporter 最短可运行链路接通**，其他Agent接口定义、单元测试，禁空壳冒充全流程。不要让六个Agent全程强制顺序调用，应按风险/证据触发，预算最大LLM调用次数和超时。
2. 工程语义：本地依据GB/T/TSG原始资料，严格区分标准原文事实、工程解释、用户输入、待检验假设。建立三值unknown/false/true证据状态、材质/介质/单位标准化、候选机理、支持/反证、缺失字段、鉴别问题、出处（clause_id, standard, clause_no,page）与RBI缺因素；输出结构化case模型。网络资料仅作为线索，不要直接写成标准原文或进行版权侵权内容抓取。
3. 后端/API：GET /health；POST /api/sessions；GET /api/sessions/{id}；POST /api/sessions/{id}/messages；GET /api/runs/{id}/events（SSE）至少设计OpenAPI并实现最短跑通路径；核心返回显式事件agent_started/tool_called/tool_returned/reviewed/finalized/error，禁止泄漏隐藏chain-of-thought（UI展示公开决策摘要）。
4. 数据库：默认SQLite+SQLAlchemy（无需朋友安装MySQL），表 sessions/messages/runs/trace_events/evidence/reviews；ORM预留MySQL URL可切换，Alembic版本迁移后再加，不直接存储API key；请求隔离、异步持久化原则。
5. 本地前端：优先可测试的网站型UI（Next.js或React/Vite任选，择定版本、许可证、复用开源布局），左侧历史会话、中央多轮聊天、右侧可折叠agent工作流与证据卡；SSE显示可审核动作流、工具调用参数/结果、错误、每步耗时，用户可删除**本应用创建的会话**；不需要模仿或盗用第三方品牌UI。
6. 原老师提交路径隔离并可单独运行；应用具备mock模式以便前端无API测试，标明mock，真实LLM模式无密钥时显式阻塞。
7. 测试：≥10条代码测试覆盖三值逻辑、API读写会话、工具输出契约、两Agent handoff、审查失败阻断、持久化SSE事件一致性；至少两条e2e案例：工程证据不足正确补问 vs 条款可查正常回答；重新通过官方validate.py --final、_selftest_tools、guardrail、harness-sync；不要把规则回退当成原生模型调用成功。
8. 整理 docs/R1_ARCHITECTURE_DECISIONS.md、docs/R1_ENGINEERING_SEMANTICS.md、docs/R1_E2E_EVIDENCE.md、docs/PROJECT_STATE.md。解释每个代码复用的上游/开源来源、licensing、准确率/耗时实验与不足。
9. 安全：严格校验用户输入、请求长度、限流、消息最大轮数、HTML/Markdown安全呈现；官网外网部署与域名DNS暂不执行（本轮只本地演示），证书/账号/密钥由Owner控制。公众设备风险判断标注辅助性质，不自动发出安全控制指令。

## 执行准则
先5分钟读约束→明确最小架构→先测试→实现第一条端到端路径→跑官方回归→记录真实证据；只在上述项目内实施，不盲目改上游。
输出最后一句：R1_READY_FOR_REVIEW 或 R1_BLOCKED，附命令、日志、变动清单、缺口。不允许宣称实际调用了LLM、已联网部署、复核了所有PDF，除非有证据。
