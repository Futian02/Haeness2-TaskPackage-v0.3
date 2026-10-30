# P16-B｜来源保真与检索质量收口

状态：**PENDING_HUMAN_REVIEW / PREVIEW_ONLY**。只写P16-B隔离目录及P16-B报告；upstream、P15成果、教师工具、正式JSONL、SQLite及应用代码均未改。

## 1. 211条表格风险队列

以P15-A `P15_A_TABLE_REVIEW_COVERAGE.csv` 221条为分母，并以26610.5表2/表3机器图像候选清单中10个clause_id做差，得到211条剩余待核记录：{"GB/T 26610.4-2022": 103, "GB/T 26610.3-2014": 78, "GB/T 26610.5-2022": 15, "GB/T 26610.2-2022": 15}。所有项目保留旧F、PDF/印刷页定位、P15 locator、表格/行/列/bbox状态及未决原因，见`work/data_staging/p16/B_REMAINDER/P16_B_PRIORITY_TRIAGE.csv` / `P16_B_SOURCE_CELLS.csv`。

- 211/211均没有独立真人核字；211/211条精确单元格仍无双人核签BBox：191条归`SOURCE_UNRESOLVED_CELL_PAGE_LOCATED`（仅定位物理页，行/列未可靠定位）；20条为表2视觉候选`AI_VISUAL_NUMERIC_ROW_MATCH_F_TEXT_PENDING_HUMAN`（录入行名和列头、未记录BBox）。CSV逐条保留PDF/页码/可验证定位或明确的细胞级未决原因，不把页定位冒充单元格核真。
- 按任务优先级先选26610.4风险最高的20条做定向页渲染与OCR，处理20/20条；源页图像保存在P16-B的`table_pages/`。OCR只是页内导航；没有将OCR读数写回数据或标成已核真。20条集中在GB/T 26610.4-2022表2的6-a至6-t，针对同一来源页定向采集；候选图像肉眼扫查显示设备行名、四个破裂口区间及FG合计与该页表格布局相符，但未记录单元格BBox，也未由第二名复核者签核。故这不是20条已核真记录，仍需逐行记录行列坐标、单位/边界、脚注及每行FG合计关系。
- 26610.4优先数值/量化因子表；26610.3表格行列仍需单元格格核；26610.5剩余15条；26610.2表1/表3五条/十条策略单元边界均保留原值待核。

## 2. DM字段语义队列

P15-B的656个G–N字段加656个O–V条件字段共1312项全部进入`P16_B_DM_FIELD_REVIEW.csv`，没有继承P15的OCR定位为“已核真”。G–N中子条标题未命中项：62；标记数值/单位/浓度/分压/温度/硬度/材料耐蚀词项及5.6/5.23/6.7高优先项各见CSV。材料易感性、介质、设备和温压仍须按原文对象核对。

5.6原图定向核查（GB/T 30579-2022印刷页9/PDF index14）产生待复核建议：候选I把材料序列`5Cr-0.5Mo`写成`3Cr-0.5Mo`；候选J把标准原词“烃相酸值/烃相介质”改成“轻相”，应分开记录177–427℃机理段与218–400℃烃相常见窗口；候选K可能漏列延迟焦化焦化轻/重蜡油回路，并将`注氢点`写成`注氨点`。这些属原图候选，且5.6.5段落续页，待第二人逐字确认。另5.6 P15候选F由5.6.1+5.6.2摘录缩短为仅5.6.1；H仍含损伤形态，故不能判机理内容全丢，但F覆盖范围缩小；须按≤300字规则复核。5.23原图（印刷页33/PDF index38）确认49–66℃只对应加氢反应器反应产物出料降温时气相NH₄HS析出/沉积；不是整机理适用温区。其材料枚举包含铝合金及镍基合金，原O候选遗漏；原文将碳钢耐蚀性较弱与其余列举材料耐蚀性较强分开描述。6.7原图（印刷页52/PDF index57）确认H₂S气相分压阈值0.0003 MPa、溶液H₂S浓度阈值50×10⁻⁶、HCN阈值20×10⁻⁶为不同条件；氢鼓泡/HIC/SOHIC温度约室温至150℃（有时更高），SSC通常82℃以下；HB200限于低强度碳钢焊接接头SSC描述。不能将分压写作设备总压或把子类型温区套为整体边界。相关变更仅进入来源建议，仍需第二人签核。

## 3. 五份补充PDF余下56章

P15章节矩阵中56个`REVIEW_NEEDED`项全部转入`P16_B_SUPPLEMENT_REVIEW.csv`，按暂定范围家族分类为：{"equipment_design_manufacturing_auxiliary": 52, "external_corrosion_control_auxiliary": 4}。仅对五份PDF各前15页定向OCR，共75页，不做全文OCR。`title_candidate_from_targeted_ocr`和`toc_ocr_evidence`是导航证据，不解除`exact_title_status=NOT_VERIFIED`：GB/T 150.1第4章可见“失效模式”，但它是建造过程中考虑的通用短期/长期/循环失效模式，不能直接等同30579服务损伤机理；GB/T 150.4附录候选归于制造/检验/验收及低温脆断设计制造；GB/T 21447定向页可读到第7章“干扰防护”、第8章“施工与验收”、第9章“运行及维护管理”，页界及第10章仍未完全确认；150.3目录附录、GB/T 151-2026标题仍需原图逐项核对。所有候选标题/页界未核实项均逐条写明最小补证要求。未把这些背景强塞入DM/RBI，也未生成补充DM记录。

