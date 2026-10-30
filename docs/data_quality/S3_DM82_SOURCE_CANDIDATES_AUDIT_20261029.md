# S3-A｜DM82 来源扫描与候选谓词审计

**状态：`READY_FOR_OWNER_REVIEW`（仅候选研究包，不等于标准适用性判定或工程验收）**  
日期：2026-10-29。所有修改仅在 S3-A 专属目录；教师源表、PDF、正式 JSONL、schema/引擎、API、数据库和状态文件均未修改。

## 范围与复现

- 依照 `docs/CODEX_S3_A_DM82_SOURCE_CANDIDATES_20261029.md` 只读加载正式 `upstream/05_提交区/clauses.jsonl` 中 `knowledge_type=damage_mechanism` 的记录，逐条生成审计行；82/82 条、clause_no 唯一性 82/82。
- 运行：`python scripts/s3_dm82_inventory_readonly.py --self-test --write`
- 验证输出：`PASS repeat-determinism outputs=5 source_rows=82 pilot=15 predicates=134 authored_cases=61 human_gold=0`。
- 该脚本没有外部依赖；`--check` 做只读重建校验，`--self-test` 重复生成并比较确定性，`--write` 仅写候选目录。
- `python scripts/s3_dm82_inventory_readonly.py --check` 是仅检查、不写文件的复跑命令。

## 数据来源与 SHA-256

| 工件 | 路径 | SHA-256 | 定位/说明 |
|---|---|---|---|
| 正式条款 JSONL | `upstream/05_提交区/clauses.jsonl` | `a8151797ba15a6a7452dd83aaec9fab4c0a815724ca45062eb1e2bac7b4d49ef` | 554 行正式条款记录；目标子集 82 条损伤机理。逐记录 SHA 见清单。 |
| 主标准 PDF | `upstream/02_损伤机理参考/GBT30579-2022_承压设备损伤模式识别.pdf` | `b941a8469f53331be2b6461484670dc83f09a2e36a039fb8c4ec9546a10ec200` | 163 PDF 物理页。JSONL 的 page 作为印刷页；物理索引 `page+5` 仅为抽样交叉验证后的索引候选，不是逐页校验结果。 |
| 损伤机理摘录工作簿 | `upstream/02_损伤机理参考/条款摘录表_损伤机理.xlsx` | `8bb05d1d0dacbe542a1713a317a769f064a9c6c7ad34053417f0dbba01a0d62e` | 仅计算哈希，未写入。 |
| 枚举定义 | `upstream/04_接口文档/enums.json` | `852554834f9e8b2b5c68115111e8d37803ef1b65e271b5ae624e9830ff445212` | 仅用于检查结构化值；没有新增枚举。 |

JSONL 记录提供 clause_id、标题、印刷页与原始内容。页图定位与印刷页到 PDF 物理索引的映射仍为 `NEEDS_PDF_CHECK`；渲染图抽样查看了 5.6、5.17/5.18、5.23 和 6.7 等页，PDF 文本层存在字体映射/OCR风险。不能将抽样目视核对外推为 82 条逐条 PDF 核验、也不能将候选偏移伪装成已核验页码。来源清单逐条保留印刷页、物理页索引候选、源/记录 SHA 和待核验状态。

## 82 条字段盘点

“有值”按正式 JSONL 原样统计；对温压区间，`[null,null]` 计为未给出数值区间。八段式来自 `mechanism_detail`：

| 字段 | 有值条数 / 82 | 空/未记录条数 |
|---|---:|---:|
| material | 74 | 8 |
| medium | 26 | 56 |
| equipment_type | 81 | 1 |
| temperature_c 数值边界 | 23 | 59 |
| pressure_mpa 数值边界 | 0 | 82 |
| other | 82 | 0 |
| description / morphology / affected_materials / influencing_factors / susceptible_locations / prevention / detection_methods / related_damages | 每字段 82 | 每字段 0 |
| verified_by 非空 | 0 | 82 |

结构化字段无值并不代表原文绝对未提及：当前扫描将空字段列为 `NOT_MENTIONED_OR_EMPTY`，叙述中可能含适用线索、超出字段表达能力的复合工况或角色信息；自动化未将它们提升成正式字段值。自动 issue 计数是**可疑线索命中数**而非互斥记录数：`NOT_STATED_IN_STRUCTURED_RANGE=141`、`NO_FORMAL_VERIFIER_VALUE=82`、`NOT_MENTIONED_OR_EMPTY=65`、角色/极性混杂=17、对象不明=9、分压/总压区分=8、子机理/侧别范围=7、局部条件=5。词法线索仅用于定向人工复核，不是质量评分。

## 试点与候选谓词

15 个真实条款试点：

