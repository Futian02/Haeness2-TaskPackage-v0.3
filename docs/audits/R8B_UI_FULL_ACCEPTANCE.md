# R8-B UI / Upload 全链验收

**状态：READY_FOR_OWNER_REVIEW（本地工程验收）；没有部署、没有提交。**

## 范围与实现

- 保留 React/Vite、FastAPI、SQLite、LangGraph 和现有 SSE wire；teacher tools 清单仍为三项。`RULE_DEMO` 在头部和运行快照显著标注，UI 不声称真实 LLM 或全历史记忆。
- `frontend/src/ConversationThreadList.tsx` 使用已安装 assistant-ui `ThreadListPrimitive` / `useExternalStoreRuntime` 对接真实会话数据，搜索、切换、创建、重命名连接 FastAPI/SQLite；对话内“问题 1…n”跳转到对应消息。
- `frontend/src/AssistantMessages.tsx` 使用 assistant-ui Thread/Message primitives 和 ReactMarkdown/GFM。输入区支持 Enter 发送、Shift+Enter 换行、拖放/文件选择、上传预览及显式选择本轮附件；右侧证据/执行审查默认折叠，事件仍仅来自 SSE。
- FastAPI 接口增量：会话重命名/归档字段、`POST /api/conversations/{cid}/files`、文件列表/预览/下载、`GET /api/runs/{rid}/input`。SQLite 新表 `conversation_files`、`message_attachments`、`run_attachments`；`runs.input_message_id` 迁移字段；run/user message/附件绑定在同事务内创建。
- Run 快照返回精确问题、结构化工况、显式选定文件、时间点前的历史消息 ID 与数量；历史消息被标记为“可用但未选择”，RULE_DEMO 不会伪称已读取或记住历史。刷新后通过服务器 snapshot 恢复，不依赖浏览器 localStorage 作为唯一来源。

## 上传安全与实测

- 白名单：TXT/MD/CSV/PDF/DOCX/XLSX/PNG/JPG/JPEG/WEBP；单文件 ≤15 MiB、每次 1–5 个；要求 multipart `Content-Length`，仅上传路由使用最高 `5×15MiB+1MiB` 总体限额，其他 API 原 128 KiB 限额保持不变。
- 服务端逐块落临时文件并累计 SHA-256；文件扩展名白名单、PDF/图像/ZIP 文档签名校验、UTF-8 文本校验、文件名叶节点清理；磁盘名为会话哈希目录+内容哈希，resolve 后限定在 upload root。跨会话相同内容使用分离存储键，读取/预览/下载必须同时匹配 conversation ID。失败路径清理暂存文件；重复内容在会话内按 hash 去重。
- 文本预览真实读取 UTF-8；PDF 优先 PyMuPDF，当前隔离运行时缺少 fitz 时用受限 stdlib text-stream fallback；扫描 PDF/复杂字体或图片/DOCX/XLSX 不声称已解析，保留 `stored_not_parsed`。
- 没有自动上传第三方模型；上传件只在用户明确选择后关联到 Run/user message，不自动进入官方标准/knowledge JSONL，也不改上游 Excel。
- 真 Edge CDP + FastAPI E2E：3 个会话×3 轮，真实 SSE 每轮 16 个事件且终态 `run_completed`；另外检查上传 TXT/PDF 与附件选择，刷新后服务端文件列表恢复。跨会话访问 404，异常扩展名/伪 PDF 分别 415，SQLite 外键关联由 `/audits/R8B_SQLITE_EVIDENCE.json` 给出。
- 最新 Edge CDP 结果：3 个真实会话、每会话 3 轮（9 次 SSE run），页面刷新后 TXT/PDF 附件卡片从 API/SQLite 恢复；3 个问题跳转按钮；移动视口 `innerWidth=390`, document/body `scrollWidth=390`；Runtime exception count 0。截图：[`R8B_edge_cdp_desktop_1280.png`](R8B_edge_cdp_desktop_1280.png)、[`R8B_edge_cdp_mobile_390.png`](R8B_edge_cdp_mobile_390.png)，日志：[`R8B_EDGE_CDP_E2E.log`](R8B_EDGE_CDP_E2E.log)。HTTP E2E：[`R8B_HTTP_E2E.json`](R8B_HTTP_E2E.json)。
- 独立 SQLite 实证：9 conversations、27 completed runs、27 user + 27 assistant messages、6 files、6 message attachment links、6 run attachment links、27 run input snapshots；3 TXT + 3 PDF 预览记录：[`R8B_SQLITE_EVIDENCE.json`](R8B_SQLITE_EVIDENCE.json)。这包含先前 HTTP 探针与最新 Edge CDP 共用的本地临时数据库，不代表生产数据。