## 4. 冻结46题检索对照

在同一554条P15候选JSONL上，实际重跑46个冻结合成查询、原gold不变：
- 官方只读工具基线：检索到37/42相关ID，micro Recall@20=0.881，MRR@20=0.816。
- P16候选：应用层全字段本地索引+query-plan扩展+RRF；检索到42/42，micro Recall@20=1.000，MRR@20=0.952。这是一次对合成gold的算法对照，不代表专业检索验收；未改变gold、官方工具或正式数据。
- 对照结果及top20逐条结果见`P16_B_RETRIEVAL_BASELINE_46.csv`、`P16_B_RETRIEVAL_CANDIDATE_46.csv`；五项各30次暖机延迟均值/p95记在对应行：likelihood_method: baseline 3.2678/4.6577 ms, candidate 3.7239/5.25 ms；matrix_5e: baseline 2.9917/4.3958 ms, candidate 3.7304/5.6557 ms；matrix_mapping: baseline 2.939/4.7755 ms, candidate 3.0893/4.3007 ms；inspection_strategy: baseline 1.7776/2.8834 ms, candidate 1.9385/2.9165 ms；dm_56_light_phase: baseline 1.5481/2.3959 ms, candidate 1.3499/1.847 ms。这是本机进程内微基准，不含API/数据库网络耗时，也不是生产SLA。未标注题非空结果只作诊断，不能判定为误报。

### 5个失配根因与对照

| frozen case | gold | baseline rank | candidate rank | 根因/整改验证 |
|---|---|---:|---:|---|
| `likelihood_method` | `GBT26610.4-2022-8.3.2` | `MISS` | `2` | Expected GB/T 26610.4-2022-8.3.2 title is 技术模块因子; source describes damage severity index and inspection effectiveness, not literal “失效概率定量分析方法”. likely semantic query/gold-scope mismatch; confirm with domain reviewer before treating as true miss. |
| `matrix_5e` | `GBT26610.3-2014-7-y` | `MISS` | `1` | 25 matrix rows have repeated content_raw/title; cell coordinates are structured rbi_detail fields that official search does not index. 5E is not present in text, so a per-cell request cannot rank target by source semantics. |
| `matrix_mapping` | `GBT26610.3-2014-7-a` | `MISS` | `2` | Query requests the matrix as a family but gold expects a single arbitrary 7-a row. Search returns matrix rows around rank boundary; top_k=20 undercovers a 25-cell family. Treat as family recall question, not one-cell semantic miss; no label change without review. |
| `inspection_strategy` | `GBT26610.2-2022-8.2` | `MISS` | `1` | Query mixes standard scope with generic “inspection interval”; 8.2 title is “检验策略的实施” and its body talks about verified damage mode, expanding circuit inspection scope/proportion, not a fixed cycle. Current scoring dilutes discriminative source phrase and ranks TSG clauses. |
| `dm_56_light_phase` | `GBT30579-2022-5.6` | `MISS` | `1` | Actual phrase “轻相介质218–400℃” is in structured mechanism_detail.influencing_factors/applicability, while standard_clause_search indexes only title+content_raw. Original source content_raw has 177–242℃ and omits the light-phase phrase; 0 hits indicate indexed-field omission/stale data, not absence from source. |

`likelihood_method`的目标8.3.2标题是“技术模块因子”，与查询“失效概率定量分析方法”并非明显同义；扩词可能改善rank，但gold是否真相关仍要领域人审。`matrix_mapping`问25格却只标一个7-a，不能据此调参伪造精度。`inspection_strategy`应以“验证后扩大同一腐蚀回路检验范围/比例”作为区分短语，而不是检验周期泛词。`dm_56_light_phase`为空结果与文本只索引title/content_raw、条件在结构字段的机制相符。整改方案在`P16_B_CHANGE_PROPOSALS.jsonl`中，均是隔离建议。

## 5. 来源和状态口径

- P16-B变更建议：11条（6条DM来源/字段复核建议+5条检索应用层建议）；不自动变更教师Excel/正式JSONL。
- 211条源表格高风险行仍未逐格验证；20条定向OCR不是20条准确率；候选视觉扫查仍待人工签核。
- 656个G–N字段、656个O–V条件字段、56章目录/内容以及retrieval gold仍需真人/领域审查。补充PDF的75页定向OCR不是全文或章级验收。
- P15合成查询指标和P16本地候选策略是可复现工程回归，不是专家准确率。

## 复现

```powershell
python scripts/p16_b_fidelity_retrieval.py
python -B -m unittest tests.test_p16_b_fidelity_retrieval -v
```
