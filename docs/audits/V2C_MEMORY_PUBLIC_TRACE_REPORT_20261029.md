# Aetheris V2 S1-C 验收记录（2026-10-29）

状态：`READY_FOR_OWNER_REVIEW`（功能专项通过；全项目回归有既存/范围外失败，故不标记全量 PASS）

## 1. 范围与边界

本轮按 `docs/CODEX_V2_S1_C_MEMORY_UI_20261029.md` 实施，仅修改：

- `backend/store.py`
- `backend/conversation_memory.py`（新增）
- `frontend/src/components/trace/ActivityTrace.tsx`
- `frontend/src/trace-events/model.ts`
- `tests/test_v2c_conversation_memory.py`（新增）
- `frontend/src/components/trace/ActivityTrace.test.tsx`
- `frontend/src/trace-events/model.test.ts`
- 本报告

未修改 `backend/api.py`、`backend/deepseek.py`、`orchestration/`、`upstream/`、教师三个工具、正式数据、真实数据库、密钥、部署配置。没有把 `ConversationMemoryService` 接入 Graph/API；这是 S2/API 与 Graph 所有者的后续接线工作。

启动前读取本轮指定的 `AGENTS.md`、`docs/PROJECT_STATUS_CURRENT.md`、`docs/AETHER_V2_REQUIREMENTS_ARCHITECTURE_20261029.md`、`docs/AETHER_V2_MODEL_POLICY_GUARDRAILS_20261029.md`、S1-C 任务书与 P13 聊天回放/附件隔离验收记录。项目状态文件是中心状态文件，且不在本轮独占写入清单，因此本轮不改；请 Owner/A 将本报告状态并入该中心状态。

## 2. SQLite 会话级记忆实现

### Schema 与迁移

`backend/store.py` 在既有单一 SQLite WAL 数据库中以可重复 `CREATE TABLE/INDEX/TRIGGER IF NOT EXISTS` 增加 schema version 1：

- `conversation_memory_schema`：记忆 schema 版本。
- `conversation_memories`：按 `(conversation_id, memory_version)` 存储摘要、父版本、覆盖消息边界、source message IDs、source hash、生成类型、模型标识、状态及错误码。
- `conversation_fact_assertions`：按 conversation 保存事实断言、字段/值/单位/对象、来源消息、provenance、确认状态及 superseded 链。
- 同会话来源触发器拒绝外会话消息；已确认事实必须来源于同会话 `user` 消息。逻辑隔离是 SQLite `conversation_id` 命名空间，不是新建每会话数据库。

迁移不回写原始消息正文。专项测试在临时 SQLite 中模拟旧 schema（删除新增表/触发器后 reopen），确认 message ID 与原文仍保留、schema 可重建、数据库处于 WAL。未打开真实 DB；没有对真实 DB 或正式数据做读写。

### `ConversationMemoryService`

接口：

- `get_recent_visible_history(cid, max_turns, max_chars)`：只取同会话 user/assistant 可见消息，最多 12 轮并受字符预算限制。
- `get_confirmed_facts(cid)`：只返回当前 confirmed 状态；candidate、superseded 不进入确认上下文。
- `record_user_confirmed_fact(...)`：仅显式用户消息/结构化确认可产生 confirmed 事实；同字段/对象的新确认把旧值标记 superseded 并保留审计行。
- `record_candidate_fact(...)`：模型/助手候选保留 candidate 状态，不能升级事实。
- `propose_summary_if_needed(...)`：模型默认关闭；仅显式 `allow_model=True` 且注入 provider 才执行，无网络客户端/自动付费调用。敏感轮次/带附件消息在未授权时不送摘要 provider。摘要失败、无效 schema、超长均记录失败版本并回退有限原始历史。

