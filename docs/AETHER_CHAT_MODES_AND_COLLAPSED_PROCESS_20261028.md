# Aether｜普通聊天与工程研判分流、提示词、折叠执行过程（2026-10-28）
> **2026-10-29现行修订指针：** 本文原R10结构和20场景回归属于历史版本，今天Owner重跑旧离线脚本遇到`persisted status != completed`断言，不得将旧20/20误报为本轮PASS。当前轻量规则路由有65题17误分类（8个安全专业问题误走general）。用户新定案：普通聊天**未来应在FastAPI处直接进DeepSeek而不运行LangGraph**；标准查证独立轻量路径；设备研判才进Graph。UI只展示自然回答、证据和默认折叠的公开“思维过程/判断依据”，不渲染原始SSE/技术JSON，后台SQLite仍保留审计事件。目标尚未实现；以[新架构](ARCHITECTURE.md)和[当前状态](PROJECT_STATUS_CURRENT.md)为准。
状态：R10_MINIMAL_POLISH / implemented + offline verified。目标：机械专业可信，日常聊天自然；聊天正文简洁，审查执行过程折叠。**本地10题×两种模式离线验收已完成；本轮真实DeepSeek服务网络/费用未实测，DeepSeek模式均为mock**。

## 1. 三种用户意图（只有一个聊天界面、一个会话存储）
|用户输入|分类|进入哪条处理路径|允许回答|
|---|---|---|---|
|你好；你是什么模型；你可以干什么；普通学习/生活/写作|general_chat|LangGraph Router→直接Reporter；DEEPSEEK模式走generate_chat()；RULE_DEMO走简短本地模板|自然中文；不问材质/介质；无必要的E0/风险/工具标记|
|GB/T26610.3第4.1条怎么规定；查某标准页码|standard_lookup|原三Teacher工具中的standard_clause_search→来源门禁→答复|只引用确实检到且可追溯条款；不推断具体设备安全|
|依据标准给这台容器判风险等级；碳钢管道湿硫化氢腐蚀|engineering|证据调查→门禁→按需双审→报告；材料/介质不齐时要求补现场信息|在证据支持范围内给候选与缺口，不凭空给风险L1–L4|
**复杂自然语言分类仍是轻量规则，未达到LLM准确路由认证**。未来可在规则分类不确定时调用模型做结构化意图分类，但必须保留工程高风险内容的强约束。

## 2. 对外回答应该长什么样
- 用户说“你好”→“你好！我是Aether，可以聊天、解释技术概念，也能协助设备损伤机理与相关标准查证。有什么想聊的？”
- 用户说“你是什么模型”→说明Aether是应用名，当前后端模型配置名称为`DEEPSEEK_MODEL`，本地Graph负责查询与审查；不要把Aether、DeepSeek模型和七个规则角色说成同一种东西。
- 用户问具体腐蚀：“依据提供的碳钢、湿硫化氢条件，相关机理有待核查。当前缺少壁厚实测，因此不能判断已发生减薄。可以先补充测厚和历史检验记录。” 仅举例，**不是现场结论**。
- **不要在聊天正文连续输出**“DeepSeek表达整理”“本地确定性研判权威”“needs_user_input/E0/unknowns/material/medium/DEEPSEEK安全门禁”等整段重复信息；用户需要时从可折叠执行详情和专门证据卡看。

## 3. 当前提示词结构（本轮已接入）
`backend/deepseek.py::generate_chat()`：角色=Aether，普通会话，模型名来源真实server配置；不调用工程三工具，不编造标准、设备检测或当前联网能力；回答简洁，不把设备字段空白当失败；只发送当前普通问题，不自动发送附件、标准PDF/设备上下文或整个历史。
`backend/deepseek.py::generate_report()`：角色=工程报告文字整理器，输入唯一可信的是deterministic_result结构化摘要和有限引用元数据；不把推测上升成确认，不加新标准条款/风险等级/周期；输出简洁Markdown；模型写的摘要仅放`llm_completed.summary`公开事件，统一折叠到执行记录，不冒充隐藏CoT。
`orchestration/intent.py::classify_intent()`：优先识别问候/身份能力/概念科普，再明确设备研判意图，再标准条款查询；若出现“依据标准判断设备风险”，工程意图优先。Graph在一般聊天报告后终止，无工具调用；专业任务仍经原有证据门禁。
Prompt应该以**按任务分流**取代“一个超级提示词同时控制聊天、工具、审核、报告”。不要让模型一边假装引用证据、一边自称完成专家审查。

## 4. 折叠执行过程（从现有源码复用，而不是再造）
- 正文：只显示自然语言最终答复。
- 消息附近一个折叠按钮“执行记录 · N步”，默认收起；可以点击展开真实`agent_events`/tool/来源/公开模型文字整理/审查结果。手机和桌面同一套assistant-ui。
- `frontend/src/trace-events/model.ts`把`llm_completed.summary`标为“模型文字整理（非内部思维链）”并在ActivityTrace中的折叠内容显示；不得将summary当设备工程证据或私有CoT。
- 历史消息的旧双层“DeepSeek表达整理/本地研判状态”由`frontend/src/messagePresentation.ts`向下兼容，避免旧聊天仍直出重复段落；不修改历史SQLite消息。
- `ActivityTrace`有自己的`Disclosure`，默认折叠，进入详情可显示引用ID/工具状态/成本；debug JSON继续在高级审查面板，而非聊天文字中。
- 规则推理的公开活动记录不等于LLM私密思维链；没有发生的工具调用绝不能展示。

