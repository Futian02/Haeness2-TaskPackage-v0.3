# Codex S2｜基于Owner真实复核的Aetheris V2最小可验证集成（2026-10-29）

使用唯一工作根：`D:\作业\竞赛\计算机设计智能体\机械智能体`。

**任务性质**：S1 A/B/C已提交候选且Owner独立审计，允许推进**隔离联调候选**。**不授权默认V2切换、不授权部署/启动生产服务、不授权付费LLM、不授权改动老师正式数据和人审**。一次只由一个集成Codex窗口修改共享后端/前端文件，避免三窗口互相覆盖。先检查git状态和并行任务，如果还在写相同文件，停止并协调Owner，不猜别人的变更。

## 1. 开工必须逐项读取
- `AGENTS.md`、`docs/PROJECT_STATUS_CURRENT.md`
- `docs/AETHER_V2_REQUIREMENTS_ARCHITECTURE_20261029.md`
- `docs/AETHER_V2_MODEL_POLICY_GUARDRAILS_20261029.md`
- `docs/audits/OWNER_V2_S1_ABC_INDEPENDENT_REVIEW_20261029.md`
- `docs/audits/V2A_ROUTER_GATE_REVIEW_20261029.md`
- `docs/audits/V2B_AGENTIC_CANDIDATE_REPORT_20261029.md`
- `docs/audits/V2C_MEMORY_PUBLIC_TRACE_REPORT_20261029.md`
- `docs/CODEX_V2_S2_INTEGRATION_OWNER_GATE_20261029.md`
- 真实`backend/api.py`,`backend/store.py`,`backend/deepseek.py`,`backend/model_profiles.py`,`backend/intent_router_v2.py`,`backend/conversation_memory.py`,`orchestration/agentic_v2.py`,`orchestration/agentic_contracts.py`,`orchestration/intent.py`,`frontend/src/components/trace/ActivityTrace.tsx`,`frontend/src/trace-events/model.ts`.

## 2. 已被Owner真实修复，不得回滚
Owner于本轮在`backend/intent_router_v2.py`新增“带编号条款无查询动词仍为标准意图”和“高风险子任务不能藏于general route”；`orchestration/intent.py`新增有上下文的设备短句兼容但普通任务不继承设备；`tests/test_owner_v2_routing_regressions.py`四项。
复跑：R9 19/19、A+P13/R10专项25/25、S1 A/B/C+R9 55/55、Owner4/4、Owner65 65/65，全通过。
整仓unittest discover 275 tests 0 FAIL 1 ERROR 3 SKIP（P16-A缺fitz），系统Python单独`pytest -q -p no:cacheprovider tests/test_p16_a_evidence42.py`5/5；前端直接node Vitest118/118、tsc、Vite build通过，主bundle614KB警告。**不要拿跳过/删测试/改题库来伪造PASS。**

## 3. 工作必须分阶段，Gate不通过即停
### S2.0（先执行、最重要）统一可复现测试环境
- 确定项目虚拟环境缺PyMuPDF且`tests/test_p16_a_evidence42.py`属于pytest风格，给出依赖安装/环境配置建议和稳定测试入口（pytest与unittest都在固定环境运行）。不要触碰P16人工签名或改动正式候选。确认其他可选SDK的3 SKIP恰当。
- 老`evals/r10_offline_chat_matrix.py`仍报`persisted status != completed`，调查当前`model_profiles.safe_profile`和`GenerationResult`接口与旧tuple Mock的差异，给出新版本离线矩阵或独立合约测试；老R10历史数据保留，不覆盖旧输出。
- Windows node实际存在`D:\Program Files\nodejs\node.exe`；本轮`npm --prefix frontend`的子shell找不到node，但是直接node Vitest、tsc、Vite CLI均成功。固定可复现命令/cwd/PATH，不以shell异常判源码失败。
- 所有测试依赖+版本锁定，不执行未授权在线包升级；如果确实要安装软件/改全局环境，先提供Owner审核说明，不要默默操作。

