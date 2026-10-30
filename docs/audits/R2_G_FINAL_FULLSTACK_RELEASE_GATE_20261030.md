# R2-G 最终集成与全栈发布门（2026-10-30）

## 结论

**STOP_FIX_REQUIRED / NO-GO（完整Owner UI验收未闭合）**。R2-G 已完成可复现缺陷修复、A2候选索引只读接入、匿名新设备上下文隔离、P0安全拦截补强、64条回归实际执行、前端回归、临时SQLite后端运行、Edge桌面/移动真实普通聊天 smoke。不能签发 `GO_ISOLATED_OWNER_UI_TEST`：完整真实Edge专业A/B、SCC、多轮更正、全场景SSE重放、来源证据和失败恢复未由浏览器自动化实际跑完；全量 Python unittest 在项目venv仍有一个 `fitz` 可选依赖导入ERROR。因此保留 `STOP_FIX_REQUIRED`，不得将普通聊天 smoke 等价成全验收。

生产、默认V2、真人工程判断均为 **NO-GO**。无真实付费模型调用、无正式数据写入、无老师upstream修改、无8000/8001服务触碰/重启。V2/专家候选默认关闭，运行模式仍 `RULE_DEMO`。

## Gate 0 — 基线与边界

- 按合同阅读 `AGENTS.md`、`docs/PROJECT_STATUS_CURRENT.md`、R2 Owner precheck、G execution contract，以及关闭文档要求的A1/A2、B1/B2/C/D/E/F/QA交付物。A1/A2分别位于 `docs/data_quality/`，并非缺失；未重启六路开发。
- 预检已经记录的老师冻结文件 `upstream/05_提交区/clauses.jsonl` SHA-256 为 `a8151797ba15a6a7452dd83aaec9fab4c0a815724ca45062eb1e2bac7b4d49ef`；本次验证结束仍只读。upstream 初始工作树存在既有 Excel 修改/未跟踪备份文件，未处置、未清理。
- 端口只使用隔离 backend `127.0.0.1:8878` 和 Vite `127.0.0.1:5174`。正式/旧端口8000/8001没有由本次任务启动或重启。隔离SQLite位置：`%LOCALAPPDATA%\Temp\aetheris-r2-shadow-c84djwg4\shadow.sqlite3`；启动器删除provider凭据，健康响应 `llm.configured=false`。
- 关键启动/源文件/测试文件的修改前SHA及备份清单在 `%LOCALAPPDATA%\Temp\r2-g-backup-20261030-125806`。不得用全仓重置还原；Owner如需回滚，只按该清单逐文件恢复，并复核其前后变更。

## Gate 1 — P0旧R10兼容及64题

在固定的项目venv下先复现 Owner 记录的4 FAIL、2 ERROR。根因分别是：概念性SCC题的错误“必须调工具”fixture、10MPa总压被误当H2S分压的错误fixture、失败case中途抛异常导致去重hash只记到50、health capability字段迁移、两个子进程E2E写死旧合同号。对照新API/产品合同修正断言与题目语义，没有删除测试、缩小样本数或放宽安全门。

- `P0-N-01` 调整为概念性F1，不要求无意义工具调用；补充SCC必要概念断言。
- `P0-X-04` 保留总压力事实，但不伪造介质及H2S分压。
- health断言现在分别检查 `flags.expert_guidance_candidate` 和 `capabilities.professional_guidance`；临时SQLite API测试使用 `aetheris-r2.0.0`，并实际执行响应、终态及助手答复断言。
- 64条 authored regression逐题完整执行；最终重复题hash为52个唯一问题。新增反例断言阻止未知介质/分压被补造。

最终命令及结果：

```powershell
.venv-langgraph\Scripts\python.exe -B -m unittest tests.test_p0_expert_guidance tests.test_r9a_industrial_candidate tests.test_p12_context_flow -q
# Ran 50 tests ... OK
.venv-langgraph\Scripts\python.exe -B -m unittest tests.test_p13_router_hypotheses tests.test_r2_safety_claimgate -q
# Ran 15 tests ... OK
```

总计65项定向集成/安全测试通过。另新增55条B1红队语义组合（55/55拒绝不受支持安全结论/来源ID或范围错配），并修补“裂纹已排除，可维持生产”“可恢复运行”等漏过变体；3条相关红队测试通过。

## Gate 2 — A2索引接线及来源适用性边界

