# Codex P3-A｜React视觉产品纵切｜严格只改前端（2026-10-28）
状态：任务书已审核但**未自动启动**；用户明确要求借鉴成熟OSS做漂亮的多Agent聊天网站。另一个执行者负责数据和后端，不允许两个窗口并发写同一文件。

## 基线
本地根目录：`D:\作业\竞赛\计算机设计智能体\机械智能体`，先读`AGENTS.md`、`docs/PROJECT_STATE.md`、`docs/audits/P2_RBI1_LANGGRAPH_EVIDENCE.md`，然后`backend/api.py`、`backend/store.py`、`web/index.html`。P2官方三Tool不变；P2 StateGraph规则节点、45tests PASS。后端最小API：
- `GET /api/health`；
- `POST/GET /api/conversations`；
- `GET /api/conversations/{cid}`（消息历史）；
- `POST /api/conversations/{cid}/runs`返回`events_url/run_id`；
- `GET /api/runs/{rid}/stream`文本事件SSE（单行data JSON，含kind, agent, payload, sequence）；
- `GET /api/runs/{rid}/events?after_sequence=...`重放事件。
先实测当前JSON结构，再写Typed TS适配器；不要猜返回字段。客户端要按`run_id+sequence`去重；断连重试不触发重复执行。

## 允许写入区域
只在**全新**`frontend/`下面创建Vite+React+TypeScript应用及其测试、依赖锁；相关文件放`docs/audits/P3A_FRONTEND_*.md`。**不改**`upstream/`、`backend/`、`orchestration/`、`tests/`和已有`web/index.html`，避免与P3B和Owner XLSX并发冲突。前端开发服务器Vite代理`/api`到127.0.0.1:8000，故后端当前无需CORS/API修改。

## OSS 复用与UI决策
- 必选`assistant-ui` TypeScript/React聊天框架（MIT，`https://github.com/assistant-ui/assistant-ui`）；基于其Thread、Message、Composer、ThreadList组件做非套路风格聊天界面；如果它的runtime难以对接自定义FastAPI SSE，先建立自定义Runtime适配而非换掉后端。禁止为了赶进度宣称静态mock已经对接实际后端。
- 必选`shadcn/ui`基础组件（官方 Vite 文档 `https://ui.shadcn.com/docs/installation/vite`），结合Tailwind主题变量；仅使用开源免费组件。
- 选`@xyflow/react`（MIT，`https://github.com/xyflow/xyflow`）渲染**观测型**Agent执行图；图的连线/节点状态来自真实事件，不允许画始终绿色PASS的静态演出。早期可先在右侧时间线基础上做可折叠图，避免一次性把所有功能堆在首页。
- AG-UI/CopilotKit **不在本轮再加入另一套重型runtime**；当前自定义SSE保持协议兼容的Adapter结构，未来需求证明确有价值再迁。

## 核心页面体验（高级、克制、舒适）
桌面三栏：左侧280px会话目录（新对话、历史搜索、案例快捷入口）；中央弹性聊天区（800~1000px最佳读宽、Markdown/引用卡、附件占位禁上传未经批准PDF、Composer固定底部）；右侧340px折叠式Evidence Inspector（Agent timeline、真实tool call、引用标准/条款/印刷页、反证冲突与待补问）。窄屏改抽屉/Tab，保证手机使用。
视觉：高级研究工作台风格而非学生Demo：微暖背景+深石板文本，深色模式；强调色低饱和靛蓝，source证据用轻青绿，未审核/待补用琥珀，仅失败用红；8px间距系、12~16px卡片圆角、细边和微阴影、优雅动效（200ms）、骨架屏、键盘焦点状态、中文排版。
输出每次run要清楚标`RULE_DEMO`或真实LLM模式；在右侧显示six roles的`started/completed/skipped`状态、确实返回的tool调用与耗时(若有)，E0/E1/E2/E3证据等级。用户点击结果引用能打开“标准文档/条款”抽屉；原PDF不允许未授权上传或暴露到公网。
消息操作：复制、重试（应创建新run，不是原run再次消费）、展开出处、折叠工具轨迹、历史恢复；同一run SSE断连自动走`events?after_sequence`保证event单调且去重。
产品仅是辅助研判：不能显示安全认证、绝对risk或无证据检验周期。

## Gate
- `npm ci` / `npm run build` / `npm run typecheck` / UI组件测试必须真实通过，锁文件提交进新`frontend/`但不要git add；
- 真实FastAPI→前端创建会话→消息→EventSource/SSE→右栏trace→刷新历史持久→重放 去重E2E；截图桌面1280和移动390（能用本机浏览器才宣称截图，不能拍就BLOCKED）；
- 假数据固定独立fixture且页面显著`SIMULATION`；真实演示使用现有RULE_DEMO标识；
- 测试标准引用/证据等级、工具源失败与缺工况、网络超时和响应式；
- 产物`docs/audits/P3A_FRONTEND_ACCEPTANCE.md`含实际命令/耗时/截图路径/待做，Stop at READY_FOR_OWNER_REVIEW.
