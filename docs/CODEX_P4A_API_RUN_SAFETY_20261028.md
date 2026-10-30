# Codex P4-A｜API/SSE幂等+真实输入安全门禁（独立backend工作区）
先读AGENTS.md、docs/audits/OWNER_P3_INDEPENDENT_REVIEW_20261028.md、evals/owner_p3_regression_probe.py，及backend/api.py/store.py、tests/test_api_vertical_slice.py。P3现有54+6 PASS是基线。固定教师3工具与五键协议不可改。

**允许写：** backend/、tests/test_p4a_*.py、docs/audits/P4A_*.md；仅这些文件。禁止改frontend/、orchestration/、upstream/、原始RBI XLSX/PDF及共享docs/PROJECT_STATE.md，以便与P4-B、P4-C并行。

目标与验收：
1. 修同run重复流：SQLite单事务原子 `claim_run` queued→running，只允许唯一worker。后来到达的GET不能重算run，应可靠地回放已发事件并在执行完成前订阅新事件或明确提供带状态的恢复API。模拟双client/10并发、进程重启场景，执行器真实计数=1，assistant消息=1，事件序列无重复，无SQLite lock崩溃。不要只在JS前端做dedupe；后端是权威。
2. 修RunIn默认自动提供`常压塔顶空冷器/换热器/碳钢/氯化氢`。只传question的POST必须生成unknown/ask_for_context，绝不可产生设备事实或风险输出。例子仅显式案例模式使用，且标示为simulation；保护合法旧前端明确填工况的行为。
3. 在 `backend/store.py` 增加只读/分页`list_runs_by_conversation`，补`GET /api/conversations/{id}/runs`，便于跨设备恢复时间线，排序和所有权检查；保持既有SSE `schema_version,run_id,session_id,sequence,type,agent,payload`不变。
4. 本地演示强制127.0.0.1安全假设；定义生产部署`AUTH_REQUIRED` fail-closed（不能在无用户鉴权/隔离时公开），health不返回绝对数据库路径，添加输入长度/并发/速率限制及合适错误码，不访问真实用户私有资料。未来公网鉴权可以列出独立有界清单，但绝不能把“预留”写成“已完成”。
5. 完整验收：重复run race探针从repro转为防回归PASS；原Python 54+新测试；API SSE重放/状态迁移；官方validate --final；并且记录变更前后数据正确性、异常恢复行为；停在READY_FOR_OWNER_REVIEW。

输出 docs/audits/P4A_IDEMPOTENCE_SECURITY.md；若并发订阅实现需要额外架构设计，先做到“单次执行+明确等待/恢复接口”并如实标BLOCKED，不能虚报支持连续实时订阅。