### S2.1 接线模型驱动执行与三路径，feature flag默认关闭
- `RULE_DEMO`、原R9继续默认并始终可回退；新`V2_AGENTIC`候选通过显式flag启用，**默认off**。A目前真的让纯普通FastAPI worker绕过Graph；必须保持。
- 纯标准查证走轻量标准工具和来源门禁；混合DAG **不能只是存结构快照**。最低闭环可串行处理general explanation→standard→engineering→synthesis依赖，工程优先；确实没有实现的子任务必须明确`deferred`/TRANSITIONAL，不要谎称执行。
- 用mockable Provider adapter实现符合V2结构化Planner路由和Graph的接口，可在无外部网络测试；真LLM Provider默认禁用，无Owner明确许可不从本机.env取key或发HTTP。LLM失效、schema错误、上下文不全要可解释有限降级。
- 封装不同图的output schema和public trace events Adapter，所有state/results有run_id与conversation_id，原SQLite lease/CAS/SSE sequence/唯一终态不退化。

### S2.2 幂等/恢复与安全
- B当前`graph.compile()`没有持久checkpointer，`ReplayLedger`是单Python对象缓存；线程`Future.result(timeout)`不会真杀底层操作。**不解决这几点不能把V2切换成默认**。
- 与当前SQLite运行/事件/回放一致地实现run/thread存储、重试不重复副作用、超时不遗留失控并发、取消与失败可恢复；用户输入/检索数据提示注入不能改变白名单，只有老师原三工具。要拿测试证明，不是口头声称。
- 真实模型后续使用provider原生timeout/Token输出上限，模型请求和老师tool attempts分别计，失败不把mock回退算原生模型成功。

### S2.3 接入会话事实/摘要与前端公开详情
- `ConversationMemoryService`正式接入API，按cid读取最近可见消息+摘要+源明确确认的事实。user确认、LLM候选、旧事实superseded严格区分；同会话私有设备信息不自动发普通聊天Provider；增量summary默认关闭、mock可测、源hash一致。
- 前端目前参数投影**过度遮蔽**：`frontend/src/trace-events/model.ts`把material/medium/temp/pressure全部替换成“已记录”，且不允许teacher`standard_clause_search.keyword`的公开展示。用户要求普通视图自然回答+默认折叠公开步骤，点击后查看经授权/脱敏的**实际工具输入、结果和标准证据**。设计最小化的可核查公开视图与**授权Owner本地审查视图**，无真正认证时不暴露full raw JSON和企业敏感字段。SSE仅传输和审计，普通界面不输出原始frame。
- 用本机真实Edge桌面/移动尺寸验证，不以Vitest/CSS单测冒充浏览器E2E。若浏览器不可用报告BLOCKED。

## 4. 所有核心Gate必须可复现
1. 65旧困难题、120作者整理样本+**新的独立盲标集**；安全专业→general在测试集误判为0；混合任务拆解真正执行且最终答复不泄漏模型猜想。
2. 实际Python unittest/pytest明确0 FAIL/0 ERROR（可选依赖合法SKIP要列原因）；完整前端 Vitest118/118起 +typecheck+build；教师validate554/200、teacher tools17项不变。
3. 临时SQLite下真实FastAPI TestClient→Run→event→SSE→message的三路径与混合路径、错误重试、R10 20场景新合约、会话A/B隔离；mock Provider，绝不计费。
4. 至少30专业正/反/未知合成案例（不得冒充真人专家gold）；来源哈希/证据等级/风险等级null/条件缺失保持；缺材料仍能做有限标准调查。
5. 并发1/4/8、429 backpressure/Retry-After、有界重试/queued终态/断点恢复完整实测；不能用并发8另一种简易负载成功抵消Owner旧27个429案例。
6. 不新建第四个老师工具，不修改`upstream/**`、P16审核表、人签、真实业务SQLite、个人密钥；没有真实LLM100、人工50或ModelScope不得发正式验收PASS。

## 5. 提交/报告和停止规则
- 开始先输出：当前Git快照、风险点、预计涉及文件、备份/回滚方案，再有界开发。
- 每修好一个阶段记录**实际运行**命令与退出码、样本量、跳过项、源码状态；失败可保留，但必须诚实说明。
- 状态文档`docs/audits/V2_S2_OWNER_INTEGRATION_20261029.md`和更新`docs/PROJECT_STATUS_CURRENT.md`；代码候选保留feature off。
- 最终返回：DONE/PARTIAL/BLOCKED判定、文件清单、核心失败或未证实项、下一步Owner需要审核的精确问题。
- **只允许集成候选和本地mock/临时库验收，严禁默认上线、真实Provider收费、外网部署或覆盖教师正式数据。**
