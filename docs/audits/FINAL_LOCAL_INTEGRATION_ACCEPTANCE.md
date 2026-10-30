# 最终本地集成验收

**结论：READY_FOR_OWNER_REVIEW**（本地演示 Gate 已完成；不部署、不提交、不删除或移动历史文件）。

日期：2026-10-28。范围仅为整合已有 R9-A 有界 LangGraph、R8-B React 聊天 UI、R9-B ActivityTrace 与现有 FastAPI / SQLite / SSE；未建设第二套 Graph、后台任务框架或观测平台。

## 1. 当前唯一运行闭环

```text
frontend/dist (React) → FastAPI → R9-A LangGraph (RULE_DEMO)
    → 老师固定三个工具 → SQLite (run/message/claim/event/file) → SSE replay → 助手消息折叠执行过程
```

- `backend/api.py` 的正式 worker 使用 `IndustrialCandidate`；Graph 的真实阶段/工具事件走既有 SQLite EventSink 和 SSE，tool budget / investigation / review retry 均有界。
- 对 Graph 的真实 hypotheses 与 reviewer findings 做轻量适配后写进现有 claims 表和事件；只在 Graph 明确标记冲突时写 disagreement，不为满足测试制造反证。消息写入时带 `run_id`，刷新按 SQLite run/events 恢复。
- `frontend/src/AssistantMessages.tsx` 把 R9-B `ActivityTrace` 放在对应 assistant turn 内，默认折叠；来源与审查结果来自该 run 的持久化事件。没有事件时不造记录；不展示模型隐藏思维链。
- 老师工具合同仍恰好是 `damage_mechanism_query`、`rbi_lookup`、`standard_clause_search`；五键结果协议未动。`risk_level` 全程保持 `null`。
- 运行模式清楚标为 `RULE_DEMO`，**未配置/验证真实模型 API；REAL_LLM = BLOCKED（本地演示完成不等于真实 LLM 验收）**。

## 2. 本轮变更文件

实现：

- `backend/api.py`、`backend/store.py`
- `orchestration/r9_industrial_candidate.py`
- `frontend/src/App.tsx`、`frontend/src/api.ts`、`frontend/src/AssistantMessages.tsx`、`frontend/src/components/trace/ActivityTrace.tsx`
- `tests/test_api_vertical_slice.py`、`tests/test_r9a_industrial_candidate.py`、`tests/test_p6a_parallel_evidence.py`、`tests/test_r9b_observability.py`、`tests/test_p3b_evidence_audit.py`、`tests/test_p4a_api_safety.py`、`frontend/src/AssistantMessages.final.test.tsx`

文档与证据：

- `README.md`、`docs/ARCHITECTURE.md`、`docs/PROJECT_STATE.md`、`docs/PROJECT_STATUS_CURRENT.md`、`docs/LEARNING_ENTRY.md`
- 本文件；Edge 截图 `FINAL_LOCAL_DESKTOP_1280.png` 和 `FINAL_LOCAL_MOBILE_390.png`

本轮未向 `upstream/` 的工具、Excel、PDF、正式 JSONL 写入；没有执行 convert 写盘；没有改其他项目；没有提交、部署、删除或移动文件。E2E SQLite 和上传文件使用 `%TEMP%` 临时目录，不写入项目 `data/`。

## 3. 自动化回归结果

| 命令 | 结果 |
|---|---|
| `npm run typecheck --prefix frontend` | PASS |
| `npm test -- --run`（在 `frontend/`） | **74/74 PASS**（含 2 个最终 assistant-turn/run-scope 集成行为测试） |
| `npm run build --prefix frontend` | PASS；Vite 仅提示一个 575.21 kB 的主 JS chunk 可继续拆分，不影响构建/运行 |
| `\.venv-langgraph\Scripts\python.exe -B -m unittest discover -s tests -q` | **134 tests PASS**；3 项仅依赖可选 Phoenix/OpenInference SDK 的专项在基础环境精确 skip |
| `observability/.venv/Scripts/python.exe -B -m unittest tests.test_r9b_observability -q` | **6/6 PASS**（Phoenix 独立环境真实执行） |
| `python -B upstream/04_接口文档/validate.py --final` | **PASS**：clauses 554/554、trajectories 200/200；DM 82、RBI 472、多步 144、三类特殊轨迹各 15 |
| `python -B upstream/05_提交区/_selftest_tools.py` | **17/17 PASS** |

