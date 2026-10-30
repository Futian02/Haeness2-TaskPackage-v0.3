# Aetheris S3｜82条损伤机理适用性语义层与专业评测合同（Owner，2026-10-29）
**状态：OWNER_DESIGN_APPROVED_FOR_READ_ONLY_CANDIDATES / NO_OFFICIAL_DATA_WRITE / NO_PROFESSIONAL_RELEASE。**
范围为项目**自有知识派生层**；老师`upstream`下PDF、XLSX、JSONL、convert、enums、三个原版工具全部保持只读；当前正式库554=RBI472+DM82、200轨迹、17工具合同已验证，不代表设备专业适用性。Codex为本机任务，直接使用本地文件与终端，不要求任何远程连接器。

## 0. 动机与不可混淆的四层证据
同一损伤机理的召回、条款血缘、适用性、设备已发生四层不可混同：
1. **Retrieved**（E0）：词法/语义相关；`damage_mechanism_query`候选可能包含广义词面关联；
2. **Grounded**（E1/E2边界）：标准code/条号/页/短摘录定位且文本候选经过源核对；页图未人工审查不提升真人状态；
3. **Eligible**（E3候选）：机理**必要条件**与用户确认工况三值比对，分清部分支持、未知与硬反证；不使用没有来源的材料/工况；
4. **Observed damage**：独立检测证据证明已发生；若没有测厚、裂纹探伤/腐蚀形态等，不得声称已经损伤。
**安全优先**：危险候选可以保留在POSSIBLE层，不能将`unknown`视为排除；分类漏危险、错排除优先于减少显示候选数。自有层不是第四个老师工具，不更改teacher API。

## 1. 当前基线
`docs/data_quality/DM_APPLICABILITY_ROOT_CAUSE_AND_REFORM_20261029.md`为原始根因：
- 82条八段式非空全部82；`applicable_conditions.material`74/82、medium26/82（56空，可能属于非枚举真实工况）、equipment_type81/82、至少一个温度界23/82、压力界0/82、verified_by0/82；
- 由于标准介质超老师枚举，**不可为了填充率更改教师enums或把硫酸/烟气冷凝液伪映射成HCl**；
- 例如95℃HCl管道命中“烟气露点腐蚀”只说明词面关联，不能推定存在烟气侧；湿H2S换热器命中微生物、燃灰等并不自动表示成立；
- H2S分压与系统压力、壁温与介质温、耐蚀材料与易感材料、场景限定温区与整条机理全局阈值必须分离。

## 2. 派生数据规范
建议放自有`knowledge/applicability/`：
`schema_v1.py`/ `types.py`使用Pydantic；`source_manifest.jsonl`、`mechanism_conditions_candidate.jsonl`、`review_queue.jsonl`、`candidate_stats.json`。输入源对每条记录有`source_clause_id`、`source_jsonl_sha256`、PDF名称及SHA256（若真实文件存在）、条号、PDF物理索引、印刷页、来源行/列、候选摘录定位、提取器版本、updated_at。任一来源缺失填写null+reason，不造页码。
条件以**多个谓词**表达，而非压成temperature_min/max：
```json
{
  "predicate_id": "source-derived-stable-id",
  "mechanism_id": "exact clause_id",
  "subject": "process_environment | material | equipment | corrosion_condition",
  "property": "gas_side | wet_h2s | wall_temperature | total_pressure | h2s_partial_pressure | ...",
  "relation": "eq | in | >= | <= | interval | present | absent",
  "value": null,
  "unit": null,
  "target_object": "pipe_inner_wall | exchanger_gas_side | process_stream | ...",
  "polarity": "necessary | supporting | excluding | protective | contextual",
  "role": "trigger | susceptibility | protection | byproduct | example | disambiguator",
  "scope": "whole_mechanism | specific_subtype | operating_phase",
  "provenance": {"clause_id": "...", "page": null, "text_span_ref": null, "source_sha256": null},
  "origin": "RULE_EXTRACTED | LLM_CANDIDATE | OCR_CANDIDATE | OWNER_TECH_REVIEW | HUMAN_SOURCE_VERIFIED",
  "review_state": "PROPOSED | NEEDS_PDF_CHECK | CHECKED_SOURCE | OWNER_APPROVED",
  "confidence_note": "nonnumeric optional",
  "source_support": "SUPPORTED | WEAK | NOT_VERIFIED"
}
```
上面为字段语义样例、**不是可直接用于正式条款的真实谓词记录**。候选自动输出默认`PROPOSED/NEEDS_PDF_CHECK`，不能以模型重写覆盖官方条文、人审或PDF证明。

