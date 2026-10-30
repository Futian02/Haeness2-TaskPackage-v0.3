# 当前项目状态（2026-10-30）
> **R2-G2 当前裁决：STOP_FIX_REQUIRED / NO_GO_PRODUCTION。** 2026-10-30 Edge桌面1440×900和移动390×844真实CDP旅程已完成普通聊天、SCC、专业A/B、60→80°C更正、来源E0审查、多轮事实更正及跨CID匿名隔离；每轮SQLite terminal、事件序列与SSE Last-Event-ID重连均可核查，移动无横向溢出，console/network未取消错误为0。项目venv统一PyMuPDF 1.27.2.2/pytest 9.0.2；451 unittest+5 P16、前端128+TS/build、教师554/200/17通过。仍未完成真实UI worker-capacity 429 queued恢复和模型/工具故障类型化错误、草稿/idempotency重试；DeepSeek未配置且未调用，专业模型能力不作通过。8000/8001和正式数据未触碰。详见[本轮G2专业浏览器审计](audits/R2_G2_FINAL_BROWSER_PROFESSIONAL_E2E_20261030.md)。
> 以下为G2前的历史Owner状态快照，不代表本轮回归结果；当前结论以本文件首条及G2报告为准。

> **Owner R2 交付前再审核：CURRENT_NO_GO / P0_MODEL_SAFETY_BYPASS_REPRODUCED / SIX_LANES_READY / LIVE_VERSION_STALE。** Owner独立复跑P0+P13+P4A **48/48**，S3+上下文+路由 **73/73**，前端Vitest **123/123**+TS，老师只读554/200、17工具全部PASS；但针对新P0.1 `validate_professional_draft`的自由文本又独立发现6条**无来源设备安全判断被错误接受**（如“该设备已确认没有安全隐患”“目前无需采取任何措施”），设备风险/停复机结论仍不可靠。8000/8001实际health都未带新版contract_version，8000 API仍缺model-profiles，新前端/旧后端问题未解除。故**不批准用户在当前线上网页做新版专业功能验收**。S3数据自动候选134条仍0条正式批准，不能当全机理排除。六并行窗口A–F和最终单独集成G的详细文件所有权与Gate已写入[总体方案](R2_FULLSTACK_PARALLEL_CLOSEOUT_MASTER_20261029.md)、[独立审计](audits/R2_OWNER_PRE_CUTOVER_AUDIT_20261029.md)、[A–F Codex文档](DOCS_INDEX.md)。所有并行工作须在本机Codex原生文件/终端完成，无DevSpace等远程本地代理；不修改upstream、真实DB或在线服务；G最终隔离测试通过后才可Owner网页测试。

## P0.1 安全结论门与条件作用域整改（2026-10-29）

**GO_FOR_FURTHER_ISOLATED_TESTS / NO_GO_DEFAULT / LIVE_BACKEND_STALE。** 增加结构化`ProfessionalClaim`与`device_disposition=UNKNOWN`门，标准摘要要求逐claim来源ID、scope、observed prerequisites与逐字source span；模型候选限定E0，设备处置claim由schema拒绝；所有可见文本一致校验并在拒绝时回退确定性安全答复。`GBT30579-2022-5.23`的49–66℃按NH4HS气相析出局部条件处理，不再作为整种酸性水腐蚀的温度硬排除；60℃/80℃同源均保留`POSSIBLE_WITH_CONDITION_UNKNOWN`，不宣称80℃必然适用。64条AUTHOR_SYNTHETIC题仍仅52个唯一问题、0真人gold；已改为实际抽取、R9图、真实冻结工具/路由分支、source policy与可见答复回归。P13测试修正为验证敏感问题二次同意缺失时adapter零调用且记录blocked事件；P4A测试double更新为当前Graph可选参数合同。确定性回答flag独立为`AETHER_PROFESSIONAL_GUIDANCE_ENABLED`（默认开）；DeepSeek候选`AETHER_EXPERT_GUIDANCE_CANDIDATE`仍默认关；两条路径均有隔离测试。

