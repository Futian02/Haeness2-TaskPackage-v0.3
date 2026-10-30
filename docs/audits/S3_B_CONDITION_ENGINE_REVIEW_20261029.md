# S3-B 三值适用性引擎复核（2026-10-29）

**结论：ENGINEERING_PASS / CANDIDATE_ANNOTATION_ONLY / PROFESSIONAL_RELEASE_BLOCKED。** 已实现版本化 Schema、纯 Python 三值判定、S3-A 候选只读适配器及 54 项合成单测。适用性规则尚无人审；不改 R9/default Graph、不接管教师候选、不输出风险级别或检验周期。不能据合成测试或自动候选宣称专业准确率。

## 范围与边界

开工依据：`AGENTS.md`、`docs/PROJECT_STATUS_CURRENT.md`、S3 全82条研究与工程规格、根因报告、`orchestration/agentic_v2.py`、老师三工具接口规范及技术指标验证方法。S3-B 只写：
- `knowledge/applicability/schema_v1.py`
- `knowledge/applicability/__init__.py`
- `orchestration/applicability_v1.py`
- `tests/test_s3_applicability_v1.py`
- 本报告

S3-A candidates 为只读输入。未修改 `backend/execution_ledger.py`、`orchestration/agentic_v2.py`、`backend/api.py`、teacher tools、正式 clauses/trajectories、enums、XLSX/PDF、教师签名或真实数据库。实现无网络/模型调用；不在默认图中注册。教师工具数量、参数及五键返回外壳没有变化。

终态 `git -C upstream status --short` 仍显示既有 RBI Excel modified、候选 XLSX 与 owner backup 未跟踪；本轮没有操作这些路径。开工时未单独记录 upstream 状态快照，因此只报告终态，不对这几项文件的历史归属作额外判断。只读计算 `clauses.jsonl` SHA-256=`a8151797ba15a6a7452dd83aaec9fab4c0a815724ca45062eb1e2bac7b4d49ef`，与S3-A manifest相同。

## 实现摘要

### Schema 与三值事实

Pydantic v2、`extra=forbid`、版本 `1.0`。类型包含 `Predicate`、`SourceRef`、`DeviceFact`、`PredicateGroup`、`ApplicabilityRule` 和 `ApplicabilityResult`。

属性对象分离：
- 材料/介质/设备类型分别使用明确 Subject 与 Property。
- `wall_temperature` 与 `process_temperature` 为不同 property，均要求明确 target object 和单位。
- `total_pressure` 与 `h2s_partial_pressure` 为不同 property，分开总压与 H2S 分压单位；不允许把 MPa 总压填作 MPa_partial。
- 气侧、烟气侧、湿H2S、水相/沉积等环境条件采用属性+精确作用对象+可选运行阶段，不用一个模糊 environment 字段混合。
- 子机理 predicate 必须声明 `specific_subtype` 与 submechanism_id；仅对相同子型判定，不能扩张为整条机理排除。
- UNKNOWN 必须为 `value=null`；零不是未知默认值。TRUE/FALSE 事实须来源于用户确认或测量；冲突事实归 UNKNOWN。

单位验证只接受相容单位；已覆盖 K↔℃、Pa/kPa↔MPa 和 H2S partial-pressure 对应单位。自定义数值属性不能吞并温度/压力单位，防止绕过对象/量纲类型。

### 判定器

Kleene 三值逻辑，AND/OR 分组：
- ALL（必要条件合取）有任一已核 FALSE 可为该条件组的 FALSE；UNKNOWN 不当 FALSE。
- ANY（必要条件备选）只有全部已核 FALSE 才为 FALSE；任一 TRUE 即 TRUE；否则 UNKNOWN。
- 缺失事实、未确认事实、目标对象/运行阶段不匹配、矛盾事实一律保留 UNKNOWN。
- 只有明确必要/排除谓词、精确对象和范围、确认/测量事实、可信源证据同时成立，才能硬排除；来源须为 `HUMAN_SOURCE_VERIFIED`、`OWNER_APPROVED`、`SUPPORTED`、人工PDF核验状态，并具 PDF/JSONL SHA、页和条号。自动提取或 S3-A candidate 无权硬排除。
- `protective`/保护材料只能成为解释性 annotation，Schema 禁止将防护描述声明为 necessary/excluding；susceptibility/resistance 角色未分辨时不能自动转成易感条件。
- 完整、已核必要条件全满足且不存在未知排除型分辨条件时，输出 `SUPPORTED_WITH_CONDITIONS`；其余保守输出 `POSSIBLE_NEEDS_EVIDENCE` 或 `NOT_ASSESSED`。
- 仅对相同子型产生 `EXCLUDED_WITH_CONFIRMED_CONTRADICTION`。
- 结果结构明确固定 `risk_level=null`、`inspection_interval_year=null`、`observed_damage=null`；适用条件不等于已发生损伤，也不等于 RBI 风险评级。

