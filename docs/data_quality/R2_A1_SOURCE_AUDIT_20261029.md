# R2-A1 原始知识来源与字段审计（2026-10-29）

**状态：`CANDIDATE_ONLY / HUMAN_PDF_REVIEW_PENDING`。** 本审计以只读方式检查正式 `clauses.jsonl`、现有 82 条 `source_manifest` 和机器字段审计。没有编辑上游 PDF/Excel/JSONL，也没有签署或升级任何记录。它证明的是文件存在、记录/字段和机器定位状态，不证明条文转述正确、页码准确或某机制适用于特定设备。

## 1. 输入、哈希与完整性

| 输入 | SHA-256 | 观测 |
|---|---|---|
| `upstream/05_提交区/clauses.jsonl` | `a8151797ba15a6a7452dd83aaec9fab4c0a815724ca45062eb1e2bac7b4d49ef` | 554行、554唯一 clause_id；472 RBI + 82 damage_mechanism |
| `knowledge/applicability/candidates/source_manifest.jsonl` | `bfc8fc9c4de9a0047e9d65f55c2569610b770be5ce4be98feba519286818db87` | 82条 30579 来源定位候选，全部 NEEDS_PDF_CHECK |
| `knowledge/applicability/candidates/dm82_field_audit.jsonl` | `8e8d4627a4bb71720417aca47b7ecaea6bb6341fcb0e1405b219eb6c9c18b2fb` | 82条机器字段盘点，334个问题标签，不等于334个已确认事实错误 |

所映射的6份PDF文件均存在，并逐文件SHA-256写入 `knowledge/applicability/candidates/a1_source_audit/audit_summary.json`。RBI 472行目前只有正式JSONL的 `page` 候选字段和标准→PDF映射，未建立逐记录PDF物理页映射；不能把该页字段写成已核印刷页。30579的82行均记录印刷页与PDF物理页**候选**，但沿用 `AUTO_OFFSET_PLUS_5` 估算映射，仅有样页交叉核对，manifest明确全部 `NEEDS_PDF_CHECK`。本轮尝试用MiKTeX `pdftotext -layout`读取30579页索引候选14/37/56（命令页15/38/57），抽样内容呈明显CMap乱码，无法作为逐字原文证据；项目venv未安装`fitz`，视觉渲染路径未执行。故精确页核验数为0。

## 2. 554行机器盘点

按标准计数：GB/T 26610.2-2022 134；GB/T 26610.3-2014 141；GB/T 26610.4-2022 139；GB/T 26610.5-2022 26；GB/T 30579-2022 82；TSG 21-2016 32。`verified_by` 554/554为空，人工验证和独立Gold均为0。所有记录只能标为 E0/机器盘点，不允许用于确认实际适用性、设备处置或风险定级。

JSONL条件对象的字段**有键**数：equipment_type 113、material 74、medium 26、other 554、temperature_c 554、pressure_mpa 554。进一步排除全空/全null后，temperature_c 仅23行有任一非null数值，pressure_mpa 为0行有数值；这说明“字段存在”并不等于获得了数据。82条DM的八段叙述字段在机器结构中均非空，但不证明叙述来自正确原文，也不代表所有材料/介质/温压前提齐全。DM机器审计标记334项：NOT_STATED_IN_STRUCTURED_RANGE 141、NO_FORMAL_VERIFIER_VALUE 82、NOT_MENTIONED_OR_EMPTY 65、ROLE_OR_POLARITY_MIX 17、OBJECT_SCOPE_AMBIGUITY 9、PRESSURE_BASIS_DISTINCTION 8、SUBMECHANISM_OR_SIDE_SCOPE 7、LOCAL_SUBMECHANISM_CONDITION 5。它们是需复核的问题类别计数，不可直接当错误真值。

## 3. 高风险条件作用域审查（正式记录字段读取；PDF原文尚未逐页核实）