验收：P0/P13/P4A定向48/48通过（47项联合+1项flag-off）；全项目venv runner 399 tests PASS、3 optional SKIP（43模块），唯一pytest函数式P16模块另由系统Python pytest 5/5通过。未经筛选的原生`unittest discover`为400 tests、1 ERROR（venv缺`fitz`）及3 SKIP；系统Python不兼容旧Tenacity/LangGraph，不用于全项目验证。教师原版`validate.py --final` 554/554 clauses+200/200 trajectories通过，三工具17/17；前端123/123+TypeScript/Vite build通过（616.15kB chunk提示）。端口8000/8001仍旧PID 59120/65000，本轮未重启、未碰真实DB；正式发布NO-GO，真人适用性核验、专家gold及Owner放行仍未完成。详见[完整P0.1审计报告](audits/P0_1_SAFETY_SCOPE_EVAL_REPAIR_20261029.md)。


## P0 专业回答修复候选（2026-10-29，独立验收）

**CANDIDATE_IMPLEMENTED / P0_TARGETED_PASS / FULL_SUITE_NO_GO / LIVE_8000_STALE。** 已在独立临时SQLite和Mock下闭合A（明确工况进入原老师工具，回答显示`GB/T 30579-2022 5.23`为E0待核候选）与B（3角度检索；危险征象提示先于正文，候选TSG条款明确条件边界；零来源Mock仍提供工程排查）。P0/DeepSeek/R9定向34/34 PASS，64条离线案例全过；全量unittest 390项仍有2 FAIL、1 ERROR、3 SKIP（P13 search mock、P4A并发订阅、P16缺fitz）。真实DeepSeek 3次受控请求中2次达到输出长度上限后拒绝、1次结构化校验通过；usage可记录部分为3086 tokens，首次失败usage未保存，不补造。`AETHER_EXPERT_GUIDANCE_CANDIDATE=0`默认关闭、V2关闭、老师工具维持3项。在线8000仍为旧PID59120及旧OpenAPI，未重启、未写正式DB。生产/默认启用保持**NO-GO**。证据及安全切换计划见[Owner P0验收报告](audits/OWNER_P0_PROFESSIONAL_ANSWER_REPAIR_20261029.md)。

**P0后续复核增量（本轮，2026-10-29）**：新增来源语义/适用范围反例过滤及两道用户问题的FastAPI→临时SQLite/SSE→真实教师工具→assistant主答闭环，新增专项测试后 `test_p0_expert_guidance.py` **15/15 PASS**。全项目当前为**392项：386 PASS、2 FAIL、1 ERROR、3 SKIP**；失败/错误类型与上段相同，P13、P4A、PyMuPDF环境仍待各自处理。前端123/123+typecheck/build通过；老师只读终验554/554 clauses+200/200 trajectories及工具17/17通过；冻结JSONL哈希前后相同。实测8000 PID59120和8001 PID65000均为旧OpenAPI `0.1.0`、无`contract_version`/candidate能力字段、`/api/model-profiles`404；本轮未向在线端口发Run/写真实库/重启。详见上方Owner P0审计报告。

> **Owner P0紧急实施前基线：PROFESSIONAL_CHAT_VALUE_GAP_CONFIRMED / CODEX_REPAIR_SPEC_READY / PRODUCTION_NO_GO。** 用户截图A明确给300系列不锈钢+碱式酸性水+60℃但在线回答要求material/medium；截图B壳体磕碰损伤的停用和验收条件却返回E0无来源无法回答。Owner读取`backend/context_slots.py`及`r9_industrial_candidate.py`并用最新版磁盘源码离线复现：A当前extract出5个事实、R9 2工具/6来源/1候选，**在线旧服务造成输入事实丢失嫌疑，但该Run快照尚未核实**；B即使最新R9也2工具/0源/0候选/unresolved。另查明`deepseek.generate_report`的提示词只授权模型改写已有规则结论，API主回答仍是模板，模型内容多在折叠事件。此段为本轮实施前记录；实施候选与当前NO-GO状态以上一节及验收报告为准。未动在线服务、老师正式标准和真实DB。

