# S2.6 真实 LLM Agent / 工具 / 压力验收记录

**状态：`REVIEW_BLOCKED` — Gate 0 已完成有界预检；Gate 1 的 100 次真实请求待 Owner 给出剩余费用上限。**

本轮只运行隔离研究脚本和本地测试。V2 默认仍关闭；没有重启/部署服务、改 API 配置、访问正式会话、修改教师数据或改变 R9。

## 范围及修改文件

新增文件全部位于 S2.6 范围：

- `scripts/s26_prepare_dataset.py`：生成固定 120 条合成提示集。
- `scripts/s26_live_preflight.py`：明确 opt-in 的真实 DeepSeek 预检；单轮最多 10 请求、输出上限 700、30 秒超时、无自动重试、记录脱敏结构元数据。
- `scripts/s26_offline_audit.py`：离线校验数据集与确定性工具门禁。
- `evals/s26/synthetic_cases.jsonl`、`evals/s26/offline_audit.json`、各次真实预检 JSONL、`evals/s26/preflight_accounting.json`。
- 本审计报告。

未改写既有 Provider、`orchestration/agentic_v2.py`、API、执行账本或 `upstream/**`。合成集标签由开发者整理，标记为 provisional，不是独立专家盲标金标。

## Gate 0：真实模型与费用 / Token 预检

### 固定合成集

- **120** 条，SHA-256：`76dcd75e0ae2152e84d997d89b835189f55ace7245a790ec1d8a68cb227f4a2a`。
- 覆盖通用/标准检索/材料未知调查/确认工况机理候选/RBI缺少PoF-CoF/混合任务/翻译/烟气露点反例/H2S分压反例/防护材料语义/提示注入/用户纠正等。
- 数据标签明确 `developer_curated_provisional_not_independent_expert_gold`，不得以本集声称专业准确率。

### 真实调用账目

真实 Provider 为 `deepseek / deepseek-flash`。为修复本地脚本写盘故障，部分合成 case 被重复请求；该故障没有导致模型自动重试，但使 7 次请求没有逐条落盘，故不把它们算作原生解析成功，也不虚构精确 Token。

| 指标 | 观测 |
|---|---:|
| Gate 0 实际供应商请求数 | **19**（任务上限 30）|
| 有逐条记录的请求 | 12 |
| 有记录的原生 Pydantic 解析成功 | 11 |
| 有记录的原生解析失败 | 1 |
| 不同合成 case 中至少一次可验证原生解析成功 | **10/10** |
| 未记录 usage 的请求 | 8（含 7 次脚本写盘异常及 1 次 Provider/解析错误）|
| 逐条可核 Token | 输入 3,750 + 输出 4,523 = **8,273** |
| 未计量请求保守预留 | 输入 28,000 + 输出 5,250 tokens |
| 保守总 Token 上界 | **41,523** |
| 后续 Gate 0 全局硬上限 | 30 请求 / 50,000 保守 Token；预算状态当前为 19 请求 / 41,523，10例续跑被本地脚本在发请求前拦停 |
| 实测 Token 对应峰时费用估计 | **$0.0065526** |
| 保守费用上界 | **$0.0212526** |

