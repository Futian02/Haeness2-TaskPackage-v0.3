# Codex P13：修复真实用户已复现的聊天失败、历史污染、工程条件性候选与联网能力
工作根：`D:\作业\竞赛\计算机设计智能体\机械智能体`。
**先完整读** `AGENTS.md`、`docs/audits/OWNER_P13_WEB_CHAT_DIAGNOSIS_20261029.md`、`scripts/audit_p13_dialogue_diagnostic.py`、`backend/api.py`、`backend/deepseek.py`、`orchestration/intent.py`、`backend/context_slots.py`、`frontend/src/api.ts`、`frontend/src/App.tsx`；再开始。不要回退P12、不要引入新框架，不改`upstream`三工具/Excel/PDF/JSONL。以本机已保存证据为第一真相。

## 现场关键故障（已证实）
- 监听127.0.0.1:8000的Python PID59120从2026-10-28 21:54:56运行，当前API GET /api/model-profiles仍404，磁盘最新版已有该路由。**确认进程旧版；不要未经Owner同意重启其他DevSpace或用户服务；先找清本服务启动命令、运行中任务，得到允许后只正常重启此FastAPI，验证实际online route。**
- 真实data/haeness2.db只读：65 run，60完成、3失败、2排队。3个失败均HTML/SVG骑车代码任务，`DeepSeek 返回空内容`，0 assistant消息。app目前把SSE error当正常terminal，用户看不到失败卡。请勿修改/清空这个DB。
- 显式工况写`介质:[碱式酸性水]`时材料介质不被正确归一，模型新路由未在旧服务加载；正常无括号写法能命中机理候选。
- 在带上轮工程上下文的同一会话，天气、HTML、图灵机讲解都错误归engineering；`generate_chat`仅发送当前user无上下文；写代码的900 max_tokens/默认thinking可能令生成不完整，必须检查真实finish_reason才下最终结论。
- 本地不自动联网，DeepSeek API key不是自动上网能力；2026官方DeepSeek有Search/Fetch端点`https://api-docs.deepseek.com/guides/search/`，和`deepseek-v4-pro` Responses内建web_search（不要混淆flash）；WebSearch为应用内部资源，不是第四个老师工具。

## 三个并行模块（同一Owner最终合并共享文件）
**Agent A（P0，模型、历史与后端运行）**：独占`backend/deepseek.py`、`backend/api.py`、`backend/store.py`仅必要增量、`tests/test_p13_model*.py`。
1. 普通聊天上下文：同会话、最近8–12轮+最近失败Run公开摘要，优先用户原话+可见助手回答；按token截断，不跨会话，不把模型隐藏reasoning_content存进去。
2. 增加`finish_reason`/实际usage/返回模型ID/合理最大输出token/思考模式配置，注意代码较长或思考预算耗尽；客户端失败时反馈结构化错误，不输出私有reasoning_content、key、provider raw body。代码类请求需能输出完整HTML/SVG，不要求真实写本地文件。
3. `generate_report`当前只生成折叠摘要却计费：保证工程聊天正文有来源支持候选和条件性解释，文字整理失败不让本地确定性报告消失；普通聊天失败必须显示错误和重试。
4. 为联网提供内部`web_search` service的可插拔调用点（Agent D创建service，A负责API胶水），禁止将工业敏感记录自动上传至搜索。
**Agent B（P0/P1，Router与机理候选）**：独占`orchestration/intent.py`、`orchestration/r9_industrial_candidate.py`、`backend/context_slots.py`、相关测试。不得碰backend/api.py/deepseek.py。
1. 先判断当前轮明确意图再用历史工况；“天气/代码/概念讲解”不因上轮有material+medium而走工程。含代词的工程继续问才利用同会话上下文。
2. `介质：[碱式酸性水]`、`介质: [湿硫化氢, 氯化氢]`等合法包装归一、以老师枚举为准；不将模糊词转成已观测损伤。
3. 区分`general_chat / standard_lookup / hypothesis_exploration / device_diagnosis / deterministic_rbi_grade`；低信息时允许“标准已有的可能机理方向、适用条件、排除条件、现场所需证据”的探索性列表，**风险L级仍不能从未知工况推断**。有来源的候选按材料介质/温压匹配与证据覆盖排序，显示“较匹配/有条件适用/暂无法判断”，不得凭空给80%、60%等假置信度；明确反证/鉴别检查，保持E0/E1和人审门禁。官方三个工具签名不能改。
**Agent C（P0，前端用户可见失败）**：独占`frontend/src/api.ts`、`frontend/src/App.tsx`、`frontend/src/AssistantMessages.tsx`与专项前端测试。不得碰后端和上游。
1. SSE error不是成功终态；`run_failed`显示真正用户可见的卡片+有限错误类型+重试按钮，不把助手空消息显示为“完成”；刷新历史后仍能看到失败run的状态。不要暴露私有provider错误原文。
2. 普通聊天代码块完整可复制，长回复折叠不应隐藏唯一答案；任务状态0次工具时不要显示虚假审查链。
3. 深浅/移动端无溢出，旧历史兼容，保留P12设置。
**Agent D（P1，联网，仅新文件）**：独占`backend/web_search.py`、`tests/test_p13_search*.py`、联网接口对接说明，不碰api.py/deepseek.py，由A集成。优先DeepSeek官方`/v1/tools/search`和`/v1/tools/fetch`；同时也可列另一个可替代Search provider但不需要接多个。网页来源要保存URL/title/时间戳并明确“外部网络资料非老师标准条文权威”；天气无城市时先问地点，勿擅自索取/推断精确位置；用户可开关联网，保密工程内容默认不联网，时间/调用预算有上限。

## P13关键门槛
1. 只读`scripts/audit_p13_dialogue_diagnostic.py`13组表，目标旧工程上下文不污染普通聊天、方括号归一、无工况探索性候选与风险级别仍空。
2. 使用离线mock覆盖`finish_reason=length/content=null`、content_filter、provider 400/429、接口中断、90秒超时、stream error，所有失败Run可被看见并重试。真实失败样本固定，不触碰生产聊天。
3. 同会话“创建HTML骑自行车动画”→“怎么回事”→“请继续生成”要保留正确历史，确保max_tokens足够，可控输出完整`<svg>`与HTML文档；没有收到任何回复需展示失败。
4. 对硬门禁/候选排序做至少20条合成案例 + ≥10条有来源标准核查；4个可信区分字段缺失不能给风险等级；E0/E1不是概率。
5. 仅获Owner许可后做最多10次小规模真实Provider请求，记录真实finish_reason、token、模型、延迟、是否调用联网工具；不用真实设备敏感数据做外部搜索，任何收费API请先告知。
6. 前端Vitest/tsc/Vite、后端全部unittest、教师validate554/200和17工具自测全过。桌面+移动真浏览器截图；报告按`代码PASS / 真实端到端PASS / 未验证`分类。
7. 不部署公网、不升级多个服务、不清理Git或用户文件。总交付`docs/audits/P13_CHAT_PRODUCTION_REPAIR_ACCEPTANCE.md`，状态`READY_FOR_OWNER_REVIEW`，达标就停。
