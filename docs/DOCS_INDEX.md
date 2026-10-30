# 澄衡 Aetheris｜文档索引与版本权限（更新于2026-10-30）

> **新R4技术选型与实施路线（未实施）：** [轻量Docling思想、标准知识扩展、24MB中文Embedding、主动调查与四层上下文](R4_LIGHTWEIGHT_KNOWLEDGE_RETRIEVAL_INVESTIGATION_CONTEXT_PLAN_20261030.md)。先修G3真实Edge故障尾项，再在独立研究目录做Docling-core风格page/bbox/semantic chunk、RRF/ONNX量化检索和ContextCompiler对照；不修改老师冻结12标准与运行服务。2026-10-30研究计划不是运行通过/DeepSeek可用性声明。

## 最新产品需求与Codex实施入口（2026-10-29晚）
- **[R2所有模块总封口与并行总合同](R2_FULLSTACK_PARALLEL_CLOSEOUT_MASTER_20261029.md)**：六窗口各自文件白名单，数据→安全模型→Graph→上下文→API/SSE→前端；最后仅由G集成，不允许未经审批直接切旧8000。
- **[Owner真实运行与模型安全新漏洞审计](audits/R2_OWNER_PRE_CUTOVER_AUDIT_20261029.md)**：当前P0.1仍有6个“无依据安全放行”绕过，独立48+73组回归及前端/教师检测通过但不能发布。
- **R2 Codex六窗**：[A数据知识](CODEX_R2_A_DATA_SOURCE_KNOWLEDGE_20261029.md) · [B模型与安全](CODEX_R2_B_SAFETY_MODEL_20261029.md) · [C LangGraph检索](CODEX_R2_C_GRAPH_RETRIEVAL_20261029.md) · [D上下文会话](CODEX_R2_D_CONTEXT_MEMORY_20261029.md) · [E后端/SSE/运行](CODEX_R2_E_API_SSE_RUNTIME_20261029.md) · [F前端Edge](CODEX_R2_F_FRONTEND_E2E_20261029.md)，全部交付后再给[G统一集成](CODEX_R2_G_FINAL_INTEGRATION_OWNER_GATE_20261029.md)。
- **[P0专业拒答/上下文丢失/证据失败恢复合同](P0_PROFESSIONAL_ANSWER_RECOVERY_CONTRACT_20261029.md)**：用户截图真实案例A/B已由Owner在最新磁盘复现。A的material/medium/temp正确但运行服务仍旧、B最新R9零source后直接unresolved。根因包括R9硬拒答、整句检索、DeepSeek只能改写且结果藏在事件。Codex优先实施专业调查规划与分层回答候选，不擅自修改老师数据或启动服务。
- **[网页发送失败根因与旧API兼容修复](audits/OWNER_WEB_CHAT_422_RUNTIME_MISMATCH_FIX_20261029.md)**：旧8000 Python+新静态前端字段冲突触发422；受限旧RunIn重试、真实重新连接、前端123项和构建PASS；新前端已被8000提供，但完整新后端仍需受控升级。
- **[Codex S2.6真实LLM与专业/压力评估](CODEX_S26_REAL_LLM_STRESS_PROFESSIONAL_20261029.md)**：有界真实API原生100组解析、连续合法工具调用、Mock/真实压力分离及专业错例，费用/超时/会话数据严格限定，禁止默认切换V2。
- **[Owner S2.5可靠性与真实LLM首测](audits/OWNER_S25_RELIABILITY_LIVE_LLM_20261029.md)**：跨进程所有权围栏、可杀子进程、双SSE、322项回归、真实DeepSeek分类3/4（4/4 JSON解析）与真实Planner有界试验；V2默认仍不切换。
- **[S3正式82机理条件知识层方案](S3_DM82_APPLICABILITY_RESEARCH_AND_ENGINEERING_SPEC_20261029.md)**：A/B两窗口可并行：[Codex A来源/候选](CODEX_S3_A_DM82_SOURCE_CANDIDATES_20261029.md)、[Codex B三值引擎](CODEX_S3_B_TRISTATE_ENGINE_20261029.md)，两者交付后再运行[Codex C独立评测](CODEX_S3_C_EVAL_AND_FULL82_GATE_20261029.md)。不得修改老师正式资料与人审。
- **[Owner S2独立复核](audits/OWNER_V2_S2_REVIEW_20261029.md)**：确认S2离线候选可保留、S2.4可继续，但未通过恢复/混合执行/默认切换Gate；**[Codex S2.4持久执行+混合DAG](CODEX_V2_S2_4_EXECUTION_RECOVERY_MIXED_20261029.md)** 为最新实施任务，先恢复协议再真实混合任务，不得开启真实收费模型或切换默认V2。
- **[S2集成历史阶段实测](audits/V2_S2_OWNER_INTEGRATION_20261029.md)**：282 unittest / 3 skips、P16-A 5/5、R10离线20/20、前端118/118、官方554/200/17；仅代表S2当前离线候选，非真实模型或业务准确率。
- **[Owner V2 S1-A/B/C独立复核](audits/OWNER_V2_S1_ABC_INDEPENDENT_REVIEW_20261029.md)**：真实复跑、R9兼容修补、Python环境与前端、S2 NO-GO阻塞；[S2升级任务](CODEX_V2_S2_OWNER_HANDOFF_20261029.md)按Owner发现重新制定，不等于直接允许默认图上线。
- **[V2十二项定案与LangGraph/SQLite架构](AETHER_V2_REQUIREMENTS_ARCHITECTURE_20261029.md)**：LLM主导规划、三路径+混合任务、有限缺工况专业调查、候选证据分级、单SQLite按会话逻辑隔离/增量摘要、UI公开过程、测试与所有权。
- **[V2模型策略与专业安全硬规则](AETHER_V2_MODEL_POLICY_GUARDRAILS_20261029.md)**：不可由模型绕过的工具白名单、E0–E3、人签、三值事实/适用性、RBI、数据私密、计划预算、SSE展示规则和负例。
- [Codex S1-A 模型路由+API直连](CODEX_V2_S1_A_ROUTER_GATEWAY_20261029.md) / [Codex S1-B 自主AgentGraph候选](CODEX_V2_S1_B_AGENTGRAPH_20261029.md) / [Codex S1-C 会话记忆+折叠UI](CODEX_V2_S1_C_MEMORY_UI_20261029.md)：允许三窗口同时开发，但必须严格分开文件所有权。
- [Codex S2 集成Owner验收](CODEX_V2_S2_INTEGRATION_OWNER_GATE_20261029.md)：**仅在S1三个窗口真实完成审查后使用**，不允许提前切换生产默认图。

