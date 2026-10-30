# P6 Owner 独立验收 / 反例审计（2026-10-28）

**裁决：P6-A并行编排原型 = CONDITIONAL_PASS_AS_EXPERIMENT，禁止直接并入生产主图；P6-B前端 = CONDITIONAL_PASS_AS_LOCAL_UI，须修复事实来源归属；P6-C人审契约 = CONDITIONAL_PASS_AS_DRAFT，禁止用于实际身份签核/专家Gold。P6整体本地开发基线通过，生产/公网上线/专业准确率结论均不放行。**

本轮没有改动老师`upstream/`PDF/XLSX、固定3个工具/五键返回、官方JSONL、backend/orchestration核心生产业务代码。新增Owner反例脚本、前端**审核专用跳过用例**、本报告及后续Codex任务书。无需将历史audit-only复现视为功能已修复。

## 实际读到的源证据
P6A审计`docs/audits/P6A_PARALLEL_EVIDENCE.md`和`orchestration/p6_parallel_audit.py`：独立StateGraph；EvidenceAuditor与Skeptic parallel fan-out；角色专属`audit_updates/skeptic_updates` reducer，Merge按`(run,claim,clause,agent,attempt)`去重；当前`orchestration/graph.py`正式路径未切换。样例数据合成，RULE_DEMO非多LLM。
P6B报告`docs/audits/P6B_UX_EVIDENCE.md`、`EngineeringReport.tsx`及实际1280桌面/390移动/E1抽屉截图：首屏已改为工况/未知/候选/补证据/来源反证；效果比P5阅读友好，但详细反证部分仍存在代码/英文名大量堆积，技术详情应折叠。
P6C`docs/audits/P6C_REVIEW_GOLD_SPEC.md`、`evals/p6c_review_schema.json`、`evals/p6c_validate_review.py`及`docs/P6C_HUMAN_REVIEW_PROTOCOL.md`：角色/真签署/Gold原则正确，无本人审核证据，身份签名只做形状预检，不是生产身份系统。

## Owner实测基线
- Python `./.venv-langgraph/Scripts/python.exe -B -m unittest discover -s tests -q`: **94/94 PASS**。
- P6A`tests.test_p6a_parallel_evidence`: **7/7 PASS**；`evals.p6a_parallel_evidence`20 synthetic场景成功：本轮parallel P50/P95 3.432/3.869ms，sequential helper 0.096/0.108ms；**前者包含图编译执行、后者是helper直接调用，口径不同，不可做加速比结论**。
- P6C `evals.p6c_test_review_schema`: 6/6 PASS，`evals.p6c_validate_review --check-template` PASS，无已签记录。
- 前端`node ./node_modules/vitest/vitest.mjs run --reporter=dot` 31/31 PASS、TypeScript `tsc -b` PASS、Vite build PASS 3103模块；后续新建的审核专用反例测试曾单独2/2重现现有错误，随后Owner改为`it.skip`，故其并入主测试后应该为31 PASS + 2 SKIP，不把错误实现的正向断言当作绿门禁。
- 官方`validate.py --final` PASS：554/554 clauses（RBI472, DM82）、200/200 trajectories。19个来源文件齐全；上游git tracked diff为空，仅原本未追踪的P2候选工作簿。
- 原RBI表`scripts.merge_rbi1_into_original --check`在**系统Python**环境PASS `READY_TO_APPEND 13 A474:W486 EXTRACTOR_SIGNED False`，未改原表。隔离venv不含`fitz`，因此同一预检在venv中导入PyMuPDF失败，属于非统一依赖入口，**不是源表变动**。后续需明确可重复运行环境。

