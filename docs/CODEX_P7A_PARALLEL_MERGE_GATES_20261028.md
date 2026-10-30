# P7-A：并行Merge审查一致性门禁（仅orchestration与P7A专项测试/评测）
必须先读`docs/audits/OWNER_P6_INDEPENDENT_REVIEW_20261028.md`，执行`./.venv-langgraph/Scripts/python.exe -B -m evals.owner_p6_adversarial_probe`，确认两个已复现问题：同键E1/E0输入反序结果不一致，任意输入grade E3竟能被merge输出。
允许文件：`orchestration/p6_parallel_audit.py`、新增`tests/test_p7a_*.py`、`evals/p7a_*.py|jsonl`、`docs/audits/P7A_*.md`。禁止改`backend/frontend/upstream`、老师三工具、Excel/PDF、Git清理部署。
修复：
1. 形式化`(run_id, claim_id, source_clause_id, origin_agent, attempt_id)`语义：完全相同payload hash则去重；同键不同payload不得first-wins。要么确定性保守合并（E0/冲突需人审）并保存双方原始sha，要么抛结构化冲突并fail-closed，绝不因输入顺序变化输出不同E0/E1。避免丢失独立反证。
2. `merge_findings`边界所有`grade`只能E0/E1（无效/未来权限未知降E0并记录reason或fail）; E2/E3仅未来真实人审外部受控途径写入，无法靠注入finding升级。
3. 精确reducer：不把`claims/disagreements/gaps`开放多写；重试同attempt、不同attempt、乱序、全相同与冲突样例；`operator.add`只负责state concat。
4. 不启用生产並行flag；保留现有稳定AgentGraph，跑Python94+新增 tests、P3/P4探针、teacher validate，参照固定tool results做**同口径**实验（不拿每次build+invoke对比helper直接调用）。若总延迟没改善如实报告。
5. `evals.owner_p6_adversarial_probe`旧版期望坏行为，不直接当通过验收。新增修复后负向测试assert违反条件不能输出E3/不能依赖顺序。
交付`docs/audits/P7A_MERGE_CONSISTENCY.md`和真实输出，停在READY_FOR_OWNER_REVIEW，不部署。
