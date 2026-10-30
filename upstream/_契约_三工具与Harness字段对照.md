# 三工具与 Harness 接口契约（字段对照表 · 第 1 步产出）

> 用途：施工前把字段名、类型、取值来源、边界行为一次定死。第 2～4 步的代码严格照此实现。
> 依据（唯一口径，按优先级）：`工具接口规范.md` > `schema/*.json` > `技术指标验证方法.md`
> 版本：v0.3 ｜ 编制日期 2026-10-26 ｜ 状态：**待人工核实后生效**

---

## 0. 一句话结论

三个工具、五个顶层字段、两处 if-then 硬约束、一处硬红线（`status="ok"` 必须带 `source`）。
数据侧已核实：**source 四件套 461/461 齐全，损伤机理八段式 82/82 齐全**；但 **rbi 侧只有 25 条风险矩阵格带等级、0 条带检验周期** —— 这决定了 `rbi_lookup` 必须"算"而不是"抄"（见 §5）。

---

## 1. 统一返回外壳（不可改）

`schema/tool_response.schema.json`：顶层 5 字段，`additionalProperties: false` —— **多一个字段就违规**。

| 字段 | 类型 | 必填 | 约束 |
|---|---|---|---|
| `status` | string | 是 | 只能取 `ok` / `out_of_domain` / `not_found` / `error`；**只能填一个值**，不许写 `ok\|out_of_domain` 整串 |
| `in_domain` | boolean | 是 | 查询条件是否落在条款覆盖范围内 |
| `result` | object | 是 | 业务结果；**`in_domain=false` 时必须为 `{}`**（`maxProperties: 0`） |
| `source` | array\<object\> | 是 | **`status="ok"` 时 `minItems: 1`**（硬红线） |
| `message` | string | 是 | `in_domain=false` 时**必须非空白**（`pattern: \S`），要说明"超出了什么" |

`source` 每一项（`additionalProperties: false`，**只许这 4 个键**）：

| 字段 | 类型 | 必填 | 取值来源（本项目） |
|---|---|---|---|
| `clause_id` | string | 是 | 记录 `clause_id`，如 `GBT30579-2022-6.16` |
| `standard_code` | string | 是 | 记录 `standard_code`，如 `GB/T 30579-2022` |
| `clause_no` | string | 是 | 记录 `clause_no`，如 `6.16` |
| `page` | integer | 是 | 记录 `page`（整数） |

> 已核实：461 条记录这四项 **零缺失**，`source` 可 100% 由记录直接构造，无需拼装、无需 guessing。
> 禁止：把 `title`、`basis_note`、`hits[].clause_id` 塞进 `source` 项（`additionalProperties:false` 会直接判违规）；也禁止用 `basis_note` 代替 `source`。

**代码侧**：`harness.py` 的 `make_response()` 已内置红线校验（`status=ok` 且 `source` 空 → `ValueError`），三个工具**一律**经它构造返回，不许手写 dict。

---

## 2. `damage_mechanism_query`（损伤机理识别与鉴别）

### 2.1 入参

| 参数 | 类型 | 必填 | 说明 / 校验 |
|---|---|---|---|
| `material` | string | **是** | 必须在 `enums.json.material` 的键或 aliases 内（护栏先归一化） |
| `medium` | array\<string\> | **是** | 数组，**不许逗号分隔字符串**；每项按 `enums.json.medium` 归一化 |
| `temperature_c` | number | 否 | ℃；不许带单位字符串 |
| `equipment_type` | string | 否 | 六类之一：塔/换热器/管道/容器/加热炉/储罐 |
| `evidence` | object | 否 | 6 个子字段，见下；**不许把这些子字段提到顶层** |

`evidence` 子字段（全部可选）：

| 字段 | 类型 | 语义 |
|---|---|---|
| `ph` | number | 塔顶水/工艺水 pH |
| `cl_ppm` | number | 氯离子 mg/L |
| `fe_ppm` | number | 铁离子 mg/L |
| `h2s_ppm` | number | 硫化氢含量 |
| `wall_thinning` | boolean | 测厚是否发现减薄 |
| `crack_found` | boolean | 是否发现裂纹 |