> 首先读 `AGENTS.md` → **[当前状态](PROJECT_STATUS_CURRENT.md)** → **[文档一致性审计](audits/OWNER_DOCS_CONSISTENCY_20261029.md)** → 按需进入课题合同/数据/执行。旧`docs/PROJECT_STATE.md`与日期型P13/P14/P15规划是**当时历史快照**，不是唯一当前真相。

## 0. 三类文档的权限和状态
| 类型 | 例子 | 规则 |
|---|---|---|
| **教师权威合同与冻结正式数据** | `upstream/README.md`、`upstream/04_接口文档/工具接口规范.md`、`技术指标验证方法.md`、`upstream/任务包问题答复.docx`、`upstream/05_提交区/clauses.jsonl` | 保留原字节，不把我们的状态说明覆盖为老师签章 |
| **项目当前事实/Owner复核** | 本索引、`PROJECT_STATUS_CURRENT.md`、2026-10-29新增Owner审计和实测 | 每轮测最新磁盘后更新；区分PASS、PARTIAL、FAIL、BLOCKED、PREVIEW_ONLY |
| **历史报告/计划/候选** | `PROJECT_STATE.md`、`upstream/05_提交区/条款抽样核对报告.md`、P2–P16原任务书及完成报告 | 保留原记录及原日期；以补充说明解决矛盾，不改写历史、伪造签名或掩盖失败 |

**缺失路径警示：** `docs/CONTRACT_LOCK.md` 当前不存在；旧索引/任务文件中的引用是历史悬空说明。以`TEACHER_QA_CONSTRAINTS.md` + 老师两份接口/指标原文作为合同对照，勿新造一个冒充老师原件的“合同锁定”文件。

## 1. 教师需求与交付
- `upstream/README.md` — v0.3九项交付清单（**权威**）。
- `upstream/04_接口文档/工具接口规范.md` — 三工具唯一签名、五键协议、损伤机理八段式（**权威**）。
- `upstream/04_接口文档/技术指标验证方法.md` — 引用50交叉人审、真实模型100组、轨迹/护栏、ModelScope（**权威**）。
- `upstream/任务包问题答复.docx`、`upstream/资料获取与摘录表填写指南.md` — 老师确认的23/25列、标准边界、OCR与原文、API版权及风险映射（**权威**）。
- [教师QA可执行摘要](TEACHER_QA_CONSTRAINTS.md) / [历史指标映射](TEACHER_REQUIREMENTS_AND_GAPS_20261027.md) — 项目解释，以原文件为准。
- `upstream/04_接口文档/convert.py`、`validate.py`、`schema/`、`enums.json`、`risk_level_mapping.xlsx` — 老师转换与Schema；默认只读。
- `upstream/05_提交区/` — 正式554条款/200轨迹、三个工具、Harness、护栏36/正常60和当期报告；**历史报告不是人审证书**。

