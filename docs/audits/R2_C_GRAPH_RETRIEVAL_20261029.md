# R2-C Graph / Retrieval Closeout (候选实现)

日期：2026-10-29  
状态：`READY_FOR_OWNER_REVIEW`（仅C隔离候选；不是全项目验收）

## 范围与边界

只修改 `orchestration/r9_industrial_candidate.py`、新增 `tests/test_r2_graph_candidate.py`、本审计文档。`orchestration/agentic_v2.py` 未修改；R9候选仍隔离，不接入默认生产图；V2默认关闭状态不变。保留既有三只读教师工具、返回合同、工具预算/持久执行账本接口。Graph测试使用fake工具；另有下列本机冻结索引只读探针。未调用真实付费LLM、未重启服务、未修改数据库或教师数据。

未获得A窗口审核索引/接口接线确认；本实现未声称已采用审核后的语义索引或embedding reranker。

## 实现

- 给SCC概念问题加规则化直答 fallback；这是F1概念应答路径，不代表模型自主知识或标准条款引用。通用概念解释可不要求设备工况；输出不附造假引用。
- 补强专业意图路由、设备渗漏问候、混合任务路由与查询同义词扩展；多查询仍由原三工具、预算和图节点限制。
- 新增**词面相关性启发式**，使用问题/扩展查询词、来源标题与正文及少量明确的碰撞族规则。增加HCl vs 烟气/硫酸/土壤/辐照/过热、湿H2S vs 不相干腐蚀族反例识别。疑似不相关来源仍留在引用候选中并带 `low_relevance_candidate`，不硬删除、不据此做全局证据排除；无法判断时标 `weak_relation_candidate` / `relation_unverified`。相关性标记不代表适用性：所有来源 `applicability=UNKNOWN`、`may_support_claim=false`。Hypothesis晋升门现在要求`topic_overlap_candidate`；`weak_relation_candidate`、`relation_unverified`、`low_relevance_candidate`保留在citations但不进入hypotheses。damage_mechanism_query与standard_clause_search两条路径共用此门。命中来源仍为E0、`may_support_claim=false`，不得当作工程结论。对壳体磕碰任务加入基于真实冻结索引的限定词面锚点：TSG 21-2016 8.5.8、8.3.6、8.5.1形成有条件候选；耐火材料、爆破片等组件范围碰撞及其他弱来源保留引用但不晋升。该规则是透明词面/作用域启发式，不是语义embedding。
- 为工具调用记录观测到的耗时摘要（p50/p95/sample_count）；空调用时三个字段分别为null/null/0。
- 修复工具来源 `score=None` 排序导致的TypeError（按缺失分数最低值排序）。

## 测试结果

命令（隔离临时SQLite路径）：

```powershell
$env:DATABASE_URL=Join-Path $env:TEMP 'r2c-owner-impact-final.sqlite'
.\.venv-langgraph\Scripts\python.exe -B -m py_compile orchestration\r9_industrial_candidate.py orchestration\agentic_v2.py tests\test_r2_graph_candidate.py
.\.venv-langgraph\Scripts\python.exe -B -m unittest tests.test_r2_graph_candidate tests.test_r9a_industrial_candidate tests.test_v2b_agentic_graph tests.test_v2_s24_mixed_dag tests.test_v2_s24_durable_execution tests.test_v2_s25_lease_fencing tests.test_v2_s25_tool_process tests.test_v2_s25_sse_concurrency tests.test_v2a_router_gateway tests.test_p12_context_flow -q
```

实际输出：`Ran 100 tests in 28.015s — OK`。

| Suite | 结果/分母 |
|---|---:|
| `tests.test_r2_graph_candidate` | 9/9 PASS；其中60条路由专业/红队样例60/60；另含真实冻结索引B回归 |
| `tests.test_r9a_industrial_candidate` | 19/19 PASS（R9原基线）|
| V2B、S2.4混合DAG/持久账本、S2.5 fencing/tool-process/SSE并发 | 余项由总数扣除：55/55 PASS |
| `tests.test_v2a_router_gateway`, `tests.test_p12_context_flow` | 17/17 PASS（context_slots恢复后的依赖集成复测）|
| 总计 | 100/100 PASS |

