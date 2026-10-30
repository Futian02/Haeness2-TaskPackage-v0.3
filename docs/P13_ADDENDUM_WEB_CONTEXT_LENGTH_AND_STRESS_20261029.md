# P13 已开工窗口增补｜联网选择、真多轮上下文、长输出、交付压力门禁（2026-10-29）
这是一份**给原P13窗口补充的验收需求**，不另开一个抢A/B/C/D文件的新任务。P14全职数据蒸馏在另一窗口且不能触碰backend/frontend/orchestration。以最早已发的`docs/CODEX_P13_CHAT_RELIABILITY_WEB_AND_HYPOTHESES_20261029.md`为主体，只补如下要求。

## 1. 用户在聊天栏直接选择联网（P13-C负责UI，A/D后端）
- 在composer附近加入地球图标或“联网搜索”选项：`off / auto / on`（关闭/自动/开启）；用户可点击切换，不去设置中心找。每个Run把`web_mode`保存到SQLite run快照、SSE事件，刷新保持会话选择。新会话默认`auto`用于公开日常问答；设备/工业敏感问题默认不把材料/工艺/附件上传联网查询，若为on也要排除敏感原文或交互确认。
- `off`不请求任何搜索；`auto`只为需要时效或公开背景问题查（天气/时政/官网/版本/价格等）；`on`对有实质检索价值的可公开问题优先查，但不能浪费在简单问候/创意/已充分本地回答上。
- DeepSeek Search/Fetch已发布：`POST https://api.deepseek.com/v1/tools/search`与`/v1/tools/fetch`，成功请求计费，不能因Chat Completions配置API Key就宣称自带联网。`deepseek-v4-pro` Responses有内置`web_search`，当前flash不是。至少返回source title/url/date及retrieval timestamp，禁止伪造链接或把网页内容算成老师的权威GB/T条款。要有timeout、调用预算、429/402可见错误、用户可关、搜索query长度和版权清洗。提到天气但没地点→先询问城市，不猜位置。
- P13-D创建独立`backend/web_search.py`供A集成，C只改前端composer、可折叠来源卡，不可与A在`backend/api.py`同时写。

## 2. 多轮上下文是第一优先功能（A主导）
- 区分两条记忆：**普通聊天历史**（system+同一conversation最近8-12轮可见user/assistant，含失败run公开状态摘要）；**设备事实槽位**（字段、来源、时间、是否已确认/冲突，不因过期设备信息污染普通聊天）；持久化都已具备SQLite基础。以`conversation_id`隔离，LangGraph可复用`thread_id`+checkpointer，但不能双份无限缓存；当前无checkpointer时用现有SQLite先实现，不加新框架。
- 对用户“怎么回事”“继续生成”“换个颜色”“再给我一个”能正确关联前一个普通请求、上一次错误信息；不是将最后一个用户问题单独发给模型。历史token超预算时优先截断最早轮，保留当前任务目标/关键用户约束，摘要必须标摘要而不是模型已确认事实；不跨聊天，不串档案，退出会话删除清空状态可选。
- 保护权限和私密工况：普通聊天不能无提示将其他会话或PDF全文、原单位设备信息送到搜索API。
- 对run context冲突：当前轮显式说明>已确认同会话工程槽位；历史工程槽位仅用于明确工程续问，不将天气、代码任务误判为工程。

## 3. 模型输出长度、思考和供应商终态（A主导）
- 官方ChatCompletion 2026参数：`thinking.type=enabled|disabled`，默认enabled，`reasoning_effort=none|low|high|max`；`max_tokens`可调，低于128k等不应该直接无界设巨大。按任务选profile：
  **一般短聊天** max_tokens建议4096；
  **代码/长文/HTML** max_tokens建议8192或16384（可配置上限，输出代码不启高思考预算，默认`thinking.type=disabled`或`reasoning_effort=none`，除非用户专门要求复杂规划）；
  **专业报告文字整理** max_tokens2048–4096，锁定现有证据来源不编造。
  考虑上下文实际长度、用户费用上限和运行timeout；如果模型不支持某字段，分provider配置，不向未知第三方无差别发送。
- 必须解析`finish_reason`（stop、length、content_filter、tool_calls、insufficient_system_resource、aborted）、`usage.prompt_tokens/completion_tokens/total_tokens`、provider返回的模型名、真实耗时；`content=None/empty`不能统一“返回空内容”后吞Run。如果finish_reason length，显示“输出被截断”，允许重试/续写；content_filter明确告知不能提供但不冒充成功；若只有reasoning_content且content为空不能把私有推理直接当答案，应给合适公开错误与重试；SSE`run_failed`必须持久化并可恢复显示。
- 保存Token只是实际provider response返回的值，不能拿本地估算冒充精确用量；失败也计真实用量（若供应商返回）。
- 如果使用JSON模式用于上下文槽位，必须满足provider结构化输出约束和schema；普通HTML长文不使用JSON模式。

## 4. 每次交付前的硬质量门禁（不全过=不放行）
**D0 既有功能**：全后端unittest、前端Vitest/TS/Vite build、老师`validate.py --final`、3工具17/17，禁止退化；刚才的P13诊断13场景各有回归断言。
**D1 路由与上下文测试**：至少30条跨主题case（10普通、10工程、5标准、5含误导上下文）+真实至少3组同会话连续4轮 + 2组跨会话串线测试；错误路由=0，用户明示字段丢失=0。
**D2 模型协议异常**：mock 30–50组（finish_reason6类、空内容/仅reasoning、400/401/402/429/500、timeout/断线、输出8192/16384、UTF-8、markdown代码、context超限），每条产生完成消息或显式失败卡，**空白沉默=0、secret泄露=0**。失败要保存且刷新可恢复，不计作成功。
**D3 负载/并发**：最少100 Run混合输入（一般对话/工程标准/无证据），并发1/4/8做本机隔离DB压测，记录P50/P95/最大值和错误率；并发工作槽满应返回明确429/等待而不丢Run或重复执行。每次SSE序号连续、同run事件不重复、终态唯一、最终answer与DB一致、失败无伪completed。真实大模型网络不用于高并发烧钱压测；小规模真实调用由Owner另批准。
**D4 搜索**：off 0次外部调用，auto仅在时效查询触发，on返回可点URL、搜索时间；无地点天气回问；Search超时/402/429显式降级和无幻觉；工业敏感文本不外泄。Mock>=20条。
**D5 真实UI**：Edge桌面/移动、浅/深、浏览器刷新、连续追问、撤销搜索模式、长代码块复制、失败卡恢复；console 0 error、横向溢出0，截图及run_id证据。Firefox/WebSpeech可记支持限制，但不可谎称支持。
**D6 专业数据**：老师正式质量核验由P14负责；本次不能拿未复核PDF条款宣称E2/E3，且RBI等级保持fail-closed。
门禁报告必须记录`PASS / FAIL / BLOCKED_NOT_TESTED`、指标分母/分子、真实/模拟、模型/服务版本、成本。任何硬用例FAIL就让Codex继续修复并复测，不能出`READY_FOR_OWNER_REVIEW`声称全通过；如果需要真实收费或人审导致不可测，诚实标BLOCKED并交付其余完成项。