## 复现的新缺陷（可执行复现实验）
### P1-1 并行Merge同键E1/E0冲突被输入顺序左右
`evals/owner_p6_adversarial_probe.py`实际调用`merge_findings([E1,E0],[skeptic])`得到E1，倒序`[E0,E1]`得到E0，`order_invariant=False`。原因`dict.setdefault`首次写入占位。既有7测试虽然验证了不同key分支乱序，却没有测试**同一key冲突**。重放可能保留过时审查等级，且可能悄然丢弃冲突。建议完全相同内容去重，冲突项保存并标`conflict_requires_review`或保守降到E0，附不一致的payload SHA和来源；任何排序/重试排列结果一致。

### P1-2 Merge信任来路级别，缺E0/E1硬上限
单独提供`AuditFinding(result={grade:'E3'})`，`merge_findings()`直接输出`verification_level='E3'`。虽然当前`_audit_branch`调用严格的`audit_claim`，因此`run_parallel_audit`常规路径仍E0/E1，但生产提升前要给 Merge 所有入口设置类型校验和**最高E1**，缺失/非法状态fail closed，并为E2/E3只接受未来真正授权人工review服务的独立升级通道。

### P1-3 P6C JSON Schema 与Python校验角色错配
构造`extraction_attestation`包含`reviewer_role='standard_extractor'`，`attestation_role='independent_reviewer'`：Draft202012Validator返回0 errors，而`validate_record()`返回角色不一致错误。两套被声称等价的结构审核路径互相矛盾，应在JSON Schema allOf if/then分别限定两种角色、重用一致的判定与negative tests。保留JSON Schema和stdlib校验各自边界，但正式写入前两者均应强制通过。

### P1-4 身份签名形式校验不可冒充真实人审门禁
实测生成**仅用于反例的合成`verified`记录**，设置`reviewer_identity_verified=true`及任意非空`reviewer_signature_ref`，`validate_record(require_verified=True)`返回[]。这与P6C协议“仅形状校验”不矛盾，但**未接外部签名证据时绝不允许业务使用函数返回空issues来提升E2/E3或标Gold**。未来要校验证书签发者、签名/身份、双人独立、资源哈希一致、可追溯时间/撤销等；禁止开发者通过配置布尔开关放行。

### P1-5 工程报告事实来源与run绑定缺失
前端`EngineeringReport.tsx/buildEngineeringReport`把任意`events[*].payload.summary`放入“现场已知”，即使是未经用户确认的Agent推断；而`lastUser`直接取当前会话最后一条user消息，不校验显示的旧run所属输入。新增`frontend/src/owner_p6_ux_adversarial.test.ts`，实际单独运行2/2重现两种错误（断言当前错误行为）；避免这个audit-only测试“证明缺陷通过”，已将两项改为`it.skip`等待P7B修复后将期待翻转、启用。正确应来自可信的用户现场声明/经确认的observations，并以run_id + immutable prompt/context snapshot为准；Agent推断属于`inferred`，不能到`known`。阅读旧run时不混合最新消息。

## 实际局限与P7建议
- 截图/本地用户体验：工程摘要主次结构显著改善，移动390长文本仍有大段反证材料，建议摘要限制长度并归并；保留审计详情全量，不可仅CSS隐藏未知来源字段而业务层误用。
- P6A尚无真正吞吐获益、真实LLM交叉验证或专业Gold；并行试验目前只读，不应伪造测评收益。正式接入前先做等口径A/B：相同固定工具调用+缓存相同、同图节点结构、建图时机、并发真实收益，观测claim质量/耗时/成本/false assurance。
- P6C规范未验证真实凭据、签名与专业资质；应先完成可签署小闭环，不建议马上拿真实厂区数据做公开Demo。
- 原始RBI Excel未合并13条：请真人署名后单独进行原路径只改摘录表、源哈希备份、官方convert/validate，禁止伪抽取人。

## 变更的Owner审查专用文件
`evals/owner_p6_adversarial_probe.py`、`frontend/src/owner_p6_ux_adversarial.test.ts`（2条暂跳过）、本报告、后续P7任务书。**没有修改P6生产代码**。