> **P0 Codex增量（2026-10-29）：P0_CANDIDATE_IMPLEMENTED / READY_FOR_OWNER_REVIEW / PRODUCTION_NO_GO。** 两个失败案例已用临时 SQLite + 当前磁盘 FastAPI/R9 + 冻结老师只读工具端到端复现并修复：A Run快照保留用户给出的材质/介质/60℃，4次真实工具调用取回`GBT30579-2022-5.23`，主回答不再重复追问并显式标注待验证；B 3次真实标准检索取得5个来源候选，零直接凹坑验收值时仍提供一般保护性分诊/排查建议，不输出风险等级、法规阈值或复机结论。新增64条合成正反例、受限结构化专业LLM规划（候选flag开启时可规划三步只读工具查询）及主回答生成、来源ID/canonical元数据核验和风险门禁。P0+R9定向34/34通过；本次全量392项有2个非P0测试失败（P13联网调用计数、P4A并发计数）及1项环境导入错误（P16-A缺`fitz`），3项可选skip，因此整仓不称全绿。专业规划器仅Mock验证，真实模型规划+执行尚未端到端验证；之前已有的合成问题主回答直连实验不等于线上API验证。真实浏览器和Owner专业人审未验证；flag默认关闭，8000服务未重启，无生产DB写入/部署/提交。详见[Owner P0审计](audits/OWNER_P0_PROFESSIONAL_ANSWER_REPAIR_20261029.md)。

> **Owner 2026-10-29网页发不出问题根因已查明并修复前端兼容：WEB_RUNTIME_CONTRACT_MISMATCH_CONFIRMED / LEGACY_CHAT_COMPAT_BUILT_SERVING / LIVE_BROWSER_SEND_PENDING / BACKEND_RUNTIME_UPGRADE_NOT_DONE。** 当前8000监听仍为2026-10-28 21:54启动的旧Python PID59120，`/api/model-profiles`404，OpenAPI旧`RunIn`不接受`web_mode/allow_sensitive_web_search/model_profile_id`，而新版`frontend/dist`已经被旧服务动态提供，导致普通POST被严格422校验拒绝并被前端错误误称“连接中断”。Owner已在自有`frontend/src/api.ts`增加**仅对准确422 extra_forbidden且无显式联网/模型选择时进行一次受限旧合同重试**，`App.tsx`“重新连接”现真实恢复health、会话和Run；5项专项测试新增，前端**123/123 Vitest、TS、Vite构建PASS**。已实测8000返回全新index与`index-D6-mJH8m.js`包含兼容逻辑，服务端未重启、正式SQLite未写/删；用户应Ctrl+Shift+R硬刷新后以默认/关闭联网尝试基础问答。**真实浏览器发送成功尚未确认，不得宣称全修复或新后端已运行。** 详细[网页422根因和降级边界](audits/OWNER_WEB_CHAT_422_RUNTIME_MISMATCH_FIX_20261029.md)。当前S3与S2.6的源码测试不代表运行中HTTP/浏览器行为；旧backend正式更新需单独备份/核准后受控重启。

