# Owner｜Aetheris网页无法发送问题：运行时版本错配与兼容修复（2026-10-29）
**状态：ROOT_CAUSE_CONFIRMED / FRONTEND_LEGACY_COMPAT_BUILT_AND_SERVING / LIVE_SEND_NOT_REPRODUCED_YET / BACKEND_UPGRADE_PENDING_OWNER_APPROVAL**。

## 1. 精确事实
用户浏览器截图提示“与服务的连接中断，本轮没有确认完成”，不是证据能直接证明断网或模型故障。`frontend/src/api.ts`把所有非RunStreamError的postRun异常一律当`connection_lost`展示，包含422 schema、404、解析错误等。

本机`127.0.0.1:8000`健康接口200；监听PID **59120**，创建于2026-10-28 21:54:56、Python.exe；父进程使用本机venv。运行中的`/api/model-profiles`返回404，当前磁盘`backend/api.py`已定义该路由。运行中OpenAPI `RunIn`仅接受`question/equipment/equipment_type/material/medium/operating_condition/field_evidence/mode/file_ids`且`additionalProperties=false`。当前前端始终POST `web_mode`和`allow_sensitive_web_search`，可选`model_profile_id`；旧Pydantic接口会返回HTTP422，不会创建该请求的Run。**因此不是网络断连，而是新前端+旧后端接口不兼容**。当前`frontend/dist/index.html`的SHA与8000 GET根主页完全相同，证明旧Python动态提供新前端静态包。

另通过GET只读扫描最近65个会话：近期Run中48 completed、15 queued，其余无Run；294个会话在列表中。15个queued可能是断连/测试/未发起stream造成，不推断数据丢失，也不能清理用户SQLite。请在批准后单独审计运行数据，不要自动删除。

## 2. 已修代码（自有前端）
`frontend/src/api.ts`：
- `ApiHttpError`保留HTTP状态与服务响应，专门识别旧FastAPI 422，仅当**全部**校验错误都是 `extra_forbidden` 且字段属于 web_mode/web_search_enabled/allow_sensitive_web_search/model_profile_id 时认定旧合同。
- 对普通自动/关闭联网、未显式选择模型的输入，第一次全量POST返回旧合同422后，**最多重试一次**旧RunIn允许的字段（含所有原始问句、设备信息、文件ID）。首次422是模型校验失败，不创建run，第二次才创建。
- 显式联网on、许可敏感联网或显式model_profile_id时**不降级**，返回明确BACKEND_VERSION_MISMATCH；不悄悄跳过用户明确要求。
- 成功降级标`legacy_compatibility`用于UI解释，适配不绕过新的专业/隐私功能，而是明确指出旧服务无法运行这些能力。

`frontend/src/App.tsx`：
- 修复“重新连接”按钮：现在检查health、重新加载列表及真实选中会话/Run/SSE历史，而非只刷新侧边栏。
- 旧后端降级成功给可见提示，明确旧服务的自动联网/独立模型配置及V2不可用；显式联网/选模型错配显示准确错误，不再误说“网络断开”。

`frontend/src/api.legacy-contract.test.ts`新增5项：422准确降级、现代后端不重发、显式联网不可降级、显式模型不可降级、无关422不得重试。

## 3. 本地实测
- 前端`Vitest` **123/123**（18文件），TypeScript build PASSED，Vite正式构建PASS（主chunk约616 KB警告非阻塞）。
- 本机8000 GET /：和新的`frontend/dist/index.html`逐字节一致；引用新资源`/assets/index-D6-mJH8m.js`，在8000实际可GET且包含`BACKEND_VERSION_MISMATCH`兼容代码。**已更新运行服务实际提供的静态前端，不需要重启旧后端。**
- 8000仍返回`/api/model-profiles` 404、OpenAPI仍旧schema：**没有更新正在运行的Python后端**。
- **未对用户真实SQLite执行POST/删除/迁移，未自动发送真实DeepSeek问题，也未进行浏览器人工点击确认**，因此只能称“兼容功能经模拟HTTP测试+实际静态资源上架证实”，不可声称真人网页E2E已经PASS。

### 真实浏览器只读布局检查（新增）
通过本机Edge独立临时Profile、1717×813窗口的headless CDP只读DOM测试（浏览器实际innerWidth1687×innerHeight717）：sidebar 258px、topbar57px、composer在y424至717可见、textarea y478至543可见、发送按钮y609至650可见；294个侧边栏项目且有1个选中。发送按钮初始disabled=true是因为探针没有输入问题，**不是排版导致不可见**。没有自动填写/提交任何问题，也未执行真人浏览器发送E2E；用户截图可能是局部剪裁或有独立缩放状态。测试入口`scripts/owner_local_ui_layout_readonly.py`（Edge安装路径需匹配本机）。

## 4. Owner和用户下一步
1. 在当前网页按 Ctrl+Shift+R 或 Ctrl+F5 硬刷新，确认拿到`index-D6-mJH8m.js`；联网模式先选“关闭”或“自动”，不显式选择旧版不支持的个人模型profile，发送一条**普通简单问题**。首次旧合同422会自动安全重试为旧字段。如果仍失败，保留该轮run_id、HTTP状态和时间（不要贴API密钥、消息机密）；不要反复创建100次Run。
2. 旧后端正式升级/重启需要**受控停机、备份DB、核实存活worker、验证最新代码依赖与系统环境**，且确认影响历史会话与queued作业。此次未进行，用户批准后可由Owner执行。真正需要新模型Profile、联网、V2 / SSE修复的完整功能，必须升级运行中的服务。
3. 之后对所有启动脚本增加`API_CONTRACT_VERSION`或`/api/health.capabilities`及前端握手，禁止前端静态资源自动追最新版而API长时间旧版。端到端E2E要求重新打开浏览器验证发送、SSE、重连、历史会话恢复；此Gate尚未过。
4. 旧Codex技术报告“源码测试通过”不代表用户浏览器当前运行版本，未来必须审服务PID启动时间、OpenAPI能力、前端bundle哈希和实测浏览器请求。
