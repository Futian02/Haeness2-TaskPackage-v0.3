# 82条损伤机理结构化适用性缺口：来源、根因及改革方向（Owner调查，2026-10-29）

**状态：ROOT_CAUSE_CONFIRMED_AT_DATA_AND_CODE_LEVEL / NO_DATA_REWRITE / SEMANTIC_REVIEW_BLOCKED。**
依据：`scripts/owner_dm_condition_inventory_readonly.py`直接扫描**正式**`upstream/05_提交区/clauses.jsonl`，并读取`upstream/05_提交区/tools.py`和老师`convert.py` / `enums.json`，以及P15/P16 B的字段审计。数字是“字段非空计数”，绝非抽取/专业正确率。

## 1. 独立复算的真实状态
正式82条`damage_mechanism`记录的**8个机理内容字段**均为82/82**非空**：description、morphology、affected_materials、influencing_factors、susceptible_locations、prevention、detection_methods、related_damages。
`applicable_conditions`结构字段为：
- material 74/82；
- medium **26/82**，**56/82未登记**；
- equipment_type 81/82；
- temperature_c有至少一个非null上下界 **23/82**；
- pressure_mpa非null界 **0/82**；
- other 82/82；
- `verified_by`非空 **0/82**。

**不可混淆**：八段式填写不等于适用性准确；介质26/82并不代表只有26条在原标准中有介质说明。56个medium空项中全部具有 `influencing_factors` 文本，许多在 `other` 明确说明“介质不在enums.json medium枚举中”，因此直接补写受控枚举可能违反老师接口。

## 2. 具体成因（按证据区分）
**原因 A：官方枚举集合 vs 标准真实环境范围不一致。** 老师`convert.py`会拒绝`applicable_conditions.medium`不在`enums.json`的值；但标准还涉及硫酸、氢氟酸、苯酚、微生物、烟气冷凝、土壤、大气、甲铵等。正式行举例：
- `GBT30579-2022-5.2`（硫酸腐蚀）：other写“介质硫酸不在enums.json medium枚举中”；
- `...-5.3`（氢氟酸腐蚀）：other记“介质氢氟酸不在enum”；
- `...-5.18`（烟气露点腐蚀）：other记“介质为烟气酸性冷凝液，不在enum”。
这些是**合同表示能力**的限制，不应擅改老师枚举或把错误介质填作替代。

**原因 B：原标准的条件不是简单 `temperature_min/max`。** 可能是“某温区易发/速率增加”、局部NH4HS析出条件、H2S气相分压、浓度/流速/壁温、分支子机理的局部阈值，不能统一压成整条机理的两个硬区间。P15/B对30579 §5.6（177–427℃与轻/烃相子条件）、§5.23（49–66℃局部析出）、§6.7（H2S分压0.0003MPa非设备总压、子型温区）已有候选证据，仍需真人裁决。

**原因 C：字段职责混淆。** `mechanism_detail.affected_materials`有时同时按耐蚀性弱→强排列，不是“所有材料都同样易感”；`other`混合材料说明、位置、子条件、单位、枚举超范围备注和场景。机械/化工事实在自由文本中，机器看见词不等于知道其在条件中的角色。

**原因 D：检索算法用弱相关文字匹配替代适用性证明。** `upstream/05_提交区/tools.py`的`_medium_signal`把枚举中的明确命中记强命中；没有枚举时只要本机理title、description、形态/主要影响因素/易发位置、other中的任一别名出现就记弱命中。弱匹配的文本并未标注“机理发生环境vs举例/污染物/副产物/影响因素”的关系。条件空且未弱匹配则排除；接着加分并最多列出前6。它可以召回相邻知识，但**无法证明E3工况适用性**。
- 原版17项教师工具自测中，输入碳钢+氯化氢+95℃管道，返回“盐酸腐蚀”和“烟气露点腐蚀”。后者的描述含HCl类污染物/露点语境，不代表给定的95℃HCl管道具有燃烧烟气侧工况。这个候选应为**需要烟气条件才能判的未证实项**，不能直接判专业错误而从标准工具代码硬删。
- 输入碳钢+湿硫化氢+110℃换热器，候选还有微生物腐蚀、硫酸腐蚀、燃灰腐蚀等；未给出证据证明是同一工况下成立。正式工具的自测只验证协议与部分预期结果，不能代替专家负例评估。

