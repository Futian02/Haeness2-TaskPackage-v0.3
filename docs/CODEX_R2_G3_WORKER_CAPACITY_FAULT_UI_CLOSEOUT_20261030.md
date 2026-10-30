# R2-G3｜最终 UI 可靠性封口：429 queued、故障提示、草稿与幂等恢复（Owner 2026-10-30）

**状态：TARGETED_FIX_REQUIRED / G2_SPECIALIST_BROWSER_PASS / DEEPSEEK_NOT_TESTED / PRODUCTION_NO_GO。**
项目根 `D:\作业\竞赛\计算机设计智能体\机械智能体`。仅本机 Codex 自有文件/终端工作，不通过 DevSpace/远程本地代理；不修改任何`upstream/**`、真人审阅/原始PDF/Excel/JSONL、正式SQLite和密码；不停止/重启8000/8001；不擅自使用收费真实模型。保持R2-G2既有全部成功证据，主G唯一修改共享源，辅助Agent可读审计、测试、独立脚本。

## G2已经通过（不重复大施工）
G2证据`docs/audits/R2_G2_FINAL_BROWSER_PROFESSIONAL_E2E_20261030.md`及`docs/audits/evidence/r2_g2_20261030/`真实Edge1440×900与390×844：hello/SCC/A60/A80/B/同CID更正/新匿名对象/跨CID/来源E0/UNKNOWN/SSE Last-Event-ID无重复均有RUN/DOM/截图；452? 请以G2实际`451 unittest（0 FAIL/ERROR,3 SKIP）`+同venv P16 pytest5/5、前端128/128、教师554/200/17为基线。PyMuPDF 1.27.2.2/pytest 9.0.2已统一；不再认为它们是当前阻塞。DeepSeek `llm.configured=false`、`RULE_DEMO`。

## Owner新诊断：必须验证的具体代码风险
1. 后端`backend/api.py::stream_run`：Run POST成功后保持queued；请求`GET /api/runs/{rid}/stream`时`_worker_slots.acquire(False)`失败返回HTTP**429**、`detail.code=WORKER_CAPACITY`、`Retry-After:2`，**queued Run已经存在**，恢复应始终对**原rid**继续订阅，不能再次POST。
2. `frontend/src/api.ts::readSse`对所有非2xx直接抛通用`Error('SSE 连接失败 (429)')`，没有显式提取`WORKER_CAPACITY/Retry-After`；`consumeRun`最多5轮自动恢复并重放；如slot长期被占，最终可能变成通用`connection_lost`，而非queued等待状态。
3. `frontend/src/App.tsx::postRun`在createRun成功立刻清除`aether:pending-run-key`、`aether:pending-run-question`及草稿；若后续SSE 429/超时，`retry()`从最后一条消息重新`postRun(last.content)`，可能**创建第二个Run**；要区分“创建Run请求429、服务尚未接收”和“已创建Run、订阅429仍queued”。这是本轮最优先修的真实状态机缺口，非单纯新增E2E脚本。
4. `frontend/src/api.ts::RunRequestError`已将POST429映射`request_rate_limited`；后端`backend/api.py`也存在一般HTTP429 `RATE_LIMITED/Retry-After:60`，不要与stream WorkerCapacity429混淆。
5. `backend/api.py`本轮对model_profile缺失在创建前HTTP503，G2已证明API503→随后RULE_DEMO hello恢复，但**没有在真实UI点击并观察503失败卡、草稿、idempotency与恢复**；模型/工具运行后失败则有`error`/failed SSE code，必须经过真实UI校验。
6. `App.tsx`当前`retry`默认从最后一个user消息再调用postRun，语义需细分：`resume queued/running`应**same run_id, no new POST**；`retry POST after uncertain network`需重用原idempotency key和完全相同的请求体/会话；只有明确用户选择“作为新运行重试”（终态failed）才能产生新run，UI说明为新运行。Context/web/profile/附件变化时不复用旧key去提交不同body，否则409。

