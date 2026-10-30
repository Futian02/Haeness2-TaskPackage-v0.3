# R1 工程语义 Schema 与草稿知识候选

## 数据模型

`orchestration/semantics.py` 使用 Pydantic 严格模型（`extra=forbid`）：

- `EngineeringObservation`: field/raw_span/value/unit/normalized_value/normalized_unit/observation_state/sampled_at/aliases。
- `Hypothesis`: 假设名称、支持/冲突证据、unknown、来源条款、候选状态、审核状态。
- `EvidenceLink`: clause id、标准号、条款号、印刷页、PDF页（可未知）、原文短摘录、抽取方式、复核状态、文件 SHA。
- `InformationGap`: 缺失字段、可询问问题、原因、优先级。

现场状态是 `observed_true | observed_false | unknown | not_applicable`。`还没测厚` 映射 `unknown`；`未发现减薄` 映射 `observed_false`；绝不把未测误读为阴性。原文跨度原样存留；解析值可转单位但不改 raw span。

## 归一化

已实现本地小型产品同义词表（Fe/铁离子、Cl/氯离子、酸碱度、H2S 等），不碰教师 `enums.json`。支持水样 mg/L 与 ppm 的 1:1 稀溶液近似（保留在 parser 代码注释中）、°F→°C、bar/kPa→MPa、年限与 pH。未知/不确定单位 fail-fast；不得自动换算现场密度相关复杂单位。

## 10条候选卡和10个自然语言样例

`knowledge/semantic_drafts.jsonl` 由 `scripts/build_semantic_drafts.py` 从冻结 `clauses.jsonl` 的十个原始机理条目生成；每卡含原 clause_id、八段式、适用条件、原 content_raw 短摘录、标准文件 SHA、印刷页。PDF 页索引未知留 null。别名与鉴别问题属于 draft，`review_status=draft_needs_review`、`reviewed=false`、E0；不是工程规则，不进入风险定级。

`evals/semantic_cases.json` 有十个现象不同的自然语言候选测试，带候选来源和预期缺项；全标 `gold=false`/`draft_needs_review`，须经人工确认才能冻结成评测金标。当前代码还没有把这十条用例当作 retrieval gold 或自动机制分类评估。

## PDF 溯源合同

Manifest 提供源文件 SHA 和文件归属。`EvidenceLink` 将 `doc_sha256`、`standard_code`、`clause_no`、`page_printed`、`pdf_page`、`quote_span`、`extraction_method`、`review_status` 拆开。此轮 clause JSONL 的 `page` 作为印刷页候选；没有逐页映射 PDF 物理页，没有 OCR，未改变原始 `content_raw`。人工查看 PDF 并确认原文支持/适用性之前，最高等级 E1。

## 学习点：机理鉴别是可证伪问题

盐酸腐蚀 vs 氯化铵腐蚀不该靠相似度得分强行选一个。先保留多个假设，写出每个假设的支持/冲突观测与 unknown，再问能区分二者的最小现场变量（例：pH、注水/结盐位置、压降与实际取样时间）。检验问题应能让某个假设被削弱/排除，而不是把“补更多数据”当结论。`unknown ≠ false` 是这类证据树的关键状态不变量。