**原因 E：业务金标准与审核缺失。** 当前`verified_by` 0/82、P16-B 1312字段槽未完成原图逐格真人签；缺少按工况验证机理“必须出现/可以出现/必须排除”的独立专家gold。因此无法报告可比较的专业precision/recall/false-positive或部署安全性。

## 3. 改革目标：不动老师 25列 Excel/convert/enums/3工具
保持官方的八段式25列及JSONL 554条作为**原始事实与冻结契约**。引入自有、版本化的**派生适用性知识层**，而非将抽取猜测写回老师Excel：
- 每个机理关联`source_clause_id`、`source_pdf_sha`、印刷页、物理页、来源子条号、短摘录和`verification_status`。
- `mechanism_environment`：canonical_medium（仅来自老师允许的枚举），另保存`source_term`（例：硫酸/烟气冷凝液）和`scope=outside_teacher_enum`，不假装canonical合法。
- **条件谓词集合而非单一上下限**：predicate kind(material/medium/environment/temperature/pressure_partial/pressure_total/concentration/flow/wall_temperature/equipment/process_unit)，operator / interval / unit / target object / stage / polarity(positive/supporting, negative/excluding) / applicability scope(global vs local submechanism)/source_ref / evidence_state。
- 区分“易发机理”与“耐蚀/防护材料”和“关联损伤”；每条信息标`role=trigger/susceptibility/protective/context/byproduct/example`，避免看到关键词就强行判断。
- 设备事实`observed_true / observed_false / unknown`，条件三值逻辑；未给浓度/工艺流程/烟气环境→**UNKNOWN，不是FALSE**。
- 每个候选输出判定级别`SUPPORTED / POSSIBLE_PENDING_EVIDENCE / EXCLUDED_BY_CONFIRMED_CONTRADICTION / OUT_OF_CONTRACT`，附支持、反证、缺失条件；未完成E2/E3不输出确诊或可计算风险数值。
- 增加溯源阶段`MACHINE_EXTRACTED / AI_VISUAL_CANDIDATE / HUMAN_REVIEWED / OWNER_APPROVED`，默认机器仅为待审，只有签审和PDF哈希合格才进启用索引。
- 自有层可以支持原文词汇召回，但派生规则过滤必须解释：为何拒绝“烟气露点腐蚀”作为非烟气设备的确定结果。

## 4. 数据重构的推荐顺序（先讨论，再受控执行）
**Phase 0：冻结测量。** 导出82条的字段覆盖与空缺缘由表；将26枚举介质条、56非枚举条按照“确实缺信息 / 非枚举 / 多角色 / 子型条件”归类。所有字段保留原始值，不回填。
**Phase 1：10–15个高风险机制试点。** 优先烟气露点、微生物、燃灰、盐酸、氯化铵、硫酸、5.6环烷酸、5.23酸性水、6.7湿硫化氢、CUI等；每个机理用原图和老师表行级溯源，建三值谓词与明确negative case。
**Phase 2：专家反例与执行器。** 先标30–50案例独立gold：正例、易混错例、缺现场信息、原文没有适用阈值、压力对象错误、设备环境冲突。比较**旧工具输出→自有后过滤器输出**在相同标准和gold上的precision@k、recall@k、false exclusion、unsupported assertion、判定延迟和拒答质量；必须避免以“更少候选”冒充更准确。
**Phase 3：规模扩展。** 试点的正确性和漏召回通过后再覆盖82条，建立工作清单和持续hash检测；论文/教师达标指标与自有产品质量指标分开。
**Phase 4：发布。** 原生正式库和派生语义索引的版本绑定，并通过Owner及领域双重人工审核后启用。无审批保留PREVIEW_ONLY。

## 5. 开发/维护边界
- 未来在自有`knowledge/`增加`applicability/`派生索引与schema，在`orchestration/`添加轻量 eligibility checker，并在`evals/`加专家gold；当前**仅设计，不创建运行逻辑，不触碰upstream**。
- 不能因为26/82较低而绕过教师白名单修改`enums.json`；不应为提高非空率在excel写一个没有限定对象的硬阈值。对所有修复计算源PDF与生成版本哈希。
- 验收前，正式工具返回只是“值得审核的候选”，不等于工业现场已判定的损伤机理。