## Gate A：写失败测试，修实际状态机
- 为Run设计客户端可持久恢复记录（cid、runId、idempotencyKey、requestBody hash、status、lastSequence、retryAfter、draft/snapshot），对意外关闭和刷新可从本地+服务Run snapshot一致性校验恢复，浏览器本地不存API密钥/模型输出机密。
- 对SSE WorkerCapacity429引入可辨别类型`run_queued_capacity`、保留`Retry-After`、Run ID、queued状态；优先继续**GET同一run**并有界指数退避/手动`继续等待`，避免无限重试；用户可离开会话不终止Run。POST rate limited未创建Run时才按原幂等key+同body重试。
- UI给用户透明显示“任务已进入队列，服务繁忙；重新连接不会重复提交”。只有服务器明确terminal failed且用户明确要求新执行才创建第二个run。失败后原草稿/附件/用户修改不应被丢弃、覆盖或泄露给新会话；不会误将队列挤满的情况显示为模型拒答。
- 遇显式模型未配置或服务不可用HTTP503（在无付费配置shadow测试）、工具单步超时/Provider timeout、Provider rejected、输出空、上游429等失败，给各自可理解的错误状态。避免把内部trace/API key/完整标准原文暴露到UI。故障注入不得伪造成真实DeepSeek能力。
- 后端必要时加纯development+loopback+temporary SQLite下的精确fault injection入口/启动参数（默认关闭、严禁生产启用），不要暴露任意工具执行接口或新teacher工具；优先通过独立测试runner在进程内可控semaphore/MockProvider注入并让真实Edge连接该隔离服务。

## Gate B：真实Edge而非只有TestClient
- 后端shadow临时SQLite，单独端口（非8000/8001），清空provider credentials；测试前后健康/磁盘源码指纹严格相同。需要改源码则停止旧shadow→重新指纹冻结→启动新shadow。测试时模型故障只能用明确标记的合成provider/隔离FaultInjection。
- **场景1 Stream429**：UI创建Run拿到rid、semaphore=0使`/stream`429，核查HTTP detail.code WORKER_CAPACITY+Retry-After、Run=queued、前端状态卡和原文草稿/快照，然后释放slot；同**rid**再次订阅→event seq连续→1 assistant message→Run completed；`/runs`总数量仍=1。桌面/移动都真正发请求。
- **场景2 POST429**：在隔离shadow用现有限速门使POST429，确认没创建Run、草稿+幂等key保留；限流解除后重发相同cid/requestBody/key只创建一次。不要让重试吞掉用户新输入。
- **场景3 Model pre-run 503**：在UI明确选择未配置模型并真正点击发送，确认HTTP503在用户主界面显示正确，草稿保留、未留下queued/ghost Run，可切回RULE_DEMO后重试。当前G2只证明API级503，不足。
- **场景4 In-run tool/provider failure**：在sandbox显式注入受控工具超时和Provider拒绝/超时（不得接入真实供应商），允许Run创建并失败；UI类型化卡+脱敏trace+draft/retry idempotency语义、同RID只1 terminal+0或1 assistant按原失败合同；可以新建不同run时明确告诉用户“新一次执行”，不把旧run状态标成功。
- **场景5**：刷新/重连和切CID后上述状态必须可恢复、移动390×844与桌面1440×900不溢出。逐场景产出RunID/CID/HTTP headers/sequence/SQLite messages/DOM截图/源指纹/准确PASS/FAIL与原始JSON，不能通过伪造fetch Mock来声称真实UI通过。

## Gate C：回归与授权边界
- 同venv全`python -B -m unittest discover -s tests -v`与P16 pytest5/5；前端Vitest/TS/Vite build；teacher554/200/17，原JSONL SHA不变；S2.5 lease/CAS/双SSE、R2-G2真实专业A/B/SCC/上下文旅程全部留存且不少于核心冒烟复测。
- 模型候选`AETHER_EXPERT_GUIDANCE_CANDIDATE=0`、V2关闭不变；`RULE_DEMO`能作为隔离预览不代表DeepSeek准确性。未经Owner明确有界预算授权，不运行真实LLM压力/大批网络模型测试。
- 出具`docs/audits/R2_G3_WORKER_CAPACITY_ERROR_RECOVERY_GATE_20261030.md`、更新`docs/PROJECT_STATUS_CURRENT.md`。全部Gate A/B/C均通过可申请`GO_ISOLATED_OWNER_RULE_DEMO_UI_TEST`，缺浏览器真实证据则`STOP_FIX_REQUIRED`。即使GO隔离demo，正式工程设备结论/生产上线仍NO_GO（真人PDF审查/专业Gold/DeepSeek并未通过）。
