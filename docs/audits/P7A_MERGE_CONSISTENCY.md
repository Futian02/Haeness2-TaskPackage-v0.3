# P7-A Merge 一致性门禁审计

状态：**READY_FOR_OWNER_REVIEW**。本轮仅修复隔离的 P6 并行审查实验 Merge；生产 `AgentGraph` 顺序路径未切换，并行生产 flag 未启用。

## 范围与变更

- `orchestration/p6_parallel_audit.py`
  - `merge_findings` 按 `(run_id, claim_id, source_clause_id, origin_agent, attempt_id)` 分组。
  - 以规范化 JSON SHA-256 判定完全相同 payload；相同键、相同 payload 幂等去重。
  - 相同身份键出现不同 payload 时，不再 `setdefault` first-wins：保留 SHA 与双方完整（经等级门禁净化的）结果，排序固定，置 `conflict_requires_review=true`、`review_status=requires_human_review` 并强制 E0。
  - merge 接受的角色仅 `evidence_auditor` / `skeptic`；无效角色或非 JSON payload fail-closed。
  - `grade` 与 `verification_level` 被外部注入为 E2/E3/其他值时均净化到 E0并附原因；skeptic 不可写 grade；本路径最高只能输出 E1。
  - reducer 仍只负责 `audit_updates` 与 `skeptic_updates` 的列表合并；不开放 claims、disagreements 或 gaps 多写。
- 新增 `tests/test_p7a_merge_consistency.py`：覆盖冲突乱序、重复重试、attempt 隔离、E2/E3/非法等级注入、角色门禁、坏 payload。
- 新增 `evals/p7a_parallel_merge_benchmark.py`：同一 StateGraph schema/nodes/merge/fixtures，图只编译一次后做顺序与并行调度比较。

未修改 `backend/`、`frontend/`、`upstream/`、教师三工具、原始 Excel/PDF、官方 JSONL。未部署、未提交或清理 Git。

## 独立缺陷复现与修复证据

修复前实际命令：

```powershell
.\.venv-langgraph\Scripts\python.exe -B -m evals.owner_p6_adversarial_probe
```

输出确认：

```text
DUPLICATE_SAME_KEY_FIRST_WRITE_WINS E1 E0 order_invariant= False
EXTERNAL_GRADE_E3_ACCEPTED E3
OWNER_P6_ADVERSARIAL_FINDINGS_REPRODUCED; this is not a production acceptance test
```

修复后再次执行同一历史 probe：退出码 1，首个旧断言报 `E0 E0 order_invariant=True` 与其硬编码的坏行为预期 `E1/E0` 不符。该 probe 是复现脚本，断言原本要发生的漏洞行为，故修复后不将其冒充 PASS；新修复断言以 P7A 专项测试为准。P6C 两项历史问题仍由该脚本后续 probe 覆盖不到，因为脚本在首个已修复断言处终止。

## 实际测试与回归

1. `python -B -m unittest tests.test_p7a_merge_consistency -v`：**7/7 PASS**。
2. `python -B -m unittest tests.test_p7a_merge_consistency tests.test_p6a_parallel_evidence -v`：新 P7A **7/7 PASS**；P6A旧测试 **6 PASS / 1 FAIL**。唯一失败是 `test_merge_deduplicates_retry_but_preserves_distinct_attempts` 将相同 identity key、不同 payload（E1 vs E0）断言为保留 E1；这与新契约“不同 payload 需保留冲突并降至 E0”冲突。该测试在 P7A授权写入边界外，未篡改或删除此旧断言，也未为全绿放宽 gate。
3. `python -B -m unittest discover -s tests -q`：**101 项，100 PASS / 1 FAIL**，失败为上条陈旧 P6A 断言。完整输出在执行窗口日志；没有其它失败。
4. `python -B -m evals.owner_p3_regression_probe`：PASS，旧缺页、双SSE单run重复执行、裸问题注入设备事实等缺陷保持修复。
5. `python -B -m evals.owner_p4_integration_probe`：完整工况 **44 events / 2 claims / 2 disagreements / 7 references**；失效worker迟到追加事件仍以 `PermissionError` 拒绝。
6. `python -B upstream/04_接口文档/validate.py --final`：PASS，**554/554 clauses、200/200 trajectories**（RBI 472、DM 82）。

Windows下以上 `python` 命令实际使用隔离解释器：`\.venv-langgraph\Scripts\python.exe`。命令原始形式及结果来自本轮终端执行。

## 同口径本地调度实验

命令：

```powershell
.\.venv-langgraph\Scripts\python.exe -B -m evals.p7a_parallel_merge_benchmark
```

20个 synthetic RULE_DEMO 场景，两个图均先构造/编译、预热；之后使用相同 fixture、状态schema、分支节点和 Merge，分别顺序/并行 `invoke`。输出：

```text
parallel P50/P95:   0.949 / 1.194 ms
sequential P50/P95: 0.608 / 0.787 ms
tool calls per mode: 20
duplicate source reads: 0
parallel_merge_equivalent_to_sequential: true
expert_accuracy: null
```

在这个纯 Python 只读实验里，并行调度没有更快；不报告加速结论，不代表真实 LLM/工具并行收益，不是专业准确率数据。两路皆使用相同的20条冻结合成 tool result；没有调用有副作用的教师工具。

## 未解决项与审查建议

- 全量 Python 仍有1个旧测试失败。若 Owner 批准，可在后续边界扩展中把 P6A 测试输入改成真正同 payload 重试，并另留专门冲突断言；当前保持文件冻结，遵守 P7A目录范围。
- `evals.owner_p6_adversarial_probe` 首项按设计仍预期漏洞，修复后必然以 AssertionError 退出；不应用它作为绿灯验收。
- 并行图仍是隔离实验、确定性 RULE_DEMO，不是多LLM，也没有专家金标。生产图保持原顺序路径。

最终状态：**READY_FOR_OWNER_REVIEW**；本报告不代表生产并行审批或工程准确率结论。
