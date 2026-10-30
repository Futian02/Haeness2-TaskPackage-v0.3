# Codex P4-B｜真正可审计的证据独立复核（仅改orchestration）
阅读AGENTS.md、docs/audits/OWNER_P3_INDEPENDENT_REVIEW_20261028.md、evals/owner_p3_regression_probe.py、orchestration/evidence_audit.py、orchestration/semantics.py、orchestration/graph.py；上游老师工具仍只能3个，不增加调用接口。
**允许写：** orchestration/、tests/test_p4b_*.py、evals/p4b_*.py|jsonl、docs/audits/P4B_*.md；禁止改backend/、frontend/、upstream/、原RBI Excel、共享PROJECT_STATE.md。

目标：
1. 修metadata missing误判：对standard_code/clause_no/page等source字段做四态matched/missing/mismatch/unknown。返回缺页时不能显示matched。E1语义严格定为“可溯源到官方完整ID及同轮工具引用”，不要把未检查的page说成已检查；缺必要metadata E0或 `partial` 标志。对假标准号/错页/丢字段写对抗测试，保留P3B 9测。
2. 当前真实teacher`standard_clause_search().source`仅四元定位，无`content_raw`。在保持官方工具完全冻结的前提下，通过可信本地 `clauses.jsonl` 回查已认证引用CID及其原文`content_raw`。引文必须把`clause_id + canonical record sha + printed page`与本轮tool source关联；若不在原库、正文空、版本不匹配→E0+need_human_review。**不可用大模型改写原文冒充官方文本**。
3. Skeptic实质独立：先从`raw observations + official source/current indices`生成反证检查，不使用Diagnosis的自然语言描述当证据；除了评估Diagnosis引用的条款，独立对现场异常词/工况做第二路检索发现漏掉的适用/不适用条款。承认纯词法或规则程序不可完成语义蕴含、E2/E3仍需独立人工/经评测模型验证。为多个互斥条件、mixed medium、temperature unknown、false vs unknown设计反例。
4. Claim分类清晰区分`source_fact/engineering_hypothesis/equipment_diagnosis/risk_level`，对证据不足输出unresolved和补测建议。不要仅凭risk_lookup返回单个L等级出设备风险判定；SSE继续不外泄未经证实的风险/周期，失败闭合。
5. 测试20个现有unreviewed合成案例的规则行为，但不能以其宣称专家金标准确率；补至少10条负向校验与跨来源冲突case，记录召回/人工审阅占比/工具次数、P50/P95与事件入库一致性。**不实现假多模型**。
6. 运行独立回归+官方validate --final，输出 docs/audits/P4B_INDEPENDENT_VERIFICATION.md，停在READY_FOR_OWNER_REVIEW。

注意：P4A正在改backend，这一轮不碰任何backend文件；如需新持久化字段先在现有event payload中后向兼容设计，接口变更留待集成。