> **关键语义**：未提供某子字段 ≠ `false`。判据里必须区分「未提供(unknown)」与「提供了 false」。

### 2.2 出参 `result`

```
result = {
  "mechanisms": [ Mechanism, ... ],   # 可能为空数组（配合 out_of_domain / not_found）
  "discriminator": string,            # 必给：还缺什么证据才能区分
  "excluded": [ {"name": string, "reason": string}, ... ]
}
```

`Mechanism` = `name` + `clause_id` + 八段式 + `match_level`：

| 字段 | 类型 | 取值来源（记录字段） |
|---|---|---|
| `name` | string | `title`（**必须是 GB/T 30579-2022 原文叫法**） |
| `clause_id` | string | `clause_id` |
| `description` | **string** | `mechanism_detail.description` |
| `morphology` | array\<string\> | `mechanism_detail.morphology` |
| `affected_materials` | array\<string\> | `mechanism_detail.affected_materials` |
| `influencing_factors` | array\<string\> | `mechanism_detail.influencing_factors` |
| `susceptible_locations` | array\<string\> | `mechanism_detail.susceptible_locations` |
| `prevention` | array\<string\> | `mechanism_detail.prevention` |
| `detection_methods` | array\<string\> | `mechanism_detail.detection_methods` |
| `related_damages` | array\<string\> | `mechanism_detail.related_damages` |
| `match_level` | string | 计算得出：`high` / `medium` / `low`（规则见 §2.3） |

> 八段式**恰好 8 个内容字段**，键名不得增删改名；`description` 是字符串，其余 7 个必须是字符串数组。
> 已核实 82 条损伤机理记录：**八段全部非空，82/82**，可直接映射，无需补空。

### 2.3 `match_level` 计算规则（本契约自定，需确认）

| 等级 | 判据 |
|---|---|
| `high` | `material` 命中 `affected_materials` **且** `medium` 命中 `influencing_factors`/`description` 中的介质环境 |
| `medium` | 只命中材质或只命中介质之一 |
| `low` | 材质属同族（查 `material_family.json`）但未直接命中 |

### 2.4 命名红线

损伤模式名必须用标准原文：`湿硫化氢破坏`（非"损伤"）、`氯化铵腐蚀`（非"垢下腐蚀"）、`高温硫化物腐蚀`（非"高温硫腐蚀"）；引用 5.21/5.22 时保留「无氢气环境 / 氢气环境」限定。改名 → `standard_clause_search` 检索失败。

---

## 3. `rbi_lookup`（风险等级与检验周期）

### 3.1 入参

| 参数 | 类型 | 必填 | 校验 |
|---|---|---|---|
| `equipment_type` | string | **是** | enums 六类 |
| `material` | string | **是** | enums |
| `mechanism` | string | 否 | 已识别的损伤机理名 |
| `medium` | array\<string\> | 否 | 数组 |
| `temperature_c` | number | 否 | ℃ |
| `pressure_mpa` | number | 否 | MPa |
| `service_years` | number | 否 | 年 |

### 3.2 出参 `result`

| 字段 | 类型 | 说明 |
|---|---|---|
| `likelihood` | string \| null | 失效可能性等级，如 `"3"` |
| `consequence` | string \| null | 失效后果等级，如 `"D"` |
| `risk_level` | string \| null | **原始等级**（低风险/中风险/中高风险/高风险） |
| `risk_level_unified` | string \| null | **统一等级** `L1`~`L4`（本任务包不出现 L5） |
| `inspection_interval_year` | number \| null | 检验周期；**无条款依据必须 `null`** |
| `inspection_methods` | array\<string\> | 推荐检验方法，可为空数组 |
| `basis_note` | string | 补充说明（**不能替代 `source`**） |

### 3.3 取值规则（基于实测数据，需确认）

实测：379 条 RBI 记录中，`risk_level_unified` 非空仅 **25 条**（全部是 26610.3 第 7 章 5×5 风险矩阵格 `7-a`~`7-y`）；`likelihood` 非空 30 条（25 格 + `5.1.2-a`~`e` 五档）；`consequence` 非空 45；**`inspection_interval_year` 非空 0 条**。

因此本工具**不能"从单条记录抄答案"**，按下面 4 步算：