`orchestration/r9_industrial_candidate.py` 增加只读A2候选指针检索；按来源哈希/manifest校验索引，候选仅作 `E0/UNKNOWN` 指针，`may_support_claim=false`，不扩充老师工具、不把来源存在或词面命中提升为专业相关性/适用性，也不直接引用为结论。事件只公开查询SHA、索引版本、authority及限量非敏感指针，不暴露原始检索query/snippet。

P13旧期望曾将任意10条generic source当成假设。修正为：无主题重叠时保持10个来源指针的E0/UNKNOWN状态，不生成假设。当前A2 64个作者合成query Top-5非空覆盖从2/64增加到8/64（初始A2报告基线）；这只是候选覆盖变化，不是Precision/Recall、专业召回或安全通过率。A2专业适用性仍无真人Gold；S3自动候选0正式批准。壳体磕碰/辐照脆化、HCl侧线和49–66℃局部析出等已知召回误差仍待人工审查。

## Gate 3 — API对象scope、来源及安全门

- `backend/api.py` 在合并历史前解析当前问题；识别 `new_object_scope` 后切换scope、跳过旧设备memory，并将断言限定在当前对象scope。匿名设备后续轮次无字段时不向前恢复旧对象事实；scope写入context与事实存储。
- `backend/store.py` 的确认上下文携带 `_object_scope`；跨匿名设备及跨会话临时SQLite回归已新增。
- 专业答案组合约束拦截未知证据下的设备安全处置结论。修正了最初安全正则的误报（普通“合格人员结合设计资料、运行条件”不能被错误判成设备批准），再以55条组合红队样例复验。
- 引述原文继续以 `原文短摘`、来源和范围作显式标注；安全判定仅豁免有来源归属的原文引述行，模型生成字段仍经过结构化及可见文本校验。
- A2 trace经真实run/API/SSE事件路径断言。teacher tool数量仍为3。

## Gate 4 — 全量回归与影子端到端

### Python全量

```powershell
.venv-langgraph\Scripts\python.exe -B -m unittest discover -s tests -v
# Ran 452 tests in 87.036s
# FAILED (errors=1, skipped=3)
```

单一ERROR是`tests/test_p16_a_evidence42.py`在该venv导入失败（缺少 `fitz`/PyMuPDF），不是测试断言失败；3个Phoenix/OpenInference测试因各自可选telemetry stack未安装而SKIP。将P16单独交给已安装PyMuPDF的系统Python pytest执行：

```powershell
D:\computer learning\Python learning\python\python.exe -B -m pytest tests/test_p16_a_evidence42.py -q
# 5 passed in 0.67s
```

补充验证：

```powershell
.venv-langgraph\Scripts\python.exe -B upstream\04_接口文档\validate.py --final
# 554/554 clauses、200/200 trajectories通过
.venv-langgraph\Scripts\python.exe -B upstream\05_提交区\_selftest_tools.py
# 17 PASS, 0 failures
```

初次前端全套运行出现单个5秒超时的异步flaky用例；单项复跑通过。未改测试阈值或预期，随后完整重跑：

```powershell
cd frontend
npm test -- --run
# 20 files, 128 tests passed
npm run typecheck
# pass
npm run build
# pass; Vite reports 621.26kB JS chunk exceeds 500kB advisory threshold
```

### 真实Edge桌面/移动普通聊天smoke

