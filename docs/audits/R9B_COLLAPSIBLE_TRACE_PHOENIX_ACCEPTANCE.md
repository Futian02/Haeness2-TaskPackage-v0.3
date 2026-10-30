# R9-B 验收与交接

**最终状态：`READY_FOR_OWNER_REVIEW`**  
**集成状态：`COMPONENT_INTEGRATION_PENDING` / `FULL_INTEGRATION_PENDING`**  
**部署/提交：未做。**

## 范围与隔离边界

- 先读取仓库 `AGENTS.md`、R9 设计文档与 R9-B Codex 任务文档；按窗口规则只在 `frontend/src/components/trace/`、`frontend/src/trace-events/`、`observability/`、`tests/test_r9b_*` 和 `docs/audits/R9B_*` 写入。
- 未修改 `frontend/src/App.tsx`、`frontend/src/AssistantMessages.tsx`、`frontend/src/api.ts`、全局样式、`backend/`、`orchestration/`、upstream 或 R8-B 共享文件；没有安装前端依赖、部署或 Git commit。
- SQLite 验收数据写入单独的 `R9B_RUNTIME_EVIDENCE/r9b-live.sqlite`（1 个演示 conversation、2 个 RULE_DEMO runs），没有写默认业务库。Phoenix 单独使用 `R9B_RUNTIME_EVIDENCE/phoenix-local.sqlite`，只监听 `127.0.0.1:6006`，并关闭 Phoenix telemetry 与外部资源加载。Python 包安装于 `observability/.venv`，没有改 `.venv-langgraph`。Langfuse 未安装。

## 实现内容

### assistant-ui 展示组件

- 新增 `ActivityTrace`，从持久化 SQLite/SSE `ApiEvent` 构造 assistant-ui typed parts，直接使用 `MessagePrimitive.GroupedParts`、`groupPartByType`、`ReasoningRoot/Trigger/Content/Text`、`ToolGroupRoot/Trigger/Content`、`ToolFallback`。
- `run_id + sequence` 去重、按 sequence 排序、跨 run 隔离；外层执行记录默认折叠，状态按 `run_id` 保存在 localStorage，历史会话回放/刷新恢复。界面显示真实调用工具数、事件数、来源标识/页码/E0-E3、审核状态；工具参数过滤敏感键，工具结果采用字段 allowlist（状态、标题/名称、CID、分数、页码），不渲染富文本结果、raw 内容/文档全文/API key。
- phase/iteration 缺失时只显示 `legacy`，不猜测轮次；已持久化事件里没有真实隐藏 CoT 的承诺，页面注明仅为真实执行事件及公开决策摘要。用户最终答复与执行记录分开。
- 添加独立演示页 `frontend/src/trace-events/demo/`，直接访问既有只读 API：会话列表 → 运行历史 → `/api/runs/{id}/events` SQLite replay；刷新、run 切换与深浅色行为可操作。该页未接入主聊天，等待 R8-B 完成后由 Owner 统一联调。

### Phoenix / OpenInference 本机观测

- 新增 `observability/bootstrap.py`：`TRACE_BACKEND=none` 默认无副作用；`phoenix` 模式限制为 localhost/loopback exporter endpoint，严格 allowlist span attributes，只上传工具名、状态、耗时、run/tool-call IDs 与 CID digest；不上传原始 query/input、标准原文、设备标识、API key。
- standalone runner 从当前冻结的 teacher tool registry 实际调用 `damage_mechanism_query`、`standard_clause_search`；OpenInference LangChain Instrumentor 配置 `hide_inputs/hide_outputs`，工具span在 agent parent 下用 OTel 计时。采集或 `force_flush` 失败作为诊断降级，不改变工具业务结果。
- Phoenix 本机 REST 查询确认 1 个 trace、6 spans：`agent_run → agent → (OpenInference Runnable invoke + teacher_tool spans)`。两次真实本地工具调用均 `outcome=ok`；工具耗时分别约 7.7ms、1.4ms；4 个 OpenInference input/output 属性值均为 `__REDACTED__`；无原始输入/输出字段。Phoenix span JSON 与截图位于证据目录。

## 验证结果

