# R2-A2 派生检索候选与查询覆盖审计（2026-10-29）

状态：`CANDIDATE_ONLY / MACHINE_CHECKS_PASS / BUSINESS_GOLD_PENDING`。本窗口只创建派生只读索引、术语查询扩展、覆盖矩阵、困难负例、复现脚本与本报告；没有修改教师数据、A1目录或运行服务。

## 1. 输入、所有权与可复现性

| 输入 | 实测 SHA-256 / 计数 | 解释 |
|---|---|---|
| `upstream/05_提交区/clauses.jsonl` | `a8151797ba15a6a7452dd83aaec9fab4c0a815724ca45062eb1e2bac7b4d49ef`; 554行 = RBI 472 + 损伤机理 82 | 冻结源，仅读；派生版本 `r2_candidate_v1` |
| `knowledge/lexical.py` | `31b64f957a9fa30fe35a9fcb14f7942d91871f93bee6cae8d8ff79a01006f68d` | 既有旧检索基线，未修改 |
| `evals/p0_expert_guidance/cases.jsonl` | 固定回归输入64条 | 标注为`AUTHOR_SYNTHETIC`，`expert_gold=false`；不是专家金标准 |
| `evals/v2b_professional_cases.jsonl` | 31条合成固定输入 | 同样不是人工金标准；本轮主对比使用前述64条 |

生成命令（项目根目录）：

```powershell
\.venv-langgraph\Scripts\python.exe -B scripts\r2_data_retrieval.py build
\.venv-langgraph\Scripts\python.exe -B scripts\r2_data_retrieval.py self-test
\.venv-langgraph\Scripts\python.exe -B scripts\r2_data_retrieval.py audit --limit 64
```

所有派生结果只落在 `knowledge/retrieval/r2_candidate_v1/`。`clauses.jsonl`含source id、标准号/条号、摘录指针、印刷页、源hash、机器场景tag和条件作用域候选；不复制完整标准原文。当前正式JSONL没有物理PDF页索引，因此派生字段显式为`null`，不猜页码。`review_state=SOURCE_RECORD_PRESENT_HUMAN_APPLICABILITY_UNREVIEWED`；索引没有第四个教师工具，不授权任何风险或适用性结论。

## 2. 检索合同

返回的每条hit区分：

- `source_record_present=true`：正式JSONL内找到该记录；不表示原文已逐页核验。
- `semantic_relevance=RELATED_RETRIEVAL_ONLY`：只表示这是待审检索候选；困难负例可以为`NEGATIVE_SEMANTIC_MATCH`。
- `applicability=UNKNOWN`：永不由词面/alias/FTS分数升级为适用结论。
- 术语alias仅用于query rewrite，既不是canonical事实，也不是来源证据。

`knowledge/retrieval/r2_candidate_v1/term_aliases.json`显式将“壳体磕碰/碰撞/凹陷”扩成“机械损伤、表面缺陷、局部变形”等检索词。该扩展用于召回TSG 21-2016 8.3.6、8.5.8等待核条款；不能将8.5.8的“发现裂纹且适用其压力容器条件”移作普通凹陷的验收阈值。

## 3. 局部条件/反例处理

### GB/T 30579-2022 5.23

源记录的49–66°C保存在谓词候选中，作用对象限定为NH₄HS气相析出/局部沉积相关窗口，极性为`supporting_subcondition_not_global_necessary_condition`。同源60°C及80°C查询均保留`GBT30579-2022-5.23`作为检索候选，不因80°C超过66°C就排除整个碱式酸性水腐蚀机理。**保留检索候选并不表示60°C或80°C已被人工核实为设备适用。**

### GB/T 30579-2022 5.6 / 6.7

5.6的177–242°C机理描述与轻相介质218–400°C叙述拆成两个待核谓词，不合并成一个全局范围。6.7把H₂S气相分压（>0.0003 MPa）与总系统压力分开，把氢鼓泡/HIC/SOHIC和硫化物应力腐蚀开裂子型温度分别标记；没有把单一子型窗口扩展到整条机理。以上都来源于结构化教师记录，物理PDF页、原文局部定位及专业签审仍缺，故为机器投影待审核。

### 困难负例