1. **候选条款**：按 `mechanism` 匹配 `title`，或用 `medium`/`equipment_type` 匹配 `applicable_conditions`，召回 `knowledge_type="rbi"` 的记录。
2. **等级**：
   - 若命中的是风险矩阵格（`7-*`）→ 直接取 `likelihood`/`consequence`/`risk_level`；
   - 若只知 `(L, C)` → **查 `risk_level_mapping.xlsx` 的「GBT26610.3-2014」页**得 `原始等级`+`统一等级`；
   - 若条款只给用语（如"高风险"）→ 查「按用语对应」页；
   - 三者都不成立 → `likelihood/consequence/risk_level/risk_level_unified` 全 `null`，并在 `basis_note` 说明缺哪一项因子。
3. **检验周期**：从命中条款 `content_raw` 抽取**明确的**周期表述（如"一般每6年检验一次""最长不得超过9年"）。
   - 抽到 → 填数值，且 `source` **必须包含该周期条款**（如 `TSG21-2016-8.1.6.1-a`、`TSG21-2016-8.10.3-a`）；
   - 抽不到 → `null`，**禁止凭经验给数**；
   - 依据 26610.3 时，其本身不给周期，`source` 须另带 26610.2 或 TSG21 条款。
4. **检验方法**：取命中记录 `rbi_detail.inspection_methods`（73 条有值）。

---

## 4. `standard_clause_search`（兜底检索）

### 4.1 入参

| 参数 | 类型 | 必填 | 校验 |
|---|---|---|---|
| `keyword` | string | **是** | 非空 |
| `knowledge_type` | string | 否 | **只能** `rbi` 或 `damage_mechanism` |
| `top_k` | number | 否 | 默认 **5**，上限 **20**（超出截到 20，非报错） |

### 4.2 出参 `result`

```
result = { "hits": [ {"clause_id":..., "title":..., "snippet":..., "score":...}, ... ] }
```

| 字段 | 约束 |
|---|---|
| `clause_id` | 记录 `clause_id` |
| `title` | 记录 `title` |
| `snippet` | **≤200 字**（硬约束，超长必须截断并保证语义完整） |
| `score` | number，0~1，降序 |

`score` 建议口径（需确认）：`0.6×title 命中度 + 0.4×content_raw 命中度`，按命中关键词覆盖比例归一到 0~1。

> `hits[].clause_id` **不能替代** `source`；`source` 取本次返回命中前 N 条的出处（至少 1 条）。

---

## 5. `status` 决策表（四值何时用）

| 场景 | status | in_domain | result | source | message |
|---|---|---|---|---|---|
| 正常命中 | `ok` | true | 业务结果 | **≥1 条** | 可空 |
| 条件超出条款覆盖（材质/介质/设备类型不在枚举或不在标准适用范围） | `out_of_domain` | **false** | **`{}`** | 可空 | **非空**，说明超出什么 |
| 条件在域内但库里没有对应条款（如某机理无 rbi 条款） | `not_found` | true | `{}` 或带空列表 | 可空 | 建议说明 |
| 参数非法 / 内部异常（护栏捕获） | `error` | false 或 true | `{}` | 可空 | 错误原因 |

> 注意：`out_of_domain` 与 `not_found` 必须分清 —— 前者是"标准管不到"，后者是"标准管但没抽到"。指标(3) 的四类异常用例正是按这个区分。

---

## 6. 枚举与归一化（护栏职责）

- 白名单**仅三张表**：`enums.json` 的 `material`、`medium`、`equipment_type`；`stream_type` 不参与参数校验。
- 归一化顺序：**alias → 规范值 → 白名单校验**，先归一化再校验（否则 `湿H2S`、`HCl`、`20#` 会被误判非法）。
- `material` 填不锈钢复合板/堆焊层时**只填复层材质**，基材写入轨迹 `input.operating_condition` 或 `applicable_conditions.other`。
- `medium` 只填腐蚀性介质/组分，**不填原油、石脑油等物流名**；`酸式酸性水`与`碱式酸性水`不得同时出现；信息不足不许用"酸性水"兜底。
- 材质包含关系查 `material_family.json`，**不用 aliases 自动合并**。

---

## 7. Harness 与轨迹契约

