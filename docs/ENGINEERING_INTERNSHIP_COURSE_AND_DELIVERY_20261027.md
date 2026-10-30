# 像“苍穹外卖”那样学一个真正的Agent全栈项目

用户希望本项目不是代做完就结束，而是像完整企业实习课题一样，从数据、DB、前后端、运行时、测试、部署、性能、协作机制都有第一性原理理解；Codex承担重复实现，ChatGPT持续规划/验收/授课，用户重点理解机制并用问题反馈。项目自洽、每轮只深入一个主题。

## 双轨并进：开发Gate vs 学习Gate
| 开发交付Gate | 本轮学的技术 | 一定亲自理解的代码 | 能验收的问题 |
|---|---|---|---|
| G0仓库+老师合同 | Git对象、sparse checkout、源码与数据血缘 | `git status/ls-files`、`convert.py` | 为什么文件不存在于工作树但GitHub已提交？ |
| G1多Agent纵向一刀 | 计算机程序状态机、ReAct、LangGraph state graph | `Harness.run`、Graph nodes、Guardrail | Agent能继续做下一步，状态来自哪里？ |
| G2前后端+SQLite | HTTP、SSE、REST、数据库范式、事务/WAL | FastAPI endpoints、SQLAlchemy models、React hooks | 刷新/断线后会话为何能恢复？ |
| G3工程语义 | IR发展史→TF-IDF/BM25→embedding、RRF→rerank | `standard_clause_search`、`knowledge/lexical.py`、语义事实模型 | 为什么5个自然句0命中、8个精准词100%？ |
| G4模型API+多Agent对照 | 函数调用Schema、上下文窗口、延迟预算、checkpoint | LLMPlanner、Supervisor、Verifier、模型事件计数 | 工具调用解析成功和答案正确为何独立？ |
| G5审查与质量工程 | 假设检验、benchmark、P50/P95、引用真实性 | E0-E3 evidence checker、冻结题集 | 为什么有条款ID也可能是错误结论？ |
| G6部署安全 | 域名、DNS、反向代理、Cloudflare Tunnel、Secrets、认证/限流 | Docker/CI/Env配置 | 隧道能提供公网地址，为何不是免费服务器？ |

## 真正值得手写的20%
Mini-agent 100-300行，三值逻辑事实抽取的小型程序，EventLog入库和重放，工具Schema守卫、基本RRF、API超时测试。
值得直接复用的80%：assistant-ui聊天组件、LangGraph checkpoint、FastAPI、SQLAlchemy、SQLite、Docling/MinerU的PDF结构化、Gradio官方演示、BFCL AST评测。
作为`LangGraph`学习者，不应该只调一次`create_react_agent`就认定会写Agent；必须亲自看懂一次GraphState的更新、Edge条件判断、ToolRegistry的权限和history的append。

## 阅读/速通资源
- `upstream/05_提交区/harness.py`：我们自己的第一门专业源码课。
- LangGraph：https://docs.langchain.com/oss/python/langgraph/workflows-agents
- Qwen-Agent：https://github.com/QwenLM/Qwen-Agent
- BFCL：https://github.com/ShishirPatil/gorilla
- assistant-ui：https://github.com/assistant-ui/assistant-ui
- Docling：https://github.com/docling-project/docling
- FastAPI：https://fastapi.tiangolo.com/tutorial/
- Full Stack Open：https://fullstackopen.com/en/
- SQLite WAL：https://sqlite.org/wal.html

## 双周迭代原则
不是要求两周干完，每个Gate可根据实测收敛。一轮定一个可复演的纵向场景，Codex提交代码与运行证据→ChatGPT检查Teacher合同/错误/性能→用户理解技术点→反馈继续。优先课程与代码一一对应，不把持续堆文件当学习完成。
