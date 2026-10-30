# P12｜模型配置与自然语言专业问答收口（2026-10-28）
Owner独立检查；本文件为可执行设计与验收任务，**不是已完成的功能声明**。

## 0. 独立实测真相
- 设置页面`frontend/src/SettingsShell.tsx`“模型”只显示`/api/health`的工作模式、provider、model、configured；两只“测试/刷新”按钮实为同一个health请求，**没有**配置管理、测试真实供应商、模型列表、切换模型的API。当前单一`backend/deepseek.py::settings()`从本机DEEPSEEK_*环境变量加载。
- P12独立修改：`SettingsShell.tsx`将重复按钮改为单个**刷新后端状态**，`SettingsShell + App.tsx`传入resolvedTheme，`settings.css`在dark/light设置下各自scope palette。CSS改动后Vitest 110/110 PASS、TS PASS、Vite生产构建PASS、后端145 tests OK (3 skipped)。**CSS浏览器实际截图仍待在Firefox/Edge验证**，不可写视觉已验收。
- `voice/SpeechInputButton.tsx`已经实现Web Speech API的lang=zh-CN/主动开始/错误显示/只填草稿；单测9项覆盖mock；但是浏览器支持有限，**Firefox稳定版通常没有SpeechRecognition API（MDN BCD标preview）**，并非一定是代码坏。先在Edge测试；确实要Firefox时加可选服务器`faster-whisper`或合规第三方语音转写供应商，不能要求DeepSeek Chat Completion直接接音频或冒充离线。
- `App.tsx::postRun`把`prompt`作为question单独发出，6个工况字段只从表单state读取。API后端`_start_worker`只从已传context的`operating_condition/field_evidence`抽温压/测量，不从`question`抽材质/介质/设备类型。
- **可重复失败用例（不发付费LLM）**：
  输入`设备：塔顶碱液管线弯头，材质：300系列不锈钢，介质：碱式酸性水，温度：60°C，该减薄属于哪类腐蚀？`且context空：`IndustrialCandidate.run(...,{})` -> `needs_user_input, tool_calls=0`。
  传结构化`{material:'300系列不锈钢',medium:['碱式酸性水'],equipment:'塔顶碱液管线弯头',temperature_c:60}`后，`run('该减薄属于哪类腐蚀',context)` ->`draft_for_review, tool_calls=2`；hypotheses含`酸性水腐蚀(碱式酸性水)`，source clause`GBT30579-2022-5.23`。但当前聊天回复只显示“已取得来源/待复核”，**没有把具体候选与最重要的待核要素表达出来**。
- `deepseek.generate_report`只整理本地规则结果（不是自主工具调用），不要把LLM报告润色当多Agent诊断。风险等级仍必须经过真实观测、适用性证据Gate，且缺条款时不允许编造成确定性判断。

## 1. 优先级 P0：不让用户手填六个表单
目标：聊天一句话描述设备→自动抽结构化槽位→有据给候选答案；表单只是**高级可选补充**。
- 在`backend/context_slots.py`新增纯函数`extract_explicit_context(question)`：先精确解析“材质:300系列不锈钢”“介质:碱式酸性水”“设备类型:管道”“温度:60℃/60°C”“压力:0.3MPa”“服役10年”等明确字段，按老师`enums.json`/material_family别名归一化；严禁把`300`误解为温度，或把“有减薄吗”解析成“测得减薄=true”。有歧义时标unknown，不要推断。
- 明确优先级：**用户本轮显式表单输入 > 本轮聊天中明确提及的字段 > 同会话最近已确认的结构化上下文 > 缺省未知**。只延续同会话，不跨会话，不从旧设备工况串线；要有冲突检测并简短询问。
- 在FastAPI run创建或worker开始前融合slots，**记录用户原话、抽取值、来源、置信方法与最终结构化快照到原有SQLite/SSE**，以便审查展开；不要偷偷将未知变成false；不能发送整个标准PDF给外部API。
- 对用户完整自然语言机械问题即使未打开表单，也要调用原三工具；如有明确材质和介质就能提出待核机理。为此需要围绕`extract_observations`补中英文单位与显式字段标注的单测。长文本自由描述若纯规则无法可靠抽取，可在明确授权/只发最小必要非敏感文本情况下加**可选LLM结构化槽位抽取**，但必须schema约束+真实用户可编辑确认；不要求本轮新增Agent。
- 对于只提供“该减薄属于哪类腐蚀”、本轮与历史都没有设备信息，应该单句询问“请告诉我材质和介质”，不是循环做2轮空检索。普通聊天依旧直走LLM。
- 引导UI：composer默认简洁，旁边“补充设备信息”点击才展开表单；已从原话提取的数据可以以可编辑chip显示，不要在用户文本里重复6个label。

## 2. 优先级 P0：报告显示**有根据的候选，而非只有状态码**
- 对`output.hypotheses=[{text:'酸性水腐蚀(碱式酸性水)',source_clause_ids:['GBT30579-2022-5.23']}]`、`verification_level=E1`这种情况，聊天正文给：
  “从你提供的材质和介质看，**酸性水腐蚀（碱式酸性水）是值得核查的候选机理**，依据 GB/T30579-2022 第5.23条（当前仅确认检索来源）。是否已经发生减薄、哪种因素主导仍需测厚、现场pH、盐组分等证据。没有足够数据时不判断风险等级。”
  注意这只是**条件性回答的示例**，具体鉴别条件必须由对应标准/知识库支持，不能假设所有场景需要同一套测量。
