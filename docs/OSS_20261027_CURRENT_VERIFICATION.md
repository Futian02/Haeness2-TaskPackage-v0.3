# 2026-10-27 开源方案现状复核（持续验证）
此文件记录本轮从官方/源仓库可核实的选择依据；每个实际依赖的确切版本还需本地锁文件与许可证扫描，不应仅靠本文件。

## 1. 多智能体编排
- LangGraph（https://github.com/langchain-ai/langgraph）：低层有状态工作流与checkpoint，适合我们学习GraphState/conditional edges/interrupt；SQLite checkpoints可本地用，应用数据库业务表独立管理。
- langgraph-supervisor-py（https://github.com/langchain-ai/langgraph-supervisor-py）：**GitHub仓库于2026-09-20归档，只读**，README明确推荐多数项目直接使用手工supervisor + tools pattern。结论：不要在首轮引入这个已归档的扩展包；直接写LangGraph StateGraph和角色交接。
- Qwen-Agent（https://github.com/QwenLM/Qwen-Agent）：可借鉴工具Schema与模型调用方法，但不替代老师ToolRegistry。

## 2. 聊天可视化
- assistant-ui（https://github.com/assistant-ui/assistant-ui）：MIT许可，React线程/流式/工具可视化 primitives，支持LangGraph与自定义运行时；优先借用消息显示与交互，减少重复造轮子。
- CopilotKit（https://docs.copilotkit.ai/langgraph-python）：AG-UI用于后续复杂共享状态、agent interrupt和HITL审批；初版先选一个UI框架，不叠两套runtime。
- 可观测参考：github.com/vllora/vllora 的Agent调用时间线/成本可视化；只做布局灵感，不直接搬全部仓库。

## 3. PDF解析
- Docling（https://github.com/docling-project/docling）：GitHub官方LICENSE MIT；支持PDF表格/页结构、多格式、结构化JSON、离线转换，先用1-3页抽样比较。
- MinerU（https://github.com/opendatalab/MinerU）：具备复杂文档/PDF/OCR/公式表格能力，许可需要查看当前上游LICENSE及权利义务，尤其公开在线服务的归属要求。不要因为技术方便忽略许可。
- **无必要对已人工结构化554条重新OCR**；只用PDF验证那些原文疑点与增量资料，OCR结果作为待人工核对候选。

## 4. 部署
- Cloudflare Tunnel（https://developers.cloudflare.com/tunnel/get-started/）：本地服务主动建立出站隧道，可映射域名，不要求源站公网IP；**源站仍须一直在线**，不能称为免费计算实例。
- Render Free（https://render.com/docs/free）：其免费Web没有持久磁盘，免费Postgres有时间限制。SQLite本地持久化不应直接放在其临时文件系统上期待永久保存。
- ModelScope Studio为老师指定Gradio交付；正式部署前查当期资源、权限和隐私，避免假设免费持续运行。

## 5. 当前结论
首版优先：LangGraph StateGraph + 原师给Harness + FastAPI + SQLite + assistant-ui。
备用：若前端框架版本/协议适配成本过高，允许自建最小React事件流渲染，但需要用冻结API合同与测试证明一致；后续再迁回assistant-ui。
不建议：首轮安装全套GraphRAG图数据库、全部Agent Framework、大规模新PDF OCR、未经许可复制第三方整个项目目录。
