# R8 双Codex窗口交接单｜2026-10-28
用户决定：本轮只并行执行RBI原Excel数据补全和豆包式React UI；LangGraph社区最简循环案例待下一轮Owner对比和决定，**暂不启动第3个Codex窗口、不改正式Agent图**。

## Codex窗口A（唯一原RBI Excel写者）
详细设计：`docs/OWNER_R8A_RBI_PDF_EXHAUSTIVE_XLSX_DESIGN_20261028.md`
可直接发给Codex的提示词：`docs/CODEX_R8A_RBI_FULL_PDF_TO_ORIGINAL_XLSX_20261028.md`
目标：461页/六PDF，逐章表公式高覆盖清单、23列有源填充、原工作簿只改摘录表、教师converter/validator真实运行或真人身份缺失时如实BLOCKED。可复核原PDF印刷页与细胞diff，不伪造任何风险数值或抽取人/复核人身份。

## Codex窗口B（独立UI及Upload API写者）
详细设计：`docs/OWNER_R8B_DOU_BAO_STYLE_OSS_CHAT_UI_DESIGN_20261028.md`
可直接发给Codex的提示词：`docs/CODEX_R8B_DOU_BAO_OSS_UI_FILES_CONTEXT_20261028.md`
目标：复用assistant-ui ThreadList/Attachments 与 LangChain Agent Chat UI的交互经验、极简聊天+固定会话侧栏+单会话逐轮跳转+真本地附件上传/SQLite+可信服务端上下文快照+可展开真实Agent事件；不迁移Next.js/Postgres，不伪造LLM思维链。

## 并行写权边界
A仅`upstream/01_RBI标准/条款摘录表_RBI.xlsx`及R8A新增审计文件（只读其他教师数据源）；B仅`frontend/`、`backend/`中上传与会话最小增量、R8B新增测试和审计文件。不准任一窗口执行git clean/reset、修改教师3工具、改原PDF或更动另一窗口文件。两个Codex窗口各自`READY_FOR_OWNER_REVIEW`，Owner下轮对Excel做独立多PDF抽样核查、OOXML逐Sheet差异检查、teacher转换终验、前端浏览器上传/上下文/性能/安全复核。

## 下一轮LangGraph社区参考（只读研究，不在这两个窗口里改代码）
优先比较官方`https://docs.langchain.com/oss/python/langgraph/workflows-agents`的Router/Orchestrator-Worker/Evaluator-Optimizer与`https://github.com/langchain-ai/agent-chat-ui`的前端运行可视化。目标选择一个尽可能简洁的`Router → Investigator loop → Evidence Gate → optional Review → Reporter`图并用最小真实实验验证，不增加固定三工具之外的新老师接口。
