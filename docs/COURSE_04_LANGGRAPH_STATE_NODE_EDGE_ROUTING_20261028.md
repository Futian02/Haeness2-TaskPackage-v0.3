# 第4课｜从现有AgentGraph过渡到LangGraph的State/Node/Edge/Conditional Routing（2026-10-28）

主线官方文档：https://docs.langchain.com/oss/python/langgraph/workflows-agents
Graph API：https://docs.langchain.com/oss/python/langgraph/graph-api
本地真实代码：`orchestration/graph.py` / `orchestration/semantics.py`；最小实验：`scripts/langgraph_state_routing_demo.py`。

## 1. 从问题出发
源输入：`塔顶铁离子浓度升高，尚未测厚，能确定风险等级吗？`。只要没有材质、介质，系统就应该问用户补充；有材质介质，则可以查询候选机理，但如果缺少风险矩阵因子，RBI不能硬打分；机理/条款查询应总是受用户工况和教师标准约束。

先分离三个问题：
1. **State**：工作内存里已经知道什么？包括字段、观测证据、尚缺条件、候选、来源、预算、当前结果。
2. **Node**：当前一步**做什么**？抽取现场事实/检索条款/鉴别机理/审查/报告；node通常接收state、返回局部update，不要随意直接把一个共享mutable列表塞到并发节点里。
3. **Edge**：执行完A之后**接下来去哪里**？固定线路/条件分叉；State不等于流程控制本身。

`StateGraph`基本公式：
`S_{t+1} = merge(S_t, update(node_i(S_t)))`
`node_{t+1}=route(S_{t+1})`。
实际运行不是只把agent名字排序后用for循环调用——固定序列只能表达有限分支，缺少图执行检查、并行super-step、checkpoint/interruption控制。

## 2. 最小可跑代码对应关系
```python
from typing import TypedDict, Literal
from langgraph.graph import START, END, StateGraph

class State(TypedDict):
    material: str
    medium: list[str]
    route: str
    answer: str

def supervisor(s: State):
    return {"route": "ask" if not s["material"] or not s["medium"] else "retrieve"}

def router(s: State) -> Literal["ask", "retrieve"]:
    return s["route"]

def ask(s): return {"answer": "请先提供材质与介质"}
def retrieve(s): return {"answer": "具备检索输入；实际仍须调用官方三工具"}

g = StateGraph(State)
g.add_node("supervisor", supervisor)
g.add_node("ask", ask)
g.add_node("retrieve", retrieve)
g.add_edge(START, "supervisor")
g.add_conditional_edges("supervisor", router)
g.add_edge("ask", END)
g.add_edge("retrieve", END)
graph = g.compile()
```
代码`compile()`检查图结构，并产生可执行对象；`invoke`返回最终状态，`stream(..., stream_mode='updates')`可以按节点增量观察，适合我们的FastAPI SSE.

## 3. 结构化条件路由（项目级）
```
START → Supervisor
          ├─ missing material/medium → AskForFacts → END
          ├─ out_of_domain → Reject → END
          └─ valid → EvidenceAgent → DiagnosisAgent
                                       ├─ insufficient info → Reporter (with missing questions)
                                       └─ has bounded RBI inputs → RbiSpecialist → Auditor
                                                                          ├─ evidence conflict, retry_budget>0 → EvidenceAgent
                                                                          └─ else → Reporter → END
```
路由**只读**最新State，决定下一节点；若节点需要同时更新State并指定goto，可用`Command(update=..., goto=...)`，但不再为该节点并排定义会同时触发的静态边。

## 4. reducers：为什么并行有时会数据冲突
设LexicalAgent与SemanticAgent同时计算`hits`，如果两节点都返回`{"hits":[...]}`，默认两个并发写入同一State key可能报冲突或仅有覆盖行为。应该设计为`hits: Annotated[list[EvidenceHit], operator.add]`或各写`lexical_hits`/ `semantic_hits`，再由独立融合节点做RRF/去重。**仅给list加Annotated并不保证业务去重正确**，证据ID相同应在融合节点按standard+clause编号归并并保存provenance。

## 5. state与SQLite的职责
`State`是当前run的执行上下文，LangGraph checkpointer存关键执行快照（支持超时恢复、人工interrupt、重试幂等）；`backend/store.py`SQLite WAL中的conversations/messages/agent_events是用户会话与可回放产品审计。可以都使用SQLite技术，但它们存储的语义不同；不应使用前端React状态当唯一持久来源。

## 6. 官方标准与流程图的意外关联
本轮发现GB/T26610.1-2022的5.2.1将RBI区分定性/半定量/定量三类型；7.2.2强调输入数据真实性与重要缺失，8.1.2要求按不同工况识别不同损伤模式，14.3.2规定评估周期到期后的再评估。这些不直接提供风险值，却适合做**Supervisor路由依据、NeedMoreInfo阻断检查、变更事件触发再评估**。静态文件化为事实库、状态图执行为决策过程，这两种层次互相补充。

## 7. 实际环境门禁（本轮真实失败）
本地Python3.11.9+langgraph1.1.2+langchain-core1.2.19+tenacity5.1.5：执行`python -B -m scripts.langgraph_state_routing_demo`在导入tenacity时因`asyncio.coroutine`不存在失败。**不是图算法错**；应在隔离venv升级兼容Tenacity/做pip check后重跑，禁止改全局Python、monkeypatch标准库以伪造通过。直至修好，COURSE_DEMO=BLOCKED，但代码和公式可先学习。

## 8. 必做的两个学习实验
- 路由A：输入`material=""`,`medium=[]`，只能触发Ask，不执行Teacher Tool；
- 路由B：`material="碳钢"`,`medium=["氯化氢"]`，会走检索+诊断，但应继续保持`wall_thinning=unknown`，不填L3；
- 进阶：刻意漏注册一个节点，观察编译期/构建期失败，而非SSE执行中途才KeyError；接着给图加循环次数预算。所有检查都应该有明确预期而不是只看报不报错。

## 9. 今天的检验问题
为什么`state["missing"] == []`不代表`risk_level`已可靠？提示：缺少的未知项能否由当前抽取器完整识别？标准适用性与证据支持是否经过审计？
