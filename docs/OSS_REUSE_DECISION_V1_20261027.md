# 开源复用清单（项目适配版）

遵守开源优先，但**不把公开库完整源码再拷贝到任务包**。必须读README、依赖、License、找到要复用的最小API/文件、补回归与attribution后才采用。各开源库实际版本/许可需在引入当日复查，禁止凭印象认定授权。

| 开源/官方项目 | 精确可复用模块 | 是否现在采用 | 原因 |
|---|---|---|---|
| [Qwen-Agent](https://github.com/QwenLM/Qwen-Agent) | native function calling, tool schema, ReAct样例 | 借鉴源码，不重写上游工具 | 模型解析是未验收核心；保留老师ToolRegistry签名 |
| [Gorilla/BFCL](https://github.com/ShishirPatil/gorilla) | AST评测与tool-call测试集设计 | **优先引入评测** | 老师要求100真实样本≥95原生合法调用 |
| [Gradio](https://github.com/gradio-app/gradio) | Blocks、JSON、Progress/streaming | **尽快采用** | 官方明确建议并要求ModelScope |
| [ModelScope Studio组件](https://github.com/modelscope/modelscope-studio) | Ant Design风格布局组件 | 仅在版本兼容且Gradio演示能跑后加 | 当前最新版依赖Gradio>=6.28；我们旧requirements是5~6，不宜一上来贸然升级 |
| [LangGraph](https://github.com/langchain-ai/langgraph) | Checkpoint、interrupt、state graph、human-in-the-loop | 条件采用 | 基础Harness已具备循环；只有需暂停恢复或复杂分支才有收益 |
| [LangChain](https://github.com/langchain-ai/langchain) | Model/Tool适配、Middleware与agent | 参考课程，不替换老师给定协议 | 禁止改老师的三个工具 |
| [FAISS](https://github.com/facebookresearch/faiss) 或 [Qdrant](https://github.com/qdrant/qdrant) | dense vector检索 | 按大样本语义测试需要再引入 | 554条并不需要立即上分布式向量库 |
| [RAGAS](https://github.com/vibrantlabsai/ragas) | 检索/groundedness评估 | 仅为补充，不代替人工逐页审查 | 高风险场景仍需E2/E3的真实条款支持 |
| [Anthropic Contextual Retrieval](https://www.anthropic.com/research/contextual-retrieval) | contextual BM25/embedding索引思路 | 下一轮选做 | 条款分成八段时别丢标准章节背景 |

关键区分：`standard_clause_search`是老师固定**对外工具签名**，可以在内部实现选实验检索引擎，只要保持状态/来源/Schema一致，并在单独分支全回归；目前 `knowledge/lexical.py` 故意只做旁路实验，不是第四个工具。

性能决策权：如果FTS5、Embedding、RRF、reranker在冻结的自然语言金标上没有质量收益/引入大量延迟，就不导入产品；实验结论按机理名称/工况描述/相似误判/负例分开统计。
