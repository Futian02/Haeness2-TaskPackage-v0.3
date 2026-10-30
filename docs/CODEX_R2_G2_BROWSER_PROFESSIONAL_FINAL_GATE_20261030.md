# R2-G2｜隔离UI最终验收尾项（Owner，2026-10-30）
**裁决：STOP_FIX_REQUIRED → 仅在实测全链后方可 GO_ISOLATED_OWNER_UI_TEST；NO_GO_PRODUCTION 仍保持。**
项目：`D:\作业\竞赛\计算机设计智能体\机械智能体`。本机Codex原生文件/PowerShell；禁止为本机读写调用DevSpace。A–F及G已有成果必须保留，不重新开展六路大改；**唯一源码写入Owner**，其他子Agent只读审计、并行独立测试。冻结老师upstream的PDF、Excel、JSONL、工具接口；不修改正式SQLite、历史会话、人工审核字段；不停止或重启8000/8001；不擅自付费调用LLM。

## Owner当轮独立复核（这些是新证据，不是Codex报告转述）
1. 直接读取`docs/audits/R2_G_FINAL_FULLSTACK_RELEASE_GATE_20261030.md`、最新`docs/PROJECT_STATUS_CURRENT.md`及Edge截图/JSON，真实截图桌面1440×900、移动390×844均可见“你好”及答案，输入区没有越界。桌面/移动JSON各自有真实run_id、连续事件sequence、run_completed、无浏览器console错误；目前**只有Hello Smoke**，不能证明专业主答。
2. `python -B -m unittest tests.test_p0_expert_guidance tests.test_r9a_industrial_candidate tests.test_p12_context_flow -q`：Owner重跑**50/50 PASS**。
3. `python -B -m unittest tests.test_r2_safety_claimgate tests.test_r2_graph_candidate tests.test_r2_context_memory -q`：**31/31 PASS**。
4. `python -B -m unittest tests.test_r2_browser_e2e tests.test_r2_api_contract -q`：**14/14 PASS**。这只是QA协议/后端API测试，非真实浏览器所有场景通过。
5. `cd frontend && node node_modules/vitest/vitest.mjs run && node node_modules/typescript/bin/tsc -b tsconfig.json --pretty false`：**128/128 PASS，TS通过**（首次从根目录执行导致vite.config读取错误，改为frontend cwd后正常）。
6. 官方`validate.py --final`**554/554+200/200**、`_selftest_tools.py`**17/17**，正式JSONL SHA：`a8151797ba15a6a7452dd83aaec9fab4c0a815724ca45062eb1e2bac7b4d49ef`。
7. 项目venv`fitz`/PyMuPDF均无，G完整unittest452项1 ERROR 3SKIP，P16另外以系统python pytest 5/5通过。要统一可复现环境，不能把分环境拆跑算单个全绿。
8. `scripts/r2_browser_e2e.ps1`现只有`-HelloSmoke`/欢迎页流程，没有长期保留的A/B/SCC/多轮/失败恢复完整浏览器runner；G自述的临时Node/CDP扩展因`Error: Uncaught`中途异常，没有完整JSON/截图证据。

## 精确执行合同（次序严格）
### A. 修复浏览器runner可观测性与复现能力
- 保留已通过的hello smoke及全部runtime/disk/backend/frontend指纹 fail-closed，不得移除安全检查来过测。
- 给`Runtime.evaluate`失败记录`exceptionDetails.text`、`exception.description`、`exceptionDetails.stackTrace.callFrames`、evaluate expression短哈希、CDP target url/ID、Node stdout/stderr、browser PID、console/network错误、真实退出码，避免只显示“Error: Uncaught”。
- CDP命令Promise增加有界超时与page target重试/识别新窗口机制；PowerShell NativeCommandError要保留原Node堆栈。避免原脚本中用隐式值代替RunId、误把`/runs`对象当array。独立新增`scripts/r2_browser_journeys.ps1`或同等可重复命令，别用一次性命令行拼巨型JS后丢失。
- 尽量保持E/F交付sha不变，如须变源码则重新指纹冻结/重启**隔离shadow**，不触碰正式服务。