### Teacher / S3-A 适配

`annotate_teacher_candidates` 复制结果并**仅增加** `applicability_diagnostics`，不删除、不重排教师 `mechanisms`。S3-A JSONL 适配 `import_s3a_candidate_annotations` 仅导入字段语义已明的材料、介质、设备类型，且统一成为 CONTEXTUAL annotation；未解决的温压/环境/侧别/局部条件进入 quarantine，不猜对象、角色、单位或关系。

实读 S3-A 候选：
- summary 声明 134 条候选 predicate、15 条 pilot、82 条manifest；human_reviewed=0、reliable_approved_predicate=0、expert_gold_labels=0、全PDF逐页核验=false。
- 实际导入 110 条可识别字段为上下文 annotation，覆盖 15 个 clause_id；0 条 necessary，0 条 exclusion。
- 24 条因属性/对象语义仍未映射而隔离：`metal_surface_temperature`(1)、`organism_survival_temperature`(1)、`environment`(1)、`side`(1)、`wall_temperature`(1)、`dewpoint_reference`(1)、`condition`(1)、`temperature`(6)、`hydrogen_presence`(1)、`gas_partial_pressure_H2S`(2)、`temperature_c`(4)、`mass_fraction_NH4HS`(1)、`metal_temperature`(1)、`stress_state`(1)、`water_presence`(1)。
- 材料 44 条来源角色均含 susceptibility/resistance 未分辨信息，adapter 将其作为上下文文字，不能将耐蚀材料误当作“没有损伤易感性”的排除证据。
- 自动候选PDF页码不作为核实页号导入。原候选、反例与manifest未写回。

适配器通过 2 条临时 JSONL fixture 测试：确定字段仅成为非判定 annotation，未映射的壁温候选进入 quarantine。S3-A 所有候选仍是研究材料，不是经审核规则。

## 测试记录

### 专项

命令：

```powershell
.venv-langgraph\Scripts\python.exe -B -m unittest tests.test_s3_applicability_v1 -v
```

最终结果：**54 tests, OK**。覆盖 54 个确定性 fixture 场景，包括单位边界、混合对象/侧别/阶段、子型作用域、材料 protection、必要条件 ALL/ANY、来源门禁、提示注入字段拒绝、教师结果加法保留、S3-A适配与UNKNOWN排除分辨条件。

开发过程实际失败与修复：
1. 首轮专项 52 项：1 FAIL + 2 ERROR。泛型数值字段错误接纳温度单位；修复为温度/压力只能使用带对象类型的 property。两个 fixture 错将未确认水质写成带值的 UNKNOWN；按合同改为 `null + UNKNOWN`。
2. 增加 Subject/property 约束后，3 个阶段测试 fixture 缺少 `wet_service → corrosion_condition` 映射；修正测试 helper，不放宽生产 Schema。
3. S3-A 临时 JSONL fixture 首轮 53 项出现 1 FAIL；原因是测试写入了字面 `\\n` 而非换行符，修复 fixture 序列化。最终专项全过。
4. 追加“未知排除条件不能升级为 SUPPORTED”门禁后，最终 54 项全部通过。

### Aetheris 回归

完整 unittest discover 命令在 DevSpace MCP 请求窗口内无最终输出，返回 timeout；**不记为通过**。随后按无重叠模块组完整执行当前测试发现范围：

