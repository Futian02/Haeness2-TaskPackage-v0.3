# P11 简洁产品精修｜澄衡 Aetheris 设置 / 今日统计 / 执行过程 / 语音（Owner设计，2026-10-28）

## 本轮目标与核心约束
这是**一次产品体验精修**，不是重新搭平台。继续用React19+Vite、assistant-ui、FastAPI、SQLite、LangGraph、现有SQLite SSE和独立可选Phoenix。绝不换Next.js、数据库或引入微服务。
- 统一名称：**澄衡 Aetheris**；中文展示“澄衡”，英文标识“AETHERIS”，说明“工程智能助手 · 可进行日常聊天”。原工程Aether/Haeness2老名字仅保留兼容配置/旧文档。
- 品牌图：Owner已用ImageGen生成一张盾牌+齿轮+字母A+图节点的绿色图；本机先以**精简SVG同概念版本**做实际icon/favicon。PNG高分辨率素材在当前聊天附件，由用户人工保存到frontend/public/brand/时可进一步替换，禁止假称已经复制PNG到本机。
- 默认主聊天保持简约；左边会话侧栏可收合（收合状态保留，移动抽屉）；右边“执行审查”默认可收起；高级设置/活动统计独立页面/面板而非继续塞入聊天主屏。
- 仅显示真实SQLite和模型事件：Token和费用如果未从provider返回则展示“未记录”，**不能通过字数×0.75伪造为精确Token**；估算若提供须单独标“估算”。饼图仅按真实mode/任务分类/事件类型分布，空数据用空态。
- 现有实际模型后端多数是通用对话或报告整理；R9图规则审查不是多个真实LLM。Codex风格“编辑文件/命令运行”仅在未来确实有相应执行工具时才展示，当前三个老师工具只读查标准/损伤/RBI，不能生成假的命令与文件diff。
- 现有归档接口只是软归档。提供“归档会话”管理列表、恢复操作，永久删除另行确认，**本轮不需要永久删除**。
- 本机用户模式，无外网生产暴露。模型 API Key只能在本机服务环境配置，UI不能显示/echo Key，模型配置页面用Health或独立安全配置提供provider/model/启用状态/测试连接入口，绝不在localStorage放私钥。
- 当前用户已经交给Codex API 接入，请避免覆盖`backend/deepseek.py`及`backend/api.py`中的真实模型开发，先做无后端破坏的UI模块和明确API提案。

## 具体模块
### 1. 文字与布局（Owner已经本机改）
- Inspector标题19px、节标题15px、事件文字14/12px、证据14/13px、角色图13/11px、关键调试12px，保持暗色模式对比、桌面右栏不易溢出；本次由Owner修改`frontend/src/styles.css`。
- 不强迫整个项目所有文字都放大到16px：辅助状态保留12-13px，用户阅读主体14-16px。新设置页面沿用该字号层级。

