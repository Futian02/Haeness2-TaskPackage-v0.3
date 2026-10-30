# R8-B｜豆包式简洁聊天工作台：开源复用、会话导航、附件、上下文和审计UI设计
日期：2026-10-28｜STATUS=APPROVED_DESIGN_NOT_EXECUTED
根目录：D:\作业\竞赛\计算机设计智能体\机械智能体
修改目录：`frontend/`、`backend/`（仅本任务所需的上传/文件/会话/Run关联接口）、`tests/test_r8b_*.py`、`docs/audits/R8B_*`；**不碰upstream任何教师PDF/Excel/工具/JSONL，不碰orchestration/**。R8-A并发修改`upstream/01_RBI标准`及数据审计文档，两者不抢文件。
核心目标：**像豆包一样简洁、舒适、轻量的交互**，而非完全复制品牌Logo、专有设计资产/源码。以“会话栏+主聊天区+附件+上下文+可展开执行轨迹”构成可实际使用的本地工程AI助手。

## 一、开源项目复用研究与取舍（核对源项目版本和license再拷贝）
|项目|官方地址|在本项目中的用途|方式|
|---|---|---|---|
|assistant-ui|`https://github.com/assistant-ui/assistant-ui`|Thread、ThreadList、Composer、Attachments、消息操作、无障碍/运行时适配|**主组件库**，现有frontend已依赖`@assistant-ui/react@^0.15.32`|
|assistant-ui Thread list sidebar|`https://www.assistant-ui.com/elements/thread-list-sidebar`|固定侧栏、历史列表、搜索/切换、移动抽屉|优先直接复用现成元素，保持与自有SQLite会话列表的Controlled adapter|
|assistant-ui Attachments|`https://www.assistant-ui.com/docs/guides/attachments`|附件按钮、拖放、预览、上传进度、错误回滚|优先官方AttachmentAdapter；大文件走后端上传，不要全部转base64塞聊天历史|
|langchain-ai/agent-chat-ui|`https://github.com/langchain-ai/agent-chat-ui`|Thread / LangGraph streaming / 侧边Artifacts / 节点运行态|MIT，可参考/复用**明确组件**并保留许可；它用Next.js，**不整体迁移**|
|vercel/chatbot|`https://github.com/vercel/chatbot`|桌面会话体验、消息滚动、附件状态和空白引导|参考交互和适合的MIT源组件；自带Next.js/Postgres/Vercel Blob，**不迁移后端**|
|Open WebUI|`https://github.com/open-webui/open-webui`|附件管理、会话中关联文档、知识库交互|只参考产品交互；独立核对许可证，禁止直接大量复制代码|

可继续保留React19、Vite8、TypeScript7、Tailwind4、Radix、`@xyflow/react`、react-markdown，现有`frontend/src/App.tsx`、`AssistantMessages.tsx`、`uiModel.ts`、`EngineeringReport.tsx`等按最小diff演进。禁止引入第二套Agent运行框架、Next.js部署链、替换SQLite、迁移成OpenWebUI全栈。所有第三方新代码保留原版权/License说明，`docs/audits/R8B_OPEN_SOURCE_PROVENANCE.md`写具体仓库、commit/tag、文件与许可。

## 二、视觉/布局与信息架构
**设计目标**：界面安静、文本舒适、无花哨霓虹/机器人大头像/迷宫图；白或极浅暖灰底、低饱和绿色点缀（保留当前色系）、14~16px聊天正文，清晰的用户/系统语气区分；轻边框/微阴影/适度圆角。提取成熟开源控件后做品牌中性化设计，不复制豆包图标。
桌面≥1200px默认：
- 左侧250~278px可收合**对话侧栏**：新对话按钮、搜索、按今天/昨天/更早分组、点击快速切换历史、当前项高亮、重命名、归档；明确保存到SQLite而非只localStorage；删除操作如未来添加需二次确认且默认先归档。
- 主区宽度自适应、**正文最大宽760~860px**：新对话欢迎/提示、聊天气泡/markdown/code/table、消息复制/重新发起、流式状态、长报告折叠/来源链接，Composer吸底。
- 右侧默认折叠：一个“过程·证据”按钮打开 Drawer/Inspector，展示每轮实际Agent节点/工具事件、公开决策摘要、引用与反证。React Flow放在二级查看，不强占聊天正文。
- **每次对话内部跳转**：可展开“本对话目录/轮次导航”，列出每条用户提问的简短标题及时间，点击定位到对应消息；至少50轮可用，折叠后不占主空间。这与左侧“会话列表”是两个维度，二者都实现。
- ≤768px移动：会话栏改滑出抽屉，主区单栏，底部Composer，过程/证据放Sheet/Tab，附件卡换行、状态清晰。
基础交互：Enter发送/Shift+Enter换行，发送中暂停按钮仅在后端真实支持取消时启用；历史切换不能污染当前Run；重新生成必须创建新run且前端告知，不重复触发同一run。空/失败/重试/断网/取消上传有清楚反馈。
可访问性：键盘导航、焦点环、label、contrast、移动点击面积≥40px，尊重reduced-motion；浅色和深色两套。

## 三、文件上传是后端真实功能，不是“加号图标”
当前`backend/api.py`只有会话、Run、SSE和审查查询；`backend/store.py`九表（无文件附件关联）；`APP_ENV=production`无认证时fail-closed。**不能只做前端预览就说实现了文件上传。**
建议最小文件类型：`pdf,docx,txt,md,csv,xlsx,png,jpg,jpeg,webp`。**原样存储与只读预览阶段**先支持文件元数据、TXT/MD内容预览和基础PDF文本抽取；DOCX/XLSX/图片如抽取器尚未通过真实测试则明确`stored_not_parsed`，不要声称模型能理解所有格式。不支持exe/js/bat/ps1/zip宏及任意URL抓取，默认拒绝。单文件默认≤15MiB、每消息≤5文件；用户可调整但需服务端同步限额，不能依靠前端检查。
后端设计：
- `POST /api/conversations/{cid}/files`：multipart流式接收；校验实际字节长度、MIME和魔数（扩展名不可信）、文件名净化、SHA256、UUID路径防目录穿越、可选病毒检测能力状态；本地磁盘`data/uploads/<opaque-id>`，**SQLite只存元数据/关联/状态，不把15MB的文件直接存BLOB**；如果解析失败文件状态可见且不进入检索。
- `GET /api/conversations/{cid}/files`、`GET /api/files/{file_id}/metadata`、`GET /api/files/{file_id}/preview`（有白名单、安全Content-Disposition/Content-Type和字节范围限制），文件ID绑定会话。路径不返回本地真实绝对地址。
- 建表建议`conversation_files(id, conversation_id, file_sha256, original_name, safe_path, content_type, size_bytes, uploaded_at, extraction_status, source_type)` + `message_attachments(message_id,file_id,...)`；`run_attachments(run_id,file_id)`或经用户明确选择再绑定；外键/版本迁移与WAL一致。
- 上传文件不等于隐式采用其中内容为设备事实。运行时只在该聊天中由用户明确勾选/选择的文件进入上下文，引用带`file_id + page/position + extraction_status`。非官方文档永远不得因为上传而变成老师的标准来源或E1~E3官方证据。
- **最重要安全门禁**：默认本地loopback，生产无认证拒绝服务；上传绝不自动外传第三方LLM、文件日志脱敏、PDF/docx文字当不可信数据防prompt injection、禁止上传模板主动覆盖原始RBI工作簿。
- 既有FastAPI中间件`_MAX_BODY_BYTES=128*1024`，上传新API必须正确单独按流限额处理，不能直接调大所有API体积上限到几十MB；需要检查chunked传输、multipart越界/压缩包炸弹、0长度、重复文件、并发与失败磁盘清理。
- 图片/文件卡显示上传中/完成/失败/仅保存尚未解析，附件点开元数据和可用预览。

## 四、会话上下文：区分“页面历史”和“真正的模型上下文”
- SQLite现有`conversations`、`messages`、`runs(context_json,question)`，Run已持久存用户问题和工况，但`GET /api/runs/{rid}`目前只返回状态元数据，前端P7B运行快照部分在localStorage。需补**可信的服务端只读Run输入快照**接口（限本会话、本地环境），替代本地缓存作为事实来源；对外请求不得泄露隐藏prompt或密钥。
- 会话历史分页/按时间或ID排序、稳定切换；每条用户消息或Run可关联附件文件ID与引用。前端“当前上下文”面板分成：本次用户输入、手动设备工况、明确纳入的附件、历史对话摘要（若未来模型启用）、本轮标准来源。
- 现在仍是`RULE_DEMO`，没有真正跨轮LLM上下文窗口/模型记忆。**不要因页面显示历史消息便宣称LLM理解并记住全部历史**。本轮可实现可靠的后端context assembly模型和严格事实快照，用`context_included_message_ids`、`file_ids`、长度/令牌预算字段标清楚未来模式会读取什么，真实LLM接入后再跑token/summary效果。
- 正式模型provider未配置时默认仅展示“运行模式 RULE_DEMO；会话持久化已启用，模型跨轮上下文尚未启用”的文案，不加假模型思考动画。更新R8的图事件只读适配，不修改编排核心。
- 需要设计`GET /api/runs/{rid}/input`和`GET /api/conversations/{cid}/messages?cursor`时保持当前协议兼容，所有E2E包含刷新/跨会话/离线重连/运行中切换。

## 五、执行轨迹：模仿成熟Agent工作台的外部审计，不展示虚构隐藏CoT
主屏回复下面折叠`查看执行过程 (N步)`，展开显示节点状态、工具名、真实合法参数、返回摘要/原始授权数据、证据条款与页码、E0/E1审查状态、公开的决策理由与耗时。右侧高级Inspector显示SSE序号、Run ID、Claim、哈希、冲突，不要求业务用户先懂技术结构。**完整的公开执行轨迹**依靠已有`agent_events/tool_calls/claims/disagreements`数据库；内部私有模型隐藏链路不可声称读取/展示，代码运行/创建文件也只有在确实执行过对应工具时才展示。
只有出现实际执行轮次的LangGraph新事件才显示第1/2/3轮与回环；目前默认RULE_DEMO七节点一次顺序，不能凭UI虚构有“迭代三轮”。E0/E1仅溯源，不表示专业正确或人类审核通过。

## 六、R8-B分期实现（保证Codex可交付）
P0 **视觉和会话**：开源复用ThreadList/Composer，左固定侧栏+搜索+点击跳转+分组/重命名，单对话消息目录；不需要改数据库即可先做展示，但后端完整CRUD需要实际保存。
P1 **上传闭环**：前端选文件/拖拽→真正后台存盘+SQLite元数据→列表/预览→消息/运行绑定→刷新恢复/断线不丢。先实现TXT/MD/PDF，其他格式可以声明`stored_not_parsed`，仍要实现正确的文件持久化和安全白名单。
P2 **上下文和审计**：服务端Run输入快照、文件选择引用、历史消息分页、审计抽屉；真实跨会话不泄露和同Run SSE去重。
P3 **视觉精修+回归**：桌面1280/1440/1920、手机390、深色、20轮以上、长中文/Markdown表格、附件5个、上传失败与虚假MIME、拖放、历史点击跳转、断网/刷新、错误状态；保留React测试36/36 baseline并新增≥14个有效行为用例，所有新后端P8专属测试真实通过。

## 七、验收硬门槛与交付清单
- 不替换React/Vite/FastAPI/SQLite/LangGraph，不修改教师三个工具/原始标准或JSONL，保持R8A两条线完全隔离。控制依赖大小和版权归属。
- 务必真实展示：创建3个会话、每个≥3轮、sidebar点击切换、旧Run可按序恢复、单对话定位到第2/3轮、上传至少TXT和PDF并关联会话、刷新文件仍在、重复文件策略明确、下载受控、非白名单/超大/伪装类型拒绝、两会话附件互不可见、context展示不捏造模型记忆。
- 后端调试HTTP证据/SQLite行数及外键/文件哈希/安全错误码/截图必须同源可复现；真实Edge E2E`API全200`不应包含预期的4xx负向测试（负向拒绝要记录为正确的4xx），console 0 error，真实SSE event序列一致。
- 前端`Vitest≥50`（原36+≥14）、`npm run typecheck`、`npm run build`，后端原Python基线101中P7A旧断言失败不属于此窗口职责；只记录本窗口自身新增测试PASS，严禁为了归零删除/修改P7A旧测试与证据门禁。
- 记录`docs/audits/R8B_UI_FULL_ACCEPTANCE.md`：引入的OSS具体文件/版本/许可清单、修改目录、视觉截图（桌面+移动）、端到端HTTP/SSE/SQLite/文件存储证据、上下文真实状态、已知限制、内存/延迟与回滚办法。
- 还没做真实LLM、权限系统或文件多模态解析时直接标`BLOCKED/NOT_IMPLEMENTED`，不能用mock页面冒充后端实现。
