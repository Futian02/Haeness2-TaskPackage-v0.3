# P7-C：人审Schema与校验器一致性，权限闭合契约（仅evals/p6c*与P7C评测/文档）
先读`docs/audits/OWNER_P6_INDEPENDENT_REVIEW_20261028.md`、`docs/P6C_HUMAN_REVIEW_PROTOCOL.md`、`evals/p6c_review_schema.json`、`evals/p6c_validate_review.py`和`evals/owner_p6_adversarial_probe.py`。必须重现JSON Schema允许`reviewer_role=standard_extractor`与`attestation_role=independent_reviewer`错配，但stdlib拒绝。
允许修改`evals/p6c_*`、新增`evals/p7c_*`、`docs/P6C_HUMAN_REVIEW_PROTOCOL.md`、`docs/audits/P7C_*.md`；禁止碰backend/frontend/orchestration/upstream/老师三工具和原RBI Excel。
目标：
1. Draft202012 Schema与stdlib执行入口对role匹配、必要字段、日期、重复身份、status许可、hash格式等保持一致；对cross-validator differential生成至少40条正/负synthetic fixtures，错误角色两侧必须一起拒绝。模板本身unsigned仍允许结构校验但不允许verified。
2. 明确`validate_record(require_verified=True)`当前仅shape-validation，即使填写假`identity_verified=true`与虚构signature string也会返回[]。不能暗示已完成真实签署验证。设计单独`HumanReviewAuthority.verify_attestation(...)`接口契约：可信身份/签名服务、审核角色资质、撤销与有效期、资源hash/原PDF版本绑定、两名独立签署人、E2/已确认设备条件作为E3前置、冲突仲裁。默认fail-closed，**不得**在本任务中用布尔字段绕过真实认证或生成假记录。
3. 设计Gold采样验证和人工签署闭环的模拟测试（mock authority必须显著标synthetic，不能误入正式数据库）；实名资料需Owner授权并存受控系统；原表13条仍只许check-only。
4. 6项原测试+新增40条差分测试+官方validate全部通过，`OWNER_P6`审计坏例复现脚本不能作为修复通过证据；改用新增修复测试。
交付`docs/audits/P7C_SCHEMA_AUTH_CONTRACT.md`，注明`SCHEMA_ONLY_NOT_HUMAN_VERIFIED`，STOP READY_FOR_OWNER_REVIEW。
