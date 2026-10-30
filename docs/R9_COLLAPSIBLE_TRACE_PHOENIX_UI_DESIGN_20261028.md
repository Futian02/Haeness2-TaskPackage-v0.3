# R9-B｜豆包式折叠执行过程 + Phoenix SDK 可观测性（2026-10-28）
状态：DESIGN_ONLY_NOT_EXECUTED。R8B Codex正在改`frontend/`及`backend/`；**先只写隔离trace组件/观测模块，后整合，不在两窗口同时抢App.tsx/API**。

## 用户要求与正确实现
用户想在一条聊天答复附近看见`思考中→检索标准→核验出处→审核→报告`，默认折叠，单击展开（可再逐步看参数、原文定位和耗时）；刷新与切换历史会话后还能恢复。这是**外部实际执行与可公开决策摘要**，不能承诺真实模型未提供的隐藏逐token私有chain-of-thought。
已有React19+Vite+assistant-ui`@assistant-ui/react@^0.15.32`、现成SQLite/SSE和原审查/ReactFlow；不能换框架，也不能把Phoenix开发者UI源码直接嵌进公开聊天。保留用户侧本地真实事件+Phoenix开发者侧深度Span两个层次。

## 最小复用方案（直接复用成熟组件！）
**前端唯一主组件库=assistant-ui官方**：
https://www.assistant-ui.com/docs/guides/chain-of-thought
https://www.assistant-ui.com/docs/guides/part-grouping
参考官方`MessagePrimitive.GroupedParts`, `groupPartByType`, `ReasoningRoot/Trigger/Content`, `ToolGroupRoot/Trigger/Content`, `ToolFallback`;其旧版`ChainOfThoughtPrimitive`是Legacy，不应作为新项目默认。官方支持分组reasoning+tool，也支持把人类审批作为standalone独立控件。MIT允许在保留版权和许可前提下直接借鉴已公布React组件/安装源代码。
当前`useExternalStoreRuntime`消息文本≠自动有typed reasoning/tool parts。需要**SSE Event→UIActivityPart投影**：只有收到真实`tool_called/tool_result/decision_summary/claim_checked/...`才生成part或直接绑定独立activity-panel。不得把纯RULE_DEMO摘要伪造为模型真实token reasoning。由于同run异步sequence和replay，用`run_id,sequence`去重，按`phase/iteration/step_id/parent_step_id`分组；缺字段旧事件兼容`phase=legacy`，不能猜第2/3轮。
建议UI：
- 回答上方窄灰色状态条「已检索2项 · 发现证据不足 · 待人审」，折叠状态；
- 点击展开Timeline：每步“调查/检索标准/证据校验/独立审查/结论”，真实工具状态loading/complete/error，显示时间/页码/可靠性E0/E1；
- 点击工具一行，再展开合法参数、结果摘要、引用页；默认不把数百KB受版权保护标准原文或隐私input公开；
- 用户提出E2/E3批准必须是单独HITL控件，不可和活动trace折叠掉；
- Agent代码文件修改等事件只有真实该工具执行过才显示，本项目三个老师工具无写文件功能，不能仿造Codex操作日志。
- 轻盈视觉：正文最大宽760-860px，活动面板只占回复上方单个可折叠块，右侧开发者Inspector不在默认视线；移动390可纵向滚动。
**前端开源拼装而非全造**：Github`assistant-ui/assistant-ui`官方组件直接安装/复制并保存MIT NOTICE，局部桥接SQLite SSE即可。优先对现有assistant-ui做增量扩展，避免新的大框架。

