# P4-C UI Evidence — READY_FOR_OWNER_REVIEW

日期：2026-10-28  
状态：**READY_FOR_OWNER_REVIEW**（未部署、未提交 Git）

## 变更范围

仅修改 `frontend/` 与本审计目录内的 `P4C_*` 证据。未修改 backend、orchestration、教师工具、RBI Excel、PDF 或共享项目状态文件。

- `frontend/src/App.tsx`：会话/详情请求使用 AbortController 与 epoch 防止过期响应污染当前界面；运行状态按会话隔离；运行事件序列去重持久化；专注聊天开关；基于事件的 Agent 状态与边；claim 聚合/详情；本地运行历史和 API 历史运行列表。
- `frontend/src/api.ts`：详情和 replay 接受 abort signal；新增全页分页读取 `GET /api/conversations/{id}/runs`，保留 localStorage 作为本地后备。
- `frontend/src/uiModel.ts`、`AgentFlow.tsx`：纯事件模型；边只由相邻观测到的 `agent_started` 事件生成，计划节点未运行时为 pending，run 结束后未运行节点为 skipped，failed 与 completed 区分。
- `frontend/src/styles.css`：桌面专注聊天/可折叠 Inspector、窄屏 drawer、移动端历史抽屉、中文长文本/表格/代码换行及深色对比度。
- `frontend/src/App.behavior.test.tsx`、`frontend/src/uiModel.test.ts`：新增 8 条真实 DOM 行为测试和 9 条观测模型测试。
- `frontend/scripts/start_p4c_edge.ps1`、`frontend/scripts/p4c_edge_e2e.mjs`：本机 Edge CDP 真浏览器验收脚本，连接实际 FastAPI + SQLite + SSE 服务。

## 命令与结果

在 `frontend/` 执行：

```powershell
node ./node_modules/vitest/vitest.mjs run --reporter=dot
```

结果：**4 个测试文件通过，24/24 tests passed**。

```powershell
node ./node_modules/typescript/bin/tsc -b --pretty false
```

结果：**PASS**。

```powershell
node ./node_modules/vite/bin/vite.js build
```

结果：**PASS**，Vite 8.3.5 转换 3102 modules 并生成 production bundle。

```powershell
node ./scripts/p4c_edge_e2e.mjs
```

结果：**PASS（实际 Edge、真实 FastAPI/SQLite/SSE，不是 mock E2E）**。CDP 检查 1280×900 初始聊天宽 750px、页面宽度无横向溢出（`bodyScrollWidth=1280`）；创建会话并执行一次运行，SSE 收到并持久化 16 个事件，末事件 `run_completed`；`after_sequence=5` replay 返回剩余 11 个事件；刷新页面从运行事件存储恢复 16 条 timeline 事件；`GET /api/conversations/{id}/runs` 实际返回 200 并显示运行历史。浏览器 console messages/errors 均为 0。桌面 1440×960、移动 390×844、切换深色、874 字符中文输入均已由 CDP 实际交互并截图。

API E2E 记录：`P4C_EDGE_E2E.json`，其中请求状态码、run ID、事件类型、重放计数、恢复计数和浏览器控制台结果均为脚本采集的实际值。最近一次 run ID：`7cb649d1-c833-46fb-9bd4-55615e79ce32`。

## 行为测试覆盖

1. 首条 SQLite 会话加载并传递 AbortSignal。
2. 从历史切换会话。
3. 搜索过滤历史会话。
4. 专注聊天折叠与无障碍按钮恢复 Inspector。
5. 移动端历史抽屉开/关。
6. starter prompt 仅填入编辑器而不自动发送。
7. 工况上下文表单展开、编辑、收起。
8. 深色模式切换并持久化。
9. 明示本地运行索引不跨设备恢复。
10. Agent 未运行/启动/完成/失败/跳过状态推导。
11. 图边按实际相邻 `agent_started` 事件建立，忽略乱序及中间非启动事件。
12. 按 `claim_id` 合并；保留完整 claim 历史，最新事件决定当前状态。
13. `requires_human_review` 独立显示人工复核状态。
14. local run ID 去重并按最近记录排序。

## 实际截图

- `P4C_WELCOME_1280.png`：欢迎态。
- `P4C_DESKTOP_1280.png`：1280 桌面、真实 SSE 执行图和时间线。
- `P4C_DESKTOP_1440.png`：1440 桌面布局。
- `P4C_MOBILE_390.png`：390px 移动端布局。
- `P4C_DARK_MODE_1280.png`：深色主题。
- `P4C_LONG_CHINESE_INPUT.png`：874 字中文输入换行。

截图均由本机 Edge CDP `Page.captureScreenshot` 采集。当前图中连线只表达已观察到的运行跳转；空白/未执行节点显示等待或 skipped，不绘制“计划边”，避免把设计路径冒充运行事实。调试 JSON 默认折叠，claim 卡展示结构化字段；历史 SSE 事件继续保留在 timeline。

## 失败、边界与后续

- 本 P4-C 前端测试、typecheck、production build 与真实浏览器 E2E 均通过。
- 上游协作窗口报告的全仓 Python 测试状态是 **80/81 通过，1 项 P3B 旧断言失败**：旧断言期待 E1，而 P4B 的新安全门禁使用 E0。此为 P4B/P3B 语义兼容问题，不属于 P4-C 修改范围；P4-C 未改后端或该测试。
- localStorage 运行历史仅为本机后备，UI 明示不跨设备；服务端接口用于 SQLite 持久化历史。API 分页当前按服务返回分页大小循环读取。
- 本轮 E2E 覆盖单次 run 的实时 SSE、序列重放、刷新恢复、会话列表与历史运行读取；没有声称覆盖跨设备身份/权限、多浏览器并发或生产部署。
- E2E 的运行记录来自服务端 SQLite；每次运行生成隔离 SQLite 数据库。测试 Edge profile 使用 `%TEMP%`，不复用用户浏览器 profile。

## 停止状态

**READY_FOR_OWNER_REVIEW**。未部署、未 `git add`、未提交。等待 Owner 检查截图、P4C diff 和 P4B/P3B 兼容问题处理方案。