> **Owner S2.5 最新实测：S2_5_ENGINEERING_RELIABILITY_CANDIDATE_PASS / REAL_LLM_EXPERIMENT_ONLY / V2_DEFAULT_NO_GO / S3_DESIGN_READY。** 直接修复自有`backend/execution_ledger.py`的动作/子任务并发抢占：活进程所有权检查、owner_claim结果提交围栏、仅真正结束进程允许只读重领；对正式三教师只读工具新增独立可终止的Python子进程执行，显式剥离模型密钥环境。新增2跨进程活所有者测试+2双SSE/多Run隔离测试+3子进程超时/白名单测试均通过。分组全量**322项：319 PASS、3 SKIP、0 FAIL/ERROR**，P16-A pytest5/5、前端Vitest118/118+TS、教师554/200与17/17均通过；Mock并发1/4/8各100 Run 0 errors。**真实DeepSeek已进行有限研究请求**：JSON450四例路由结构解析4/4、语义符合3/4；真实Planner连续4次模型调用、2次标准检索并有5个来源，但也发生过确定性policy拒绝，尚不具专业正确性或真实Planner综合验收。真实LLM Adapter保持显式研究入口，**未接入生产V2开关**。完整[Owner审计](audits/OWNER_S25_RELIABILITY_LIVE_LLM_20261029.md)和[S3全82知识层规格](S3_DM82_APPLICABILITY_RESEARCH_AND_ENGINEERING_SPEC_20261029.md)；Codex A/B可按独立文件所有权开始，C需等A/B交付。PID复用/进程树、多实例长期压力、真实模型独立盲标、人审核验/Edge复测仍阻止正式切默认V2。历史S2.4及早前状态均为旧时间快照。

> **S2.4 最新增量：S2_4_PARTIAL / V2_DEFAULT_NO_GO。** 本地临时 SQLite/Fake Provider 完成持久执行账本、独立进程崩溃恢复、mixed DAG 串行执行与服务端 trace allowlist 投影。315 unittest（312 pass、3 optional skip、0 fail/error）分组全量通过，P16-A pytest 5/5、R10离线20/20 replay、教师validate554/554+200/200、原工具17/17、前端118/118 + TS/Vite通过。规定的 scripts/test_s2.py 两次因DevSpace MCP约120秒请求时限没有返回最终状态；分组覆盖完成但不声称该runner PASS。Gate 1仍为PARTIAL：FutureTimeout不能强杀已运行线程，真实双run并发/双SSE故障注入未做；Gate 2隔离测试通过但GO受Gate 1阻断；Gate 3 Edge 1440×900与390×844真实E2E因Desktop Commander设备离线而BLOCKED。R9默认路径不变、AETHER_V2_AGENTIC_ENABLED默认0。无真实模型、部署、在线服务重启、正式数据库或老师upstream写入/修改，人审记录未动。完整Gate、命令、失败原因、恢复方案见[S2.4审计](audits/V2_S2_4_EXECUTION_DAG_REVIEW_20261029.md)。

---

> **Owner S2独立复核：S2_ACCEPTED_AS_OFFLINE_CANDIDATE / S2_4_ENGINEERING_APPROVED / V2_DEFAULT_NO_GO。** 对真实代码与[Codex S2报告](audits/V2_S2_OWNER_INTEGRATION_20261029.md)进行复核；Owner额外重跑`tests.test_v2_s2_integration` **4/4 PASS**，确认默认flag关闭、Fake候选run/event适配、SQLite checkpoint存在、同CID确认事实复用。**此复跑不等于重新运行完整282项，也不证明进程崩溃恢复**。目前B仍采用Fake Planner、混合DAG deferred、ReplayLedger仅内存、FutureTimeout不能强制杀运行线程、前端keyword及设备工况均占位符、摘要与Edge真机验收未闭环。Owner已写[审核与恢复原则](audits/OWNER_V2_S2_REVIEW_20261029.md)和[Codex S2.4精准任务](CODEX_V2_S2_4_EXECUTION_RECOVERY_MIXED_20261029.md)：**先运行持久执行账本/跨进程恢复，再实现混合DAG串行真实执行；未过Gate保持V2关闭。** 最新说明优先；下列S1/旧Owner记录为当时快照，不应覆盖当前S2状态。

