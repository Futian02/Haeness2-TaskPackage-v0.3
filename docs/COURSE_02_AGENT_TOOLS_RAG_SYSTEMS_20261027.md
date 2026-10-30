# 同步学习课程｜第2课：为什么RAG快不等于Agent快？(约45–70分钟，可分段)

## 课程目标
不背框架名：会画出一个完整RBI Agent的控制流，能分解延迟，辨认四种质量指标的含义，并写出一份合理的检索策略。
前提：读 `upstream/05_提交区/harness.py` 中 `Harness.run` 与 `RulePlanner`；读 `upstream/05_提交区/tools.py` 中 `standard_clause_search`；读 `knowledge/lexical.py` 和 `evals/benchmark_retrieval.py`。

## 第一节（10分钟）：从古典信息检索到RAG
1. 精确术语匹配；倒排索引；TF-IDF→BM25。
2. 双编码器embedding：`s(q,d)=q·d/(||q||||d||)`；检索语义相近但不承诺适用性。
3. Hybrid：结构化字段过滤 + BM25 + embedding，RRF(`d`)=Σ 1/(k+rank_i(d))；
4. Rerank：用cross-encoder在小候选集合上多花计算获得更好质量。
5. Contextual Retrieval：索引每一条时带上标准号、章标题、条款适用边界；原`content_raw`仍保留原文，不让LLM改写证据。
读官方：https://www.anthropic.com/research/contextual-retrieval 。

## 第二节（10分钟）：拿本项目做“查询总耗时”预算
单问题总时间不是search函数时间：
`T_total≈T_parse + Σ_t (T_model_t + T_tool_t + T_guard_t) + T_reviewer + T_UI`
已实测8个精确术语30次/题：官方词法warm均值0.2134ms、FTS5 0.0258ms、两者Recall@5=1；但首次初始化183ms vs 19.6ms（口径不同）。**这些不能推广为生产请求时延**，更不能说明embedding不需要。
模型往返多轮通常比零点几毫秒的纯内存检索更影响体验。减少无效LLM轮次、增加并行性必须仍满足“≥5轮连续工具调用能力”的老师测试（不代表每次都强行5轮）。

## 第三节（15分钟）：三个现象反例，认识工程语义
输入1：“HCl，碳钢，95℃”——术语明确，BM25可命中，结构化硬过滤必须先做。
输入2：“塔顶水pH降低，铁离子升高，近期流量波动”——没有“盐酸腐蚀”关键词，可能需要归一化术语、语义召回或模型提取意图；**不能直接得出机理**。
输入3：“材质和工况未提供，只问‘是否高风险’”——即使embedding找到了风险矩阵条款，也缺失EF/IF/MCF/PF/MDF和后果，风险等级要`null`；向量相似不是“判级依据”。

## 第四节（15分钟）：与LangChain和LangGraph如何对应
`RulePlanner`或`LLMPlanner` = 决策策略π；
`Harness.run` = 状态转移循环；
`ToolRegistry` = 执行动作集合；
`Guardrail` = 可执行约束；
`Trajectory` = 可审计动作-观察状态序列。
LangChain `create_agent` 封装了这类通用loop与Tool定义；LangGraph增加检查点、持久化、人工中断恢复。当前老师已给骨架，继续手搓最小loop有助于理解执行语义，并可对比成熟OSS的边界。只有当需求超过骨架时才考虑迁移。
官方入口：https://docs.langchain.com/oss/python/langgraph/workflows-agents
Qwen-Agent源码：https://github.com/QwenLM/Qwen-Agent
BFCL评测：https://github.com/ShishirPatil/gorilla

## 第五节（约10分钟）：最小实验
在本机项目根目录运行：
```
python -B -m evals.benchmark_retrieval
python -B -m unittest discover -s tests -v
```
然后手工拟定10个真实自然语言描述问题（候选准真值由查PDF的人工确认），观察两个检索器rank不同。没有人工真值时只演示，不宣称谁更准确。
后续追加有代表性的错误处理：0证据、相反证据、材料归一化与真值unknown。

## 迁移挑战：你能解释吗？
某用户一句话同时包含“碳钢、pH6、未测厚、能否决定检验周期”：
(1) 为什么“未测厚”不等于“测得没有减薄”？
(2) 哪个工具提供损伤候选、哪个工具找检验等级判据？
(3) 哪些参数缺失时只能给补充数据清单而不是L3？
(4) 模型输出一个合法工具调用，但结果是错条款，它通过哪种测试、未通过哪种测试？

掌握要求：能独立说清四问、画出流程、指出原Harness中一次 history append、给出一个失败示例；学习不能用“机器测试通过”冒充人的理解。
