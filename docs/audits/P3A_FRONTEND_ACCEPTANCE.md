# P3-A React 前端纵切验收记录

- 日期：2026-10-28（Asia/Shanghai）
- 状态：**READY_FOR_OWNER_REVIEW**（未提交）
- 写入边界：仅新增 `frontend/` 与本审计文件；未改 FastAPI、orchestration、root tests、教师工具/原始资料或 `web/index.html`。
- 验收环境：Windows 11，本机 Edge（Playwright channel `msedge`）、Node 24.11.1 / npm 11.6.2，后端使用项目隔离环境 `.venv-langgraph`。

## 实现摘要

- 新建 Vite + React + TypeScript 应用，Vite `/api` 代理到 `127.0.0.1:8000`；前端保留 FastAPI 返回字段，现有 SSE `type` 与未来增量 `kind` 均可识别，未识别事件仍进入时间线。
- 使用 assistant-ui `ExternalStoreRuntime` 适配持久化消息，配合 Markdown/GFM 消息展示、自定义输入、历史会话、搜索、复制事件详情、重试新 run、深浅主题和窄屏历史/对话/审查 Tab。
- shadcn/ui 风格的 Button/Badge 基础组件与 Tailwind CSS 4 主题变量；React Flow 节点/边状态由当前实际 Agent 事件派生。遵循 React Flow OSS attribution，不隐藏其署名。
- 右侧审查区消费真实 SSE 事件、工具调用/返回、引用、claim/review/contradiction 等事件族；未知事件也可点开原始 payload。按 conversation 在 `localStorage` 保存最近一次 `run_id`，回访时 GET `/events?after_sequence=0` 恢复事件时间线，序号以 `run_id + sequence` 去重。
- 工况表单不预填设备事实；材质、介质、温压/年限、现场证据均由操作者显式提供。只展示 `RULE_DEMO` 与服务实际返回的证据等级、来源和人工复核字段，不臆造风险等级或认证结论。

## 真实 API/SSE 证据

隔离运行命令：

```powershell
$env:DATABASE_URL='sqlite:///D:/作业/竞赛/计算机设计智能体/机械智能体/frontend/.p3a-e2e.sqlite'
.venv-langgraph\Scripts\python.exe -m uvicorn backend.api:app --host 127.0.0.1 --port 8000
# 另一终端
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

`GET /api/health` 实际返回 HTTP 200，`mode=RULE_DEMO`、SQLite 位于 `frontend/.p3a-e2e.sqlite`，三项教师工具名称保持原样：`damage_mechanism_query`、`rbi_lookup`、`standard_clause_search`。

浏览器 E2E 使用本地 Playwright Python + Edge，真实经前端 UI 创建会话、填写设备/工况、发送文本、POST `/api/conversations/{id}/runs`、GET SSE stream；不是 mock。实际结果：

- SSE 请求 HTTP 200，收到 **34** 个带序号事件；右侧时间线展示 34 条，证据区域展示 5 张真实 `reference_added` 来源卡片；浏览器 pageerror = 0、UI alert = 0。
- 助手回复来自 SQLite/FastAPI 的 `RULE_DEMO` 执行；原文报告候选机理未返回，明确显示待补现场信息与 E1/E2/E3 边界，不标风险等级。
- 刷新后历史目录 **9** 个会话条目，选中会话恢复 **2** 条消息和 **34** 条持久化事件（经 `/api/runs/{id}/events?after_sequence=0` 回放）。
- Edge 实拍截图：`frontend/evidence/p3a-e2e-desktop.png`（1280×900）和 `frontend/evidence/p3a-e2e-mobile.png`（390×844）。截图生成前等待页面与响应式过渡稳定。

另外直接用 Python requests 核验 API payload：

```text
POST /api/conversations                 -> 200 {id,title,created_at,updated_at}
POST /api/conversations/{id}/runs       -> 200 {run_id,status,mode,events_url}
GET /api/runs/{run_id}/stream           -> 200 text/event-stream; charset=utf-8
SSE data JSON                           -> schema_version,event_id,run_id,session_id,sequence,ts,type,agent,payload
GET /api/conversations/{id}             -> persisted messages
GET /api/runs/{run_id}/events?after_sequence=0 -> persisted event replay
```

## 命令与测试输出

最终使用隔离 npm cache `"$env:TEMP\npm-cache-p3a-final"` 避开本机并行 npm cache 冲突：

```powershell
npm ci --cache "$env:TEMP\npm-cache-p3a-final" --registry=https://registry.npmjs.org
# added 335 packages; audited 336 packages; found 0 vulnerabilities

