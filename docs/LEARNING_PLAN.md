# 一边交付、一边学：机械可信 Agent 学习计划

## 指导原则
**我们不是先上完大模型课程再编程**；而是从已有 Harness 中抽出最值得理解的一小段，自己解释原理→小实验→对照现成框架→回到项目写清楚。每个模块只抓20%核心理念，进入下一层再深入。

| 课 | 我们正在解决的问题 | 理论/历史 | 读哪些真实源码 | 需要做的实验与产出 |
|---|---|---|---|---|
| 1. Harness | LLM为什么不是智能体的全部？ | 有限状态机、ReAct、闭环控制、Agent vs Workflow | upstream/05_提交区/harness.py: Harness.run / RulePlanner | 规则引擎真跑、观察History与Tool循环，画状态流 |
| 2. Tools | 为何给Model API不够？ | 函数调用、接口契约、守卫条件、依赖倒置 | ToolRegistry/Guardrail/三个tools | 反例：缺参数、未知工具、未归一化介质；完成contract测试 |
| 3. Knowledge/RAG | 标准 PDF 如何变成可信可查证据？ | 倒排索引、TF-IDF、BM25、embedding、RRF、reranking | upstream/tools.standard_clause_search + knowledge/lexical.py | 8~20题小金标、Recall@5/MRR/P95，做词法基线对照 |
| 4. LLM决策 | 模型为何有时拒答/乱调工具？ | ReAct/约束解码、JSON schema、温度、模型失败回退 | upstream/LLMPlanner | 10题真实API后扩至100题 BFCL AST，分拆raw parse与fallback |
| 5. 检查器 | 如何知道模型给的条款真正成立？ | 设计契约、信息检索groundedness、假设检验 | reviewer扩展点 | E0~E3四级证据审查，测错误引用能否阻断 |
| 6. 多Agent | 多一个代理是否一定更好？ | 单agent基线、judge偏差、并行延迟与成本 | reviewer + 可选 LangGraph | 成对同题对照1/2/3体；有收益才启用 |
| 7. 产品与工程 | 为何Agent在真实服务上失控？ | OS调度、超时、异步、checkpoint、熔断、可观测性 | app/runtime.py、app/web.py | Gradio公开演示、冷/热启动、P50/P95、异常重放 |

## 技术时间线（我们讨论时按这个展开）
- 信息检索：词法匹配→TF-IDF/BM25→深度双塔向量→混合召回→cross-encoder/ColBERT重排。
- Agent：传统规则系统→搜索/规划→ReAct→工具调用格式约束→可恢复运行时和多代理协作。
- 编排：用最小 Python for-loop理解状态机；当中断恢复/人工接管变为真实需要，才比较 LangGraph checkpointer、LangChain middleware，不在本轮盲目重构。

## 第一组讨论问题
1. “盐酸腐蚀”这种术语与条款编号，BM25精确检索为何可能比embedding更好？
2. “塔顶铁离子升高，水样pH偏低”这种自然描述，没有“盐酸腐蚀”词时，向量召回何时会弥补词法召回？
3. 将一份标准切成300token chunk后，“5.1.1适用材质”与“5.1.7检测方法”分开，会不会破坏工况判定需要的上下文？
4. 既然可以用LangChain.create_agent快速组装，我们为何仍在这里保留一套教师提供的Harness？其教学价值和合同约束分别是什么？

## 学习输出约定
每次讨论都从**一段实际代码、一个公式、一个反例、一个可复现实验**出发，理论不要求一次吃完；每轮最多深入一个主模块，遇到不熟的 OS/编译/数据库概念再补基础。