`hard_negatives.json`定义了至少一项有来源的语义反例：搜索“壳体磕碰损伤”时，GB/T 30579-2022 7.11“辐照脆化”解释里的粒子—晶格“碰撞”是词面重叠，语义对象不同，必须标`NEGATIVE_SEMANTIC_MATCH`，不可当壳体机械损伤支持。该记录不证明任何真实设备“无辐照”或“无损伤”，设备适用性仍是`UNKNOWN`。

第二项反例是用户明确限定“非烟气侧”的HCl工况：5.18“烟气露点腐蚀”即便词面命中，也标成负例；5.1盐酸腐蚀仅作为相关候选。查询层不凭95°C认定机理或排除露点条件，仍需核实相态/位置/成分。

## 4. 现有64条固定回归问题 old/new 对比

命令：`\.venv-langgraph\Scripts\python.exe -B scripts\r2_data_retrieval.py audit --limit 64`。基线为未修改的`knowledge.lexical.SqliteLexicalRetriever`；新候选为别名扩展的内存FTS5。比较维度仅为Top-5是否非空及本机单次查询时间记录；完整逐题old/new ID在`knowledge/retrieval/r2_candidate_v1/retrieval_audit.json`。

| 指标 | 旧基线 | 新候选 | 说明 |
|---|---:|---:|---|
| 输入数 | 64 | 64 | 固定作者合成问题，非专家Gold |
| Top-5非空数 | 2/64 | 8/64 | 仅“非空覆盖率”，不是Recall、精确率、正确适用率 |
| 非空率 | 3.12% | 12.50% | 增量+9.38个百分点；整体非空率仍低，提示自然语言切词/query rewrite需继续迭代 |
| precision / Recall@k / MRR | `null` | `null` | 没有逐题人工标注的相关条款Gold，不能计算 |
| 专家Gold | 0 | 0 | 人工判定的设备适用性也是0 |

脚本还运行5组指定域关键案例（酸性水60/80°C、壳体磕碰、非烟气侧HCl、湿H₂S分压、烟气酸露点），完整ID、alias以及负例标记都记录在审计JSON。它们是回归探针，不是独立真值集。没有对并行SSE、后端工具调用或线上服务做运行测试。

## 5. 专项机器测试

`self-test`当前 **9项PASS**：554/472+82源记录计数；60°C和80°C都检出5.23；壳体磕碰映射到TSG 8.5.8/8.3.6；7.11辐照脆化负例规则；非烟气HCl下5.1与5.18负例区分；H₂S分压映射到6.7；检索结果适用状态保持UNKNOWN；5.23温区为局部作用域而非全局必要条件。

实际一次测试命令顺序：

```text
python -B scripts/r2_data_retrieval.py self-test   PASS（9 checks）
python -B scripts/r2_data_retrieval.py build       PASS（554 rows；472 RBI +82 damage_mechanism）
python -B scripts/r2_data_retrieval.py audit --limit 64  PASS（64 frozen author-synthetic inputs）
```

冻结源哈希构建后再次核对仍为`a8151797ba15a6a7452dd83aaec9fab4c0a815724ca45062eb1e2bac7b4d49ef`。此前第一次audit因脚本未把项目根加入`sys.path`而失败，已修复路径并完整重跑；第一次self-test发现硬负例没有实际出现在top-k，于是测试改为明确验证负例classifier，避免虚报“该负例已从搜索器命中”。

## 6. 未决与交接

1. 老师记录的PDF物理页为空；需独立PDF证据审阅，不可把`printed_page`复制为物理页。
2. 64题作者合成题并非冻结的逐条相关性金标，整体非空召回较低；请G/Owner建立≥50条由领域人员逐项标注的查询Gold，分开标来源存在、相关性、条文支持、实际适用。
3. TSG 8.3.6/8.5.8查询到只说明“可能相关”。普通磕碰没有通用停机、维修或验收限值。本报告不提供RBI等级、设备放行或复机许可。
4. 5.23、5.6、6.7分型条件和单位仍需人工对原PDF核对；索引中的机器拆分不得回写正式标准。
5. `scripts/r2_data_retrieval.py`只实现离线候选检索基准。它没有被接入Graph或教师工具，也不代表实际工具结果已覆盖；接口建议见本报告第2节合同与`manifest.json`。

最终等级：机器派生与回归候选可复现；语义精确率、条文支持率、真实适用性与专家可用性均`UNKNOWN`，所以保持`CANDIDATE_ONLY / BUSINESS_GOLD_PENDING`。