> **S2 Owner集成最新状态：NO-GO（仅本地隔离候选）**。S2.0测试入口与R10离线矩阵兼容修复完成：全量282 unittest 0 FAIL/0 ERROR/3可选SKIP，P16-A pytest 5/5；R10 mock 20/20 replay一致；前端Vitest 118/118、TypeScript、Vite build通过；教师只读validate554/554 clauses、200/200 trajectories，原工具17/17。S2.1–S2.3仅部分接线：混合DAG仍deferred，checkpoint只证明临时SQLite可写、未证明崩溃恢复/取消/副作用幂等，Edge桌面/移动E2E未验收。V2保持默认关闭，且candidate仅允许临时目录SQLite。没有付费模型/部署/在线服务重启/教师数据写入。完整实测和Gate矩阵见[audit](audits/V2_S2_OWNER_INTEGRATION_20261029.md)。

> **Owner 2026-10-29 S1-A/B/C独立代码审核：S1_OWNER_REVIEW_ACCEPTED_WITH_CONDITIONS / S2_PREP_ALLOWED / DEFAULT_V2_CUTOVER_NO_GO。** 实际复跑A 11/11、B 16/16、C 9/9、R9 19/19（新旧路由兼容已由Owner修复）、新Owner4/4、65道困难意图一致65/65；A/B/C+R9专项55/55，前端Vitest118/118+TS/Vite build通过。整仓上一轮275 tests为0 FAIL、**1 ERROR（项目venv无fitz）**、3 SKIP；系统Python独立P16-A pytest5/5。当时R10离线矩阵在当前模型Profile/Mock合约下断言失败；S2已修复兼容并在新文件验证20/20，见S2审计。**真实LLM Router/Agent Planner尚未接线；B无持久checkpoint/ReplayLedger仅内存；C记忆未接API且公开工具参数遮蔽过度；混合DAG仅过渡R9，不能切默认图。**详情[Owner独立审核](audits/OWNER_V2_S1_ABC_INDEPENDENT_REVIEW_20261029.md)及[Codex S2精确任务书](CODEX_V2_S2_OWNER_HANDOFF_20261029.md)。本轮未动老师数据、签名、真实DB、在线进程或付费API。

> **Owner 2026-10-29 V2需求评审定案：DESIGN_FROZEN_FOR_S1 / CODE_NOT_IMPLEMENTED。** 用户确定12项产品需求：LLM结构化路由+强制规则门禁，混合任务拆解，LLM更自主的专业LangGraph候选+可回退RULE_DEMO，无详细材质仍进行受限标准分析，三值适用条件与证据候选，开发期Owner审核但不冒真人签名，按会话逻辑隔离+有界历史/按阈值摘要，简短回答+脱敏折叠过程，重召回不漏关键危险，有限重构保留历史。完整[设计](AETHER_V2_REQUIREMENTS_ARCHITECTURE_20261029.md)、[模型规则](AETHER_V2_MODEL_POLICY_GUARDRAILS_20261029.md)、[Codex并行任务导航](DOCS_INDEX.md)已经落盘；三份S1提示词是实施任务，尚未执行/验收，禁止把DESIGN称为程序PASS。

