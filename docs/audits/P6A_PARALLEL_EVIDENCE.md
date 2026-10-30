# P6-A 有界并行证据审查实验

状态：**READY_FOR_OWNER_REVIEW**（实验隔离；生产 `AgentGraph.run` 仍只走原顺序图；未部署）

日期：2026-10-28

## 边界与设计

- 新实验入口 `orchestration.p6_parallel_audit` 单独构造 LangGraph StateGraph，`EvidenceAuditor` 与 `Skeptic` 从同一只读快照在一个 super-step 并行；两者不传递自然语言审查结果。下游 `merge` 等待两个分支完成，再对独立结构化视角做稳定合并。
- 两路只写 `audit_updates` / `skeptic_updates`，均显式 `Annotated[list[...], operator.add]` reducer；不在 fan-out 分支写 `claims`、`disagreements`、`gaps`。合并键为 `(run_id, claim_id, source_clause_id, origin_agent, attempt_id)`；同 attempt 重放幂等，不同 attempt 保留；不同 agent 的相反判断不会合并丢失。
- Provenance grade 仅由独立审核结果映射，审核状态固定 `requires_human_review`；Skeptic结果等级固定E0。绝不由 reducer 升级E2/E3，不生成设备级风险等级。调用方输入快照不会被修改。
- 此 StateGraph 只接受调用方提供的当前run工具结果与canonical索引，不执行老师工具；没有加官方接口/工具。`RULE_DEMO`仍为规则实验，不是多LLM或专家金标。生产默认路径无并行flag、无路由变更。

## 本轮实测

### Reducer 负/正例与并发审查

命令：

```powershell
.\.venv-langgraph\Scripts\python.exe -B -m scripts.lesson05_parallel_reducers
.\.venv-langgraph\Scripts\python.exe -B -m unittest tests.test_p6a_parallel_evidence -v
```

原课程负例实际得到 `InvalidUpdateError At key 'notes': Can receive only one value per step`；带 reducer 的真实 LangGraph fan-in 输出 EvidenceAgent 与 Skeptic 两路，课程脚本 `LESSON_05_PARALLEL_REDUCER_PASS`。P6A定向测试 **7/7 PASS**，包括20个合成场景、E0/E1上限、unknown、缺源、缺字段失败关闭、冲突双视角保留、随机分支完成顺序下的merge一致性、attempt去重、无reducer并发冲突。

### 20个合成输入顺序/并行比较

命令：

```powershell
.\.venv-langgraph\Scripts\python.exe -B -m evals.p6a_parallel_evidence
```

结果文件：`docs/audits/P6A_PARALLEL_EVIDENCE.json`。本机日志：parallel P50/P95=`3.190/3.950 ms`；sequential helper P50/P95=`0.084/0.114 ms`；每模式20个场景，工具调用总数均20，重复source ID读取0，非法风险等级/E2/E3计数0，专业准确率 `null`。计时包含parallel分支每次建图/compile/invoke，而顺序侧使用直接helper调用，口径不等价，只是当前脚手架开销观察，不作为生产并行性能结论。实验输入均为合成fixture，非真实标准引文、非专家Gold。

### 完整回归及链路门禁

| 命令 | 实际结果 |
|---|---|
| `\.venv-langgraph\Scripts\python.exe -B -m unittest discover -s tests -q` | **94/94 PASS**（P6新增后） |
| `\.venv-langgraph\Scripts\python.exe -B -m evals.owner_p3_regression_probe` | 缺页保持missing/E0、同run双SSE只执行一次、裸请求无注入设备事实、教师source schema无quote；`OWNER_P4_REGRESSION_PROBE_PASS` |
| `\.venv-langgraph\Scripts\python.exe -B -m evals.owner_p4_integration_probe` | 44 SSE events / 2 claims / 2 disagreements / 7 references；run completed；failed run后旧worker追加事件收到 `PermissionError` |
| `\.venv-langgraph\Scripts\python.exe -B upstream\04_接口文档\validate.py --final` | 554/554 clauses、200/200 trajectories，官方终验PASS |

完整 unittest 包含 P5A 租约/事件回归及API/SSE持久化测试。P4集成探针实际记录的44条事件保持连续业务链结果，SSE读写代码未改。P6 parallel StateGraph本身不接SQLite写端、不发SSE事件，因此本实验没有独立伪造SSE时序数据；生产SSE正确性仍由上述API/SQLite回归链验证。

## 变更清单

- 新增 `orchestration/p6_parallel_audit.py`：隔离的只读并行审核图、角色专属reducer、幂等合并。
- 新增 `tests/test_p6a_parallel_evidence.py`：LangGraph负例、场景/grade/冲突/retry/乱序/输入失败测试。
- 新增 `evals/p6a_parallel_evidence.py`：20例比较器，生成JSON证据。
- 新增 `docs/audits/P6A_PARALLEL_EVIDENCE.json`：机器可读实测指标。
- 本审计报告。

无失败项。未修改 backend/frontend/upstream，教师三工具与五键协议、原始Excel/PDF、正式JSONL全部保持冻结；未执行数据转换、Excel写盘或公网部署，无Git索引/提交操作。

## Owner复核点 / 下一步

1. 审阅各分支审查输入快照字段、`attempt_id`定义和attempt间结果保留策略。
2. 决定是否继续只读并行实验；真实工具副作用/业务SSE事件租约仍必须由P5A写入路径处理，不能把LangGraph reducer当成SQLite事务锁。
3. 没有专家金标前只检查状态/引用完整性，不报告准确率；RULE_DEMO不是多模型交叉审核，也不产生E2/E3结论。