## 验证命令 / 结果

```powershell
.\.venv-langgraph\Scripts\python.exe -B -m unittest discover -s tests -p 'test_r8b_*.py' -v
# 7 tests: PASS（含真实 multipart 文件落盘、文本/PDF 预览、签名拒绝、超限、6文件拒绝、隔离、Run 快照）
cd frontend
npm run typecheck
npm test -- --run
npm run build
```

- 新增 `test_r8b_upload.py`：7/7 PASS。
- Vitest：7 个测试文件、62/62 PASS（原 36 项和 R8B 新增 14 项以上；额外 12 项依赖/列表/状态行为核验）。
- TypeScript：PASS；Vitest 7 files / 62 tests PASS；Vite production build PASS。当前主 chunk 为 574.76 kB（gzip 175.18 kB），仍有 500 kB 建议拆分的构建告警。尝试 lazy-load ThreadList 后触发既有会话列表行为测试在 Suspense fallback 期间失败，已回退为同步导入并复测全绿；因此没有将 chunk 警告写成已解决。
- Python 全套使用隔离 `.venv-langgraph`：124 项中 123 PASS、1 FAIL。失败为既有 P6-A `test_merge_deduplicates_retry_but_preserves_distinct_attempts`（期望 E1、实际 E0）；本任务未修改该窗口逻辑/测试。完整日志：[`R8B_PYTHON_REGRESSION.log`](R8B_PYTHON_REGRESSION.log)。R8B 专项为 7/7 PASS，日志：[`R8B_BACKEND_TESTS.log`](R8B_BACKEND_TESTS.log)。
- 系统默认 Python 的老 Tenacity 报 `asyncio.coroutine` 缺失；因此 Python 回归统一使用项目已有 `.venv-langgraph`，未改任何 teacher dependency/tool。

## 未完成与 Owner 审查点

- 附件组件和输入 UI仍有项目定制部分；assistant-ui Thread/ThreadList primitives 已接入，但本轮未将现有 composer/上传 adapter 全部替换为 assistant-ui ComposerPrimitive/AttachmentAdapter。左侧会话显示逐条时间戳，尚未添加显式日期分组标题；其余新建、搜索、切换、重命名已由 UI/行为测试覆盖。功能链路已在 Edge 验证，建议 Owner 决定是否要求纯 primitives 迁移及显式日期分组。
- 审查/证据内容由真实 SSE 事件驱动；当前 graph 是 RULE_DEMO，不能展示为真实多模型/独立 LLM。
- E2E 为本机回环演示而非生产身份隔离；项目根 AGENTS 既有 production fail-closed 仍保留。
- R8-A workbook 有13条无签名 DRAFT，完整461页人工/视觉复核尚未完成；此UI任务未读/写源Excel/PDF，见 `R8A_RBI_FINAL_AUDIT.md`。
- 最终停在 READY_FOR_OWNER_REVIEW；没有做公开部署/提交。Vite、R8B Uvicorn 与 Edge CDP 测试进程已按精确命令行/PID 定向停止；复查后 8000/5173/9222 无监听。测试数据库/上传文件仅位于系统 Temp，未删除任何工作区文件。