修复/断言对齐：

- 整体验收初跑中，旧测试有 3 个失败：P3B 仍要求旧 Claim 事件，P4A 仍期待已被短 Graph 替换的 `decision_summary` 和旧 `run(state, emit)` 假 Graph 接口。正式路径保留 Claim/Disagreement 查询：Graph 的真实 hypotheses / review rows 现在写入原 SQLite ledger；测试改为核对真实审查与“无实际冲突就无 disagreement”。空工况测试改核对实际 `phase_started` 路由摘要；并发测试使用当前 Graph worker 签名。改后主套件 134/134 通过。
- P6A 过时断言从 E1 改为保守 E0，并核验冲突 payload 保留；未放宽 P7A 合并算法。
- Phoenix SDK 测试只在模块确实不可用时跳过；未捕获或吞掉测试异常。基础环境 3 skip、隔离环境 6 PASS。
- 构建的 chunk-size warning 已保留为非阻塞信息，未通过改低阈值隐藏。

## 4. 真实 Edge + FastAPI + LangGraph + SQLite + SSE E2E

实际启动 Microsoft Edge **142.0.3595.53**（本机二进制、CDP 自动交互）访问 `http://127.0.0.1:8000/`；该 URL 返回生产 React build，由同一 FastAPI 提供 API 和静态资源。环境变量将数据库与附件目录指向 `%TEMP%`。没有连接 Phoenix 服务或第三方模型 API。

本地服务和浏览器执行入口：

```powershell
$env:DATABASE_URL='sqlite:///C:/Users/37813/AppData/Local/Temp/final-local-integration-v3.sqlite3'
$env:UPLOAD_ROOT='C:/Users/37813/AppData/Local/Temp/final-local-integration-uploads-v3'
\.venv-langgraph\Scripts\python.exe -m uvicorn backend.api:app --host 127.0.0.1 --port 8000
& 'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe' --headless=new --disable-gpu --no-first-run --remote-debugging-port=9222 --user-data-dir='C:\Users\37813\AppData\Local\Temp\haeness2-edge-final' http://127.0.0.1:8000/
node "$env:TEMP\edge_final_e2e.mjs"
```

延迟批次通过 `urllib.request` POST `/api/conversations`、POST `/api/conversations/{id}/runs`、消费 `/api/runs/{id}/stream` 到 `run_completed`，再 GET replay/events、conversation/messages 和 claims；3 组各循环 5 次并在脚本内断言 run_id、sequence、assistant cardinality、tool/review 和 null risk_level。脚本只在 `%TEMP%` 短期保存，不作为产品代码提交。

桌面 UI 按序完成：

1. 新建会话，问题“分析设备风险”：回答要求补材质/介质，0 工具调用，执行记录为 2 步。
2. 同一会话提问 `GB/T 26610.3-2014 风险等级的确定 标准条款`：未填写材质仍执行单次 `standard_clause_search`，出现 1 次检索/来源追踪。
3. 经 UI 填设备、设备类型、碳钢、湿硫化氢、温压与现场 pH/H2S/测厚；通过 UI 文件选择器将本地 TXT 上传到 FastAPI，文件在 SQLite + 本地存储记录并绑定本次 run；再发起机理问题。观察到 `damage_mechanism_query` 与 `standard_clause_search`，Auditor/Skeptic 分支并行，持久化审查与 5 项候选；无风险等级。
4. 打开最新助手消息的折叠执行记录，真实渲染 `review_started`、两条 `agent_completed`、`review_result`、来源卡及 claim review；刷新页面后历史消息、附件和 3 个 run 的 trace 恢复。最新 ActivityTrace 的 `run_id` 与 SQLite 消息关联。
5. 手机 viewport 390×844：`scrollWidth=390`、横向溢出 false；`RULE_DEMO` 和聊天/审查 UI 可见。Edge console errors = 0。