- 只展示来源ID、印刷页/缺失原因可查的字段；有候选但E1，不说“无法形成任何结论”，而应说“无法形成确定性结论，但有候选”；并标注模型报告整理非专家复核。
- 把`needs_user_input`/`draft_for_review`/E0/E1等状态码放到折叠执行记录/证据卡；正文不显示“RULE_DEMO”、“draft_for_review”、“unresolved”等内部标记。对200条历史回答只向后兼容，不回写旧SQLite内容。
- 未有source/无候选时，给明确的可操作下一步，不用一段安全免责声明替代回答。标准引用错误绝不能掩盖为已核验。

## 3. P1：**真正的网页模型配置**（小型本机版→未来公网多用户版）
与单一`DEEPSEEK_* env`的区别：网页上能选Provider、模型名、API入口并新增凭据、连接测试、切换会话配置、删除凭据。
先从最小产品层分离：`ModelProfile {id, user_id, provider, model, endpoint, credential_id, enabled, verified_at}`。UI读取`GET /api/model-profiles`，新增/编辑`POST/PATCH`仅提交API key一次，后端回显只含masked/key_configured，不可GET取回明文。
- 本机单用户：明确login/owner gate或仅localhost管理员权限，不要把未认证`POST config`暴露公网；密钥本机由Windows DPAPI或系统密钥环安全保存，**不入SQLite明文、不入前端localStorage、不进SSE/logs**。未实现secret store时本轮只支持模型名切换+后台.env键配置，并诚实说明限制。
- 公网多用户：先实现认证、session归属、owner验证、CSRF/滥用限制、加密托管密钥（KMS/专用secret store）、轮换/撤销、成本配额。全站共享`DEEPSEEK_API_KEY`要区分`site-managed`模式，普通用户不能修改管理员全局密钥；`BYOK`要逐用户隔离并在UI说明隐私传输。
- Provider registry: `DeepSeek`和`OpenAI-compatible`最小2类，模型白名单或后端模型列表；HTTPS endpoint限制与SSR防护，**不允许用户任意设置内网IP/localhost/file://**；避免未来网站被当代理请求内部资源。
- `POST /api/model-profiles/{id}/test`真实调用最小非敏感token提示并返回延迟、模型、usage/错误码、费用提醒；与`GET /api/health`严格区分“后端可达”和“供应商真实可用”。不要发送真实设备数据做测试。
- 选择的模型profile在Run创建时**server snapshot**，SQLite持久化只存profile_id、实际模型/解析状态/tokens，不存密钥。更换模型不回写历史Run。模型只是回答整理时不要标LLM_AGENTS。
- 限制后端配置开关（管理员权限）与会话模型偏好，所有model调用必须使用明确属主的profile解析；未授权不发网络请求；增加模型API错误、失效凭据、超配额、异步断线的e2e测试。

## 4. P1：深浅主题与语音（Owner做了可界定的最小修复）
- Owner已改`SettingsShell.tsx`接收`resolvedTheme`，App传`mode`，`settings.css`为dark/light设独立背景及前景变量；去掉两个其实都GET health的“测试服务连接”假按钮，剩下`刷新后端状态`；`frontend/src/SettingsShell.settings.test.tsx`同步更新并加dark/light绑定测试；Vitest 110/110、TS、build通过。浏览器浏览器**暗色视觉截图仍待实测**，需Codex分别在Edge/Firefox点切换，验证computedStyle、12-16px对比、不产生白底白字；检查dark所选按钮对比色、辅助text、右侧Inspector、手机。
- 语音在Firefox当前通常不可用，开发者测试应分别检查`window.SpeechRecognition||webkitSpeechRecognition`，用Edge/Chrome做一次真实中文语音转写（需要用户主动授权麦克风）；如果Firefox必须支持：第二阶段实现`MediaRecorder→本机/已授权STT服务→文本回填`，只传音频，经明确授权；禁止拿用户手机麦克风假传给DeepSeek，不能静默录音。
- 若选择完全本地转写，可用`faster-whisper`或`whisper.cpp`成熟项目，可选依赖与资源说明，别抢当前核心业务性能。

## 5. 验收矩阵（实现后写一份简短报告）
|Case|输入|期望|
|---|---|---|
|A|只有聊天框: 设备塔顶碱液管线弯头、材质300系列不锈钢、介质碱式酸性水、温度60°C，该减薄属于哪类腐蚀？|自动抽值，Teacher Tool至少1次，返回候选机理和待核条件，不凭空定级|
|B|表单空、自然语言只说“你好”|DeepSeek普通自然回答，不调用机理工具|
|C|只有“这个设备风险等级是多少”，缺材料/介质/后果|询问缺失因子，0确定性L级|
|D|自然语言材质与表单材质冲突|明确冲突不静默覆盖|
|E|重复同会话“那怎么检测？”|沿用最近明确证实的工况并标注历史来源；不同会话不串|
|F|GB/T26610.5-2022面积后果表|真实检索来源，E0/E1可区分，不伪造PDF数字|
|G|模型管理未登录/恶意外部endpoint|拒绝；不可访问凭据，不可打内网URL|
|H|切换模型→发问→刷新|真实新model已用；旧Run显示旧模型；Token精确来源于provider|
|I|暗色设置页|真实浏览器白字不贴白底；颜色对比可读|
|J|Edge语音点击|权限/中文识别可用，转写只填输入框；Firefox显示不支持/可选STT|

**测试命令**：`node frontend/node_modules/vitest/vitest.mjs run --reporter=dot`、TypeScript/Vite prod build、`./.venv-langgraph/Scripts/python.exe -B -m unittest discover -s tests -q`、老师`validate.py --final`、Edge真实e2e双视口。
**文件边界**：此轮不要修改`upstream/`PDF/XLSX/JSONL、老师工具合同、用户真实历史SQLite，也不要在无授权情况下部署公网。模型密钥必须仅由后端保管，后端健康检查不可冒充供应商连接测试。
