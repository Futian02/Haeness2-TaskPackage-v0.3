# Codex P6-C：可签署人工审核/E2E3评测与专业Gold规范（纯文档和评测schema）
目标在项目`docs/`、`evals/p6c_*`中设计**人工审核状态与评价方案**，不写真实用户身份或伪造专家标签。只允许 `docs/P6C_*.md`、`docs/audits/P6C_*.md`、`evals/p6c_*`；不动`backend/orchestration/frontend/upstream`。
读P2 RBI13候选PDF记录与P4B、P5C审查报告。提出`review_id,reviewer_identity_verified,reviewer_role,claim_id,source_sha,source_clause_id,pdf_printed_page,device_context_hash,assessment_type(E2_source_entailment|E3_applicability),verdict(supported|contradicted|unresolved),justification,reviewed_at,reviewer_signature_ref`的Schema，必须区分用户确认（设备工况真实）与领域专家结论审查及教案抽取人/复核人；不可仅由LLM文本生成身份或签名。
设计匿名化最小工程现场事实、blind A/B差异分析：单Agent vs顺序多Agent vs受控并行、多种真实case人审指标：citation precision/recall、unsupported claim rate、false assurance、missing-info detection、abstention cost、latency/cost；synthetic20+14只作为开发测试，不算expert Gold。建议首批10-20个专家可独立判断的脱敏测试工况及至少双人标注冲突仲裁流程，但只存占位模板而非已审核结果。
制定由真人把GBT26610.1第13条补录到原Excel的签署SOP；当前只提供`scripts/merge_rbi1_into_original.py --check`，未拿到真抽取人不允许--apply伪姓名、不能宣称RBI485/total567；老师转换与终验仍沿固定程序。
报告 `docs/audits/P6C_REVIEW_GOLD_SPEC.md`，附schema与可执行纯校验测试（仅校验模板而不伪造签署），停在READY_FOR_OWNER_REVIEW。
