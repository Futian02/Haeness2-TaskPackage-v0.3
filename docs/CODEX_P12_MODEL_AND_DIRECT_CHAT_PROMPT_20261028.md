# Codex P12：自然语言设备问答 + 网页真实模型配置（最终集成任务）
工作目录：D:\作业\竞赛\计算机设计智能体\机械智能体
首先完整读取 AGENTS.md 和 docs/P12_MODEL_SETTINGS_NL_CONTEXT_REVIEW_20261028.md；里面有本轮Owner复现、10组验收案例和安全边界。任务完成后要真实运行这些案例，而不是只写文档。

阶段一 / P0：零表单自然语言工况自动理解
用户只在聊天框输入「设备：塔顶碱液管线弯头，材质：300系列不锈钢，介质：碱式酸性水，温度：60°C，该减薄属于哪类腐蚀？」后，自动抽取明确值与教师枚举归一化，沿用原三工具，并呈现酸性水腐蚀（碱式酸性水）等待核候选+来源+未知数据。不得捏造减薄实测、风险L级或把E1冒充E3。
输入优先级：本轮明确填写的表单 > 本轮文字中明确的值 > 同会话前轮经确认的工况 > 未知。不同会话严格隔离；冲突不得静默覆盖。对低置信度输入要求确认。
输出正文只写自然语言结论、候选及缺口，内部status和证据审查详情仍放折叠区。普通闲聊不调工程工具。

阶段二 / P1：模型配置页真正可用
后台提供模型profiles增删改查、加密凭据引用、安全连接测试、会话模型选择与Run快照；前端只回显masked key、配置状态和真实test结果。禁止把API密钥明文写在localStorage、普通SQLite表、日志或SSE；当前无账户/安全密钥托管时只能在loopback管理员模式做本机功能，绝不能把无认证配置接口发布公网。支持现有DEEPSEEK_*环境变量作为兼容配置。
让本机当前『刷新后端状态』继续只读health；新增真实provider测试按钮须提示计费、发最小非敏感请求、显示模型、延迟、真实usage/错误。provider/model切换后必须影响真实API调用且能从Run核证，不允许假展示。

可并行子任务，严格不抢共享文件：
A: backend/context_slots.py、backend/api.py（唯一修改者）、必要的orchestration小改、tests/test_p12_context_*.py、最终集成App.tsx/SettingsShell.tsx/api.ts。
B: backend/model_profiles.py、backend/model_profiles_router.py、frontend/src/model-settings/、专项测试；B不改backend/api.py/App.tsx/SettingsShell.tsx，交组件和router给A。
C: frontend/src/messagePresentation*、frontend/src/EngineeringReport.tsx、frontend/src/components/trace/、frontend/src/voice/和相应测试；C不改App.tsx、backend/api.py、styles.css；Firefox不能语音时清楚提示，Edge真实测试，不强制引入STT平台。

Owner已完成并需保留：SettingsShell新增resolvedTheme、App传mode、settings.css独立dark/light调色、去掉虚假的测试服务按钮改成刷新后端状态、SettingsShell.settings.test.tsx更新；前端110/110、TS/build通过，后端145 tests OK(3可选跳过)。不要覆盖Owner改动。
验收：前端Vitest/TS/Vite、后端全unittest、老师validate 554/200、三工具17/17；Edge暗色/浅色桌面1280与手机390截图；实测无表单输入、同会话续问、材料冲突、自然语言候选带出处、零证据拒绝等级、模型配置后真实切换、身份/密钥安全、浏览器麦克风。
不修改upstream任何PDF、Excel、老师三工具、正式数据库；不部署公网、不重排目录、不清理用户数据；写一份 docs/audits/P12_FINAL_USER_FLOW_ACCEPTANCE.md，准确区分已测和阻塞，达到收工Gate停 READY_FOR_OWNER_REVIEW。