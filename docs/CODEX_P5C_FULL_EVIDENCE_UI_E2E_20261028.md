# Codex P5-C｜浏览器完整证据流正向E2E/审查UI可读性（只改frontend/）
先读`docs/audits/OWNER_P4_INDEPENDENT_REVIEW_20261028.md`、`docs/audits/P4C_UI_EVIDENCE.md`、`docs/audits/P4C_EDGE_E2E.json`，以及`frontend/scripts/p4c_edge_e2e.mjs`。当前24个Vitest和现有缺工况E2E为基线，不可删除。

边界：只改`frontend/`与`docs/audits/P5C_*.md`。不改`backend/`（P5A正在独立修改）、`orchestration/`、`upstream/`、老师三工具、Excel。

验收：
1. 在真实Edge CDP本地E2E里明确输入`material=碳钢`,`medium=氯化氢`,`equipment_type=换热器`，问题为`塔顶水样pH 5.8，铁离子 4.1 mg/L，尚未测厚，可能的损伤机理？`；真实FastAPI→LangGraph→冻结三工具→SQLite→SSE（不mock）。
2. 必须观察非空`reference_added`/claim_added/claim_checked/requires_human_review以及不同E0/E1来源记录、2条或更多有效claim；移动/桌面截图中点开来源抽屉，验证CID、印刷页、canonical hash/quote、来源门禁和unknown状态展示，无凭据不出现E2/E3或具体L等级。业务风险等级不能靠CSS隐藏而仍在DOM或JSON中泄露。
3. 断流replay恢复所有claim/来源；快速切换两个会话，无交叉串线；在1280/1440/390与深色/长中文下截图验证，console 0错误、API返回200。
4. 审查图在267px的侧栏可小，但应有`放大/独立抽屉/全屏图`路径，保证Agent节点字至少可读；未发生边不伪造，跳过节点明确识别；Claim按claim_id聚合最新状态，时间线保留原事件。
5. 保留现有24项测试，新增行为回归至至少30项，TypeScript和production build通过；禁止引入新的重型GUI框架、外传标准PDF或传真实私密资料。
交付`docs/audits/P5C_EVIDENCE_UI_E2E.md`及真实本机截图、请求状态、run_id、claims和事件计数，不以空工况E2E冒充完成；停在READY_FOR_OWNER_REVIEW。