摘要以增量版本写入，不替换原始 messages。每版绑定 source IDs、边界、parent version、hash、model_id、status；读取时逐层验证本版及父链 source hash，坏版不作为有效摘要。摘要的权限标记固定为 `untrusted_context_hint`，不参与事实确认。`record_user_confirmed_fact` 不做自然语言猜测：用户问“160℃会怎样？”不会自动写成设备温度。

当前 S1-C 仅提供存储/服务 Adapter；API/Graph 不调用该服务，故生产对话上下文行为未被本轮改变，也未宣称生产多租户隔离或后端认证已实现。

## 3. 公开执行过程与隐私投影

- 折叠入口标题采用“思维过程 · N 步”，默认关闭；折叠内部仅显示公开阶段摘要，工具调用可继续展开查看。
- `model.ts` 不将 SQLite/SSE 原 payload 复制到 UI：工具入参采用严格 allowlist，工况值做值脱敏；嵌套任意对象、prompt、文件路径、设备标识、自由文本字段丢弃。工具结果只保留公开状态、命中/来源标识、标准条款及页码等有限字段。
- `public_rationale`、错误摘要、模型公开表达摘要经过凭据、邮箱、联系方式、设备标识及温压数值脱敏；JSON 样式原文不直接当公开摘要。
- `ActivityTrace.tsx` 传给 assistant-ui Tool Fallback 的 args/result 来自上述投影，未使用原始事件对象，不展示原始 SSE/后台 JSON/隐藏思维链。原始 SQLite/SSE 事件协议和历史 replay 数据未修改。
- 不存在工具事件的普通聊天不生成步骤；按 run_id 过滤；每阶段继续可折叠；原有 `@media(max-width:520px)` 阶段和工具布局保留。

说明：“思维过程”只是 UI 文案，折叠区内容是阶段与执行事件的公开摘要，不是模型 CoT。SSE 历史回放沿用同一 `projectActivity` 投影路径。

## 4. 测试与实际命令

### S1-C 临时 SQLite

```powershell
.\.venv-langgraph\Scripts\python.exe -B -m unittest tests.test_v2c_conversation_memory -v
```

结果：9 项通过（隔离/旧 schema reopen、明确修正与审计历史、候选不升级、越会话外键拒绝、有界历史、摘要增量/父链哈希校验、模型关闭与敏感门禁、异常 fallback、Store reopen replay、附件会话过滤均覆盖）。临时 DB 位于系统 Temp 随测试清理，不触碰 `data/`。

### 前端

```powershell
cd frontend
npm test -- --run
npm run typecheck
npm run build
```

结果：Vitest 17 个文件 / 118 项通过；TypeScript `tsc -b --pretty false` 通过；Vite build 通过。Build 输出仍有单 chunk >500 kB 警告（index bundle 约 614.49 kB）；构建成功。

覆盖折叠默认态、run 隔离、历史事件投影、无事件不造步骤、工具分层展开、标准来源、深层敏感字段过滤、凭据/联系方式/设备标识/温压脱敏、前端公开摘要与自然语言答复分离。移动端用现有 520px 响应式规则及小屏可读性组件行为做 DOM/CSS 回归；Playwright connector 本轮启动连接等待超时，未采集真实 Edge 手机 viewport 截图，因此视觉 E2E 是未验证项，不计为 PASS。

### 全项目回归

```powershell
.\.venv-langgraph\Scripts\python.exe -B -m unittest discover -s tests -q
```

全量回归重复运行后结果有明显漂移，均为真实全量执行且退出码 1：第一次 `Ran 268 tests`，`failures=24, errors=6, skipped=3`；紧接着最新一次 `Ran 275 tests`，`failures=1, errors=3, skipped=3`。最新输出临时保存为 `C:\Users\37813\AppData\Local\Temp\v2c_full_unittest_20261029_final.log`，前一次为 `C:\Users\37813\AppData\Local\Temp\v2c_full_unittest_20261029.log`。结果漂移说明项目全量测试/数据夹具目前不稳定；因此不把第二次较少的失败数当作通过。`-q` 只记录 skipped 数，没有打印具体 skip 原因。

