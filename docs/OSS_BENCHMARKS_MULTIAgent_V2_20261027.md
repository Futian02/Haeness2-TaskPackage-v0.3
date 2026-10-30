# 参考项目对照（2026-10-27，架构借鉴而非代码搬运）

- `QwenLM/Qwen-Agent` https://github.com/QwenLM/Qwen-Agent
  自带PDF/docx/xlsx解析与BM25 RAG、可配置关键词生成/检索，适合参考`DocParser`/`retrieval`实现以及中文术语提取；不要直接把PDF块检索结果当标准法定依据。官方文档 https://github.com/QwenLM/Qwen-Agent/blob/main/qwen-agent-docs/website/content/en/guide/core_moduls/rag.md
- `langchain-ai/langgraph` https://github.com/langchain-ai/langgraph
  StateGraph、节点/边/Command、人审与checkpoint。优先直接调用受维护的原生API，别在本项目重造状态图。注意部分旧`langgraph-supervisor`示例已不再是优先现代路径，按最新官方文档审查版本。
- `assistant-ui/assistant-ui` https://github.com/assistant-ui/assistant-ui
  React聊天容器、工具调用卡片、会话历史，可接LangGraph或AG-UI；适合豆包式对话界面而不需要从零造聊天消息渲染。
- `CopilotKit/OpenIntelligentUI` https://github.com/copilotkit/openintelligentui
  参考面板、交互图表/Generative UI；一开始不全抄其广泛工具和服务。AG-UI事件SSE可复用RUN_STARTED、STEP、TOOL_CALL、STATE与TEXT_MESSAGE等结构。
- `CopilotKit/CopilotKit` https://github.com/CopilotKit/CopilotKit
  参考AG-UI协议和React客户端状态同步/工具渲染；可先用适配器封装现有Agent事件，不必一上来全部迁移。
- `ShishirPatil/gorilla` https://github.com/ShishirPatil/gorilla
  BFCL格式与AST成功率测评；老师要求100真模型案例不算规则fallback。

评估维度：功能复用、当前版本API稳定性、License和版权、是否可离线运行、是否改变老师对外三工具、是否便于后续MySQL与域名部署、中文/工程语义适用性、性能与测试。选一个轻量组件完成一个垂直切片，不宜同时引入多套不兼容的消息协议。

官方可视化事件参考 https://www.copilotkit.ai/blog/developers-guide-to-the-ag-ui-protocol
