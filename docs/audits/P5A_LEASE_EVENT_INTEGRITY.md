# P5A — Lease-bound event integrity

**状态：READY_FOR_OWNER_REVIEW**（本机回归完成；未部署、未提交）。

## 目标 / 范围

修复 Owner 在独立 SQLite 探针中复现的终态后旧 worker 仍可追加事件。只改 `backend/`、`tests/test_p5a_*.py` 和本报告；未改 `orchestration/`、`frontend/`、`upstream/`、教师三工具、五键返回协议或原始 Excel/PDF。修复可撤销：仅回退 `backend/store.py`、`backend/api.py` 和本 P5A 测试/报告；无数据库表结构迁移。

## 实现与状态模型

事件写入由 `Store.append_event(..., worker_token=...)` 原子执行：先 `BEGIN IMMEDIATE` 获取 SQLite 写锁，再在同一事务确认 `runs.status='running' AND runs.worker_token=?`，然后分配 `MAX(sequence)+1` 并同时写 `agent_events` 与 tool/evidence/claim/disagreement 投影。校验、序号分配、事件和投影处于同一事务，恢复线程与旧 worker 不会出现 TOCTOU 窗口。无效、过期、错误 token 或 failed/completed 状态抛 `PermissionError`，事务回滚，不留下序号或投影碎片。

`recover_stale_run` 在同一事务将有效过期租约 CAS 为 `failed/worker_lost`、清除 token/heartbeat 并写唯一系统 `error(worker_lost)` 事件。它调用内部 `_insert_event` 特权路径，而不是允许 worker 伪装 system event。租约恢复与 append 的交错由 SQLite 串行化：若 append 先获得写锁，它是恢复前的合法事件，随后 `worker_lost` 终态事件序号更大；若 recovery 先提交，旧 append 被拒绝。恢复后不存在任何更晚的业务事件。

生产 API 的 graph `emit` 显式传 worker token；检测到 heartbeat/append 租约丢失后终止 graph 的后续事件。异常处理会尝试带原 token 记录 error；权限拒绝被吞并为“旧 worker 已失效”，不会二次写事件或覆盖系统的 `worker_lost`。图上的 `run_completed` 信号先在API内暂存，`finish_run_with_message` 再以 token+running CAS 将 completed、唯一assistant回复和最终 `run_completed` 事件一次提交；消费者看不到“已完成事件但失败终态”的半提交状态。失效 worker不会把 failed 改回 completed。

为保留已有测试/内部可信 callback 的旧调用形态，无 token 调用只在该 `Store` 实例内兼容：首次写入通过原子 `queued -> running` 取得随机本地 lease；终态/租约回收时清除本地能力。它不是 system 通道，也不能越过 running/token 校验。线上 API 不使用该兼容分支。

### DB / 迁移 / 回滚

`runs`、`agent_events`、`tool_calls`、`evidence_refs`、`claims`、`disagreements` schema 均未改变；业务数据文件无迁移。回滚只需撤销上述两份 backend 文件的代码差异，并保留/移除新增测试和报告；回滚旧逻辑会重新暴露 Owner 所报的孤儿事件风险，因此禁止在未解决前部署旧版本。

## 实际复核

基线修改前：

```text
python -B -m unittest discover -s tests -q
Ran 81 tests ... OK
python -B -m evals.owner_p3_regression_probe
OWNER_P4_REGRESSION_PROBE_PASS: all three former defects remain fixed
python -B -m evals.owner_p4_integration_probe
FULL_CONTEXT ... events 44 claims 2 disagreements 2 references 7
LATE_EVENT_AFTER_FAILED_RUN_ALLOWED 2 status failed
```

修复后命令及本轮实测：

```text
python -B -m unittest tests.test_p5a_lease_event_integrity -v
Ran 6 tests ... OK
python -B -m unittest discover -s tests -q
Ran 87 tests ... OK
python -B -m evals.owner_p3_regression_probe
OWNER_P4_REGRESSION_PROBE_PASS: all three former defects remain fixed
python -B -m evals.owner_p4_integration_probe
FULL_CONTEXT ... events 44 claims 2 disagreements 2 references 7
LATE_EVENT_AFTER_FAILED_RUN_REJECTED PermissionError
python -B upstream/04_接口文档/validate.py --final
PASS; 554 clauses / 200 trajectories
python -B -m scripts.check_sources
PASS; present=19 / required=19
python -B upstream/05_提交区/_selftest_tools.py
PASS; 17 tests, 0 failures
```

P5A tests覆盖显式/伪造 token、failed/completed 拒写、worker失效回收的 system event、10线程业务 append 与过期租约回收竞争、原子 completed+assistant+run_completed，以及历史 trusted emitter 兼容路径不得终态绕过。序号无重号；终态事件分别只有获胜者的 `run_completed` 或回收器的 `error/worker_lost`。原 P4 probe 没被修改；它通过捕获异常输出拒绝结果。

教师合同保持冻结；后续同轮分别运行官方 `validate.py --final` 与 `scripts.check_sources` 做冻结区复核。P5C 前端正向完整工况 E2E 为另一条独立范围，不属于本报告验收。

## 学习点

这类漏洞不是“多加一个 if status != failed”即可：若状态查询与事件 INSERT 是两个事务，中间仍可被恢复线程夺走租约。关键是把租约 CAS、序号分配、主事件行和物化投影放进一个 SQLite 写事务。可用线性化顺序解释竞争结果：每个 writer/recovery 操作都在 `BEGIN IMMEDIATE` 获得写锁处线性化；只有锁内看到 active token 的 writer 能提交。后续可实验 WAL 锁等待、busy timeout、任务进程崩溃和多进程而非仅多线程的调度。