真实Edge 142分别以桌面1440×900和移动390×844打开本地Vite，由代理连临时SQLite后端；完整运行 `你好` → API创建 → SSE消费 →事件重放→SQLite助手消息持久化→终态 `run_completed`。两组均无console errors；UI显示回答，接口合同及后端运行指纹和磁盘一致。组件高度在视口内，移动无水平溢出。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/r2_browser_e2e.ps1 -Browser Edge -ApiBaseUrl http://127.0.0.1:8878 -FrontendUrl http://127.0.0.1:5174 -OwnerApproved -HelloSmoke -Viewport desktop -OutputDirectory docs/audits/evidence/r2_g_20261030
# PASS, Edge/142, run 0e1377bf-5156-4083-b03f-ef05a7480556, context_resolved→intent_routed→run_completed
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/r2_browser_e2e.ps1 -Browser Edge -ApiBaseUrl http://127.0.0.1:8878 -FrontendUrl http://127.0.0.1:5174 -OwnerApproved -HelloSmoke -Viewport mobile -OutputDirectory docs/audits/evidence/r2_g_20261030
# PASS, Edge/142, run 857b62a8-3599-41d8-bd4f-433719b3056a, context_resolved→intent_routed→run_completed
```

截图与JSON原始证据：

- 桌面欢迎页：`docs/audits/evidence/r2_g_20261030/Edge_desktop_20261030_131435_welcome.png`
- 桌面聊天完成：`docs/audits/evidence/r2_g_20261030/Edge_desktop_20261030_131435_hello.png`
- 移动欢迎页：`docs/audits/evidence/r2_g_20261030/Edge_mobile_20261030_131438_welcome.png`
- 移动聊天完成：`docs/audits/evidence/r2_g_20261030/Edge_mobile_20261030_131438_hello.png`
- Edge证据对象：`docs/audits/evidence/r2_g_20261030/Edge_desktop_20261030_131435.json`、`Edge_mobile_20261030_131438.json`。

**未完成的浏览器情景**：普通聊天smoke先前确实桌面/移动均通过，但它不覆盖专业旅程。完整CDP编排尝试1未获得Edge页面target；随后修正runner后端源指纹payload为base64 JSON、前端HTTP探测改为`curl.exe`（pwsh的`Invoke-WebRequest`在本机抛NullReferenceException）。再次执行原runner通过健康/磁盘指纹、HTTP和Edge target阶段，但Node/CDP随后抛出仅显示`Error: Uncaught`的NativeCommandError，未生成新场景证据。没有绕过指纹自检、没有冒充完整浏览器通过。首次旧runner错误`/runs`响应按`{runs:[]}`对象处理已修复。完整A/B、SCC、多轮更正、浏览器里失败恢复与专业来源证据仍需定位Node/CDP异常后重新实跑；现有Python临时SQLite集成覆盖不替代真实浏览器用户旅程。

## 运行源码指纹与安全状态

- 后端合同：`aetheris-r2.0.0`
- 后端运行/磁盘源指纹：`sha256:51dcdca504fc13eb4ae4e884ee3b35ec2018cec81d25a9b95c51ded60968b7be`
- 前端源码指纹：`826730eb3224622ed24fa54789a6caad35e08db3e137c30a5647eeca86e567b0`
- Python运行时：3.11.9；Node：24.11.1；Edge UA：`Edg/142.0.0.0`
- backend health：`default_mode=RULE_DEMO`、`llm.configured=false`、`flags.expert_guidance_candidate=false`、`flags.v2_agentic=false`、`teacher_tool_count=3`。
- 进程/健康记录：`%TEMP%\r2_g_shadow_parent.log`；全量测试/前端/老师验证日志见 `%TEMP%\r2_g_python_full2.log`、`r2_g_p16_system.log`、`r2_g_frontend_vitest2.log`、`r2_g_frontend_typecheck.log`、`r2_g_frontend_build.log`、`r2_g_teacher_validate.log`、`r2_g_teacher_tools.log`。

## 剩余门槛与恢复步骤

1. 在隔离shadow中定位Node/CDP的`Error: Uncaught`（以及独立浏览器runner未找到页面target的首轮情况）；base64 JSON指纹传递与前端HTTP探测已修，保持磁盘/运行指纹比较严格。检查CDP异常必须输出完整exception stack/target process diagnostics，再推进场景。
2. 添加并运行桌面/移动浏览器旅程：专业A/B、SCC概念、多轮事实纠正、同CID匿名新设备及新会话隔离、SSE断流后重放、真实UI来源证据显示、模型不可用失败后RULE_DEMO恢复。保存每一程页面截图、run ID、events与source IDs。
3. 在项目venv统一安装/锁定PyMuPDF，并重新完整跑 `unittest discover`；确认3个telemetry skip有意且仍可独立执行。
4. 持续保持A2 `E0/UNKNOWN/may_support_claim=false`；安排来源适用范围人工抽检及Gold创建，尤其review旧风险假召回。未获人工批准前不宣称专业适用性/召回验收。
5. 再由Owner独立复核并决定是否给 `GO_ISOLATED_OWNER_UI_TEST`；真人gold、教师签核、正式服务切换仍须另行授权和评审。

## Owner下一阶段决策建议

将当前产物作为可复核的离线候选留存，不执行部署或线上迁移。先批准仅限本地shadow的Edge E2E harness启动/序列化修复与项目venv的可选测试依赖统一；本报告中的 `STOP_FIX_REQUIRED` 解除条件逐项完成、证据包复核后，再由Owner单独决策隔离UI测试。任何来源可找到不代表来源适配当前设备，更不代表设备安全结论成立。