截图是本机 Edge 页面截图（PNG）：

- 桌面 1280×900：[`FINAL_LOCAL_DESKTOP_1280.png`](FINAL_LOCAL_DESKTOP_1280.png)
- 手机 390×844：[`FINAL_LOCAL_MOBILE_390.png`](FINAL_LOCAL_MOBILE_390.png)

## 5. API/SSE 本地延迟与 SQLite 证据

通过真实运行的本地 Uvicorn/HTTP API 测量每场景 5 次，计时从创建 Run 的 HTTP POST 到消费完整 SSE terminal event；包含 SQLite、worker、规则工具及本地检索，不包含 LLM 或公网网络。P95 使用 n=5 最近秩样本，即该组最大值。

| 场景 | P50 / P95 (ms) | 真实调用/审查证据 |
|---|---:|---|
| 缺工况 | 158.97 / 172.72 | 0 tool；2 events；needs-user-input |
| 纯标准检索 | 329.83 / 378.99 | 1× `standard_clause_search`；8 events；不需要材质 |
| 湿硫化氢机理调查 | 1019.44 / 1489.70 | `damage_mechanism_query` + `standard_clause_search`；30 events；`parallel_review=true`；5 个待人工复核 claim |

SQLite 取证库：`%TEMP%\final-local-integration-v3.sqlite3`。回归 HTTP 样本及 UI 会话合计：4 conversations、18 completed runs、36 messages、240 events、1 conversation file + 1 run attachment、30 claims、0 disagreements。校验器逐个 run 检查：状态 completed、每个 run 恰好 1 条 assistant 回复、event sequence 从 1 连续递增、event `run_id` 与请求匹配、终端 `risk_level` 全为 null，**18 个 run 零异常**。附件 extraction status 为 `text_preview`；上传仅作 UI/存储验证，不因此进入教师标准数据。

## 6. 文件边界与需要 Owner 处理的既有状态

- 本轮正式数据只读检查通过，未调用 `convert.py`，未操作 PDF/Excel。`upstream/` 当前 HEAD 为 `d7877bf387482b2fa9b148d30860da59ccad48b3`。
- 终态 `git -C upstream status --short` 显示 `01_RBI标准/条款摘录表_RBI.xlsx` 为 modified，另有 `RBI_GBT26610_1_13candidates_for_review.xlsx` 和 `.bak_owner_before_rbi1_20261028` 未跟踪。此任务执行的验收命令只读 `validate.py --final`、JSONL 与工具自测，没有对这些 Excel 路径写入；由于本任务未在开工时记录 XLSX 哈希/初始 status，**不能据当前证据断言这些 dirty 文件来自哪个更早窗口**。没有擅自回滚或覆盖，需 Owner 独立审计其归属和签核状态。
- 官方数据终验 554/200 仅证明当前正式 JSONL 符合教师 validator；不表示 R8A 13 条未签名 RBI 摘录已签核、不表示 461 页 PDF 已完成人工视觉复核。
- REAL_LLM、真实抽取人/独立复核人签核、RBI 正式补录、公网部署和教师侧真人验收均不是本地演示 Gate 的通过项。

## 7. 收工 Gate 与状态

启动说明已写入根 `README.md`：先构建 React，再通过唯一 FastAPI root 进入聊天；包含缺工况、纯标准检索、明确工况、文件上传、折叠 trace 和刷新恢复。当前回归、API/SSE、DB、Edge 桌面/手机和教师只读验收均已执行。达到任务书本地收工 Gate，停止新增功能，状态 **READY_FOR_OWNER_REVIEW**。
