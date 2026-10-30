# P3-B 独立证据核查实施记录

状态：`READY_FOR_OWNER_REVIEW`（2026-10-28）  
实现模式：`RULE_DEMO`；这是确定性规则节点，不是多模型交叉审查，也没有模型的私有推理过程。

## 边界与冻结接口

- 本轮仅在 `orchestration/`、`backend/`、`tests/test_p3b_*.py`、`evals/p3b_*.jsonl`、本审计文档内改动；未改前端、教师源/数据、原始 XLSX/PDF、README、共享项目状态。
- 注册表实际核对仍为三工具：`damage_mechanism_query`、`rbi_lookup`、`standard_clause_search`。参数表仍分别是官方原定义；未增删工具。
- 教师工具五键返回保持 `status, in_domain, result, source, message`。教师官方终验仍通过。
- 对有足够温度、压力、运行年限和候选机理的旧调用场景保留 `rbi_lookup` 调用；如果缺少这些关键输入，RBI specialist 记录信息缺口并跳过调用。即便旧场景真实调用了工具，风险字段也仅保留在内部工具证据里，不生成风险 Claim、不出现在回答或 SSE `tool_result` 中；需独立 likelihood + consequence 证据和适用性复核才可进入后续人工工作流。本轮并未实现该人工签署过程。

工具注册表现场检查（隔离环境）：

```text
tools= ['damage_mechanism_query', 'rbi_lookup', 'standard_clause_search']
damage_mechanism_query ['material', 'medium', 'temperature_c', 'equipment_type', 'evidence']
rbi_lookup ['equipment_type', 'material', 'mechanism', 'medium', 'temperature_c', 'pressure_mpa', 'service_years']
standard_clause_search ['keyword', 'knowledge_type', 'top_k']
```

## 实现与证据流

1. `orchestration/semantics.py` 新增严格 `Claim` schema：来源条款、观测 ID、假设、判定、E0–E3、review status、结构化检查及独立校验信息；额外字段拒绝，避免未知字段悄悄流过。
2. `orchestration/evidence_audit.py` 逐条核对正式库成员、本轮工具 source、标准号/条款号/页码及可明确检查的材质/介质/设备/温压边界。来源 ID/页码核实只允许 E1；规则节点不声称 E2 语义蕴含或 E3 设备适用性。条件冲突被记为 `checks[].status=mismatch`，仍将新 Claim 保持 `unresolved/requires_human_review`，不由机器伪造最终反证结论。
3. `SkepticAgent` 读取原始观测和本轮工具返回的原始条款记录（包括可用的 `content_raw`），形成对 Claim 的独立证据缺口记录；它不把 Diagnosis 文本当证据。没有 `content_raw` 时明确记为不可核查，缺测厚、温压/年限等信息保持 unknown，而非“没有损伤”。
4. StateGraph 仍顺序执行，不启用并行 fan-out；审查事件包含 `claim_added`、`claim_checked`、`requires_human_review`，审查结构同时落到 SQLite claims/disagreements 表。旧 SSE 事件字段保持，事件 sequence 单调且可回放；新增 claims/disagreements API 为加法接口。
5. SQLite 事件 payload 增加截断和常见 secret 字段去敏；RBI 的 `likelihood`、`consequence`、`risk_level`、统一等级、周期字段在 SSE 公共副本上递归移除，原始工具结果仅留内部运行态证据，不修改教师结果对象。

## Claim 样例（真实 RULE_DEMO 执行）

输入：`塔顶水样pH 5.8，铁离子 4.1 mg/L，尚未测厚，可能的损伤机理？`；上下文为碳钢、氯化氢、换热器，无温压及运行年限。

Diagnosis 新建事件（摘要）：

```json
{"claim_id":"evidence-sample-mechanism-1","kind":"mechanism_candidate","text":"工具候选机理：盐酸腐蚀（待独立核证，不代表设备已发生该损伤）","source_clause_ids":["GBT30579-2022-5.1"],"observation_ids":["obs-ph","obs-iron_ion","obs-wall_thinning"],"verdict":"unresolved","grade":"E0","review_status":"draft_needs_review"}
```

Auditor/Skeptic 核验后（摘要）：

```json
{"claim_id":"evidence-sample-mechanism-1","verdict":"unresolved","grade":"E1","review_status":"requires_human_review","checks":[{"check":"official_membership","status":"matched"},{"check":"current_run_source","status":"matched"},{"check":"condition:material","status":"matched"},{"check":"condition:medium","status":"matched"},{"check":"condition:temperature","status":"not_specified"},{"check":"condition:pressure","status":"not_specified"}],"independent_validation":{"mode":"RULE_DEMO","reviewer_role":"skeptic","result":"unresolved"}}
```

完整实际回答中的关键行：

```text
执行模式：RULE_DEMO（确定性节点，不是多LLM结果）。
待补现场信息：暂不请求 RBI 判级；需补充：temperature、pressure、service_years
可审查声明：...=unresolved/E1/requires_human_review
证据级别：E1=官方条款ID存在且来自本轮工具返回；E2原文蕴含、E3工况适用性尚未人工复核。
```