| 条款 | 文件中的机器定位候选 | 源记录所示条件 | 适用性结论 |
|---|---|---|---|
| GB/T 30579-2022 5.23 | 印刷页候选32；PDF页索引候选37；`NEEDS_PDF_CHECK`；源PDF SHA `b941a846…ec200` | structured `temperature_c=[49,66]`；`other`将49–66℃联系到NH4HS气相析出。记录同时描述酸性水/NH4HS腐蚀机理、浓度/流态等因素 | 49–66℃是与局部析出相关的条件候选，不得投影成全机理必要温区。60℃命中数值区间只表示语义相关候选；是否存在局部气相析出及其它前提仍未知。80℃在区间外只能说明不满足该局部区间，不能排除整个酸性水腐蚀机理。两者均 `applicability=UNKNOWN`，需核原文并由专家审查。 |
| GB/T 30579-2022 5.6 | 印刷页候选9；PDF页索引候选14；`NEEDS_PDF_CHECK` | structured 177–242℃位于 `applicable_conditions.temperature_c`；218–400℃出现在轻相介质的影响因素描述 | 不得把影响因素范围和结构化损伤范围合并或互相覆盖；字段角色、相态、温度对象待原文核验。 |
| GB/T 30579-2022 6.7 | 印刷页候选51；PDF页索引候选56；`NEEDS_PDF_CHECK` | 结构化 `pressure_mpa=[null,null]`；自由文本涉及湿H2S气相分压阈值；温度/硬度条目含不同子机理边界 | 总系统压力不能替代H2S分压；氢鼓泡/HIC/SOHIC/SCC应按各自条件作用域管理，不可把聚合范围用于所有子型。原文、单位和页码需人工核实。 |

本表中的条款号、字段值来自冻结JSONL机器读取，并不构成已核标准条文引用。没有复制长段标准文本。

## 4. 记录级交付与复现

- `knowledge/applicability/candidates/a1_source_audit/record_source_audit.jsonl`：554行来源台账，含record SHA、标准/版本、JSONL页字段、印刷页候选、PDF物理页候选、PDF SHA、映射状态、字段键、审阅状态。
- `knowledge/applicability/candidates/a1_source_audit/critical_mechanism_scope_review.json`：5.23/5.6/6.7温度、压力及子机制边界摘要，区分来源存在、语义相关、适用性未知。
- `knowledge/applicability/candidates/a1_source_audit/audit_summary.json`：计数、来源SHA、PDF SHA及字段覆盖统计。
- `knowledge/applicability/candidates/a1_source_audit/generate_a1_audit.py`：只读源文件、只写自身目录的确定性重建脚本。

复现命令（PowerShell，项目根目录）：

```powershell
.\.venv-langgraph\Scripts\python.exe -B knowledge/applicability/candidates/a1_source_audit/generate_a1_audit.py
```

脚本校验冻结JSONL SHA、554唯一ID、输出行数，并在执行后再次验证源哈希未变。

## 5. 失败项与下一步人工队列

- **未完成**：554条每条记录到原PDF印刷页/物理页的视觉证据映射；数值表逐格复核；82条DM逐段原文核验；材料、介质、压力基准、温度对象/相态和保护条件的专家适用性签核。当前精确逐页人工核验0/554，未给precision/recall或“来源准确率”。
- **不能通过机器自动补齐**：空的正式 `verified_by` 不补签；structured null不从上下文推测；从八段摘要中自动识别出的温度/材料/介质只做待审候选。
- 建议G/Owner队列先复核5.23 p32、5.6 p9、6.7 p51的PDF页图/上下文，再复核风险最高的所有带数字与分压/局部凝析/露点条目。核验记录需双人/专家完成后另行形成批准版本，不回写本A1机器台账。

**机器运行结果：** 554/554行完整、554个唯一ID、源SHA匹配冻结值、六份标准PDF文件存在；`verified_by` 空554；精确PDF页人工核验0；结论仍为 `CANDIDATE_ONLY`，不是发布数据。

