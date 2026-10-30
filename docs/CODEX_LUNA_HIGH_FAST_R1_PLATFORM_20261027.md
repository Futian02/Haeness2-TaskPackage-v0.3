# CODEX / Luna High Fast — R1 企业级多智能体平台立即执行任务（2026-10-27）

工作根目录：D:\作业\竞赛\计算机设计智能体\机械智能体
先读：AGENTS.md、docs/PROJECT_STATE.md、docs/MASTERPLAN_V1_TEACHER_FIRST_20261027.md、upstream/README.md、upstream/04_接口文档/工具接口规范.md、upstream/04_接口文档/技术指标验证方法.md、docs/TEACHER_QA_CONSTRAINTS.md。
**用户新定位优先：把本任务当企业实习，建企业级多智能体平台。** 老师的单Agent是交付基线而非产品上限；三官方工具、Schema、教师标准资料是冻结兼容边界。

## 首轮有界实施，按优先级执行，不要泛泛写空计划
P0. 检查upstream Git干净状态，执行根目录 scripts/SYNC_ALL_UPSTREAM.ps1，完整检出所有HEAD文件；不git clean/reset，不改父级项目。核原始PDF、两份Excel、样例、reference_code，建立文件SHA、来源、大小、可访问状态。若不具备磁盘/网络权限，记BLOCKED，不造假。
P1. 在自有app/platform等产品层搭最小**可真正运行的本地网站**。优先FastAPI + React/Vite/TypeScript（如果Node可用），统一后端REST及SSE；前端采用现代聊天应用双栏：左侧会话/搜索，中间消息和当前执行步骤时间线，右侧“证据抽屉”（真实clause_id、标准、条款、页码、核验状态），可切换展示过程与最终摘要。用户实时看到公开决策摘要、工具名、参数、观察、耗时；绝不暴露模型私有隐藏推理。缺真实LLM key时明显标识规则演示，不能模拟LLM成功。
P2. 存储使用**SQLite默认+可插拔MySQL**：定义Repository协议，迁移/初始化脚本，sessions/messages/runs/tool_calls/evidence_refs/feedback 6表；可靠记录步骤、会话恢复、结构化日志、关联来源和参数，权限与secret不落库；基础版本先支持SQLite，无需朋友本地安装MySQL。MySQL后续通过DATABASE_URL适配，勿直接硬编码两种分叉逻辑。
P3. 设计**三角色运行流程**：Coordinator负责意图/材料/现场信息归一化、EvidenceAgent只调用原3个教师工具、Reviewer审查出处/适用条件/未知量、ReportAgent负责可阅读摘要与待补充检查项。它们内部作为角色/节点，而对老师导出的工具仍只有三个。角色可逐步从规则执行升级真实LLM、能开关reviewer，多Agent是目标而不是假报已自主。
P4. 准备PDF→标准条款→工程语义知识建设：首先读取原GB/T 30579与GB/T 26610 PDF、两份XLSX并仅从可核实原文提炼“现场现象/已知证据/缺失数据/鉴别问题/可能机理/排除条件/条款号”的**候选机制文档**；模型辅助的每个断言必须记录来源页码+审核状态，未人工核对的标draft/unverified，不直接回填老师正式clauses.jsonl。优先选10个典型机理示例，并制作10-20个自然语言输入测试。
P5. 保留现有 app/runtime.py 和 upstream官方Harness；使用 adapter 隔离，不改变tools名/参数、统一5键、八段式、schema、原PDF/XLSX/JSONL。先跑官方基线、现有13项测试，新增HTTP/SSE/SQLite/多agent节点/基础e2e测试。若前端实现过多，以真后端+可用最小UI优先，**禁止只交静态mock图**。

## 首轮文件输出（实际代码+证据）
- docs/PLATFORM_ARCHITECTURE_R1.md — 模块图、状态流、权限边界、数据库ER、API/SSE contract、分步开发范围；
- docs/ENGINEERING_SEMANTIC_SCHEMA_R1.md — 机理卡字段、三值Unknown、证据与页码映射、人工审核状态；
- docs/R1_EXECUTION_EVIDENCE.md — 实测环境、命令与exit code、运行URL、可打开UI、数据库增删读、逐步Trace是否来自真实上游、全量Git同步状况；
- 可运行后端/frontend和迁移测试、启动脚本；没有Node/Gradio等环境时需要写精确依赖/安装步骤与BLOCKED。
- docs/PROJECT_STATE.md更新。

## 验收线
A: 上游git HEAD不改变且所有教师合同/正式数据字节不改，官方validate --final、tool selftest、guardrail、sync、原13 tests保留通过。
B: 本地网站可以从真实输入调用真实官方工具，显示真实Trace与source，不只硬编码场景。
C: 关掉网页再启动，SQLite保留会话、历史步骤和引用；如果尚没完成必须明确NOT VERIFIED。
D: 每个Agent节点职责、输入输出、失败策略明确定义；没有真实LLM时不要称自主多智能体成功。
E: 至少3个证据不足场景不误把unknown=false、不凭推断给出风险/周期；错误引用被Reviewer拦截。
F: 工程语义初稿全部有标准来源、存疑与审核状态；没有原文/版权权限就不捏造条款。
G: 任何API钥匙/隐私数据不提交或打印；不得公网部署/修改用户域名DNS，未经确认只在127.0.0.1运行。
H: 交付文件与测试日志，止于READY_FOR_REVIEW由ChatGPT复核，不自称模型100例或公网验收完成。

上限：**本轮只完成本地可运行MVP与数据库/多智能体骨架、10个机理样例**，不要把所有高级RAG、3D、复杂UI、免费服务器、域名一股脑做完，避免不可运行的巨型框架。下一轮在真实对照基线后再做模型并行、rerank、网页优化与部署。
