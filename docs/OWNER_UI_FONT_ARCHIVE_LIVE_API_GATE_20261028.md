# Owner 2026-10-28｜当前界面可读性修复、会话归档与真实模型接入验收

当前工作目录：`D:\作业\竞赛\计算机设计智能体\机械智能体`。**本轮只修改 frontend 的 CSS/会话归档入口及专项测试，没有改 backend/deepseek.py、backend/api.py、Graph、教师数据或密钥，也没有发起任何真实模型推理请求。**

## A. 本轮 DevSpace 实测状态
- 原截图中字过小的确是源 CSS：助手消息12px、侧栏11px、输入框11px、设备与工况输入9px。已直接改`frontend/src/styles.css`：聊天正文16px、聊天输入16px、侧栏14px、工况表单14px高40px、工况折叠标签13px、搜索14px、新建按钮14px、顶栏13px、其他相关标签适度放大。
- `frontend/src/ConversationThreadList.tsx`新增“移出列表”图标及ARIA label，`frontend/src/App.tsx`使用已有`api.archiveConversation`；先确认，执行中会话不能归档；成功后会话从列表隐藏，SQLite永久保留供恢复。**这不等于物理删除**；如用户要“彻底删除所有聊天和上传文件”，需要以后单独做后端删除操作并确保确认/文件引用，不能冒充已实现。
- 将“设备与工况·可选”改为“机理研判需填写材质/介质”。纯标准引用查询不需要这些字段；一般闲聊/问候现在仍错走RULE_DEMO缺工况，见下文。
- `frontend/src/ConversationThreadList.archive.test.tsx`新增测试：按钮确实调用onArchive，不触发会话切换。
- 直接验证：TypeScript PASS、Vitest原74/74 PASS、归档新测试1/1 PASS、Vite build PASS、Python unittest136项OK(3可选skip)；本机FastAPI`GET /api/health`返回200，mode=DEEPSEEK、llm.configured=True、model=deepseek-flash，tool list3个；这只是配置可见，不代表已经向外部provider成功推理。
- 使用独立临时SQLite+TestClient核实已有归档API：create200、PATCH archived200、普通列表不再出现、include_archived列表仍可见。没有修改真实用户数据库与任何现有聊天。

## B. 当前生产部署**不能**认定真实多模型Agent完成
已读`backend/deepseek.py`：`generate_report()`仅把RULE_DEMO图的deterministic_result、至多8条citations及已知设备条件发送到OpenAI-compatible Chat Completions，将结果改写为中文最终报告；不通过模型选择/调用`damage_mechanism_query/rbi_lookup/standard_clause_search`，也不通过模型自主决策Investigator或两个Reviewer。
`backend/api.py`支持DEEPSEEK mode及health configured，但**当前状态是rule-graph+LLM reporter**，不是多LLM交叉证据审核。输入“你好”在`route_task`仍走`missing_context`，所以会回复补材质，DeepSeek只能润色这个错误。输入“请依据标准判断这台设备风险等级”因`_is_standard_lookup`优先检测“标准”会错误归为`standard_lookup`。
`backend/deepseek.py`消息请求`conditions`含equipment/equipment_type/material/medium/operating_condition，意味着**工况摘要会发送第三方API**，不是零工况外发；实际生产设备敏感数据上线前必须明确授权与脱敏。附件没有直接传出，标准原文全文也未包含（依据当前代码）。

## C. 交给正在操作API的Codex的最短需求（不要扩充工程）
1. 先确认真实DeepSeek请求成功：一条**非敏感测试输入**，验证HTTP状态、真实模型名、文本、耗时、token usage（如果provider返回）；失败提供错误码，不在日志输出key。当前configured=true只表示本地key非空，不能算LIVE_PASS。
2. 把模式状态清晰分成`RULE_DEMO` / `LLM_REPORT_ONLY` / 真正的`LLM_AGENT`（名称可精简，至少报告中区分）；正式要达到后者，模型需实际进行**3个冻结官方工具的native function calling或等价可验证JSON工具规划**，保留每次工具调用的真实参数/结果与错误，独立审核不能只改写其自然语言回答。
3. 修简单Router误判：`你好`是`general_chat`，`仅问标准编号/条款`是`standard_lookup`，`依据标准判断这个设备的风险等级`是`diagnosis/rbi`并缺因子时明确拒绝设备定级；增加正反例测试而不换完整Graph架构。
4. 模型驱动真实调查至少一次多轮Tool→LLM→Tool回环、一个Reviewer条件启动案例与一个证据不足安全退出案例；若独立双模型审查太贵，先一个调查LLM + 一个独立Auditor LLM，Skeptic可先规则但明确标注，禁止声称全是真LLM。
5. 小样本10题（标准、机理、缺数据、域外、错误检索、混合意图）→100题教师正式模型解析与至少5轮轨迹；分报模型原生工具成功率、LLM错误、fallback次数、citation支持性、TTFT/P50/P95总时延、tokens/成本，合规真实PDF引用需后续真人≥50条复核。不能把本地R9的百余条pytest当API测试。
6. 不直接打开公网：现中间件`APP_ENV=production`拒绝所有请求，loopback-only仅本机可用；用户所说“生产级测试”先指**有真实API调用的严谨本机准生产验收**，不是通过改APP_ENV就变公网生产服务。
7. Codex正在部署provider时，Owner不会读或暴露API key、不会发送付费请求；先完成本地frontend独立改动验收和API health只读检查。

## D. 待Owner确认
若要永久删除对话而非移出列表，最后添加一个单独且显式的“彻底删除”操作，确认后连同已无引用的附件清理；默认仍建议可恢复的归档。
