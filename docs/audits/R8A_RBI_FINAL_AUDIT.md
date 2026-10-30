# R8-A RBI PDF → 原表审计

**状态：READY_FOR_OWNER_REVIEW；全页OCR索引已完成，但461页人工视觉/数值复核和真实双人签署仍未完成。新增13行仅DRAFT。**

## 原表与回滚

- 原件备份：`D:\作业\竞赛\计算机设计智能体\机械智能体\upstream\01_RBI标准\条款摘录表_RBI.xlsx.bak_owner_before_rbi1_20261028`；原SHA-256：`38cf71bf9f9868cfa531729cda70dea2e2857b3a788ec1a67f56d27ef01512f9`。
- 更新后原路径：`D:\作业\竞赛\计算机设计智能体\机械智能体\upstream\01_RBI标准\条款摘录表_RBI.xlsx`；SHA-256：`e43f7b0d3381a38fa648c2505e27d1c87893af5aea89aa119097dbfc49c6b7bf`。
- 新增行：474–486；RBI源表条款从472变485；U/V签名均空；13条G–S/K等无来源字段留空。
- 23列、4工作表；`摘录表`既有A1:W473逐格值/类型/style_id一致；另3表值/公式/style/尺寸/合并/验证一致。
- OOXML ZIP仅`xl/worksheets/sheet2.xml`变化；其余所有包成员字节相同；无格式重绘。

## 六份PDF页面覆盖索引

- 页级索引：461页；对应章节/既有条款映射CSV：498行。OCR覆盖数：461；页面状态：{'needs_visual_review': 449, 'needs_human_review': 12}。
- OCR用于定位章节/表/公式，不能证明原文、印刷页、数值、单位、适用条件准确。逐页图像级复核仍需人工；目录/表格/公式和乱码页全部留待审核，不标“核验通过”。
- 20项固定随机种子数值/表格/公式抽查清单位于`R8A_RBI_NUMERIC_FORMULA_RECHECK.csv`，全部`needs_human_visual_review`，没有伪称数值通过。

## 当前转换和官方数据状态

- 真实抽取人与独立复核人缺失；老师`convert.py`按必填U字段门禁预期BLOCKED，不能合法将候选纳入JSONL。未改老师程序，未改正式`clauses.jsonl`。
- `validate.py --final`核验的是未变更的既有正式JSONL，不是新草稿。
- 13条映射及逐格变化见`R8A_RBI_PDF_COVERAGE_LEDGER.csv`、`R8A_RBI_CELL_DELTA.csv`；PDF哈希/页面数量见`R8A_RBI_PAGE_INVENTORY.csv`。

## 数值、风险与周期门禁

- 26610.1的13条均只摘方法性原文，G/H/I/J/K及无依据条件字段留空；不从标准方法描述推导设备风险。
- 已有25格风险矩阵数据未修改；未从OCR/示例量扩展风险或周期。TSG21安全状况1–5级不映射到L1–L4。
- 表格/公式/周期数字抽查当前未获独立视觉复核，明确为待审核；不将OCR数字写入Excel。

## 失败/阻塞

- 初次`r8a_build_coverage.py`已完整OCR 461页并写出两份索引，但在打开非`.xlsx`后缀备份时openpyxl拒绝扩展名；脚本已修复为BytesIO读取。索引数据已实际生成；本轮没有为脚本改动重复跑九分钟OCR。
- 没有真人签名，因此正式转换BLOCKED；保留新增草稿，不伪造签核。无真人复核的461页也不能宣称已穷尽核证。
- 不执行`validate.py`通过来冒充草稿验收；只对原始官方JSONL作回归。

## 回滚

- 回滚前先Owner核对两份SHA；可由Owner批准后将备份恢复原路径：`D:\作业\竞赛\计算机设计智能体\机械智能体\upstream\01_RBI标准\条款摘录表_RBI.xlsx.bak_owner_before_rbi1_20261028`。本轮未提交/部署。
