# Codex P5-A｜租约失效后的事件写入一致性（只改 backend/ 和 P5A测试）
**目标**：修复Owner已独立复现的`Store.append_event()`在`run.status=failed`或`completed`后仍能被旧worker写入事件的问题。任务输入必须先读`docs/audits/OWNER_P4_INDEPENDENT_REVIEW_20261028.md`和`evals/owner_p4_integration_probe.py`。

边界：只允许改`backend/`、新增`tests/test_p5a_*.py`、新建`docs/audits/P5A_*.md`。不改`frontend/`、`orchestration/`、`upstream/`、原始Excel、PDF、老师三工具、PROJECT_STATE。上轮Owner刚调整`tests/test_p3b_evidence_audit.py`和`evals/owner_p3_regression_probe.py`，不要回滚。

设计要点：
1. 内部worker事件写入必须绑定`worker_token`和run状态`running`；EventStore写入中原子核验租约（同一SQLite事务），防止失效的old worker继续写claim/tool/reference/run_completed。系统来源事件如`recover_stale_run`产生的`worker_lost`必须保留明确的特殊路径，不允许假worker冒充系统。现有测试直接`store.append_event`回归使用未授权路径的情况要明确迁移或提供独立`system_append_event`，不得直接让其重新绕过校验。
2. 若租约在graph运行中失效，最后的`finish_run_with_message`CAS已经拒绝提交，但graph依旧可能调用emit：在后台记录安全拒绝后停止该旧worker的后续事件，最终用户状态不允许从failed跳completed。避免在worker失效后catch异常又写出一条非法error事件造成二次故障。
3. 一个run终态只允许最后有效终态事件，SSE持久化replay可重现，顺序不重号；用10线程交错和同时lost→append证明原子性。区分正常completed vs worker_lost失败，不重复assistant消息。
4. 额外检验`APP_ENV=production`仍为AUTH_REQUIRED，teacher工具注册/五键合同不变；真实运行端到端2个用户并发、断线重放测试不得退化。所有81项 Python测试+新增tests、`evals.owner_p3_regression_probe`和`evals.owner_p4_integration_probe`需通过；后一探针目前把'late events accepted'作为复现，Owner可以另改为正式负向校验，但请不要碰该文件（由Owner更新）。
交付`docs/audits/P5A_LEASE_EVENT_INTEGRITY.md`含真实重复序列、状态迁移、业务SQLite结构变更、异常处理与回退办法；停在READY_FOR_OWNER_REVIEW，未部署。
