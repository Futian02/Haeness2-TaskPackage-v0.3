# P6-B 工程报告 UX 验收记录

**状态：READY_FOR_OWNER_REVIEW**（本地真实 Edge E2E 已通过；未部署公网、未提交 Git）。

## 范围与实现

本窗口只改 `frontend/` 与本报告。没有修改 `backend/`、`orchestration/`、上游教师工具、RBI Excel、PDF 或正式 JSONL。

- `frontend/src/EngineeringReport.tsx`：从当前会话用户输入、结构化 claim 检查项及 Skeptic/反证事件派生确定性摘要，呈现已知输入/未知字段、候选机理、补证据建议、E0/E1来源与反证；unknown 不补默认值，`current_run_source` 之类来源门禁不误标为现场未知。
- `frontend/src/App.tsx`：摘要优先；来源抽屉改用中文标签，并将UUID/hash/原始JSON、复核历史和详细反证放在默认折叠的审计详情；显示E1“条款已定位，但专业适用性待复核”和E0“来源不足”。
- `frontend/src/AssistantMessages.tsx`：超过500字的 assistant 长报告默认收起原文，点击后展开完整内容。
- `frontend/src/styles.css`：摘要卡响应布局、移动端单列、44px可操作区域和键盘焦点样式。
- `frontend/src/App.behavior.test.tsx`：补充摘要、E0/E1状态、反证与长报告折叠行为回归。
- `frontend/scripts/p5c_full_evidence_e2e.mjs` 与 `frontend/scripts/p6b_ux_e2e.mjs`：报告计数拆分为 `reference_event_gates` 与 `claim_grade_counts`；引用事件和 Claim grade 各自统计，不再混用母体。P6B脚本输出到 `frontend/evidence/p6b/`。

没有把 `RULE_DEMO`描述为多LLM；没有把E1升级为E2/E3，没有给出L级设备风险结论；机器Claim仍是`unresolved/requires_human_review`。

## 实际命令与结果

在 `frontend/` 执行：

```powershell
node ./node_modules/vitest/vitest.mjs run --reporter=dot
# Test Files 4 passed (4); Tests 31 passed (31)

node ./node_modules/typescript/bin/tsc -b --pretty false
# PASS，exit 0

node ./node_modules/vite/bin/vite.js build
# PASS；3103 modules transformed；build 1.19s

node ./scripts/p6b_ux_e2e.mjs
# PASS；Edge CDP 127.0.0.1:9222 + Vite 127.0.0.1:5173 + FastAPI 127.0.0.1:8000
```

实际E2E结果保存在 [`frontend/evidence/p6b/P6B_FULL_EVIDENCE_E2E.json`](../../frontend/evidence/p6b/P6B_FULL_EVIDENCE_E2E.json)：run `2580424b-7b55-4df1-9094-abd1b77cf579` 完成，44条连续SSE事件(1–44)、2条Claim(E1×1/E0×1)、7个reference_added、2个disagreements；所有Claim均未决且要求人工复核。`after_sequence=5` replay返回39条、从6开始；刷新后由SQLite重放还原44条与2张Claim卡；会话切换未串线。UI实际打开E1、E0和reference来源详情、放大图；390px移动端及1440px桌面检查通过。API状态全部200，`console_errors=[]`，页面无横向溢出。

计数现已分开：7条 reference event 都是原始 `E0` 门禁事件（`reference_event_gates={"E0":7}`）；结构化Claim分布为E1=1、E0=1（`claim_grade_counts={"E1":1,"E0":1}`）。不能把这两个统计相加成引用总数。

## 浏览器证据

均位于 `frontend/evidence/p6b/`：

- [桌面工程摘要](../../frontend/evidence/p6b/P6B_ENGINEERING_SUMMARY_1280.png)
- [E1来源抽屉](../../frontend/evidence/p6b/P6B_E1_SOURCE_DRAWER_1280.png)、[E0来源抽屉](../../frontend/evidence/p6b/P6B_E0_SOURCE_DRAWER_1280.png)、[reference来源抽屉](../../frontend/evidence/p6b/P6B_REFERENCE_DRAWER_1280.png)
- [完整审查图](../../frontend/evidence/p6b/P6B_GRAPH_EXPANDED_1280.png)、[SQLite刷新恢复](../../frontend/evidence/p6b/P6B_REPLAY_RESTORED_1280.png)
- [390px移动端](../../frontend/evidence/p6b/P6B_MOBILE_390.png)、[移动端来源抽屉](../../frontend/evidence/p6b/P6B_MOBILE_SOURCE_DRAWER_390.png)、[1440px桌面](../../frontend/evidence/p6b/P6B_DESKTOP_1440.png)
- [深色模式](../../frontend/evidence/p6b/P6B_DARK_MODE_1280.png)、[长中文输入](../../frontend/evidence/p6b/P6B_LONG_CHINESE_1280.png)

## 失败与处理

1. 第一轮Vitest 28/31：旧E1测试仍期待反证字段默认展开、历史事件只渲染一份；产品现在把复核历史/反证移入折叠区，更新回归断言为展开后核验。新增长报告测试也揭示assistant-ui runtime仅承载显示内容，不适合以message primitive作原文档案；改为将长文本运行消息压缩成提示，同时在可访问`details`中保留完整原文。最终31/31通过。
2. 第一轮P6B Edge脚本使用旧字段名查找hash/quote，和已本地化且默认折叠的审计字段不一致；第二轮明确打开“原始证据与审计详情”，并按中文标签验证。之后真实E2E通过。产品来源字段不丢失。
3. 初次截图/JSON曾临时由脚本写入 `docs/audits/`，发现超出本窗口严格审计文件边界后，逐项移至 `frontend/evidence/p6b/` 并修改P6B脚本输出目录，再完整复跑E2E。`docs/audits/`最终仅新增本报告。

## Owner复核点与边界

- 摘要中的“已知”来自用户消息和本轮事件；没有输入的现场条件继续列作未知/建议补证，不推导失效概率、后果、风险级别或检验周期。
- RULE_DEMO结果只用于本地演示及UI链路验收，不代表真实模型准确率或专家认可。
- E1只说明条款可定位、专业适用性仍待复核；E0代表来源不足；源JSON/hash默认折叠。
- 本窗口结束在`READY_FOR_OWNER_REVIEW`。没有公网部署或Git索引/提交操作。
