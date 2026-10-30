# Codex 窗口 A｜澄衡 Aetheris 设置中心 / 应用壳 / 可折叠侧栏（唯一主页面合并者）
项目根目录：`D:\作业\竞赛\计算机设计智能体\机械智能体`。
现在即可执行。完整读取`AGENTS.md`、`docs/P11_AETHERIS_PRODUCT_POLISH_DESIGN_20261028.md`、`frontend/src/App.tsx`、`ConversationThreadList.tsx`、`frontend/src/api.ts`、`backend/deepseek.py`只读。以最新实际代码为准。
本任务你可调度若干Codex子智能体，但文件边界必须清楚；三个窗口不能同时写`App.tsx`或`styles.css`。
**允许写**`frontend/src/settings/**`、`frontend/src/SettingsShell.tsx`、`frontend/src/SidebarShell.tsx`、`frontend/src/App.tsx`、`frontend/src/ConversationThreadList.tsx`、`frontend/src/api.ts`仅设置与归档API增量、`frontend/src/settings/settings.css`（或同模块新样式）、`frontend/src/*.settings.test.tsx`、`docs/audits/P11A_*.md`。**不写**`frontend/src/styles.css`（Owner当前精修）、`frontend/src/dashboard/**`、`frontend/src/voice/**`、`frontend/src/trace-events/**`、`frontend/src/components/trace/**`、`backend/api.py`、`backend/deepseek.py`、`orchestration/**`、`upstream/**`。
你是唯一负责统一插入B/C提供组件的人，但在B/C交付前先完成主功能，绝不编造组件导入。
1. 名称统一：用户可见“澄衡 Aetheris”（欢迎页、侧栏brand、浏览器title）；保留旧localStorage key `aether-theme`的读取迁移，不能清除旧会话/数据。Owner已经生成本地`frontend/public/assets/aetheris-icon.svg`的简洁同概念品牌icon（如存在直接引用）；如不存在先保留现有A方块并在报告标待接，不去搬远程PNG。
2. 设计Codex式设置页面（路由或轻面板皆可，保持简约）：左菜单“常规 / 模型 / 性格 / 会话与归档 / 外观 / 语音 / 关于”，右内容区不小于14px正文。图标使用lucide；桌面支持返回聊天、手机自适应。
3. 常规：字体缩放90/100/110%（不要把CSS全局变成硬coded 9px）、舒适/紧凑模式、主题浅深跟随系统（保留当前主题设置）、是否默认展开执行记录。设置持久化localStorage，但不得放密钥/个人隐私。
4. 模型：后端`/api/health`实时展示服务商、模型名、`DEEPSEEK`/规则模式及已配置状态。模型切换**必须**真的被后端接受且按指定模型调用后才可展示为“已切换”；当前无模型列表接口时只做只读当前模型+环境变量配置提示+测试连接按钮（请求能产生实际费用要写明），不造装饰性选择框。人格/语气：4种preset（专业严谨/自然友好/知心陪伴/简洁高效），仅存为本地用户偏好；实际影响普通LLM提示词必须有可验证后端入口，若无法在本窗口修改后端，则先标“待服务端接入”，不虚报已生效。等API模型部署窗口结束、三窗完成后，由唯一集成Owner修改`backend/deepseek.py`把品牌称呼更新为“澄衡 Aetheris”、接通可选性格参数；工程审查提示词与证据Gate不受性格偏好覆盖。自定义指令最多500字，不越过工程审查门禁。
5. 归档管理：已有`api.archiveConversation` + `GET /api/conversations?include_archived=true`，先真实验证；实现查看归档会话、搜索、恢复（PATCH archived=false），从列表隐藏/恢复后无需刷新浏览器。不要自动物理删除聊天和附件。
6. 左会话栏可以一键收起展开：收起后只剩窄导航或完全隐藏，主聊天变宽，状态持久保存；移动端仍保持原抽屉。顶部“设置/统计”小图标入口，后续B/C组件由你集成；审查侧栏保持独立可收合。
7. 和B/C约定仅通过typed props事件契约整合：`UsageDashboard`由B提供，`SpeechInputButton`与`ActivityTrace`优化由C提供。保持App.tsx是唯一合并点，不能在两侧重复造数据状态。
8. 前端专项测试：设置切换/刷新持久化、暗色切换、归档恢复、窄侧栏和手机、模型没有key时真实状态，不显示key。跑Vitest/TS/Build；后端保持旧134+或最新现有基线不退化。
仅写`docs/audits/P11A_SETTINGS_SHELL_ACCEPTANCE.md`简短验收，截图1280与390真浏览器，`READY_FOR_OWNER_REVIEW`。不部署、不改上游、不删除旧数据。功能够用后停止，不引入全套状态管理框架。
