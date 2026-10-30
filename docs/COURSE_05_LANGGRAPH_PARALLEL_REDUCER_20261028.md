# 第5课｜为什么LangGraph并行节点必须设计Reducer（2026-10-28）

官方：https://docs.langchain.com/oss/python/langgraph/graph-api#reducers
结合当前真实项目：`orchestration/graph.py` 仍是顺序七角色的 StateGraph。下列示例是独立学习，不改变老师固定三个工具或正式工程判断。
最小真实实验：`scripts/lesson05_parallel_reducers.py`
运行命令：`./.venv-langgraph/Scripts/python.exe -B -m scripts.lesson05_parallel_reducers`

## 动机：为什么多个Node同时写回会冲突？
当前真实专业任务：设备现场铁离子升高、尚未测厚，EvidenceAgent检索候选标准、Skeptic独立检验缺失现场证据。
这两条执行路径应该并行，减少串行等待，又不能由Skeptic简单复制Diagnosis文字。
LangGraph基于Pregel风格的super-step机制：节点在同一轮读入状态快照，产生各自局部更新。若两个节点在同一super-step更新同一个无reducer字段，默认字段是覆盖语义，而并发覆盖没有唯一正确的新值，于是报`InvalidUpdateError`。

公式：设状态S_t，两节点分别返回更新u_A,u_B。无Reducer情况下同一key的`S_{t+1}[key]`不确定；指定Reducer R，可定义
`S_{t+1}[key]=R(R(S_t[key],u_A[key]),u_B[key])`。
R本质是二元更新合并函数。并发合并应考虑交换性/结合性以及重复、重试引起的幂等性，不要假定`operator.add`保证逻辑去重和固定顺序。

## 真实实验（本机通过）
① `BadState.notes: list[str]`无Reducer。START同时向search和skeptic发送输入，两者都更新notes；本机实际返回
`EXPECTED_CONFLICT InvalidUpdateError At key 'notes': Can receive only one value per step...`。
② `State.candidates: Annotated[list[Evidence],operator.add]`和`trace: Annotated[list[str],operator.add]`允许两节点同轮追加。随后`graph.add_edge(['evidence','skeptic'],'merge')`做fan-in barrier，证据独立汇合，Merge节点按`(claim_id,agent)`做确定性排序再分析。
本机结果：两条`hyp-1`分别来自EvidenceAgent和Skeptic；最终`['候选待核：不生成设备风险等级','测厚状态=unknown']`；`LESSON_05_PARALLEL_REDUCER_PASS`。
所有`TEST-CLAUSE-S1`均明确是教学fixture，未引用真实原文。

## 真正生产化之前
- 共享状态应将`source_hits`和`counterevidence_hits`分别定型，避免将所有原始对象放进同一个列表导致不清楚来源角色；每项包含`claim_id/source_clause_id/origin_agent/run_id/attempt_id`。
- `operator.add`保证拼接，不保证去重、排序、源版本、同一request重复性。归并节点按`(run_id,claim_id,source_clause_id,origin_agent,attempt_id)`做幂等合并，保存原始两个审查视角、正负证据不要只保留最高分。
- 比较版本`sequential`和`parallel`，采用同一输入、固定工具快照、20+条synthetic负例和后续领域专家签核集；测质量门禁、额外调用、P50/P95、总token成本（真实模型接入以后）。
- P5A已经保证SQLite一个run只启动一次并有有效token；若并行节点共享事件流，业务事件writer必须维持全局sequence有序及租约CAS；而StateGraph的reducer解决的是图State的并行更新，**不是SQLite事件顺序冲突**。
- 当前RULE_DEMO只跑确定性逻辑，不可因并行了便说是独立多LLM专家审查；若通过interrupt让用户审核，恢复后节点前缀可重跑，任何副作用应幂等。
- 下一课：checkpoint vs business Store vs human approval；真正的审核状态是`pending→approved/rejected`，E2/E3需来源与审核身份/时间，不是LLM输出`approved`字符串。

## 课后思考
同一个标准条款ID被两路召回、一次支持、一次指出条件不满足，是否应该把两个事件去重成一条“E1”？不可以。要区分“相同source id”的数据去重与“不同审查视角”的证据保留，后者是监督报告的价值所在。