## 3. 三值判定原则（Kleene，基于必要条件）
对每个明确的必要谓词，根据**用户确认/测量**工况映射`TRUE/FALSE/UNKNOWN`。弱相关词、模型摘要、检索说明不能自动成为事实。
- 某必要条件确证FALSE，且适用范围与子型一致，才可从该**具体子型**标记`EXCLUDED_WITH_CONFIRMED_CONTRADICTION`；不能把子型不成立扩大为整个大机理不可能。
- 全部必要条件满足且有对应源、无强反证→`SUPPORTED_WITH_CONDITIONS`，只表示**适用条件支持**，不表示已发生；若必要条件集不全/原文未核，最高只能`POSSIBLE_NEEDS_EVIDENCE`。
- 有未知条件/未核候选→`POSSIBLE_NEEDS_EVIDENCE`或`NOT_ASSESSED`；不能把未知写成FALSE。材料耐蚀等保护性描述不是“无腐蚀”硬排除条件。
- 凡条件或来源存在争议，`NO_VERIFIED_HARD_EXCLUSION`：允许公开说明疑点，但禁止给设备确定性风险等级/检验周期。
- 工况适用性与工程Risk等级两级门禁互相独立；PoF、CoF、完整参数缺失时risk_level=null。

## 4. 试点目标与来源
优先从正式82条按**真实标题/Clause ID动态选择**10–15条；典型类别：HCl、H2SO4、NH4Cl、NH4HS、湿H2S、燃灰、烟气露点、CUI、微生物、酸性水、环烷酸及临界高温机制。不能从记忆猜条号；对不在82正式库的类别标UNAVAILABLE而不造记录。
每条**至少**记录源句、1条支持条件、1条假设会混淆的反例、1个UNKNOWN缺证，以及任何`role=protective`的容易误读场景。
源分级：正式`clauses.jsonl`是程序口径；源PDF逐字及适用性仍待独立人工核对；自动提取/视觉/模型生成只能形成审阅候选。`source_pdf_sha`真实校验才能给源绑定。

## 5. 评价数据集与基线
分离三套集，不共享用于调参的同一条作为盲测：
- `gold_dev`: 30–50构造/来源核查案例，包括支持、必要条件矛盾、UNKNOWN、材料耐蚀角色错判、壁温/介质温、H2S分压/总压、负例以及提示注入。
- `gold_holdout`: 人工独立盲标≥50例，至少2名独立复核者（未签之前`HUMAN_GOLD_PENDING`而不是可信gold）。
- `shadow_cases`: 未上线离线回放的复杂用户问题，不污染正式数据与会话事实。
比较**同输入旧工具** vs 新自有候选适用层：Critical Hazard Recall@K、False Exclusion Rate（重点）、Precision@K、Unknown Calibration、Unsupported Assertion Rate、evidence coverage、p50/p95时延。分别计已标/未知/冲突分母与置信区间，不以增加 UNKNOWN 数量或删除候选冒充精准。
Gate：冻结测试中任何有明确支持的关键危险机理被错误硬排除→NO_GO；任何缺PoF/CoF硬给L1–L4→NO_GO；任何伪条款/页码或伪真人签字→NO_GO。其他指标由Owner和领域审核联合设阈值，不编造全场景“100%安全”。

## 6. 交付流水线
P0 只读全82审计：按枚举缺口、role冲突、条件作用域/单位不足、原PDF证据状态分组；source sha manifest；保留待审原因。
P1 10–15机理试点：提候选谓词和反例证据卡，不直接修改原表；精确标记原文/推断区别。
P2 三值适用引擎：自有`orchestration/applicability_v1.py`，可注入条件库和已确认fact，仅判断候选层，不调用第四teacher工具。
P3 单元和双集比较：先合成红线/负例，再独立人工盲标；若人工不可用报告GOLD_BLOCKED，不把模型互审当作人工。
P4 只有Owner+领域人审批准后，才讨论与LangGraph V2联动并受feature flag保护；最初采用shadow diagnostics，不能偷偷改变默认R9结果。
P5 全82覆盖：前15通过后批量扩展，记录每条的source/审批和无法表达字段，不以覆盖数量等于高质量。

## 7. 任务分工与文件所有权
Codex A（数据与来源）负责`knowledge/applicability/candidates/**`、`scripts/s3_*.py`、`docs/data_quality/S3_*.md`；只读upstream，别动AgentGraph。
Codex B（三值引擎）负责`knowledge/applicability/schema_v1.py`、`orchestration/applicability_v1.py`、`tests/test_s3_*.py`；不改原三工具、API、A候选。
Codex C（对照评测）负责`evals/s3/**`、`docs/audits/S3_*.md`；不修改老师/P16 Gold签名、不让测试同源泄露；开始前先等A/B合约稳定。
同一时段若S2.5可靠性修复仍在写`backend/**`和`orchestration/agentic_v2.py`，S3窗口**禁止编辑这些共享路径**；按单所有者合并。
