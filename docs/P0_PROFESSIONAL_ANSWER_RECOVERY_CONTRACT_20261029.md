# Aetheris P0｜专业智能体“缺信息即拒答”根因与分层分析改造合同
日期：2026-10-29；Owner 现场复查。**状态：ROOT_CAUSES_CONFIRMED / CODEX_IMPLEMENTATION_REQUESTED / DEFAULT_PRODUCTION_NO_GO**。
工作根：`D:\作业\竞赛\计算机设计智能体\机械智能体`。本机Codex直接使用本地终端与文件；不可自行调用DevSpace/远程连接器。保护其他窗口进行的S2.6/S3-A/S3-B/S3-C未提交文件，不以git clean/reset覆盖。

## 0. 现实故障和代码证据（不能只改prompt）
截图A：`设备：塔顶碱液管线弯头，材质：300系列不锈钢，介质：[碱式酸性水]，温度：60°C，问题：该减薄属于哪类腐蚀？`，网页答`请补充材质与介质后再检索。待补充：material medium`。
截图B：`设备发生壳体磕碰损伤，什么情况需要停机维修？验收判定标准是什么？`，网页答`未取得可追溯出处；无法形成受证据支持的结论。`。

Owner本地复现于新版**磁盘源码**（不是运行中的旧8000）：
- `extract_explicit_context(A)`得 equipment=塔顶碱液管线弯头、equipment_type=管道、material=300系列不锈钢、medium=[碱式酸性水]、temperature_c=60.0；route=device_diagnosis。R9.run(A) 2个工具、6条source、1个hypothesis、status=draft_for_review。
- `extract_explicit_context(B)`为空是正常现象（问题未给材料/介质，不代表不能分析），route=hypothesis_exploration；R9.run(B) 2个工具、0源、0候选、status=unresolved。该拒答问题**最新版也存在**。
- `backend/context_slots.py`新版已支持A；8000仍是10月28日旧Python PID59120，当前OpenAPI没有web_mode/model_profile_id、`/api/model-profiles`404；网页给出A缺材质很可能是版本不一致（尚未单独取该Run持久snapshot核证），不可归咎新版提取模块。
- `orchestration/r9_industrial_candidate.py:route_task/evidence_gate/_report`含`missing_context→ask_user`、`no citations→unresolved`硬路径，部分机制问题未作检索前的有条件分类讨论；`investigator`只搜索整个原问题变形后检索，缺专业意图→多关键词策略。
- `backend/deepseek.py:generate_report`明令模型“**不负责检索、诊断或复核，只能忠实改写既有结果**”；`backend/api.py`把生成文本放入`llm_completed.summary`折叠事件，主回答使用机械模板。这是大模型专业调查能力没有开放的直接原因。
- S3-A已形成82 manifest/134条候选谓词/15条试点；S3-B三值判定54个合成测试PASS但**无人工审核的necessary/exclusion谓词**、0条正式适用性硬判定；不要把S3注释自动当作正式标准依据。
- 教师冻结标准472 RBI+82 DM、3工具及source 5键、审计链、50人审、100原生解析要求不动。

## 1. 目标：Bounded Expert Investigation，分层回答而非拒答/幻觉两极
原则：**模型可以提出专业假设与检验路径，不能绕过事实确认、条款真实性、原教师工具白名单、风险定级/立即复机放行门禁。**
回答固定认识层级（UI无需全按模板硬套）：
- **F0 已提供/已确认工况**：来自当前文字/结构表单/同会话确认，保留raw span、source、范围、冲突、不确定值（用户陈述不自动变成实测）。
- **F1 一般工程原理（非具体标准要求）**：在模型可用且安全边界下，允许常识解释、可能的失效模式、针对性调查计划；必须标`general_engineering_guidance/unverified_knowledge`，不得凭空引用标准页、强制验收阈值、法规数字。
- **F2 标准库可追溯证据**：每条statement有真实teacher source IDs、code/clause/page与检索信息（源级E0/E1取决于source验证），不得把“检索出条款”当“适用性得到验证”。
- **F3 工况条件适用性**：S3-A/B作为shadow-only annotation，三值UNKNOWN不得被模型转换成排除；未核实人工PDF的candidate不升级为标准结论或危险排除。
- **F4 设备级诊断/风险/停用/复机**：现场检查/材料设计与压力/损伤程度和适用法规缺少时不得确定损伤已发生、给RBI L1–L4、确切检验周期、绝对继续使用/复机许可；有高危信号必须显著提示立即停用/隔离评估的通用安全建议（具体决定按设备类别、现场制度与有资质人员审批）。
用户不完整工况时仍至少给F1，可能给F2/F3，只有F4严格拒绝定论；不应无条件追问材料/介质才开始F1。