> **Owner 16:29+ 最新总门禁：LOCAL_DEMO_READY / TEACHER_SCHEMA_PASS / REAL_HUMAN_EVIDENCE_BLOCKED / BUSINESS_APPLICABILITY_UNVERIFIED / ROUTER_ADVERSARIAL_GATE_FAIL / RELEASE_FORBIDDEN。** “READY_FOR_OWNER_REVIEW”只适用于部分代码/证据包的审核交付，**不是教师最终验收或发布批准**。
>
> **可信入口（按优先级）：** 本文当前增量 → [教师50抽样口径](data_quality/TEACHER_SAMPLE50_EVIDENCE_STATUS_20261029.md) → [DM82机理适用性根因](data_quality/DM_APPLICABILITY_ROOT_CAUSE_AND_REFORM_20261029.md) → [Owner系统/压力与路由实测](audits/OWNER_DATA_ROUTING_TEACHER_STRESS_AUDIT_20261029.md) → [P16-C门禁报告](data_quality/P16_C_BOUNDED_CORRECTIONS_20261029.md)。此前所有P13/P12/R10测试数及“通过”仅代表**当时版本**，与本轮真实回归结果矛盾时以最近实测为准。
>
> **教师验收当前事实：** 官方验证554/554条款、200/200轨迹（多步144、三特殊类型各15）PASS；原版工具17/17；P16-C专项14/14。但最新P16-C全套记录238项/1 FAIL/3 skip（R8B极简PDF提取fallback），不称全套绿。历史 `upstream/05_提交区/条款抽样核对报告.md`自述50/50是2026-10-27旧样本，**未见可验证的交叉人审身份链**；P16新种子50样本真审0/50、42个变更对象真审0/42，合并90个唯一对象；真实引文准确率 UNKNOWN；正式发布PREVIEW_ONLY。真实LLM原生解析100组≥95、≥5轮真实连呼及ModelScope链接尚未证明。
>
> **本轮新增调查：** 正式82条损伤机理八段式8字段全部非空；结构化medium只有26/82、material74/82、equipment81/82、温度界23/82、压力界0/82、复核签字0/82。空介质常因标准环境词不在教师枚举，而非一概录入错误。65题自拟困难路由集仅48/65与预期一致（17失败，含8条专业被送普通），不等于真实流量准确率。隔离RULE_DEMO负载100并发4全部完成；100并发8为73完成/27 queued并返回429，不是证明数据丢失，待完善重试/背压。
>
> **确认的用户界面目标（尚未改代码）：** 普通闲聊直接一次DeepSeek（可选联网另计）；纯标准查证轻量检索；具体设备工程判断进入LangGraph。用户可见仅自然回答、必要来源证据和**默认收起的“思维过程/判断依据”摘要**；教师可核查的工具名称、脱敏输入/结果由折叠面板展示，不能展示或下载原始SSE帧、技术事件JSON或数据库审计记录。SQLite保留完整事件，SSE仅作为后台传输与恢复机制；不可声称展示模型内部私密思维链。现有前端折叠ActivityTrace可能含较技术的事件详情，**待后续UI映射精修**。
>
> **目录维护规则：** 不大规模迁移项目/老师目录、不动PDF/XLSX/正式JSONL、真实DB、密钥、上游仓库；只整理导航和状态索引。参阅[文档一致性审计](audits/OWNER_DOCS_CONSISTENCY_20261029.md)及[文档索引](DOCS_INDEX.md)。

---

## 历史 P13 产品交付快照（保留原时点，不代表本轮总门禁）

状态：**READY_FOR_OWNER_REVIEW**。P13 本地代码与离线回归已完成，未提交、未部署、未写生产数据库、未改教师上游。P13 证据见 [`audits/P13_CHAT_PRODUCTION_REPAIR_ACCEPTANCE.md`](audits/P13_CHAT_PRODUCTION_REPAIR_ACCEPTANCE.md)。

## P13 当前增量（2026-10-29）

- 聊天失败以有限错误码/失败 SSE 事件落库，UI 显示安全错误卡和重试；刷新后从 SQLite Runs/SSE 恢复。失败不插入空 assistant 消息，DeepSeek 原始错误体与隐藏 reasoning 不呈现。普通对话历史严格限定同会话；长输出记录finish_reason/真实usage/模型/耗时，代码max_tokens配置范围8192–16384。
- 当前轮意图优先于历史工况。方括号/JSON介质按老师枚举归一；E0有源探索候选可显示条件/反证/补证，不推概率或设备风险等级。
- 聊天联网模式 `off/auto/on` 按会话存储并写入Run快照；`auto`仅对明确公开时效问题触发，敏感工况需二次同意，设备表单/附件/标准原文不自动外发。Search来源有标题/URL/时间并标注非老师标准权威来源；失败在回答与SSE中可见，不改老师三工具。
- 验证：后端195 tests OK / 3 optional Phoenix/OpenInference skips；前端115 tests PASS、typecheck/build PASS；官方终验554/554 clauses、200/200 trajectories、工具selftest17/17；本地并发100 runs × 1/4/8共300次0错误。Edge 142隔离本地桌面/移动截图与互动回放见 `audits/evidence/P13/`。
- 当前127.0.0.1:8000旧PID59120仍未重启；其 `/api/model-profiles` 404与磁盘新代码不一致。无真实付费模型请求，真实公网Search/Fetch未验证。P13停在`READY_FOR_OWNER_REVIEW`，**非最终验收**；无部署或提交。

