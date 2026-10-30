# P16-B｜P15-C五个检索未命中诊断

状态：`PROPOSAL_ONLY_NOT_RELEASED`。基线使用只读官方工具；候选在隔离内存索引上试验，gold和上游工具均未修改。46条查询均为synthetic，不构成专家质量验收。

| case | query | gold | baseline rank | candidate rank | global Recall@20/MRR@20 |
|---|---|---|---:|---:|---|
| `likelihood_method` | 失效可能性定量分析方法 GB/T 26610.4 失效概率 | `GBT26610.4-2022-8.3.2` | MISS | 2 | base 0.881/0.816; cand 1.000/0.952 |
| `matrix_5e` | 26610.3 风险矩阵 5E 高可能性 E后果 | `GBT26610.3-2014-7-y` | MISS | 1 | base 0.881/0.816; cand 1.000/0.952 |
| `matrix_mapping` | GB/T 26610.3-2014 风险矩阵图1 25格 | `GBT26610.3-2014-7-a` | MISS | 2 | base 0.881/0.816; cand 1.000/0.952 |
| `inspection_strategy` | 26610.2 基于风险的检验策略 检验周期 | `GBT26610.2-2022-8.2` | MISS | 1 | base 0.881/0.816; cand 1.000/0.952 |
| `dm_56_light_phase` | 环烷酸轻相介质 218℃ 400℃ | `GBT30579-2022-5.6` | MISS | 1 | base 0.881/0.816; cand 1.000/0.952 |

## 根因和整改验证

### `likelihood_method`

Expected GB/T 26610.4-2022-8.3.2 title is 技术模块因子; source describes damage severity index and inspection effectiveness, not literal “失效概率定量分析方法”. likely semantic query/gold-scope mismatch; confirm with domain reviewer before treating as true miss.

候选rank：2。需用holdout查询验证词汇扩展并请领域人员复核gold；不得用这46题内调参数宣称泛化。

### `matrix_5e`

25 matrix rows have repeated content_raw/title; cell coordinates are structured rbi_detail fields that official search does not index. 5E is not present in text, so a per-cell request cannot rank target by source semantics.

候选rank：1。需用holdout查询验证词汇扩展并请领域人员复核gold；不得用这46题内调参数宣称泛化。

### `matrix_mapping`

Query requests the matrix as a family but gold expects a single arbitrary 7-a row. Search returns matrix rows around rank boundary; top_k=20 undercovers a 25-cell family. Treat as family recall question, not one-cell semantic miss; no label change without review.

候选rank：2。需用holdout查询验证词汇扩展并请领域人员复核gold；不得用这46题内调参数宣称泛化。

### `inspection_strategy`

Query mixes standard scope with generic “inspection interval”; 8.2 title is “检验策略的实施” and its body talks about verified damage mode, expanding circuit inspection scope/proportion, not a fixed cycle. Current scoring dilutes discriminative source phrase and ranks TSG clauses.

候选rank：1。需用holdout查询验证词汇扩展并请领域人员复核gold；不得用这46题内调参数宣称泛化。

### `dm_56_light_phase`

Actual phrase “轻相介质218–400℃” is in structured mechanism_detail.influencing_factors/applicability, while standard_clause_search indexes only title+content_raw. Original source content_raw has 177–242℃ and omits the light-phase phrase; 0 hits indicate indexed-field omission/stale data, not absence from source.

候选rank：1。需用holdout查询验证词汇扩展并请领域人员复核gold；不得用这46题内调参数宣称泛化。

候选整改在`work/data_staging/p16/B_REMAINDER/P16_B_CHANGE_PROPOSALS.jsonl`（5条检索应用建议）。逐题top20及30次延迟见baseline/candidate CSV；延迟是本机进程内微基准，不含HTTP/SQLite网络耗时。