## Phoenix优先，Langfuse不同时装
Phoenix官方：https://github.com/Arize-ai/phoenix
OpenInference：https://arize-ai.github.io/openinference/python/instrumentation/openinference-instrumentation-langchain/
1. 在**隔离环境**使用官方`arize-phoenix`服务及`phoenix-otel`、`openinference-instrumentation-langchain`；本地localhost访问，默认`TRACE_BACKEND=none`，可配`phoenix`。
2. 不从Phoenix复制它的Trace React全站源码到我们Web。其服务许可为ELv2等非MIT限制，本项目若二次分发/托管须单独法律核查。其价值是直接运行完整现成**Trace waterfall / Agent/LLM/Tool span tree**，无须我们造追踪平台。
3. 业务FastAPI线程spawn Graph worker，根context要显式传到worker，否则root span和langgraph span可能不同trace。当前老师工具是普通`spec.func`，自动OpenInference不一定采集，需要`observability/`的`trace_teacher_tool(tool_name,args_digest,source_count, status)`在**产品适配层**手动埋点，不改老师工具接口。
4. **Span可恢复权威仍是SQLite事件**：已有`run_id/sequence`严格本地持久化，OTel传输不保证逐条可靠；Phoenix中只存脱敏统计和事件span，不能作为业务唯一来源，失败导出不能导致回答失败。UI来源数据依然从SQLite replay而不是Phoenix API取。
5. 客户端可显示一个本地开发者级「Trace」入口（管理员可见），打开本地Phoenix项目页；没有已验证具体trace URL/API前不可硬编码“点击某span”的路径。普通用户只能看聊天折叠过程。不因跳转到Phoenix而丧失一体化UI目标，因为**用户过程在我们的React内就是原生可折叠**。
6. 若要更深度内嵌Phoenix via iframe/复制页面：先审许可证、认证、同源限制、CSP、iframe headers和权限；**默认拒绝简单无鉴权iframe**。将来拥有授权的单机离线工具可试，但不作为本阶段门槛。
7. `TRACE_BACKEND=phoenix`真实运行需同root/child trace_id，2个老师工具span名称正确、源与设备字段脱敏、parallel子span不散架、失效worker不产生乱序业务事件；用OTel trace export/dump验证，而不是仅看“server running”。控制额外开销、失败batch exporter静默旁路但有dropped计数。
8. Langfuse官方https://github.com/langfuse/langfuse 后期若要Prompt管理/100题质量集/模型成本另行选用；依赖复杂，不把Langfuse+Phoenix一起装，不在同run双自动instrument导致重复事件。

## 最小事件投影合同（给R9A对接，独立于内部隐藏CoT）
现有SSE外壳`{schema_version,event_id,run_id,session_id,sequence,ts,type,agent,payload}`原封不动。
新结构化event（**内部建议**；尚未写到backend）：
`type` = phase_started|agent_started|tool_called|tool_result|decision_summary|evidence_gate|review_started|claim_checked|review_result|requires_human_review|run_completed|error
`payload`至少由`phase,iteration,step_id,parent_step_id,public_rationale,tool_call_id,source_ids,verification_level,duration_ms,review_status`可选字段组成。旧事件没有时只能按`agent`作弱分组且标“旧版执行”，不可虚构迭代。
UI typed adapter仅展示**public_rationale=公开决策摘要**，不给LLM隐藏推理层承诺；当确有真实provider显式提供reasoning summary时可单独标记`provider_public_reasoning`与来源，但不可要求模型泄露内部思维链。

## 验收
- 一条真本地RULE_DEMO run：按持久化SQLite事件展示可以折叠/展开、每个tool调用状态、CID/page/E0/E1、审查，刷新恢复100%，同run SSE帧去重；不能显示虚构2轮/3轮。
- 一个模拟case（标注simulation）：phase/iteration重复和并行Auditor/Skeptic兄弟span，顺序无依赖，前端按parent_step_id稳定显示。
- 浅色/深色、桌面1280/1440及手机390，过程默认折叠，长记录不会破坏布局；现有36+及R8B新UI测试不退化。截图真实浏览器、console errors0。
- 隔离Phoenix验证：`none`模式业务全部正常；`phoenix`可见根run→graph→tool spans同trace，关键三个Teacher tools真实调用参数只采脱敏hash，secret/input原文测试不能在OTel exporter payload找到。
- 只在本地运行，默认不公网；不触碰老师PDF/Excel、三个工具的函数签名/返回、不改正式业务数据库表结构（如要追加映射字段先提出迁移合同）。
- 交付`docs/audits/R9B_TRACE_UI_PHOENIX_EVIDENCE.md`与`R9B_LICENSE_NOTICE.md`，包含源仓库/commit/许可、实际复用的组件文件、UI截图、Phoenix Trace证据与失败降级；停在READY_FOR_OWNER_REVIEW。
