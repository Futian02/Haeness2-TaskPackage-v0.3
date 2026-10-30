# V2-A 路由网关验收报告（2026-10-29）

状态：`READY_FOR_OWNER_REVIEW`（实现与专项验收已完成；全量回归仍有 1 FAIL、3 ERROR、3 SKIP，见下文）。本报告为机器验收记录，不含人工签署，也不宣称实测线上分布或真实 DeepSeek 路由调用。

## 1. 本窗口边界与变更

只写入 S1-A 允许范围：

| 文件 | 修改 |
|---|---|
| `backend/intent_router_v2.py` | 新增严格结构化意图 schema、DAG 校验、模型候选解析、确定性安全策略门、注入式 provider 接口、失败回退 |
| `backend/api.py` | 每轮存储路由快照；普通聊天走 FastAPI worker 直接分支；准确记录路由模型与答复模型调用数；保留 R9/SSE/SQLite/事件兼容 |
| `orchestration/intent.py` | 以 V2 确定性策略作为 legacy 分类投影，保留原有子类和上下文后续问法兼容 |
| `tests/test_v2a_router_gateway.py` | 新增路由、模型 Mock、SSE/SQLite 端到端与错误门禁测试 |
| `evals/v2a_router_gold.jsonl` | 新增 120 条作者整理盲测集 |
| `docs/audits/V2A_ROUTER_GATE_REVIEW_20261029.md` | 本验收报告 |

未修改 `backend/store.py`、`backend/deepseek.py`、R9 Graph、`frontend/**`、`upstream/**`、正式数据、环境密钥、数据库文件或服务进程；未提交、未部署、未重启 8000 端口进程。普通 FastAPI 测试在临时 SQLite 数据库中完成。

## 2. 路由行为与安全边界

### 路由行为

| 路由 | 当前执行 | 路由模型调用数 | 说明 |
|---|---|---:|---|
| `GENERAL` | FastAPI worker 内直答；不调用 `graph.run`、不调用教师工具 | 默认 0；若显式注入并启用结构化 provider 则 1 | `DEEPSEEK` 模式调用既有 `deepseek.generate_chat`；`RULE_DEMO` 使用现有本地对话回退 |
| `STANDARD_LOOKUP` | 复用 R9 Graph，标记 `TRANSITIONAL_R9` | 默认 0 | 未冒称独立轻量标准检索器 |
| `ENGINEERING` | 复用原 R9 Graph | 默认 0 | 继续使用已有三教师工具注册表与图内安全门 |
| `MIXED` | 解析成最多 4 个有向、拓扑有序子任务；当前按工程优先复用 R9，标记 `MIXED_ENGINEERING_FIRST_R9` | 默认 0 | 子任务 DAG 是规划快照，不代表已独立并行执行 |
| `CLARIFICATION` | 当前兼容回退至 R9 Graph | 默认 0 | 暂无单独轻量澄清执行器 |

默认 `V2A_LLM_ROUTER_ENABLED=0`；本次没有发出真实模型 HTTP 请求，也未访问真实付费模型。新路由模块不读取密钥；但既有 `backend.deepseek` 在 API 导入时会按原逻辑加载 `.env.local` 到进程环境（本任务未修改该模块或密钥）。结构化路由调用通过进程内注入的 callable 驱动，并由测试 Mock。即使仅把路由 feature flag 打开、没有显式注入 provider，也会安全回退，不会自行创建网络客户端。

结构化模型仅提出 `primary_route`、`subtasks`、澄清字段和公开理由。Pydantic 严格枚举/额外字段拒绝、最多 4 子任务、DAG依赖排序和 `model_usage` 服务器字段校验均已实现；模型不能授权工具、宣称人工审核、输出安全许可或将专业安全请求降为普通聊天。安全请求的确定性门禁优先。

### 调用次数口径

终态 `run_completed` 同时写出：`intent_model_request_count`、`generation_model_request_count` 和合计 `model_request_count`。普通 DeepSeek 聊天在默认本地意图路由下为 0+1=1；若启用并注入路由 provider，则为 1+1=2。专业/标准路径如果配置 DeepSeek 并触发表达整理，答复生成也单独计为一次。`intent_routed` 是开始阶段事件，只记录意图路由请求数；终态计数包含后续答复请求，避免把“路由器一次”误报为整轮仅一次。

## 3. 65 条与 120 条样本验收

### Owner 固定 65 条

命令：

```powershell
.\.venv-langgraph\Scripts\python.exe -B evals/owner_mixed_intent_route_audit.py
```

结果：`65/65` 通过，`misrouted=0`。类别：general 23、standard 15、engineering 27。该集是 Owner 筛选的困难样本，不是随机总体准确率估计。

### 新增 120 条作者整理盲测

专项测试命令：

```powershell
.\.venv-langgraph\Scripts\python.exe -B -m unittest discover -s tests -p test_v2a_router_gateway.py -v
```

