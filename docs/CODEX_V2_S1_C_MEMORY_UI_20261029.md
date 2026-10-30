# CODEX S1-C｜会话级记忆、SQLite逻辑隔离与前端公开过程
项目根：D:\作业\竞赛\计算机设计智能体\机械智能体
性质：本地临时SQLite和前端公开信息投影；禁止触碰老师/真实SQLite/在线服务。
先读`AGENTS.md`、`docs/PROJECT_STATUS_CURRENT.md`、`docs/AETHER_V2_REQUIREMENTS_ARCHITECTURE_20261029.md`及`backend/store.py`,`backend/context_slots.py`,`backend/deepseek.py`,`frontend/src/components/trace/ActivityTrace.tsx`,`frontend/src/trace-events/model.ts`,`frontend/src/api.ts`,相关测试。阅读P13实际SSE失败回放、上传文件会话隔离记录。先看当前Git status/并行改动。

## 独占可写
`backend/store.py`、新建`backend/conversation_memory.py`、`frontend/src/components/trace/ActivityTrace.tsx`、`frontend/src/trace-events/model.ts`、`tests/test_v2c_conversation_memory.py`、`frontend/src/components/trace/*.test.tsx`或新独立测试文件、`docs/audits/V2C_*.md`。不得改`backend/api.py`,`backend/deepseek.py`,`orchestration/**`,`upstream/**`,真实DB、老师签字、密钥和部署服务。对现有代码只做极小向后兼容改变；不得创建每会话一个sqlite数据库文件。

## 会话记忆目标
- 一份SQLite WAL DB中的**conversation_id逻辑独立命名空间**。消息/文件/任务/执行审计/设备上下文/摘要按cid严格过滤；用户会话A上传文件/设备条件绝不被会话B看到。Graph checkpoint是run执行恢复，不直接当跨轮的真实工程工况。
- 使用向后兼容SQLite迁移新增`conversation_memories`和可选`conversation_fact_assertions`表：严格外键/唯一/版本/源消息范围/hash，已有真实消息不丢不覆盖；迁移只能用测试环境的临时SQLite验证。DB打开时不能对生产db自动无条件重写数据；不要改`data/`。
- `ConversationMemoryService`提供`get_recent_visible_history(cid,...) / get_confirmed_facts(cid) / get_compacted_summary(cid) / propose_summary_if_needed(...)`等清晰界面；第一版无真实LLM也能工作（最近12轮或按token预算截取），摘要仅在达到阈值且Owner授权/配置Model mock时触发。每次摘要都有source message ids、结束边界、source hash、版本、模型标识、status；增量摘要不能“先覆盖旧历史再重写”导致丢事实。真实付费调用默认关闭。
- 将用户明确陈述/结构化确认的现场事实与LLM候选/报告文字分开存：每个field值、单位、事实对应对象(总压力/H2S分压/壁温等)、来源用户消息、确认/撤回/冲突标记。检测建议、模型假设、自然语言误识别不允许自动写成已观测设备事实。最新用户纠正温度时，旧assertion保留在审计历史并标superseded，模型概括不得覆盖用户更正。
- 摘要失败/含矛盾/目标超额时fallback到有界原始历史；不得跨会话混用，也不得将设备敏感资料塞进普通聊天摘要，除非当前轮显式授权最小必要字段。接口测试基于临时Store直接调用，不需要修改A负责的api。给A写清楚接线协议，等待S2单所有者接入。

## 前端公开过程
- 当前`ActivityTrace.tsx`的`argsText=JSON.stringify(step.tool.args)`和直接`AssistantToolFallback`路径可能暴露全量JSON；在公开投影上统一用allowlist+字段脱敏投影，把`tool_called`,`tool_result`,`review_result`,`source_ids`等转换为人可读步骤摘要。**不得删除SQLite源事件/SSE传输/replay**，不把隐藏LLM CoT传给前端。
- 主回答简洁，默认折叠“思维过程 · N步”，每阶段按需二次展开工具友好名称、脱敏输入参数、执行结果摘要和标准出处；老师要求用户能核查工具真实输入/输出，不能仅留“工具已调用”四个字。原始SSE、复杂JSON、secret/header/file contents、非授权现场敏感值不打印或缓存到普通UI。
- 对不存在工具事件的普通聊天不生成虚构步骤；历史R10/P13事件回放投影兼容；默认收起、移动端文字可读、键盘可操作；避免把localStorage当可信审计事实。
- 不新增公共“管理员原始SSE”入口，没有真身份认证时只能本地owner审计控制台查看SQLite。

## 测试（不许使用真实用户数据库）
临时DB独立会话A/B附件/历史/设备事实/摘要隔离、旧schema迁移、摘要增量覆盖及反向hash、用户纠正工况、LLM总结不准确/JSON坏/超时、断点恢复、无模型fallback、相同run_id幂等。前端Vitest覆盖泄密字符串不能显示、折叠、展开脱敏工具入参/结果、标准出处、未知项、历史消息、普通聊天0事件。运行`npm test -- --run`、`npm run typecheck`、`npm run build`于frontend、Python相关专项；结果含失败/skip详细说明。不能宣称完整后台鉴权/生产多租户已经实现。

## 交付
`docs/audits/V2C_MEMORY_PUBLIC_TRACE_REPORT_20261029.md`说明数据库版本、迁移脚本备份机制、摘要策略及额外model计费开关、源消息不会被覆盖、UI demo截图/测试、未覆盖端点、给S2的Adapter API、FAIL清单。生产DB/老师数据0变更。