## P12/R9 本地集成基线（2026-10-28）

`frontend/dist` → FastAPI (`backend/api.py`) → 有界 R9-A LangGraph (`orchestration/r9_industrial_candidate.py`) → 原样冻结的三个老师工具 → SQLite 与现有 SSE。刷新后，聊天、消息-run 关联与该轮真实执行事件从 SQLite/API 重放恢复。执行过程折叠显示在助手回复内。当前本机已配置 DeepSeek：LangGraph/工具/证据门禁仍是确定性流程，DeepSeek 仅负责基于有界摘要整理表达，不代表多 LLM Agent，也不作设备风险判断。

## 已验证

- React 单元/集成测试、TypeScript 和生产 build：见最终验收报告。
- 后端 unittest 主环境全绿；3 项仅依赖可选 Phoenix/OpenInference SDK 的专项在该环境精确 skip，独立 observability 环境 6/6 PASS。
- 老师正式数据只读终验：`clauses.jsonl` 554/554，`trajectories.jsonl` 200/200；工具自测 17/17。该事实不等于 13 条 RBI 草稿已签核或 461 页 PDF 已人工逐页审查。
- 本机 `.env.local` 配置 DeepSeek（Git 忽略，不进入提交）；health 显示 `mode=DEEPSEEK`，模型为 `deepseek-flash`。实际 FastAPI → LangGraph → DeepSeek → SSE → SQLite 垂直切片通过；无凭据的其他环境继续默认 `RULE_DEMO`。
- 前端会在 health 报告 DeepSeek 已配置时选用 `DEEPSEEK`；明确发送到模型的仅有用户问题与本地有界摘要，不传附件、PDF、标准原文摘录或密钥。回答同时保留本地确定性研判/来源状态，明确 DeepSeek 文本只是表达整理。
- 本机 DeepSeek 真实调用验证不等于质量评测或专家验收；无公网部署，无多模型交叉审核结论。该次密钥曾在聊天中粘贴，后续应轮换本机密钥。
- 2026-10-28 修复聊天工作区高度约束：历史消息过长时 flex 子项的默认 `min-height:auto` 把 composer 推出视口，同时根容器 `overflow:hidden` 阻断页面滚动。现将 `.chat-scroll` 作为明确的内部滚动容器并保持输入栏固定可见。Edge CDP 桌面 1440×900 与移动端 390×844 实测通过；详见 [`audits/LOCAL_CHAT_SCROLL_FIX_20261028.md`](audits/LOCAL_CHAT_SCROLL_FIX_20261028.md)。
- 2026-10-28 增加 Doubao 风格的单轮过程折叠：可见回答保持简洁，助手气泡内默认收起“思考过程 · N 步”；展开后只呈现 SQLite/SSE 实际执行事件、已筛选公开摘要，以及可选的“DeepSeek 表达整理”摘要，不展示隐藏思维链。已有历史消息按旧版分节拆成折叠过程摘要与最终答复；详见 [`audits/LOCAL_THOUGHT_COLLAPSE_20261028.md`](audits/LOCAL_THOUGHT_COLLAPSE_20261028.md)。
- 2026-10-28 设置正式品牌图标：用户提供的 AETHER 青绿色徽标用于侧栏品牌、欢迎态、助手头像、等待态及浏览器 favicon；原始 PNG 复制到 `frontend/public/assets/aether-icon.png`，保留原文件像素与 SHA-256。Edge 实测图片和 favicon 均成功加载；详见 [`audits/LOCAL_BRAND_ICON_20261028.md`](audits/LOCAL_BRAND_ICON_20261028.md)。
- 2026-10-28 R10聊天模式补验：新增10场景×RULE_DEMO/DEEPSEEK模式的离线FastAPI→Graph→SQLite→SSE回放矩阵；20/20 trace replay一致。DEEPSEEK请求全部为mock，未发送真实模型请求。发现并修正“风险等级的确定”标准检索误入缺工况路由；确切设备风险判断仍走engineering。历史双段assistant消息兼容增加前端回归。记录与逐run指标见 [`AETHER_CHAT_MODES_AND_COLLAPSED_PROCESS_20261028.md`](AETHER_CHAT_MODES_AND_COLLAPSED_PROCESS_20261028.md) 与 [`../evals/r10_offline_chat_matrix_20261028.jsonl`](../evals/r10_offline_chat_matrix_20261028.jsonl)。
- R10变更验证：`\.venv-langgraph\Scripts\python.exe -B -m unittest discover -s tests -v` **140 tests OK / 3 optional Phoenix skips**；`npm test -- --run` **78/78 PASS**、`npm run typecheck` PASS、`npm run build` PASS（保留 Vite 577.31 kB 大 chunk warning）。

