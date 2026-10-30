# P7-B：工程摘要的事实来源与历史run隔离（仅frontend）
先读`docs/audits/OWNER_P6_INDEPENDENT_REVIEW_20261028.md`、`frontend/src/EngineeringReport.tsx`和`frontend/src/owner_p6_ux_adversarial.test.ts`。原31 Vitest PASS、TypeScript/Vite/Edge完整工况44事件链通过；P6B布局保持不推倒重来。
允许只改`frontend/`和`docs/audits/P7B_*.md`；不得改`backend/orchestration/upstream`或老师工具与RBI文件。
P1修复：
1. `已知现场事实`只来自明确绑定本轮run的用户输入、合法工况字段、经确认observations；`decision_summary`、agent输出`summary`、unverified inference全部标推断/待证，严禁混入已知。需要保留 reported/observed/inferred/unknown状态、字段来源和必要时input timestamp；防止已知=设备已损伤的伪推论。
2. 查看历史旧run时，不用当前conversation最后一条user消息；如当前已有API `GET /api/runs/{rid}`不含question/context，必须设计从历史消息与事件的可回溯运行关联或在创建run时仅缓存不可变prompt快照（注意跨设备/清理浏览器缓存不可假装能恢复）；如需新后端只读API，提出合约到下轮P7A以外的集成任务，不能偷偷改backend。可信度不够就显示`来源待确认`而不是错配。
3. Owner新增2条`owner_p6_ux_adversarial.test.ts`目前skip且断言旧BUG；先改成期待正确行为并启用，新增历史切换与恶意agent-summary负例测试，再全量Vitest/TypeScript/build、Edge+FastAPI+SQLite+SSE完整工况和两run历史恢复。截图桌面1280/390，信息层级自如、未超范围。
4. 右侧反证长段中文、标准ID冗余做折叠/按claim归组，严禁删真实审计证据、禁CSS隐藏错误风险级数据继续泄漏。
交付`docs/audits/P7B_KNOWN_FACTS_UX.md`，含完整运行身份绑定方案、失败fallback、证据及不支持项；STOP READY_FOR_OWNER_REVIEW。