## 2. 必做代码路线
### Gate A 实际运行版本及输入证据（P0）
- 实时发现/报告`/api/health`,`/openapi.json`版本和Run创建/工况抽取、工具选择、回答生成版本。新API增加`contract_version`和能力列表，前端在不匹配时明确提示，但不在未经Owner许可时重启或改真实SQLite。
- 完整拷贝截图A/B为本地合成回归，在**前端POST→API snapshot→context_resolved→Graph→teacher工具→assistant主文**链逐项断言；前端字段留空不是用户没提供事实。普通用户自行补完整材质才能工作视为FAIL。
- 如果某词不在教师enum：保留`raw_medium`/normalized_candidate/unknown_enum状态，用standard_clause_search作初步探索而不是把原文抹掉；**不修改老师enum，不制造假canonical**。温度、压力带单位和对象；材料大类“300系列不锈钢”不擅自确定304/316。
- A用户说“该减薄”不代表有量化测厚数据：设备材料介质是真实**用户陈述**，测厚数值/损伤类型是待验证。

### Gate B 路由与调查计划（P0）
- 设计`ProfessionalIntent`细分 Concept/MechanismExploration/DeviceInvestigation/StandardsLookup/MaintenanceSafety/CodeCompliance/RBIGrade/Compound；B必须走`MaintenanceSafety+StandardsLookup`，不该被当成没有材料而结束。
- 从问题生成最多3–5条精准、有界teacher查询：例如B“承压壳体 机械损伤/凹陷/撞击”“壳体变形 裂纹 无损检测”“修理 复检 验收 条款”；根据真实官方库术语动态选词、加同义词/对象名/动作词，不“编造某GB/T条规定”，不得将普通浏览器网页当老师标准。
- 执行原版`standard_clause_search`/合法`damage_mechanism_query`/合法`rbi_lookup`，每次记录args、budget、返回结果、source IDs、消歧/negative evidence；ZERO_SOURCE不得等于ZERO_HELP。基于source目录关键词/索引可做自有只读派生检索，但不增加老师第四个接口，遵守原版权与来源规范。
- 零来源时先`GENERAL_ENGINEERING_GUIDANCE_WITHOUT_VERIFIED_STANDARD`，给明确`standard_clause_unverified`，而非硬称强制验收标准或停止工作。终止只针对unsupported claims，不能终止整个助手。
- mixed任务多目标分段工作：安全隐患建议优先、然后标准查证、最后报告，不得让写作新增诊断结论。

### Gate C 专业Model角色（P0）
- 保留现有真实`DeepSeek`账号/模型配置，**不自动/无界调用付费API**；新增`ExpertHypothesisPlanner`或结构化`ProfessionalExplanationDraft`可注入Mock测试，正式默认候选/可关feature flag，带明确请求/Token/超时预算。
- 必须允许模型基于**用户事实+一般工程知识+实际可用source摘要**提出候选机制、作用条件、反证、危险信号、证据采集与问题优先级，不能只让它转述`_report`的一句拒答。必须输出结构化JSON并做Pydantic、白名单、来源ID交叉核查，展示给用户时合适地转自然中文。公开的是工作步骤摘要，不是隐藏思维链。
- 不经检索确认的模型段落只能标`GENERAL_GUIDANCE`或`HYPOTHESIS_UNVERIFIED`；引用`GB/T/TSG`编号/条款/印刷页时**必须**对真实source校验，没source禁止写“第x条要求”。可以说“我尚未核实具体强制验收条款”。
- 分类实现的核心约束：`unverified_general_guidance != verified_standard_requirements != confirmed_device_diagnosis`。不要为了避免幻觉将前者全部禁掉。
- 实际用户可见正文承载结构化结果：`已知工况→可能原因与判别依据→已查标准/未核实来源→下一步现场检查→缺什么信息及为什么→高危提示`。不要把模型的实质分析藏在SSE或折叠事件里。证据卡/活动过程依然保持默认折叠。