### 7.1 执行循环

- `MAX_ROUNDS = 8`（指标要求 ≥5 轮）。
- `call_tool` 顺序固定：`check_tool_exists` → `check_params` → `spec.func(**args)` → `check_response_format` → `check_in_domain`。
- `planner(task_input, history)` 返回 `{"thought","tool","args"}` 或 `{"thought","final_answer"}`。
- 四类异常各自对应护栏方法：工具不存在 / 参数非法 / 出域 / 返回格式不合规。

### 7.2 轨迹记录字段（`trajectory.schema.json`）

顶层必填：`traj_id`、`task_type`、`input`、`steps`、`final_answer`、`annotator`、`checked`；可选 `special_type`。

`input` 6 个必填（**缺字段不行，没有信息填空字符串**）：`equipment`、`material`、`medium`（数组）、`operating_condition`、`field_evidence`、`question`。

`steps[]` 每项 6 个必填、`additionalProperties:false`：

| 字段 | 说明 |
|---|---|
| `step` | 编号，从 1 起 |
| `thought` | 本次调用的思考 |
| `tool` | 仅限三个工具名 |
| `args` | 必须符合该工具的入参 schema（含必填校验） |
| `result` | **工具真实返回的完整外壳**（含 5 字段），不许塞 `{}` |
| `observation` | 对返回的观察与下一步判断 |

`final_answer`：`conclusion`（string）+ `basis`（clause_id 数组）。
**`basis` 规则**：仅 `special_type="out_of_domain"` 允许为空；其余不许空；**每个 clause_id 必须在 clauses.jsonl 中存在**。

`task_type` 判定：调用步数 **≥3 → `multi_step`**，否则 `single_step`（注意：≥3 而非 ≥2）。
`special_type`：`exclusion` / `insufficient_info` / `out_of_domain`，普通轨迹**不写这个键**。

> `Step` 里的 `blocked`/`block_kind`/`elapsed_ms` 只进运行日志（`to_dict`），**不进**数据集（`to_record` 只导出 `RECORD_STEP_FIELDS`）；被拦截的轨迹由 `to_record` 抛 `DatasetExportError` 挡在数据集外。

---

## 8. 数据现状实测（决定实现方式，供核实）

| 检查项 | 实测结果 | 对实现的影响 |
|---|---|---|
| `source` 四件套（clause_id/standard_code/clause_no/page） | **461/461 齐全** | source 可直接构造，0 风险 |
| 损伤机理八段式填充 | **82/82 八段全非空** | 直接映射，无需补空 |
| `rbi.risk_level_unified` | 仅 **25 条**（都是 `7-*` 矩阵格） | 必须查映射表算，不能抄 |
| `rbi.likelihood` | 30 条（25 格 + `5.1.2-a~e`） | 需与后果等级组合才成形 |
| `rbi.inspection_interval_year` | **0 条** | 只能从 `content_raw` 抽取或填 `null` |
| `rbi.inspection_methods` | 73 条 | 可返回，其余为空数组 |
| `content_raw` 长度 | 中位 58 字，最长 295 字 | `snippet` 200 字截断规则必需 |

---

## 9. 待你核实的 4 个决策点

1. **`rbi_lookup` 的等级来源**：确认"矩阵格直接取 + 其余查映射表 + 都无则 null"这套算法（而不是要求库里必须存齐）。
2. **检验周期**：确认允许"从 `content_raw` 正则抽取明确的'N年'表述"，抽不到就 `null`（不引入任何经验值）。
3. **`match_level`**：确认 high/medium/low 三档及其判据（规范未给死规则）。
4. **`score`**：确认 0.6×title + 0.4×content 的加权口径。

以上 4 点你若认可，第 2 步就按此写码；若要改，改这张表即可，代码未动。

---

## 10. 明确不改的东西

- 三个工具名、参数名、`result` 内键名 —— 一个都不改。
- `enums.json`、`material_family.json`、`risk_level_mapping.xlsx` —— **只读**，不修改。
- `harness_skeleton/harness.py` —— 保持原样作参考，实现在 `05_提交区/harness.py` 新建。
- `clauses.jsonl` —— 本步不动；核对发现问题走 xlsx → convert 的正规链路。
