# Codex P6-B：工程可读报告与移动审查体验（只改frontend/）
先看`docs/audits/OWNER_P5_INDEPENDENT_REVIEW_20261028.md`和`docs/audits/P5C_EVIDENCE_UI_E2E.md`，阅读P5C移动390、E0/E1、放大图截图，保持完整真实FastAPI/SSE/SQLite链路、前端测试30/30基线。
允许修改：`frontend/`和`docs/audits/P6B_*.md`，不动`backend/`、`orchestration/`、老师工具和Excel。可给前端增加**确定性报告视图变换**，从现有reporting/claim/observation/unknown字段生成可读卡，但不能把已有原始数据升级成设备定论，不许假装有新后端事件。
首屏改成：①已知工况与不确定值②可能机理（明确待核）③缺失的测厚/温压/年限等需补证据④正式来源记录（E0/E1）与独立反证摘要；长度过大的原始UUID/hash/英文JSON放进默认折叠的“原始证据与审计详情”Tab。
E1来源卡显示`条款已定位，但专业适用性待复核`；E0显示`来源不足`；绝不显示E2/E3或L级设备风险结论，保留run_id/序号完整回放/同轮来源的底层可见性。移动390应把工程结论和证据抽屉合理分层，中文500-1000字报告折叠并可展开，键盘焦点/按钮大小可用，视觉风格继续克制、不加第二套重型UI。
检查`P5C_FULL_EVIDENCE_E2E.json`中reference_gate_counts混合了ref事件E0和claim E1的计数口径，修报告脚本命名为独立`reference_event_gates`、`claim_grade_counts`，防止总数看似8 > 实际7。
执行Vitest≥30、typecheck、build、真实Edge完整工况SSE44量级/Claim2/E1E0/抽屉/刷新/移动测试，输出截图和 `docs/audits/P6B_UX_EVIDENCE.md`，停在READY_FOR_OWNER_REVIEW，不对公网部署。