1. `.venv-langgraph/Scripts/python.exe -B -m unittest` + 第一组 13 个模块（deepseek adapter、engineering semantics、import guard、lexical、Owner routing、P11–P14）：**77 tests OK**。其中 P13 local load 1/4/8 并发各100 runs，错误0。
2. 同命令 + 第二组 12 个模块（P15/P16/evidence/API/claim/lease/parallel/merge）：**99 tests OK**。
3. 同命令 + 第三组前 7 个模块（API vertical slice、R10、R8B、R9、runtime/store）：**66 tests OK，3 optional skips**。
4. 同命令 + 第三组剩余 7 个模块（V2 router/graph/memory/S2/S2.4/S3）：**127 tests OK**。

总计 **369 discovered，366 PASS、3 optional SKIP、0 FAIL/ERROR**。分组覆盖为完整项目 unittest 模块列表；整仓 discovery 一次性runner超时另行保留。

老师原合同只读验证：
- `.venv-langgraph/Scripts/python.exe -B upstream/04_接口文档/validate.py --final`：554/554 clauses、200/200 trajectories、144 multi-step、三类特殊轨迹各15，PASS。
- `.venv-langgraph/Scripts/python.exe -B upstream/05_提交区/_selftest_tools.py`：17/17 PASS。
这两项证明冻结格式/工具回归，不证明适用性规则专业正确率。

## S3-A字段兼容冲突与待定项

1. S3-A `operator` 使用 `in/interval/requires/greater_than/equals/below/conditional_values/contains/conflicts_with/greater_than_or_equal`；S3-B 使用受控 `eq/in/ge/le/interval/present/absent`。不能机械同义映射，尤其 candidate-only polarity、对象不明确时。
2. S3-A `polarity` 为 `candidate_support_or_scope_only/candidate_only`；S3-B 为 `necessary/supporting/excluding/protective/contextual`。待S3-A/Owner给出明确语义映射前，adapter 仅落到 contextual。
3. S3-A `review_state` 为 `PROPOSED_NEEDS_PDF_CHECK/PROPOSED_SCOPE_UNRESOLVED`，S3-B source review enum 为审定状态；不存在任何候选可进入硬规则。
4. S3-A `target_object` 多为 “equipment/process context (candidate; exact component unresolved)”；不能与 `pipe_inner_wall`、`gas_side`、`process_stream` 等现场事实相比较。Adapter 设为隔离的 `candidate_context_unresolved`，从不匹配事实。
5. 24 条候选属性需 Owner/S3-A明确 target、stage、单位、对象、role、polarity；不自动填补。
6. S3-A 有 61 条 author-synthetic counterexamples，标记 expert_gold=false、human_reviewed=false。无法用于报告专家 Recall、False Exclusion、Precision、真实性未知校准或工业正确率。
7. 当前 Pydantic schema 尚未以任何人审S3-A样本验收。S3-A和S3-B后续应锁定版本化字段映射表，保留未知字段与拒绝原因。

## Gate与恢复建议

- **S3-B工程实现：PASS**（schema、引擎、合成测试、S3-A注释适配）。
- **知识专业审核：BLOCKED/PENDING**（无人审、无独立gold；S3-A页码尚非逐页核验）。
- **默认图接入：未进行/待Owner批准**（当前只提供本地Python shadow函数；保持R9/default Graph不变）。
- **发布与风险决策：NO-GO**（不输出risk_level、检验周期、已发生损伤）。

下一步：
1. S3-A/Owner签字确认候选字段与S3-B Property、对象、单位、scope、role、polarity映射；材料要区分 susceptible 与 protective。
2. 先独立人工核对若干源 PDF 页、源摘录和候选定位；未核区域维持 PROPOSED，不触发硬排除。
3. 独立专家建立 ≥50 holdout gold；未签前继续 `HUMAN_GOLD_PENDING`。用冻结查询比较 Critical Hazard Recall@K、False Exclusion、Unknown Calibration、Unsupported Assertion，并在固定本机硬件报告 p50/p95；本地 adapter 可算格式和计时，不可把 synthetic 当准确率。
4. Owner批准后，再另开受控任务做 shadow-only Graph 接线和回滚验证；本次没有动Graph。

## 学习点

这里把 Kleene 三值逻辑落实为两层：事实层 `confirmed/unconfirmed/unknown`，条件层 `ALL/ANY`。UNKNOWN 通过真值表传播，不参与 FALSE 分支；因此缺介质、未知烟气侧或缺H2S分压只能要求补测，而不能变成排除。材料字符串也先经过 role 语义门：易感性和防护是不同命题，只有经过审定的必要条件才可进入 exclusion 判定。