最终结果：`11 tests, OK`。120 条结果按意图期望类别统计：general `21/21`、standard `17/17`、engineering `82/82`（其中安全混合主路由 7 条）；总误分 `0/120`，professional→general `0`，general→professional `0`。分组覆盖闲聊、标准查证、专业机制/RBI、混合、改口/更正、缺上下文、提示注入与文字转换。该集合为本窗口新建的作者整理 holdout，不是外部独立盲标或线上抽样；结果不能外推线上流量分布。

## 4. API / Mock / 存储与负载验收

`test_v2a_router_gateway.py` 覆盖：

- JSON schema / 枚举 / 多余授权字段 / 过多子任务拒绝。
- Mock 合法模型建议及策略门改写；非法 JSON、超时、provider 异常、非法工具字段、权限/人工签署声明的 fail-safe 回退。
- 混合问法生成 `standard → engineering → synthesis` 拓扑 DAG；无上下文设备安全请求仍进入专业路由。
- 普通 DeepSeek Mock 聊天的 FastAPI 路径：`graph.run` 调用次数为 0，mock 生成器调用 1 次，run 与 assistant message 同一 SQLite run_id，SSE 含终态事件。
- 普通 chat 同时注入路由 provider 和答复 Mock 时，终态模型请求总数为 2；标准与专业请求继续到 R9 Graph。

`test_p13_router_hypotheses` + `test_r10_casual_chat`：`14/14 OK`。`test_p4a_api_safety`：`11/11 OK`。P13 本地负载测试在同一全量回归中通过：并发 1/4/8 各 100 run、均 0 错误，且测试断言每 run 单一有序终态；测得 p95 分别约 `90.9ms / 304.6ms / 1469.7ms`。worker 容量限制与 queued/429 原策略未移除。

## 5. 官方数据验证与全量回归

官方只读验证命令：

```powershell
.\.venv-langgraph\Scripts\python.exe -B upstream/04_接口文档/validate.py --final
```

结果：`PASS`，clauses `554/554`、trajectories `200/200` 通过；其中 damage_mechanism `82`、RBI `472`、multi-step `144`、三类特殊轨迹各 `15`。本次只读运行工具，没有改动 upstream 文件。

全量回归命令：

```powershell
.\.venv-langgraph\Scripts\python.exe -B -m unittest discover -s tests -v
```

最终真实结果：`274 tests in 56.197s`，`FAILED (failures=1, errors=3, skipped=3)`。专项 S1-A、P13路由、R10聊天、P4A API门禁、官方数据验收均通过；不得将全量回归写成 PASS。

剩余失败/错误：

1. **FAIL** `test_r9a_industrial_candidate.R9AIndustrialCandidateTests.test_low_quality_retrieval_rewrites_and_retries_with_traceable_source`：预期工具调用 `>=2`，观测 `0`。
2. **ERROR** `test_r9a_industrial_candidate.R9AIndustrialCandidateTests.test_identical_query_zero_information_gain_stops_loop`：结果 `gate_decisions` 为空，断言读取最后 gate 时 `IndexError`。
3. **ERROR** `test_r9a_industrial_candidate.R9AIndustrialCandidateTests.test_transient_tool_failure_retries_and_records_attempt_count`：`tool_calls` 中没有 `standard_clause_search`，抛 `StopIteration`。
4. **ERROR** `test_p16_a_evidence42` 收集失败：测试环境 `.venv-langgraph` 缺 `fitz`/PyMuPDF（`ModuleNotFoundError`）。未安装依赖、未扩大本窗口文件边界。
5. **SKIP 3**：可选 Phoenix/OpenInference 观测 SDK 测试因隔离环境未安装而按测试条件 skip。

以上 R9 Graph/P16 项均未由本窗口文件修改；本次没有可证明的任务前基线，因此记录为“当前回归遗留”，不伪称已证实是历史失败或本次无关。

## 6. 限制与 Owner 后续决策

- 实际付费结构化路由未接线/未调用。当前交付的是生产前的注入式 provider 协议和 mockable 路由器；需 Owner 单独批准并提供正式 provider 接线位置、调用预算与密钥读取契约，方可接入真实结构化模型。现有环境 flag 默认 off，不以支付授权作推断。
- 新增 120 条是作者整理测试集，不是独立盲标；提交 Owner 或领域审核者作盲标复核后再将结果定为验收金标准。
- 混合 DAG 当前只做路由快照与保守工程优先调度，未实现分子任务并行执行。
- `STANDARD_LOOKUP`、`ENGINEERING` 继续依赖 R9；上列 R9 Graph 回归项需其所有者在对应窗口修复并重跑。
- 完成共享 API 集成前，Owner 应审核一般/标准/专业 SSE 事件和调用数口径；尤其是增加的 `phase_started(route=...)` 兼容事件。

结论：S1-A 有界实现和专项测试完成，当前状态 `READY_FOR_OWNER_REVIEW`；全量测试存在上述可复现遗留，等待 Owner 对真实模型接线、盲测金标准以及 R9/P16 修复范围审阅。