## 2. 数据血缘、真实性与发布
- [数据血缘](DATA_LINEAGE.md) — 标准PDF → 两张摘录表 → teacher convert → JSONL → 三工具 → 图与审核；含E0–E3划分。
- [历史50/50与新50条口径对照](data_quality/TEACHER_SAMPLE50_EVIDENCE_STATUS_20261029.md) — 首选入口：历史报告不等于正式独立真人交叉复核，当前0/50及0/42。
- [82条损伤机理适用性根因及改革方案](data_quality/DM_APPLICABILITY_ROOT_CAUSE_AND_REFORM_20261029.md) — 26/82 medium、23温度、0压力的合同/语义根因；暂不重写数据。
- [P16-A42条证据审查](data_quality/P16_A_CHANGED_RECORDS_REVIEW.md) / [P16-B来源与检索](data_quality/P16_B_SOURCE_FIDELITY_AND_RETRIEVAL.md) / [P16-C交付门禁](data_quality/P16_C_BOUNDED_CORRECTIONS_20261029.md) — **机器交付完成，但E2/E3与真人发布门未关闭**。
- [Owner独立深审](data_quality/OWNER_P16_LIVE_HANDOFF_AUDIT_20261029.md) / [Owner系统路由与压力审计](audits/OWNER_DATA_ROUTING_TEACHER_STRESS_AUDIT_20261029.md)。
- `work/data_staging/p15/`及`work/data_staging/p16/` — 未签候选与审核卡，全部PREVIEW_ONLY，不得当正式标准。

## 3. 现行产品架构和用户展示
- [架构：当前与目标](ARCHITECTURE.md) — 当前所有请求进图；目标一般聊天直调DeepSeek、纯标准查证轻量检索、设备判断进LangGraph。
- [普通聊天及折叠执行过程历史实现](AETHER_CHAT_MODES_AND_COLLAPSED_PROCESS_20261028.md) — 2026-10-28 R10版本记录，部分说明已被P13升级或当前新要求取代。
- [P13联网/上下文/负载规则](P13_ADDENDUM_WEB_CONTEXT_LENGTH_AND_STRESS_20261029.md) — 2026-10-29阶段任务设计，当前负载实测需看最新Owner报告。
- `frontend/` React聊天、`backend/` FastAPI SQLite SSE与DeepSeek、`orchestration/` 当前图和路由；`app/`保留老师Gradio参考层。
- **UI边界：** 普通用户只看答复、必要证据、默认折叠的公开判断过程；老师演示中可展开经安全脱敏的工具名称、入参及结果摘要供逐步核查，但不展示原始SSE帧、完整数据库事件JSON或模型隐藏CoT。SSE仅承担后台传输/恢复。

## 4. 测试与实测
- `scripts/owner_dm_condition_inventory_readonly.py` — 复算82机理结构字段覆盖，0写入。
- `scripts/owner_docs_consistency_readonly.py` — 本地文档自检与悬空链接扫描，0写入。
- `evals/owner_mixed_intent_route_audit.py` — 65例自拟混合意图困难测试，48一致/17不一致；不是线上准确率。
- `scripts/owner_p13_api_sse_graph_stress.py` — 隔离SQLite与本地工具压测，并发4 100/100；并发8 73完成+27个429排队，需Backpressure续测。
- `tests/`、`evals/` — 测试代码及gold候选；严禁把mock当真实LLM100组。
- [2026-10-28 Owner教师评测历史](audits/OWNER_FULLSTACK_TEACHER_METRICS_20261028.md) — 老师格式、护栏与未达标边界；新的全量测试参见P16-C报告。

## 5. 维护与归档原则
- 当前**不移动/删除/合并**老师标准、上游仓库、历史审核证据、P15/P16人工表、RBI备份、数据库、附件或其他项目代码。
- 日期型项目报告保留历史事实，新结果只在本索引、最新PROJECT_STATUS_CURRENT和有明确版本的Owner补充说明中更新。不要全量替换旧报告里的历史测试数字。
- 数据质量重构先源图试点，再迁入自有版本化语义索引，仍保持老师三个工具及双Excel转换口径。
- 根目录`README.md`是启动说明，不是发布证书。任何“通过”必须给分母、时间、对象、原版/候选、真实/模拟、人/机签核和代码哈希。