### B. 真实Edge两种视口的专业旅程（必须真正发请求）
至少 desktop1440×900、mobile390×844：
1. Hello 基线；SCC概念无需材质能解释拉应力+敏感材料+腐蚀环境+裂纹，主答真实可见；
2. A：300系列不锈钢/碱式酸性水/60℃弯头减薄；Run snapshot保留已知材质/介质/温度；有合法老师source ID（若仅E0必须标待审）；不重复问已提供信息，不给设备风险等级；再测试80℃不能因为5.23局部49–66℃而硬排除整种机理；
3. B：壳体磕碰/停机维修/验收；多查询至合法teacher返回来源；专业主答需给具体条件化危险征象与现场检查，TSG8.5.8只是条件参考而非无条件凹坑阈值；不能给“可继续运行/无需停机”的未经证实许可；如果来源0也必须提供一般安全调查。
4. 同CID修正材质/介质，原始用户事实新的覆盖旧的但留审计；同CID“另外一台未命名设备”不得沿用前台设备事实；跨CID不串料。
5. SSE断流→`Last-Event-ID`或events replay接续、事件不重复、同Run仅一个assistant消息；被限流返回429保留queued、再次订阅/恢复；故意制造模型不可用/工具超时，在真实UI呈现类型化错误和可安全回退的专业引导，保留草稿/idempotency key不产生重复Run。
6. 证据卡展开/折叠与来源E0/UNKNOWN/未经人审正确呈现；移动页面无水平溢出、输入框始终可见；无隐藏推理/系统prompt/密钥泄露。
**每条**保存RunId/CID、真实问句、脱敏input snapshot、HTTP状态、SQLite终态、events序列/teacher工具名、主答正文、source ID、DOM/截图、精确用例PASS/FAIL。不能只测Mock或后端TestClient然后标浏览器PASS。

### C. 统一PyMuPDF依赖和整仓回归
- 检查项目现有lock/venv，不全局升级。经本机项目约定允许时，向**项目本地venv**加入兼容、可版本锁定的`PyMuPDF`，避免系统Python与venv二元验证；仅有离线可用wheel则优先使用，任何依赖安装失败如实标环境BLOCKED。
- 在相同venv重新完整`python -B -m unittest discover -s tests -v`，目标0 FAIL/0 ERROR；3个明确可选telemetry SKIP要在报告列原因及对业务的影响；P16运行在同一环境5/5，不要修改测试期望掩盖原有记录问题。
- 前端Vitest≥128+TypeScript+Vite build，teacher554/200/17，S2.5双SSE/lease/崩溃恢复，G的P0 50/50、B安全红队保持通过。关键源SHA、磁盘/运行指纹和故障注入前后需一致。

### D. 状态与发布
- 由于当前`RULE_DEMO`,`llm.configured=false`,`expert_guidance_candidate=false`,`v2_agentic=false`，在隔离UI旅程通过后也只能批准**受限Rule Demo研究体验**；用户真正想验的DeepSeek专业推理还需独立预算化真实Planner/模型生成+安全门闭环，不可用Mock冒充真实智能体。
- 自动产物/教师机器校验不替代原PDF物理页、82机理条件审核、50真人签核和领域专家Gold；全为0则正式设备/风险结论NO-GO。
- 更新`docs/audits/R2_G2_FINAL_BROWSER_PROFESSIONAL_E2E_20261030.md`与`docs/PROJECT_STATUS_CURRENT.md`，分别给`GO_ISOLATED_OWNER_RULE_DEMO_UI_TEST` / `STOP_FIX_REQUIRED`及`NO_GO_PRODUCTION`裁决。Gate失败以原日志为证，不许修改安全断言/省略未通过场景。