费用按照 DeepSeek 官方价格表当前公布的 `deepseek-flash` 峰时 cache-miss 输入 $0.30/百万 tokens、输出 $1.20/百万 tokens 估算；对未计量请求采用每次输入 3,500 tokens 的保守预留，并按请求时输出 cap 预留（7×700、1×350）。价格可能调整，实际账单以供应商为准。来源：[DeepSeek Models & Pricing](https://api-docs.deepseek.com/quick_start/pricing/)。

可见成功响应均由原生 Planner `PlanProposal` Pydantic 校验，`fallback_used=false`。没有把 Mock、规则回退或业务工具执行结果算进原生解析成功。11 条已落盘成功调用的 latency 为 2.12–4.74 秒，样本 p50=3.111 秒、nearest-rank p95=4.741 秒；这是包含重复case的串行预检统计，不代表服务压力、线上 p95 或容量结论。

### 预检发现

1. 原生 JSON + Planner schema 在 10 个不同合成 case 上均至少有一次解析成功；这**不等于**100 条门槛达标，也不代表路由正确。
2. `GENERAL_EXPLANATION` 样本被模型提出 `standard_clause_search`，说明“可一般解释”与“必须查库”的边界还需真实盲评。
3. 工况未知的工程调查样本有模型提议 `damage_mechanism_query` 的迹象；现有策略门应在执行前据显式材料/介质拒绝或改路由，但此轮没有保存其参数，故不声称策略实际拦截率。
4. 有一个真实 Provider 调用未完成解析；最初输出上限为 350 tokens，适配器只暴露 `RuntimeError`，其底层错误原因和 usage 没有入账。不能确证是截断还是其他响应异常。
5. 首次恢复性预检遇到本地写盘变量错误，导致 7 个已经发出的请求没有逐请求 JSONL；已在脚本中修复，但这些调用只能进入请求数与保守成本账，不进入成功率分子。

## 离线结构 / 策略检查

`scripts/s26_offline_audit.py` 输出：**8/8 PASS**，真实模型请求数 0。检查包括：120 条数据集完整、提示哈希、三工具白名单、合法标准搜索参数、query/keyword 不一致拒绝、第四工具拒绝、工况不足时 DM 请求改走标准检索、RBI 输入不足时不能直接产生风险等级路线。

这些是确定性门禁和固定夹具检查，不等价于模型100例的原生工具参数合法率，也不代替标准/设备专业人士复核。

历史 S2.5 回归专项本地重跑：

```text
python -m unittest tests.test_v2_s25_lease_fencing tests.test_v2_s25_sse_concurrency tests.test_v2_s25_tool_process -v
Ran 7 tests — OK
```

`pytest` 在 `.venv-langgraph` 环境未安装；因此使用 Python 自带 `unittest` 入口执行同一批 7 项测试，不安装依赖。

本地无模型 Run/SQLite 压力与容量回归另行重跑：`tests.test_p13_local_load` **2/2 PASS**，其中 c1/c4/c8 各 100 个 RULE_DEMO 本地 Run：均 0 errors、Run/message/event终态断言通过；c1 p50/p95=53.449/66.000 ms，c4=128.650/327.301 ms，c8=171.395/1174.103 ms。worker 容量为0时 API 返回429且 Run 保持 queued。此测试只度量本地状态账本/测试客户端路径，不调用 DeepSeek，不测 LLM mock 推理，不外推供应商性能。

## Gate 1–3 完成状态

| Gate | 结果 | 说明 |
|---|---|---|
| 0 小样本真实预检 | **部分通过 / 有审计缺口** | 10 个不同 case 有原生 parse 成功；19 次请求，8 次无法精确 usage 归档；真实价格级别已估算。|
| 1 原生工具选择 100 组 | **`REAL_100_BLOCKED`** | 本任务书要求 Owner 明确认可预算上限/100 次真实调用风险；当前没有数值美元上限。不得将10例或离线模拟扩为100例。|
| 2 连续真实模型→工具→复核链 | **未执行** | 至少5次连续真实模型决策会产生额外调用费用；没有将 S2.5 历史链路冒充为本轮证据。|
| 3 真实 c1/c2/c4 压测 | **未执行** | 不将小样本时延或本地 RULE_DEMO 并发外推成真实供应商压力结果。|
| 专业反例的真实模型错误率 | **未判定** | 反例已纳入合成集，但没有对全部反例完成 100 例原生盲评。E0–E3 来源质量和适用性不冒充人工认定。|

**下一步唯一阻塞输入：**Owner 给 Gate 1–3 剩余实验设置一个美元总上限（例如“剩余最多 $0.10”）；收到后再按既定速率及硬 Token 上限继续。没有此上限前，`REAL_100_BLOCKED` 保持。

## 可复现命令

在项目根目录运行：

```powershell
.\.venv-langgraph\Scripts\python.exe scripts/s26_prepare_dataset.py
.\.venv-langgraph\Scripts\python.exe scripts/s26_offline_audit.py
.\.venv-langgraph\Scripts\python.exe scripts/s26_live_preflight.py --cases 10
.\.venv-langgraph\Scripts\python.exe -m unittest tests.test_v2_s25_lease_fencing tests.test_v2_s25_sse_concurrency tests.test_v2_s25_tool_process -v
```

真实脚本只用于合成输入，每请求最多 700 output tokens、30 秒超时、串行间隔至少 1.1 秒、无自动重试；跨进程全局计数/Token硬预算状态见 `evals/s26/preflight_budget_state.json`，本次账户账本见 `evals/s26/preflight_accounting.json`。当剩余预算不足会在网络请求前停止。

## Owner 决策建议

- V2 默认关闭、原 R9 不变；本轮没有批准生产开关、部署或正式结论。
- 若批准剩余费用上限，先完善真实响应的逐请求持久化/usage 日志，再跑100例；连续工具链和并发压测分别单独记数，不可混入原生解析率。
- 当前状态：`REVIEW_BLOCKED`，Gate 1 的费用上限及 Gate 0 7 条丢失逐请求证据需要 Owner 确认接受后再续。
