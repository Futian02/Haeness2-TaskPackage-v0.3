# 学习入口：从真实聊天请求追到证据

按这条路径学习，不要一上来扫全仓：

1. [`PROJECT_STATUS_CURRENT.md`](PROJECT_STATUS_CURRENT.md)：先确认当前唯一入口、模式与边界。
2. [`ARCHITECTURE.md`](ARCHITECTURE.md)：看一次请求如何穿过 React、FastAPI、Graph、老师工具、SQLite 和 SSE。
3. `frontend/src/App.tsx` → `frontend/src/AssistantMessages.tsx` → `frontend/src/components/trace/ActivityTrace.tsx`：看会话状态、run_id/事件恢复以及活动折叠。
4. `backend/api.py` 的 `create_run`、worker、`stream_run` → `backend/store.py`：看输入快照、租约、事件序号、SSE 重放和原子助手回复。
5. `orchestration/r9_industrial_candidate.py`：依次读 `route_task`、`investigate`、审查分支/合并、`_report` 与 `IndustrialCandidate.run`；对照 `tests/test_r9a_industrial_candidate.py` 看预算/门禁回归。
6. 只读检查 `upstream/05_提交区/harness.py` 和 `upstream/04_接口文档/validate.py`，理解教师合同；不在上游修改。

## 五个核心目录

- `frontend/`：聊天交互与可视化。
- `backend/`：HTTP、SQLite、SSE、上传。
- `orchestration/`：Graph 与工程语义。
- `upstream/`：老师原始工具和标准/正式数据，冻结。
- `data/`：本机运行数据库与上传文件。

辅助目录：`tests/`（回归）、`docs/`（规范/审计/学习）、`observability/`（可选本机 Phoenix 专项）。旧 `app/`、`web/`、`knowledge/`、`evals/` 与旧文档均保留用于历史追溯；不等于当前运行入口，不在本轮移动或删除。

## 建议实验

每次只改一项并保留反例：

- 空工况 vs. 完整工况：确认零工具调用门禁和调查路径。
- `GB/T` 代码/条款号不匹配 vs. 正确：验证标准来源相关性过滤。
- 没有现场测厚 vs. 明确问减薄：验证候选机理与确认性结论的区分。
- 连续两次打开同一 run：验证 SSE replay 的 `run_id`、连续 `sequence` 和 SQLite 唯一回复。

真实标准引用只用于追溯，未完成工程适用性和人工复核前不把引用命中当成设备结论。