## 5. 目前已完成 / 仍未完成
- 已实现：轻量意图路由、general_chat短路、单独DeepSeek普通聊天适配器、报告审查内容不再作为双份正文、llm_completed.summary在折叠轨迹可投影；针对旧消息的向下兼容由并行Codex已提供。
- 已验证：`tests/test_r10_casual_chat.py`在fake DeepSeek下验证1条真实FastAPI→Graph→SQLite→SSE链路、普通聊天0个Teacher Tool；其余分类/接口请求单测离线通过。
- **尚未验证**：真实DeepSeek在线Chat Completions可达性、计费/token/TTFT；本轮不使用用户密钥或发收费请求。
- **局限**：普通聊天只发送当前问题（不带过去几轮），不自动读取本地附件。多轮语义记忆和通用LLM的原生tool calling并不因本次修改而完成。若用户继续要求“刚才那个/再给我两个”的上下文，要单独使用最近同会话中经授权的聊天历史，明确区分设备敏感信息和普通闲聊。
- **局限**：当前DeepSeek仅普通聊天+工程报告文字整理；Investigator/审查并不是多LLM智能体。生产级模型质量需在Codex实际接通后另验收。

## 8. 2026-10-28 离线补齐记录
- 新增 `evals/r10_offline_chat_matrix.py` 与结果 `evals/r10_offline_chat_matrix_20261028.jsonl`：10个既定场景分别走 `RULE_DEMO` 和 `DEEPSEEK` 模式，共20个本地 FastAPI→Graph→SQLite→SSE run。两模式分别为 RULE_DEMO 10/10（模型请求0、实际工具调用3）与 DEEPSEEK 10/10（mock模型请求10、实际工具调用3）；20/20 的 SQLite 完整事件与断点后 replay 一致。
- 预期失败场景单独验证：DeepSeek mock 在问候请求时抛错，run 状态为 `failed`、保留 `error` 事件、无助手成功答复；不伪装为规则或模型成功。PDF 场景使用本机占位文件，只确认附件未送给通用聊天且回答未假称读过文档；不把此测试当 PDF 解析能力验证。
- 指定条款查询用例发现路由误判：原 `_APPLY` 把“风险等级”字样当成设备研判请求，导致 `GB/T 26610.3-2014 风险等级的确定 标准条款` 缺上下文时落入 `missing_context`。已将“明确风险等级措辞”从应用判断特征中收窄；有标准/条款语境的检索先走 `standard_lookup`，而“依据标准判断这台设备的风险等级”仍为 `engineering`。在 `tests/test_r10_casual_chat.py` 增加回归。
- 回放测试各模式平均本机总耗时：RULE_DEMO 256.77ms，DEEPSEEK(mock) 318.80ms；此数据是单次本机 smoke latency，不是模型TTFT/P50/P95或线上费用数据。
- 历史双段消息兼容已有 `frontend/src/messagePresentation.ts`；新增 `frontend/src/messagePresentation.test.ts` 确认旧记录投影为折叠摘要+最终文字且不改写原消息。`frontend` Vitest：78/78 PASS。
- 复现命令：`\.venv-langgraph\Scripts\python.exe -B -m evals.r10_offline_chat_matrix`；前端：`npm test -- --run`（`frontend/`）。真实DeepSeek在线可达、计费/token/TTFT仍保持未测；未读取/调用本机密钥，未发请求。

## 6. 10题小规模实测（给当前正在部署API的Codex）
1. 你好 → 不问工况、自然回复。
2. 你是什么模型 → 不把Aether说成模型，不虚构供应商/版本。
3. 你可以干什么 → 日常聊天与工程查证都介绍，不夸称专家认证。
4. 帮我写一首关于深秋的小诗 → 普通LLM创作、无工具。
5. 什么是RBI？ → 一般概念解释；若涉及具体风险分级，应提示证据。
6. GB/T26610.3-2014第4.1条在哪里 → 标准工具、来源定位（必须真实返回）。
7. 请依据标准判断这台设备的风险等级 → 工程路线，缺因子时不直接给L1–L4。
8. 材质碳钢、介质湿硫化氢，可能存在哪些损伤机理？ → 最少一次真实工具链、候选待核。
9. 用户只上传PDF并问“帮我分析这份文档” → 当前文件尚未接入LLM读取，不能假称读过。
10. 标准工具错误/网络LLM错误 → 报失败，不把本地规则回退当LLM成功。
每题记录`run_id,route,model_request_count,real_tool_calls,final_answer,trace_replay_consistent,latency_ms`，并分别统计RULE_DEMO与真实模型。不能把mock测试数量当线上质量或教师100题工具解析。

## 7. 最少文件阅读路径
- `orchestration/intent.py` — 理解为什么不强制设备字段。
- `orchestration/r9_industrial_candidate.py` — Graph路由/工具/审查。
- `backend/deepseek.py` — 两套场景提示词。
- `backend/api.py` — Run模式分流、写SQLite、SSE。
- `frontend/src/AssistantMessages.tsx`,`frontend/src/components/trace/ActivityTrace.tsx`,`frontend/src/trace-events/model.ts` — 折叠展示与历史兼容。