### 2. 设置中心（Codex A）
参考Codex设置导航：左侧常规/模型/性格/聊天与数据/外观/语音/关于；右侧表单。常规：语言、字体比例3档(90/100/110%)、紧凑/舒适密度、主题浅/深/跟随系统、自动展开过程开关。
模型：显示当前Provider、模型名和可用模式；在官方明确支持的`model list`内切换并保存服务端/当前会话偏好（具体权限由后端控制），支持测试连接但需真实API响应与费用提醒；密钥仅提示服务端配置状态，**不可把明文Key同步浏览器**。
性格：专业严谨/自然友好/知心陪伴/简洁高效，加自定义系统风格说明(限长且不能覆盖硬工程规则)。普通DeepSeek聊天可用，工程判断仍由证据Gate管。
聊天与数据：归档列表分页、搜索、恢复；日期分组和会话重命名已有；左侧可收合、收合以后聊天自动居中，手机仍用抽屉；不要二次造会话表。
### 3. 今日统计（Codex B）
今日/近7天/近30天：对话数、消息数、Run数、工具次数、来源核验/未决、模型请求数、可用精确token。最多2个扇形图：任务类别饼图、模式/状态占比饼图；一个每小时活动柱状图可选（不挤满看板）。图用recharts现成库（若已存在就重用），轻量原生SVG亦可但不重复造图表框架；读取SQLite SQL聚合，避免一次fetch全部消息/事件给前端统计。查询必须带起止时间+当地时区偏移，避免日期跨UTC错误。
若当前DB还没有实际Token数据，就在`llm_completed`event中引入`usage.prompt_tokens/completion_tokens/total_tokens`**仅当API返回**时保存，不能改API适配器以猜测费用；模型调用时延可以拿真实event时间。
### 4. Codex风格可折叠过程（Codex C）
主体一行「已查询2条标准 · 审查完成 · 1.2s」；点开分组显示 Investigation/Tool/Review/Report；工具展示「名称、摘要、结果、引用、耗时」，支持按照阶段折叠；开发者深层记录才显示JSON；每个`run_id/sequence`真实绑定，不用隐藏私有思维链替代。支持30~100事件、SSE增量、断线刷新，绝不因tool缺失产生虚构“已编辑文件”“执行命令”。R9B已有`ActivityTrace`和assistant-ui，**在此基础上做少量精修，不另建第三套trace**。
### 5. 语音输入（Codex C）
先使用浏览器`SpeechRecognition/webkitSpeechRecognition`，支持Chrome/Edge常见桌面环境，开始/停止/中间结果、中文zh-CN、麦克风权限拒绝、未支持浏览器时禁用并提示。注意有些实现会使用浏览器厂商的语音服务：**明确提醒可能将音频传第三方语音服务，不称为纯本地离线**；不静默录音或自动发送聊天；转写只填输入框，用户点击发送后才提交。未来按需添加完全本地faster-whisper，不作为本轮完成门槛。

## 并行文件边界，冲突时按这个分
**Owner（本轮）**：`frontend/src/styles.css`，`frontend/public/assets/aetheris-icon.svg`、`frontend/index.html`品牌标题；不抢App.tsx/api.py。
**Codex窗口A—设置/应用壳**：`frontend/src/settings/**`、`frontend/src/SettingsShell.tsx`、`frontend/src/SidebarShell.tsx`、`frontend/src/App.tsx`、后端轻量偏好接口需由最终集成Owner单独接入（真实影响性格/模型配置才算完成）；不可改stats/trace/voice模块。A作为唯一App.tsx合并者，把B/C组件挂入App，防止三个窗口同时编辑App。
**Codex窗口B—统计/数据库**：`backend/usage_stats.py`、`frontend/src/dashboard/**`、`tests/test_p11_stats*.py`、新增SQLite只读SQL；`backend/api.py`由A或最终集成者统一加route，B交付router与接口函数，不碰App.tsx/styles.css/deepseek.py。
**Codex窗口C—Trace与语音**：`frontend/src/components/trace/**`、`frontend/src/trace-events/**`、`frontend/src/voice/**`、专项测试；不碰App.tsx/SettingsShell/SidebarShell/backend/api.py/styles.css。
B/C的可用组件由A统一插到导航/Composer/消息；先分别测试，最终一个窗口做实际浏览器端到端联调。
**禁止任何并行窗口重写upstream Excel/PDF、老师三个工具、Graph、当前DeepSeek模型配置、用户实际对话数据库。**

## 功能交付 Gate 与收工标准
- 右侧文字可读：Inspector标题≥18，正文/证据≥13，技术摘要≥12；390px不横溢；暗色良好。
- 设置：主题/字号/性格/导航偏好真实生效，重启浏览器仍保留；模型配置是实际后端可用状态，不可冒充可切换模型或存密钥到浏览器。
- 左侧能一键折叠/展开；归档列表真实读后端并可恢复，至少5个真实会话混合场景。
- 今日统计真实SQL：本地新建2对话3轮+2次工具Run后统计可重复；没usage的显示“—”而非0/token推算；有usage事件能精确聚合。
- 语音：Edge手动权限下中文转写输入框，未授权/不支持时提示；不能自动发送。
- 执行轨迹：本地真实SSE“Tool→Audit→Report”折叠展开展示，长run和刷新无重影；无实际编辑文件工具不显示假的改文件信息。
- 前端原78+测试、tsc/vite构建；后端原测试全回归及老师554/200完全不退化；真实浏览器截图桌面1280/移动390/暗色，Console无错误；API密钥不暴露。
- 只写**1份总验收报告**，前期三窗各出简短验收记录，不再开P12/P13重复架构。
