# Owner P12 独立审核与项目收口表（2026-10-29）

状态：**LOCAL_INTEGRATION_PASS / REAL_PROVIDER_AND_CONTENT_GATES_PENDING**。仅只读复查 + 独立运行测试，不改源码、upstream、历史会话或模型密钥，不发付费LLM请求，不部署公网。

## 1. 独立复测记录
- 2026-10-29 DevSpace `./.venv-langgraph/Scripts/python.exe -B -m unittest discover -s tests -q`：156 tests, OK (3 skipped)，即153实际执行PASS、3可选跳过。
- P12专项 `tests.test_p12_context_flow tests.test_p12_model_profiles`：8/8 PASS。
- Vitest：16 files, 111/111 PASS；TypeScript `tsc -b` PASS；Vite build PASS，main JS 610.10kB（gzip186.49kB，>500kB构建警告）。
- 教师 `validate.py --final`：554/554条、200/200轨迹PASS；`_selftest_tools.py`：17/17 PASS，未改3工具。
- 实时本机只读`GET /api/health`：status=ok，mode=DEEPSEEK，provider=DeepSeek，model=deepseek-flash，configured=true；**不代表供应商实时调用成功**。4张P12浏览器截图在`docs/audits/P12_screenshots/`文件存在，Edge视觉检查和横向溢出为Codex验收报告结果，本Owner并未远端再次打开浏览器独立目检。

## 2. 从P3到P12实际落地项目
- P3–P7：React+assistant-ui UI、FastAPI、SQLite WAL/SSE重放、结构化Claim与E0/E1证据门禁、Auditor/Skeptic规则审查、并行一致性冲突降级、人工审核模板与测试，冻结老师三工具及5键合同；并行实验不默认上生产。
- R8–R9：聊天历史/问题定位/上传和附件存储、豆包式左右栏/移动端、R9路由—调查—并行审查—报告的有界图、按真实run_id绑定的折叠执行事件、可选Phoenix本地跟踪。
- P10–P11：普通问候/能力聊天与工程任务分流、DeepSeek普通问答与专业结果文字整理（不是LLM自主工具规划）；澄衡Aetheris视觉品牌/图标、字号/深浅主题、设置中心、可折叠会话栏、软归档和恢复、SQLite统计图、浏览器可用时的语音草稿输入（无真实录音验收）。
- P12：`backend/context_slots.py`显式材料、介质、设备、温压与年限抽取；当前表单>当前明确文字>同会话历史的优先级，冲突留痕；API`context_resolved`事件可核。API端到端单测`tests/test_api_vertical_slice.py::test_p12_chat_only_context_routes_to_tools_and_renders_sourced_candidate`：无表单自然语言可查到待核`酸性水腐蚀(碱式酸性水)`，引用`GBT30579-2022-5.23`；风险级别空，非专家确认。
- P12模型配置：`backend/model_profiles.py`在Windows DPAPI CurrentUser保护密钥、分离profile元数据；增删改激活、官方HTTPS域名白名单、真实provider连接测试入口、前端只显示masked；活跃profile被快照到新Run的`_model_profile_snapshot`，无API Key泄露；Loopback-only/APP_ENV=production阻断，**未有用户登录和公网多租户权限**。

## 3. 明确未收工的事项
1. **真实外部LLM调用/专用模型准确率**：未独立执行真实付费`test_connection`与100题模型工具规划；现有调查/并行审查主要是规则节点，DeepSeek普通聊天与报告文字整理不是独立多模型Agent。不把pytest/老师200规则轨迹当真实模型测试。
2. **模型profile的强冻结风险**：Run创建时快照profile_id/provider/model；worker实际调用`model_profiles.resolve_snapshot(profile_id)`读取当前凭据/模型。若同一profile在排队期间被编辑、删除，真实推理可能使用新配置或失败，因此只能证明“历史Run标签/模型元数据不回写”，不能声称端到端配置不可变。需要profile revision或在运行启动前核对快照一致，目标为未来上线门槛。
3. **准确Token用量未接通**：`backend/deepseek.py`当前`generate_chat/report`返回(text,duration_ms)，不提取`response.usage`；`backend/api.py` `llm_completed`事件也未附真实usage。因此P11今日图表可展示真实对话/Run/工具次数与分布，但Token暂无精确记录，应显示“未记录”，不能声称已准确计量token/费用。
4. **性格选择/自定义指令**目前只存浏览器本地偏好，`SettingsShell`明确写服务端未接入；不是可影响实时LLM回答的真实设置。
5. **RBI知识源真实性**：Excel现485条（原472+新13），正式`clauses.jsonl`仍RBI472+DM82=554；新增13缺独立签署未正式转换，全部Excel的V列未人审；GB/T26610.5面积后果表查询返回E0无命中；部分表格F列为二次改写而非连续PDF原文，需要按既有`OWNER_RBI_KNOWLEDGE_INDEPENDENT_AUDIT_20261028.md`逐条核。
6. **语音/文件**：Edge仅检测WebSpeech API，未完成真口述；Firefox未验，语音依赖浏览器。已上传附件/预览不等于模型自动阅读理解所有PDF/扫描件。
7. **外部网站/App**未部署；生产模式fail-closed；身份认证/账户隔离/密钥托管多租户/权限/监控尚缺，DPAPI方案仅Windows本机。
8. **归档≠永久删除**：会话可隐藏恢复，未完成所有历史记录/附件的真正销毁，不能误称完全删除。

## 4. Owner建议
工程平台“可本地演示并进入产品应用测试”，停止继续堆Agent/UI框架。下一轮最值钱的：
- P0：真实provider在本机主动付费确认后完成10个非敏感问题、统计真实mode/token/时延/错误；一个真实模型原生工具调用+规则与模型区分。
- P0：补检索GB/T26610.5面积后果表、数据F列来源与50条人工复核签署/新增13的合规入库。
- P1：P11 Token usage准确持久化、P12 profile修订冻结、同会话延续异常测试；网页多用户发布前补认证和KMS等，不能直接放公网。
- 可选：Firefox语音/本地STT、PDF内容真实阅读、进一步压缩首屏bundle。