| 检查 | 结果 |
|---|---|
| 前端全量 Vitest | PASS：8 files / 72 tests |
| 前端新增 trace model + UI 测试 | PASS：22 tests |
| TypeScript | PASS：`npm run typecheck` |
| 生产构建 | PASS：`npm run build`；Vite 仍显示既有主包 >500 kB 提示，不影响构建成功 |
| Phoenix 适配器 | PASS：6 unittest（默认 none、loopback、allowlist 脱敏、父子 trace/工具耗时/CID digest、OpenInference input/output 脱敏、export failure fallback） |
| 隔离环境依赖一致性 | PASS：`pip check` 无破损依赖 |
| SQLite/SSE 回放 | PASS：同一 run 全量 61/61 事件；after_sequence=30 返回后 31 个事件；tool_called/tool_result 各 2；reference_added 8；run_id/sequence 唯一且排序正确 |
| 浏览器回放/恢复 | PASS：真实 Chromium Edge 页面读取上述 API；初始折叠 → 手动展开 → 刷新仍展开且 run_id 与 61 events 保持；错误面板 0。用例记录在 screenshot/evidence 中 |
| Phoenix 真实 trace | PASS：独立 localhost Phoenix UI/API 查到 OpenInference 与实际 teacher tools 的父子 span、耗时、脱敏属性；导出失败 fallback 另有单测 |

## 浏览器与 trace 证据

`docs/audits/R9B_RUNTIME_EVIDENCE/`：

- `ui-collapsed.png`：1280px Chromium Edge，真实 SQLite 历史运行，折叠态。
- `ui-expanded.png`：相同真实运行展开后，含实际阶段、工具调用与引用 chip。
- `ui-tool-fallback.png`：展开实际 ToolGroup + ToolFallback 后的真实工具调用；结果 JSON 只保留 allowlist 字段。
- `ui-mobile-expanded.png`：390px viewport 移动布局。
- `ui-refresh-restored.png`：展开状态刷新恢复后的浏览器截图。
- `browser-verification.json`：实际 Edge/Chromium DOM 断言，含默认折叠、展开、run_id、刷新恢复、console error 计数与工具展开数。
- `replay_summary.json`、`replay_verification.json`、`verify_replay.py`：SSE 全量与 SQLite cursor replay 核验，只保留事件统计，不复制 raw event payload。
- `phoenix-trace-spans.png`：Phoenix UI 本机 trace/span tree 截图；`phoenix-local-ui.png`、`phoenix-project-tracing.png` 是项目/追踪页截图。
- `phoenix-trace.json`、`phoenix-verification.json`：Phoenix REST spans 脱敏摘录与层级/属性断言。
- `r9b-live.sqlite`、`phoenix-local.sqlite`：独立可重放数据与本地 trace 数据库。
- `python-license-inventory.json`：隔离 observability venv 全部 Python distributions 的许可元数据摘录。

## 合并建议（不在本轮执行）

1. Owner 等 R8-B 窗口停止对共享 UI 文件写入后，再把 `ActivityTrace` 接到 `AssistantMessages.tsx` 的 assistant turn，沿用其 run_id 和 ApiEvent 数据源；这一步预计只触及 `AssistantMessages.tsx`（组件接线），不应重写 `api.ts`。
2. 独立演示 adapter 已证明现有 API 足够提供历史 runs/replay；若要 SSE 实时更新，复用现有事件流接入组件状态即可。不要通过 UI 合成阶段、工具或审核事件。
3. 如果批准完整 graph trace，再另开集成变更并触及 orchestration seam；本轮 standalone `RunnableLambda + real teacher registry` 只证明 Phoenix/OpenInference exporter、层级、工具计时及脱敏，不能宣称生产 LangGraph 全图已插桩。
4. `phase/iteration/step_id/parent_step_id` 当前旧事件不含时，显示 legacy；跨 Agent/轮次的丰富时间线需后端真实事件字段先落库，再经单独契约评审。

## 交付许可

见 [`R9B_LICENSE_NOTICE.md`](R9B_LICENSE_NOTICE.md)。assistant-ui 组件 MIT 文本已与组件一同复制；Phoenix Server 使用 ELv2，仅本机开发验证，未嵌入产品。完整隔离 Python lock 与许可 metadata 清单随证据交付。