本次R2路由集覆盖SCC概念直答、零来源、设备工况缺失、A/B专业任务、HCl/H2S误召回、混合意图、工具超时/失败、预算/合同边界及真实索引B反例。60不是完整端到端模型调用，而是确定性路由表案例。fake HCl/H2S反例中，damage_mechanism_query与standard_clause_search返回的误配来源均保留citation、未生成hypothesis。

另：父窗口报告 `tests.test_p0_expert_guidance` 23项共享全链测试中存在API health字段、context medium原始值和R9 fixture相关失败/错误；该suite不属于C写权限，本窗口未修改其文件。不得将本C suite的100/100外推为P0全链通过。未做真实浏览器、真实模型/API、线上服务验收。

## 本机只读检索观察与延迟

使用 `IndustrialCandidate()` 默认只读本地冻结索引/教师工具，无远端LLM。数值是单次本地样本，不是基准或统计置信区间；每题工具耗时样本数均为3。

| 查询 | 调用数 | p50 / p95 (ms) | 观察 |
|---|---:|---:|---|
| SCC概念定义 | 0 | N/A | 直接概念fallback |
| 300系、碱式酸性水、60℃弯头减薄调查 | 3 | 6.407 / 6.407 | 命中`GBT30579-2022-5.23`“酸性水腐蚀(碱式酸性水)”；适用性仍UNKNOWN |
| 壳体磕碰后停用/维修/验收 | 3 | 6.349 / 6.349 | 14条citation（修复前试探版本误提升14条；修复后仅4条有条件候选）：TSG21-2016-8.1.7.1（仅已发现裂纹时缩短周期）、8.3.6、8.5.8（仅已发现裂纹且满足规程条件）、8.5.1；碰撞误召回如耐火材料退化、爆破片检验时间调整、再热裂纹保留citation但不晋升。不会给出停用许可/验收限值 |
| HCl烟气腐蚀 | 3 | 4.606 / 4.606 | 土壤、硫酸、辐照、燃烧爆炸、过热机制标为低相关但仍保留候选；检验方法条目未强行判无关 |
| 湿H2S损伤 | 3 | 4.694 / 4.694 | 上述异族机理候选标低相关；通用在线检验方法仍是待审候选 |

这些结果证实工具链和词面重排能标注已知碰撞类型，不证明召回充分、机制适用或工具结果语义正确。实际来源仍有多条弱相关项；无审核人员标签的precision/recall、真实语义反例集和标准条款级人工核验。

## 未完成 / Owner 联调

- 等A窗口确认只读审核索引接口后，再接审核来源关系/定位信号；本轮不自行改API、backend、SQLite。
- 仍需独立人工审核来源关系与适用范围，尤其材料/介质/温压和设备作用域；标为candidate的来源不等于相关证据。
- 仍需真实模型主回答验证、全链P0回归清零、真实浏览器/服务验收；均未完成。
- `agentic_v2.py`未编辑；相关集成suite通过，但该项不改变V2默认关闭，也不代表S2所有场景已验收。

## SHA-256

交付文件 SHA-256：

| 文件 | SHA-256 |
|---|---|
| `orchestration/r9_industrial_candidate.py` | `004C2BD2CA6FEFC8D076BD1A311AF232987DD8DBBE8BD5E685DC2BD884BFE224` |
| `orchestration/agentic_v2.py`（本轮未改；基线哈希） | `AAEE340B5A9A57007973AFE23FEF34D06047703F517F68255C38BE5360D299BA` |
| `tests/test_r2_graph_candidate.py` | `8AEA6313CCFFE4DC8FA0C5EE0B68E14FDBCD477A8034C3611765D0BFBC45B581` |

复核命令：

```powershell
Get-FileHash orchestration\r9_industrial_candidate.py, orchestration\agentic_v2.py, tests\test_r2_graph_candidate.py, docs\audits\R2_C_GRAPH_RETRIEVAL_20261029.md -Algorithm SHA256
```















