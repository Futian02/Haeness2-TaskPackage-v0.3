# Codex P6-A：有界并行审查实验与Reducer机制（只改orchestration/、P6A测试与实验）
先读`AGENTS.md`、`docs/audits/OWNER_P5_INDEPENDENT_REVIEW_20261028.md`、`docs/COURSE_05_LANGGRAPH_PARALLEL_REDUCER_20261028.md`，运行`./.venv-langgraph/Scripts/python.exe -B -m scripts.lesson05_parallel_reducers`。基线Python87/87，Teacher554/200，P5A worker lease+SSE原子事件门禁必须不退化。
允许修改：`orchestration/`、`tests/test_p6a_*.py`、`evals/p6a_*.py|jsonl`、`docs/audits/P6A_*.md`，不要改`backend/`、`frontend/`、`upstream/`及老师三工具/XLSX/PDF。
目标：保持当前顺序执行为默认唯一生产路径，新增**独立或明确flag控制**的并行候选实验：Diagnosis完成后，Evidence Auditor与Skeptic在同一super-step分别读取原始observations、canonical source以及候选claim ID（不抄对方自然语言判断），只返回局部结构化审查结果，在独立Merge节点协调。
图状态修改要精确设计：`audit_updates: Annotated[list[AuditFinding],...]`及`skeptic_updates: Annotated[list[Finding],...]`或按角色不同channel，绝不两路同时无reducer覆盖`claims/disagreements/gaps`；必须按`(run_id,claim_id,source_clause_id,origin_agent,attempt_id)`确定性去重，保留正反证与unknown，来源等级不能因operator.add自动升级到E2/E3。合并幂等且执行重试不双计。
新实验记录LangGraph INVALID_CONCURRENT_GRAPH_UPDATE无Reducer负例、带reducer正常分支、先后顺序/随机完成顺序、缺工况、冲突、来源缺失、SSE序号、错误回滚与P5A失效租约，覆盖至少15例；比较顺序vs并行 P50/P95，tool次数/是否多读重复来源、非法risk等级0，但无专家金标不能报告专业准确率。不能真正并行调用存在副作用的老师工具，前期优先并行只读审查分支。
最终完整Python及teacher validate、原P3/P4 probes均PASS；若任何共享state不稳定则不打开flag，停在`READY_FOR_OWNER_REVIEW`并提交报告`docs/audits/P6A_PARALLEL_EVIDENCE.md`，不部署。