npm test -- --reporter=dot
# Test Files 2 passed (2); Tests 6 passed (6)

npm run typecheck
# tsc -b --pretty false; exit 0

npm run build
# Vite 8.3.5 production build succeeded
# index 278.22 kB / 88.66 kB gzip; AgentFlow split chunk 177.96 kB / 57.35 kB gzip;
# AssistantMessages split chunk 485.81 kB / 142.67 kB gzip

npm audit --registry=https://registry.npmjs.org
# found 0 vulnerabilities
```

单元/组件测试覆盖：未知增量事件与 `type`/`kind` 兼容、真实 SSE data 解析、run_id/sequence 去重、断流后 replay-after-sequence 且不重复 POST run、`RULE_DEMO` / 无证据不推断风险、深浅主题和显式工况字段。

## 文件清单 / diff 摘要

新增：

```text
frontend/index.html
frontend/package.json
frontend/package-lock.json
frontend/vite.config.ts
frontend/tsconfig.json
frontend/tsconfig.app.json
frontend/tsconfig.node.json
frontend/components.json
frontend/src/main.tsx
frontend/src/App.tsx
frontend/src/AgentFlow.tsx
frontend/src/AssistantMessages.tsx
frontend/src/api.ts
frontend/src/styles.css
frontend/src/vite-env.d.ts
frontend/src/lib/utils.ts
frontend/src/components/ui/button.tsx
frontend/src/components/ui/badge.tsx
frontend/src/api.test.ts
frontend/src/App.test.tsx
frontend/src/test/setup.ts
frontend/evidence/p3a-e2e-desktop.png
frontend/evidence/p3a-e2e-mobile.png
docs/audits/P3A_FRONTEND_ACCEPTANCE.md
```

`frontend/src/api.ts` 是只读核对后新增的 typed UI adapter；保持 API path、teacher tools 与 SSE 协议不变。构建产物 `frontend/dist/` 不作为交付源文件；E2E 临时 SQLite `.p3a-e2e.sqlite` 在停止后端后已删除，未残留测试会话数据库。

## 失败与修复记录

1. `npm create vite@latest frontend -- --template react-ts` 在 Windows scaffold 拷贝 favicon 时失败（`copyfile UNKNOWN`）；保留已有目录状态，手工补齐 Vite/React/TS 文件，没有覆盖项目其他文件。
2. 本机全局 npm cache 在并行环境下出现 `EEXIST/UNKNOWN copyfile`；改用 `$env:TEMP\npm-cache-p3a-final` 和 npm 官方 registry 后 `npm ci` 成功。一次 `npm ci` 在 Vite dev server 持有 `lightningcss` native module 时触发 EPERM；停止 Vite 后干净重试成功。
3. React Flow 单测环境缺少 `ResizeObserver` mock、测试选择器命中桌面与移动两份主题/工况按钮；加入测试专用 ResizeObserver 和精确选择器后 6 项全绿。
4. 初轮 E2E 发现会话 reload 刷新 detail 时误清空本次 SSE 时间线；修正为保存 last-run id 并经服务端 replay 恢复，最终刷新后 34/34 事件还原。
5. Playwright browser extension 的 `browser_navigate` 在约 90 秒内没有返回，已停止该调用；改用本机 Playwright Python + 已安装 Microsoft Edge 完成同一页面真实操作与截图，不以静态 mock 替代。
6. 构建结束仍报告 Assistant UI 主 chunk 约 764 kB；将 AgentFlow 与 assistant-ui/Markdown 渲染拆为 lazy chunks 后，初始 bundle 降至 278 kB、Flow 178 kB、assistant 486 kB，Vite 不再输出 chunk 警告。

剩余边界：历史 API 没有提供“列出会话所有 run”的接口，UI 因此只恢复浏览器 `localStorage` 记住的该会话最近一次 run 时间线；跨设备/清浏览器存储后仍可恢复 SQLite 消息，事件需持有对应 run_id 才能回放。历史运行事件全量索引可由后端未来增加兼容接口处理，本轮不改后端。

**停止点：READY_FOR_OWNER_REVIEW。未 git add、未提交。**
