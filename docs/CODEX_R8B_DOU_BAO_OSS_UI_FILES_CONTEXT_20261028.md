# Codex Window B｜R8-B 豆包式简洁AI聊天UI｜OSS复用与真实上传上下文｜执行提示词
STATUS: READY_TO_SEND_TO_LOCAL_CODEX。与R8-A并行。**本窗口只可改`frontend/`、`backend/`中与文件上传/会话/只读Run快照有关的增量、`tests/test_r8b_*.py`及`docs/audits/R8B_*`。严禁修改`upstream/`任意文件，包括教师Excel/PDF、转换器、三工具和JSONL；不改`orchestration/`，不抢Window A任何源表。**

项目根目录：`D:\作业\竞赛\计算机设计智能体\机械智能体`

第一步阅读`AGENTS.md`、`docs/OWNER_R8B_DOU_BAO_STYLE_OSS_CHAT_UI_DESIGN_20261028.md`、`docs/audits/P7B_KNOWN_FACTS_UX.md`、`frontend/package.json`、`frontend/src/App.tsx`、`AssistantMessages.tsx`、`uiModel.ts`、`EngineeringReport.tsx`、`backend/api.py`、`backend/store.py`与现有端到端脚本。再检查现有npm依赖和开源仓库兼容性/许可证。

## 用户目标
把当前技术味较重的页面精修成**像豆包一样清爽、自然、有呼吸感的聊天网站**：左侧可折叠会话列表（新建、搜索、按时间分组、点击快速切换、当前高亮、重命名/归档）；同一会话内可点任一轮问题跳转；中间大面积聊天、Markdown、输入框固定底部；“+”菜单和拖放/粘贴真实文件上传；上下文能够可靠存入SQLite并显示当前会话/运行绑定的事实与文件；右侧执行时间线/证据默认折叠，只有用户需要才打开。视觉优先简洁，可读，桌面和手机都自然。

## 强制OSS复用
优先直接利用当前`@assistant-ui/react`及其ThreadList/Composer/AttachmentAdapter，与既有external store runtime对接；参照`https://github.com/langchain-ai/agent-chat-ui`对LangGraph流式事件、右侧artifact的设计；参考`https://github.com/vercel/chatbot`会话布局和`https://github.com/open-webui/open-webui`附件管理交互。可依法复用兼容许可的明确组件、样式模式并附licenses/source commit，不复制品牌Logo/闭源UI资产。不得为做页面而迁移Next.js/Postgres、替换FastAPI/SQLite或增加另一套大型运行框架。

## 三个必须完成的真实功能
(1) **对话列表与会话内跳转**：现有API GET/POST conversations、listRuns、replay事件必须继续工作；在任何一个会话的第2/3/10条用户消息点击右侧/侧栏目录即可滚动定位对应消息。会话切换/刷新恢复真实SQLite记录，无串线、无重复Run启动；多轮上下文来源清晰，不允许从另一个Run/当前最后一条消息猜历史事实。
(2) **文件上传闭环**：创建真实FastAPI multipart upload + SQLite文件关联表 + 本地安全存储，白名单txt/md/pdf/docx/csv/xlsx/图片，单文件默认≤15MiB、每次≤5，服务端流式限额/扩展名MIME检测/SHA/安全路径/失败清理；如DOCX、图片、XLSX内容提取未做，允许合法保存但必须显示stored_not_parsed。至少TXT+PDF要完成真实可验证的只读预览/文件引用。**现后端请求体限制128KiB，上传路径需专门隔离限制，不得放宽全部API**。上传不自动传第三方、不自动覆盖RBI原表、不自动成为官方条款证据；上传附件与conversations/messages/runs绑定并在刷新后重新呈现。
(3) **上下文管理**：利用服务端已存的Run.question/context_json建立只读可信Run输入快照，明确本轮工况、已选文件、历史消息范围；保存消息与附件引用的真实持久数据。当前`RULE_DEMO`不是LLM记忆，不能让前端假装模型理解全部历史；为未来API接入预留合法的context assembly边界和token budget，不在本任务触碰真实密钥。

## 安全与设计硬约束
保持`APP_ENV=production`无认证fail-closed以及loopback-only；上传与检索只在本地，不能暴露生产文件绝对路径，不允许把带prompt injection的文档文本当作系统指令。文件名净化，路径遍历/伪装MIME/超大/拒绝文件/并发上传/失败恢复/跨会话读越权均要做实际负向测试。文件不进入正式标准数据库；教师原三工具签名及五键合同冻结。
报告与思维链UI仅显示**真实执行过程**：官方三工具调用/参数/授权返回、实际Agent节点、每轮公开决策摘要、真实来源和E0/E1审查、SSE回放；不捏造hidden-CoT、虚构代码写入或虚构重复调查循环。模型仍是RULE_DEMO必须显著标识。为未来多轮LangGraph loop预留显示接口但当前不可假装已启用。

## 验收与交付
前端保留原36项通过，新增≥14条行为/安全测试；Vitest≥50、TS类型检查和Vite生产构建通过。后端新增P8B/upload专属测试（文件真实保存/数据库外键与元数据/拒绝异常/多会话隔离），全部PASS；完整Python现有P7A已知1项旧first-wins冲突属于别的Owner收口，不能越界修改/删除旧测试。真实Edge→FastAPI→SQLite/SSE E2E必须演示3会话×3轮、会话点击跳转、单会话第2/3轮定位、2个文件上传+保存/预览、刷新文件仍在、对应附件关联、不同会话无数据串线、超限与伪MIME正确4xx、移动390/桌面1280/1440/深色、console errors=0。截图必须来自真实浏览器而非伪静态。
交付`docs/audits/R8B_UI_FULL_ACCEPTANCE.md`、`R8B_OPEN_SOURCE_PROVENANCE.md`、Edge端到端JSON/真实截图和新增API/schema简表，报告所有BLOCKED与目前不能称为模型记忆的能力。最终停在`READY_FOR_OWNER_REVIEW`，不部署、不提交、不改老师资料。
