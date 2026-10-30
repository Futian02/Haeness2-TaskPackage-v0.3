# Luna High / Fast｜R1 多智能体企业化平台首轮执行任务（2026-10-27）

## 用户新目标
老师给机械专业朋友的单Agent任务只是官方验收基线。我们是计算机专业，长期目标是将其做成**真实可扩展的多智能体工程平台**，对标成熟Agent产品：本地网站（豆包式流式聊天+公开决策轨迹+工具调用与引用）、工程语义知识库、持久对话、基线/多Agent对照，最后自定义域名部署。本轮只做可验收垂直切片，严禁一口气重写上游。

## 工作根目录
`D:\作业\竞赛\计算机设计智能体\机械智能体`
先严格读取 `AGENTS.md`、`docs/PROJECT_STATE.md`、`docs/MASTERPLAN_V1_TEACHER_FIRST_20261027.md`、`docs/FULL_SYNC_AUDIT_PLAN_20261027.md`、`upstream/README.md`、`upstream/04_接口文档/工具接口规范.md`、`upstream/04_接口文档/技术指标验证方法.md`、`upstream/任务包问题答复.docx`、现有`app/`,`knowledge/`,`tests/`。
若本地有独立工作线程，优先**同线程续接**，不得开多个CLI抢占写锁；支持 luna high fast 时使用，否则 luna high，绝不使用模糊的伪模型名。

## P0：完整同步与归档索引
用户要求仓库当前HEAD所有追踪文件（包括所有官方PDF、XLSX、文档、reference_code和缓存）。先检查 `upstream` 本身 `git status --porcelain` 干净、磁盘空间、remote/HEAD；如安全执行 `scripts/SYNC_ALL_UPSTREAM.ps1`，即 `git -C upstream sparse-checkout disable`；执行后 `python -B -m scripts.check_sources` 19/19，清单列Git追踪文件总数、重点PDF/XLSX数量、SHA以及文件按合同/原件/资料/第三方/缓存分类。不执行git clean/reset，不移动或覆盖上游文件，不改父项目Git。

## P1：可扩展多Agent平台骨架（真正分工，不是假三按钮）
对外保持老师**仅3个Tool**参数/返回外壳完全冻结；对内搭建 `platform/` 或 `orchestration/`（谨慎名称避免Python内置冲突）：
- Supervisor Router：识别工况/标准问答/信息不足/不在范围，决定是否请求诊断、RBI或回到用户；
- Mechanism Analyst：可调用老师已有 `damage_mechanism_query`、`standard_clause_search`，输出候选+正反证据+unknown；
- RBI Specialist：只有现场因子足够才可给标准支持的等级/周期，调用 `rbi_lookup`；
- Evidence Auditor：检测ID存在、来自当前调用、标准原文蕴含、工况适用四级E0–E3，发现缺项反驳；
- Reporting Agent：把所有可验证结论整理为人可读建议，不发明新证据。
必须把**LLM agent 与确定性validator区分**：首轮至少有两个可独立替换/测试的实际agent node与一个Supervisor，另外模块可为确定性业务节点；不能用一个静态函数顺序跑就宣称多Agent质量已证明。
采用 LangGraph StateGraph/Supervisor Command 或轻量本地 state graph（二者优先成熟库），写明使用理由，持久化checkpoint边界与trace schema。模型API无凭据时可在RULE_DEMO运行，但标明Mock/Rule而非真实多LLM。

## P2：本地聊天网站垂直切片
后端优先 FastAPI + SQLite/SQLModel：MySQL作为可配置适配器，**默认 SQLite**，因为朋友无需安装MySQL。持久化：
- conversations, messages, runs, agent_events, tool_calls, evidence_refs, knowledge_documents，带run_id/conversation_id/sequence/timestamp/status；
- 不存秘钥、内部完整隐藏CoT或版权标准全文到公网数据库；
- SSE（或WebSocket）推送可审计的事件状态，断线后能按run_id重放。
前端可选 Next.js + Tailwind + shadcn/ui + assistant-ui（若Node工具可用且依赖合理），或最小独立React/Vite站点；**产品网页**支持：左侧历史对话、中央聊天与流式答案、右侧Evidence抽屉/Timeline（Agent名、决策摘要、工具/参数/返回、耗时、clause_id+页码），顶部RULE/LLM/MULTI状态标签、引导输入。
先跑通Python backend API+单页站点，无模型密钥也能显示Rule演示。老师官方ModelScope Gradio独立作为兼容展示入口，切勿拿新产品替代老师的验收。

## P3：PDF知识文档与工程语义转换（先方案 + 最小实现）
从官方PDF与现有clauses.jsonl构建**独立的工程语义层**：不改原文，记录每个语义特征的精确来源。
目标输入“铁离子高、pH下降、还没测厚”→实体+数值+时间变化+证据状态三值 {true,false,unknown} → candidate mechanisms → supporting/conflicting evidence + missing evidence + discriminator question。
定义 `EngineeringObservation`, `Hypothesis`, `EvidenceLink`, `InformationGap` 的Pydantic schemas，文档与测试涵盖 unknown≠false，单位归一化、同义词/设备别名。
PDF处理要记录 `doc_sha256, standard_code, clause_no, page_printed, pdf_page, quote_span, extraction_method, review_status`。不得直接OCR覆盖原始 `content_raw`；文档抽取可辅助生成候选，人工复核之前不可标“已认证工程机理规则”。
参考官方Qwen-Agent RAG：BM25+文档chunk+自定义检索；先做原词法/FTS5，语义embedding/re-rank只能在人工金标命中证明有收益后入默认产品。
此轮至少交10条带来源候选的语义知识草稿+10个不同现象的自然语言测试（须标注draft/needs_review），不要把外网资料当作法规条文或未经核的标准事实。

## P4：测试与验收
- 当前 `python -B -m unittest discover -s tests -v` 已13/13；新增≥12项覆盖schemas、unknown、事件序列、数据库持久重放、三个工具合同，严禁只写“空测”。
- `python -B upstream/04_接口文档/validate.py --final` 要继续PASS（当前554条、200轨迹）。
- 新增 `docs/audits/R1_MULTIAGENT_ARCHITECTURE.md`、`R1_UI_EVENT_PROTOCOL.md`、`R1_ENGINEERING_SEMANTICS.md`、`R1_EXECUTION_EVIDENCE.md` 与 `docs/PROJECT_STATE.md` 状态更新，注明具体实测命令、端口与尚未实现的部分。
- 不部署公网、不购买服务器/域名、不登录第三方账户、不上传私有PDF或key、不改老师Schema/XLSX。
- 对当前轮未完成的功能清楚列Blocked/TODO。任务结束将证据交ChatGPT独立审查，不自动开启下一轮。

## 学习配对
每交一个模块同步输出有价值的学习素材（为什么Supervisor需要共享State；SSE事件协议如何做幂等seq；SQLite WAL什么时候需要MySQL；PDF印刷页码为何不同于PDF页码；如何设计可证伪的机理鉴别）。

## 源码参考（只提取可用模块，先查License/版本）
https://github.com/langchain-ai/langgraph
https://github.com/QwenLM/Qwen-Agent
https://github.com/CopilotKit/OpenIntelligentUI
https://github.com/assistant-ui/assistant-ui
https://github.com/CopilotKit/CopilotKit
https://github.com/ShishirPatil/gorilla