## 冻结项与待办边界

- 教师三个工具、正式 JSONL、Excel、PDF、`upstream/` 全部冻结。
- 13 条未签署 RBI 候选继续作为草稿，G–J 未知风险字段保持空白；本轮未运行 convert 写盘。
- 终态检查时 `upstream/01_RBI标准` 有 Excel modified/untracked 状态；本轮未写入这些路径且未回滚。由于未留开工前哈希/状态快照，具体变更归属待 Owner 审计，详见最终验收报告。
- REAL_LLM、真实抽取人/独立复核人签核、461 页 PDF 的视觉核验、正式数据补录、公网部署均待独立 Owner/教师流程。
- R10矩阵仅是本地 mock/规则路线回归，不产生任何真实DeepSeek连接性、质量、费用、Token或TTFT结论；对话历史和PDF内容仍未提供给DeepSeek。
- 历史报告/目录不删除、不移动。`docs/PROJECT_STATE.md` 为 2026-10-27 历史状态记录。

## R2-G3 故障恢复封口状态（2026-10-30）

**STOP_FIX_REQUIRED / G3_BROWSER_FAULT_GATE_INCOMPLETE / PRODUCTION_NO_GO。** 本轮已修复前端Run提交与SSE状态机：WORKER_CAPACITY 429现在明确作为已创建queued Run，保留Retry-After并只对原RID恢复；POST不确定失败保留精确请求体与幂等键；草稿等成功终态后才清除；终态失败的新执行按钮已明确为新Run。专项前端130/130、TS/build通过；全Python 451项（3 skip）及P16 5/5、教师554/554+200/200+工具17/17通过。Edge桌面/移动RULE_DEMO聊天烟测真实通过并保存RunID、序列、SQLite消息数及截图。

G3所需真实Edge错误旅程未闭合：stream容量429同RID恢复、POST 429幂等恢复、聊天UI内模型未配置503错误卡/草稿恢复、工具超时失败卡/新运行隔离未在真实浏览器完成；G2完整专业桌面runner复跑最后跨会话场景时send按钮仍disabled并生成保留失败JSON。因此不报告GO。详见[ G3故障恢复门禁报告](audits/R2_G3_WORKER_CAPACITY_ERROR_RECOVERY_GATE_20261030.md)及`audits/evidence/r2_g3_20261030/`。未接触8000/8001、真实数据库、教师upstream写入或真实付费模型。

最终源指纹复验补充：Vite按最终源码重启后，Edge桌面1440×900 Run `722f7a25-3c0a-4e86-976b-503947ffa46b`与移动390×844 Run `45fcb3e6-6b9e-4ca5-bd44-0bfb5fddcb9b`均完成；最终前端指纹`132b8e3498dbe8ba8d1c770b6c6fbc82faab8cc017797b4fe114c38eb5f6d2c6`。故障浏览器Gate仍缺，不改变STOP结论。