### Gate D 特殊高危领域答复
- B“壳体磕碰损伤、什么时候停机、验收标准”：可以先条件化说明若涉及**承压边界**、出现泄漏/疑似裂纹/持续变形/密封异常/无法确认完整性，应当优先采取保护性隔离/停止使用并联系有资质专业人员评价；应核对设备类型（压力容器? 非承压结构?）、工作压力、损伤形貌/深度/尺寸、设计图/制造记录、NDT检测、适用监管标准、修理方案、复检验收。**不得编造统一法定凹坑深度阈值、检测合格值、必须停机的法律条号或复机许可。** 如从本地标准库证实某条，再逐条讲适用性。
- A“300系列不锈钢/碱式酸性水/60C/弯头/减薄”：应承认上述上下文，讨论候选的酸性水环境腐蚀、流动/冲刷相关局部减薄、局部腐蚀等与具体环境相关的可能机制及区别；不得未经Cl/H2S/pH/流速/沉积物/失效形貌、材质确证就断言特定机理或当场给风险等级。必须提示材料是大类、`60C`不代表壁温已经确认、`减薄`不等于已取得测厚数据。
- 纯“什么是应力腐蚀开裂”不应要求材质后才能解释；“解释某标准原文”若本地无来源须说明，仍可解释概念而非引用；翻译/润色专业文字不可无故进入设备诊断。
- 永远将`HUMAN_SOURCE_VERIFIED`与AI/Owner自动候选区分，无人工审查则不能宣称“已验证符合标准”。

## 3. 验收协议（防止假通过）
- 冻结现有R9与V2 baseline、`AETHER_V2_AGENTIC_ENABLED`默认off；新能力用独立feature flag（例如`AETHER_EXPERT_GUIDANCE_CANDIDATE=0`）先隔离试验；未获Owner授权不得切默认生产/真实DB，也不碰`upstream/**`。
- 开发前完整测试复现A/B旧结果；开发后至少**60条**独立合成与已有负例，覆盖材料与介质已有/unknown、中文半角括号/[]、同一会话更正、标准检索零命中、多次query、材料/压力角色、安全警告、人身危险、提示注入、强制伪出处、问候、翻译、缺PoF/CoF、跨会话隔离、与旧`owner65`路由题差分。
- 核心自动化Gate：A中`resolved.material/medium/temp`正确且最终**不再要求重新填写它们**；B中0source也能输出有结构的专业风险排查步骤，但引用的具体标准条款数=0且不出法定阈值；纯概念题有概念答案；缺PoF/CoF风险等级=null；未核实PDF不能冒“已验证条款”；危险候选不会因unknown错误排除；真实自然语言本轮答案不是只有状态代码/模板拒答。
- 主用户消息必须来自可追溯的`ProfessionalResponse`，测试不得只检查事件后隐藏`llm_completed.summary`。
- 独立同题R9旧版、R9+新增专业candidate、V2 fake、真实LLM（可选明示授权）的paired comparisons：内容价值/可核查性/错误断言率/延迟/Token次数/工具次数；不要把模拟LLM成功率写成付费模型成功率。
- 全部Python/前端/老师`validate554/200`、17工具与历史S2.5执行账本回归。实际浏览器Edge桌面与移动真实发送/历史/SSE验收在后端服务完成受控版本切换后执行，不能把磁盘测试当在线E2E。
- 产出`docs/audits/OWNER_P0_PROFESSIONAL_ANSWER_REPAIR_20261029.md`和新`tests/test_p0_expert_guidance_*.py`、`evals/p0_expert_guidance/**`；必须记录源码SHA/真实版本/命令/样本量/失败与剩余风险。
- 默认`NO_GO`不擅自重启8000进程，不覆盖用户生产SQLite，不清理queued；需升级则单独提出备份、运行快照、健康检查、回滚、安全切换步骤。

## 4. 对Codex的任务原则
在本机一次完成P0实验候选，允许有界单元/端到端临时SQLite测试。出问题不要只提出理论和再派子Agent：直接改代码，先闭合A/B真实失败，再拓展其他案例。S3候选只读Shadow，不等S3全82人审才开始F1一般专业分析。未取得标准不等于不能解释，也不等于可以编造标准。