最新一轮主要阻塞：

- `test_p16_a_evidence42` 导入错误：当前 `.venv-langgraph` 缺 `fitz`/PyMuPDF。
- 2 项 `test_r9a_industrial_candidate` ERROR 与 1 项 FAIL（本轮实际工具路径/计数与断言不一致）；S1-C 未改 Graph/路由，未越界修复。
- 前一次运行还有 13 项 P13 intent 子项失败（分类器返回 `general_chat`，与该批工程/机理题期待不符），以及 P3B evidence audit、P4A API safety、V2A router gateway 各 1 项失败；后一次这些用例转为通过，进一步表明全量测试有状态/夹具漂移。
- 跳过 3 项；全项目未通过，不能把专项 PASS 外推为集成 PASS。

全量回归期间附带输出的负载用例：concurrency 1/4/8 各 100 runs，errors 均为 0；它们不能抵消 unittest 失败。

## 5. P13 既有证据与本轮限制

已检查 `docs/P13_CHAT_PRODUCTION_REPAIR_ACCEPTANCE.md`（以及本轮指定 P13 回放与上传隔离记录）。其历史结果包含 SQLite/SSE run 回放、附件 conversation_id 隔离及本地负载数据。本轮新增专项对同一 Store 的可见消息与附件查询做临时库验证；没有重新启动真实 FastAPI/Graph，也未把历史 P13 报告当作本轮 API/SSE E2E 结果。

## 6. 给 S2/API/Graph 所有者的接线协议

建议在后续唯一窗口中按下列顺序接入（本轮未修改 API/Graph）：

1. 以现有 `Store` 单实例创建 `ConversationMemoryService(store, ...)`，只用当前 run 的 `conversation_id`。
2. 普通聊天 context 只接 `get_recent_visible_history(cid, ...)` 与 `get_confirmed_facts(cid)`；禁止从 checkpoint/run payload 把模型猜测晋升为确认工况。
3. 新事实必须由显式用户确认/结构化表单调用 `record_user_confirmed_fact`；LLM 候选只调用 `record_candidate_fact`。
4. 摘要先留关闭；接入 mock 做功能/成本门禁，再由 Owner 选择 provider 与显式权限流程。每轮显式传 `sensitive`；附件/敏感轮次未授权不得 summary。
5. 失败统一采用返回的 `history` 有界原文回退，不能中断 chat；不得把摘要当风险结论、事实来源或人工审核。
6. API response/SSE 仍用现有事件协议；前端只调用 `projectActivity(events)`，不要把原始事件 payload另开 UI 输出。
7. 补充 API+临时 SQLite+真实 SSE replay 的集成测试，并在 Edge desktop/mobile viewport 做截图和 console/network 核验。

## 7. 结果清单

- 通过：S1-C 专项 SQLite 与 React/Vitest/typecheck/build。
- 未通过：全项目 Python 回归（24 FAIL、6 ERROR、3 skips）；不归因给本轮范围内的 Store/trace 改动，但需 Owner 分别确认历史测试漂移、环境依赖和图行为差异。
- 未验证：真实模型摘要、在线 provider/计费、API/Graph 集成、真实 Edge 移动端视觉截图、生产 DB migration。
- 发布判断：`READY_FOR_OWNER_REVIEW`，不是集成发布 PASS。保持本地候选，无提交、无部署；等待 Owner review 和 S2 接线计划。

## 8. 工作区观察

本轮未执行任何 `upstream/` 写命令。结束后的只读 `git -C upstream status --short` 显示 RBI Excel 为 modified，候选 Excel 和 `.bak_owner_before_rbi1_20261028` 为 untracked；由于本轮开始时未保存 `upstream/` 独立仓库基线，无法归因这些状态来自本轮测试还是既有并行工作。本轮没有打开、恢复、删除或覆盖这些文件，留给 Owner 按数据审计链检查。