该运行没有 `rbi_lookup` 调用（关键现场因子不足），生成 2 个候选声明、2 条独立审查记录，0 条风险等级 Claim。另有专门回归测试覆盖旧工具调用场景：其输入提供温压/年限以维持冻结调用路径，但不给独立 likelihood/consequence；该测试证明工具调用仍发生、内部原始响应未被改写、SSE/回答没有任何风险等级内容或 risk Claim。

## 测试及官方验证日志

所有下述运行使用项目隔离环境 `.venv-langgraph`：

```powershell
.venv-langgraph\Scripts\python.exe -B -m unittest tests.test_p3b_evidence_audit -v
```

结果：9 项 P3B 专项测试 `OK`，覆盖 E0/E1 门槛、同轮来源、适用条件 mismatch、unknown 不作负证据、RBI 公共事件去风险等级、SQLite 重启后 claims/disagreements/事件回放、secret 去敏、新增 API 和兼容事件协议。

```text
.venv-langgraph\Scripts\python.exe -B -m unittest discover -s tests -q
Ran 54 tests in 4.545s
OK
```

```powershell
.venv-langgraph\Scripts\python.exe -B upstream\04_接口文档\validate.py --final
```

真实官方输出：554 条条款有效（82 条 damage_mechanism、472 条 RBI），200 条轨迹有效（144 条 multi_step；exclusion / insufficient_info / out_of_domain 各 15 条）；两 JSONL 文件分别 `554/554`、`200/200` 通过，`[终验模式] 结论：通过`。

```powershell
.venv-langgraph\Scripts\python.exe -B -m scripts.check_sources
```

结果：`present=19, missing=0, required=19`。

命令形态失败及纠正：直接执行 `.venv-langgraph\Scripts\python.exe -B scripts\check_sources.py` 时 Python 将 `scripts/` 置为导入根，报 `ModuleNotFoundError: No module named 'app'`。脚本未修改；以模块方式执行 `-m scripts.check_sources` 后通过。此为入口路径问题，不是源文件缺失。

## 性能与场景集

用临时目录 SQLite checkpoint 对真实 AgentGraph 做 25 次串行 RULE_DEMO 运行，计时 `perf_counter`；每次输入同一确定性工况，未启用网络模型。命令使用 `.venv-langgraph\Scripts\python.exe -B -` 的 inline harness，结果：

```text
runs=25 p50_ms=63.91 p95_ms=74.52 tool_calls_avg=2.00 tool_calls_range=(2, 2) unsupported_risk_claims=0
eval_rows= 20 all_unreviewed= True expert_labels= 0
```

`evals/p3b_unreviewed_scenarios.jsonl` 有 20 条合成测试场景草稿，全部 `unreviewed` 且 `expert_label=null`，覆盖材料/介质矛盾、缺测厚、负结果、多温压、多机理、RBI 输入缺失、来源不存在、错页/版本、适用性 mismatch、H2S unknown、注入型不可信来源文本及无证据 L1 等。它们不是“真实工况金标”，仍需 Owner/领域专家提供或审阅真实工况后再作为金标使用。

## 变更清单 / 审查 Diff 指引

- `orchestration/semantics.py`：Claim 结构化 schema。
- `orchestration/evidence_audit.py`：E0/E1 来源门禁、条件核验、独立 Skeptic 原始来源检查。
- `orchestration/graph.py`：Diagnosis candidate Claim、RBI 门控/兼容调用、Evidence Auditor、Skeptic、Reporter、事件及 SSE 风险字段过滤、路由注册一致性。
- `backend/store.py`：SQLite claims/disagreements、事件去敏/限长和可回放持久化。
- `backend/api.py`：只读 claims/disagreements 查询接口。
- `tests/test_p3b_evidence_audit.py`：9 项 P3B 回归测试。
- `evals/p3b_unreviewed_scenarios.jsonl`：20 条明确标为 synthetic/unreviewed 的场景模板。
- `docs/audits/P3B_EVIDENCE_AUDIT.md`：本文证据记录。

没有 Git 写操作。Owner 审查时请重点看：`Claim` 是否应进一步拆分候选机理与设备事实；来源原文不存在于教师工具返回时，当前 Skeptic 只能记录 source 不可核查而不能做文本蕴含；RBI 结果的产品展示仍被禁用，需独立 likelihood/consequence 证据、适用性规则及人工审批身份契约后另行设计；20 条评测当前只是合成草稿。

## 开放事项

- RULE_DEMO 没有语义蕴含模型；E2/E3 不能自动达成。所有新 Claim 都是 `unresolved/requires_human_review`。
- `contradiction_found` 事件协议已支持，但自动规则不擅自断言最终语义矛盾；只有后续经人工审查的明确记录才应写成定论。
- 需要真实、可追溯、经过领域专家复核的工况和标注；不能用上述合成模板冒充真实金标。
- 本轮无失败测试；唯一失败是直接执行 `check_sources.py` 的导入入口形式，模块入口已经通过。

**交付状态：READY_FOR_OWNER_REVIEW。**
