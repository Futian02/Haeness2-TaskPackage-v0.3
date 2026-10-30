# R1 Chat / SQLite / SSE 事件协议

## 页面垂直切片

`web/index.html` 是无前端构建链的本地单页：左会话列表、中间消息流+输入、右执行时间线与出处抽屉；适配窄屏。这样首轮不额外引入 npm registry/assistant-ui/Tailwind 的安装面，组件可以在产品事件协议稳定后迁入 React。`RULE / LLM OFF / MULTI · DEMO` 清楚标注，不模拟真实模型 token。

## REST

- `GET /api/health`
- `GET/POST /api/conversations`
- `GET /api/conversations/{id}`（含历史 messages）
- `POST /api/conversations/{id}/runs`（先持久化用户消息，返回 run_id 与 stream URL）
- `GET /api/runs/{id}/stream`（SSE，第一次消费 run；再次连接按数据库原序重放）
- `GET /api/runs/{id}/events?after_sequence=N`（断线后从 `N+1` replay）

## SSE Schema v1

每帧 `data: JSON\n\n`，event JSON 字段：

```json
{"schema_version":1,"event_id":"uuid","run_id":"uuid","session_id":"conversation-uuid","sequence":1,"ts":"UTC ISO-8601","type":"agent_started","agent":"supervisor","payload":{"route":"classify"}}
```

类型包括 `run_started`、`agent_started`、`tool_called`、`tool_result`、`reference_added`、`decision_summary`、`verification`、`token_delta`、`agent_completed`、`run_completed`、`error`。节点 summary 是公开决策摘要，非内部思维链。

## 幂等/持久化

SQLite `WAL` + 外键；每次事件写入后提交，`sequence` 在 `run_id` 内从 1 单调递增且唯一。Runs 有 queued/running/completed/failed；已启动/完成的 stream 请求只重放原事件，不重新触发 Agent 图。消息、事件、工具入参/返回、证据引用、知识文档为独立表，均有 run/conversation 与创建时间关联。前端以 `sequence` 排序消费，重连使用 after-sequence；同一事件通过 idempotent sequence key 可去重。

`token_delta` 当前是完成后的整段规则答复片段；真实逐 token 模型接入后应增量写入事件，不能把 Demo 延迟伪装成流式生成。取消、认证、多租户、限流、删除/保留策略尚未实现，服务只绑定 `127.0.0.1`。

## SQLite / MySQL

SQLite 无外部服务、适配朋友离线演示；WAL 支持单机读写并发，备份可复制主库前应 checkpoint WAL。当前 Store 是 sqlite3 专用：`DATABASE_URL` 可配置 SQLite 路径，非 SQLite URL 会 fail-fast；**MySQL adapter 和连接端到端测试未实现**，不是把 MySQL 说成已可用。切 MySQL 前需把 SQL repository 抽象成 storage port，确认 PyMySQL/SQLAlchemy 驱动、事务/JSON 类型、迁移与并发语义，再通过同一仓储契约测试。