| 条款 | 关注的歧义/候选边界 |
|---|---|
| 5.1 盐酸腐蚀 | 酸性局部冷凝/浓缩、pH 与设备介质；材料耐蚀性不是易感性 |
| 5.2 硫酸腐蚀 | 浓度与温度相关性复杂；介质结构字段空缺不能靠枚举补值 |
| 5.5 二氧化碳腐蚀 | 湿 CO₂/水相与干 CO₂ 区分 |
| 5.6 环烷酸腐蚀 | JSONL 温度 `[177,242]` 与叙述所示一般 `177–427℃`、轻相常见 `218–400℃` 冲突；保留冲突，不择一写成定论 |
| 5.11 保温层下外部腐蚀 | 保温外表面湿润与金属表面温度条件不等同于内部介质温度 |
| 5.14 微生物腐蚀 | 微生物存活温度/环境线索不等于腐蚀速率或必要充分条件 |
| 5.17 燃灰腐蚀 | 燃烧/灰沉积侧、燃料/灰成分；不能套用于普通过程侧酸管线 |
| 5.18 烟气露点腐蚀 | 烟气侧、局部壁温低于成分相关酸露点；H₂SO₄/HCl露点参考值不能泛化 |
| 5.19 氯化铵腐蚀 | NH₄Cl沉积、吸湿/潮解及局部水膜，区别一般盐酸腐蚀 |
| 5.21 高温硫化（无氢） | 与有氢高温硫化的机制边界候选 |
| 5.22 高温硫化（有氢） | H₂S 分压语义独立于系统总压，特定机制条件待原文核对 |
| 5.23 碱式酸性水腐蚀 | JSONL `[49,66]℃` 与 `49–66℃` NH₄HS气相析出；局部相变/沉积条件不是全局机理适用区间；浓度/流态需组合 |
| 5.24 酸性水腐蚀 | pH/H₂S 的酸性水边界，避免与碱式酸性水串线 |
| 6.1 氯化物应力腐蚀开裂 | 氯化物水相、拉应力、材料易感性；金属温度不等于流体温度 |
| 6.7 湿硫化氢破坏 | 湿润条件、H₂S分压和模式专属条件；不能用系统总压代替 |

候选数 134，批准数/可靠适用性谓词数均为 0。134 的计数包括结构化字段抽取和特意标注的冲突/局部范围候选。所有候选保持 `PROPOSED_*` 且来源页状态为 `NEEDS_PDF_CHECK`；target_object、role、polarity、scope 均带有未决或候选限定，不可直接作为判定引擎的硬门槛。特别规则：不生成 L1-L4 风险，不将耐蚀材料转化为易感材料、不将结构化温压区间自动外推为全局边界。

## 合成测试集

`professional_counterexamples.jsonl` 包含 61 组作者合成场景：15 条试点每条各 1 个支持候选、UNKNOWN 缺项、误报反例，另有 16 个跨机理对抗场景。重点覆盖：

- H₂S气相分压 vs 系统总压；
- 流体温度 vs 壁温/金属温度；
- 耐蚀/保护性材料 vs 易感材料；
- 燃灰/烟气侧 vs 普通过程侧酸管道；
- 局部析盐/露点/沉积阈值 vs 整体机理温度范围；
- 酸性水与碱式酸性水、湿与干硫化物边界。

测试是作者自拟的候选行为检查，不是标准金标准、专家标注或独立评测。字段明确标注 `AUTHOR_SYNTHETIC_PENDING_REVIEW`、`expert_gold=false`、`human_reviewed=false`。不能由 61 条测试的通过推导专业准确率。

## 产物清单与给 S3-B 的接口

- `knowledge/applicability/candidates/source_manifest.jsonl`：82 条原始来源及 hash、PDF 页候选、核验状态。
- `knowledge/applicability/candidates/dm82_field_audit.jsonl`：82 条字段覆盖、词法 issue 类别及证据定位。
- `knowledge/applicability/candidates/pilot_predicates.jsonl`：134 条 15 条试点候选。每条含 `property/operator/value/unit/target_object/role/polarity/scope/origin/source_excerpt_locator/review_state`、来源与短摘录。
- `knowledge/applicability/candidates/professional_counterexamples.jsonl`：61 条合成测试种子。
- `knowledge/applicability/candidates/candidate_summary.json`：扫描、候选、来源摘要与禁止宣称计数。
- `scripts/s3_dm82_inventory_readonly.py`：可重复只读扫描、候选生成、内置确定性和结构自测。

建议 S3-B 导入的是候选对象，不是正式适用性事实。枚举值可作为原始输入保留，但需三值逻辑（`TRUE/FALSE/UNKNOWN`）；字段缺失返回 UNKNOWN；角色至少区分暴露介质、易感材料、保护材料、局部触发条件、子模式区分条件；适用域至少区分设备/过程侧/局部位置/壁面对象/子机理。只有 PDF 条款逐条定位并由具名专业审核者复核后，才可以从候选态转移到批准态。S3-A 没有人工签名，也没有执行这一状态迁移。

## 未决项与停点

1. 82 条 PDF 页图逐页核对尚未完成；所有候选 PDF locator 均 `NEEDS_PDF_CHECK`，页图索引只作候选。
2. 5.6 的结构化温度与叙述冲突未解决；5.23 的 49–66℃保留为局部 NH₄HS析出候选，不作整条机理适用上限/范围。
3. 结构化 medium 56/82 为空，材料 8/82 为空，设备 1/82 为空；不能靠推理补教师字段或扩枚举。
4. 82 条 `verified_by` 均为空；无真人审核，无专业金标准。
5. 按分工不修改 `docs/PROJECT_STATUS_CURRENT.md`，也不修改上游/教师文件。当前包已停在 `READY_FOR_OWNER_REVIEW`，等待所有者/专业审核与 S3-B 接口接线，不切换线上 V2。
