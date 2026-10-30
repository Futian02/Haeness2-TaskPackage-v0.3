# P4-A API / SSE 幂等与安全门禁验收

**状态：READY_FOR_OWNER_REVIEW（本地验收交付；未部署、未提交 Git）。**

## 范围与冻结项

本轮仅写入 `backend/api.py`、`backend/store.py`、`tests/test_p4a_api_safety.py` 和本报告。未写 orchestration、frontend、teacher upstream、官方合同/原始标准、XLSX/PDF、共享 README/PROJECT_STATE。Teacher 工具名字仍为 `damage_mechanism_query`、`rbi_lookup`、`standard_clause_search`；未新增工具，未改五键协议。SSE仍使用单个 JSON `data:` 帧；`schema_version/run_id/session_id/sequence/type/agent/payload` 字段保留。

## 变更与实现

1. **run claim / exactly-once worker：** SQLite `UPDATE ... WHERE status='queued'` 影响行数作为唯一 worker 租约；随机 worker token 绑定 heartbeat、完成/失败状态变更。图运行由唯一胜者启动，后续 GET 接入相同数据库事件轮询，不启动第二次执行。SQLite WAL、busy timeout 与唯一 `(run_id, sequence)` 约束继续生效。assistant 回复与 `running -> completed` 通过 `finish_run_with_message` 同一 SQLite transaction 原子提交。活动 worker 每 5 秒续租。
2. **等待、断线恢复与崩溃恢复：** SSE订阅者轮询持久化事件并跟进状态，支持相同运行期间订阅、断线后带 `after_sequence` 重放以及服务重启后的终态重放。heartbeat 过期后由订阅端原子标记 `failed/worker_lost`、写入持久错误事件；不自动重试可能有副作用的图工作。错误事件保持 SSE envelope。
3. **工况缺省：** `RunIn` 中 equipment/equipment_type/material 默认 `None`，medium 默认空列表；输入仅含 question 时图路由到 `ask_for_context`，无工具调用、无设备事实或风险等级注入。显式传入工况仍按既有请求字段传递。标题、问题、工况字段、列表大小和单项长度受限。
4. **历史 API：** 新增 `Store.list_runs_by_conversation(cid, limit, offset)` 与 `GET /api/conversations/{cid}/runs`，固定会话路径范围，按时间/id倒序，返回元信息和分页总数、不泄露 question/context。参数有界；不存在会话为 404。另有 `GET /api/runs/{rid}` 返回不含私有工况的状态/恢复摘要。
5. **安全门禁：** `APP_ENV=production` 时在任何路由执行前返回 `503 AUTH_REQUIRED`，因为项目没有真实用户鉴权/租户隔离实现；dev 模式拒绝非 loopback 客户端，不信任 forwarded headers。health 不返回数据库绝对路径。Content-Length 超限返回 413，字段越界返回 422，速率门限返回 429，进程内最多 4 个并发 worker，worker 满载返回 429且run保持 queued。该实现是单机演示防护，不是公网安全认证实现。

## 实际验证

| 命令 | 实际结果 |
|---|---|
| `.venv-langgraph\\Scripts\\python.exe -B -m unittest tests.test_p4a_api_safety -q` | **11 tests PASS**，包含10线程原子 claim、10并发唯一胜者、双 SSE 同步订阅只执行一次/一条 assistant 消息/相同递增事件、重启后持久重放不重算、超时租约终结、默认工况、分页范围、health 隐私、生产 fail-closed、大小/字段/速率/并发限制。 |
| `.venv-langgraph\\Scripts\\python.exe -B -m unittest discover -s tests -q` | 最终执行 **81 项：80 PASS，1 FAIL**。失败为 `test_explicit_condition_mismatch_is_not_applicable`：断言旧结果 `E1`，当前 `orchestration/evidence_audit.py` 返回 `E0`。这是 P4-B 所属目录的并行改动/新语义，P4-A 未修改或回滚它；请 P4-B/Owner 核查该预期并协调全量绿色。 |
| `.venv-langgraph\\Scripts\\python.exe -B -m evals.owner_p3_regression_probe` | **按原样运行，脚本在首个 probe 处以 AssertionError 退出。** 输出 `metadata_page_omitted grade=E0 reported=missing expected_stronger_check=missing_not_matched`，说明缺页码现在拒绝记成 matched；但原 probe 写死 `assert check['status'] == 'matched'` 并称修改后需人工检查，和其修复目标不再一致。受 P4-A 写入边界限制未改 `evals/`。原子 stream race 与默认工况以本轮 `test_p4a_api_safety` 独立回归覆盖；teacher source schema 本轮没有变更。 |
| `.venv-langgraph\\Scripts\\python.exe -B upstream\\04_接口文档\\validate.py --final` | **PASS**：有效 clauses 554（554/554）、trajectories 200（200/200），轨迹分类及全部官方数量下限通过，终验通过。 |
| `python -B -m py_compile backend/api.py backend/store.py` | 初次新增分页 SQL 行误带补丁标记时命令未报告语法错误（Python把 `+` 解析为一元正号）；随后已修正并在 P4-A 单测通过中导入/执行相关代码。 |

### 基线对照与失败说明

Owner P3审查的基线为旧版全量 **54/54 PASS**、probe复现同 run 两次图执行、assistant重复以及 question-only 注入默认工况。本轮新增11项安全/幂等测试均通过；当前全量79项有1项旧语义断言与并行 P4-B 的更严格 `E0` 行为不一致。失败不属于本轮 API/store 范围，不能把它隐藏成全绿；整体验收应在 P4-B 修订该测试/确认期望后重跑。

## 失败/恢复语义与限制

- worker 在执行期间进程消失：租约过期后 run 变为 `failed / worker_lost` 并可在 SSE/API 查询及持久化重放；默认 **不重执行**，避免对潜在副作用/成本型工具重复提交。
- 当前是单机、单 SQLite 数据库的应用内租约/轮询模型；多主机部署须共享可靠协调/队列与租约机制，当前未验证。
- 没有用户身份、会话所有权、租户隔离、CSRF/CORS策略或反向代理信任配置。生产环境入口一律 fail-closed；公网部署未通过。
- 进程内限速状态不跨进程；不替代边缘网关/持久化限速。请求体采用 Content-Length 上限并配合 Pydantic 字段限制。
- 无服务启动、端口监听、部署、Git add/commit、Excel/PDF写入。

## Owner 验收建议

1. 与 P4-B 确认 `E0` mismatch 的预期并更新其归属测试，然后重跑全量 unittest 和本报告命令。
2. 将 owner probe 改造成断言“缺失页码不得 matched、重复流执行/assistant各一次、裸 question 无工况”，但由评测文件 Owner 在允许范围内处理。
3. 如需多进程/公网，先实现真实认证、用户级 conversation/run 权限检查及跨进程队列/限流，再重新做安全审查；不能仅移除 `AUTH_REQUIRED` 门禁。
