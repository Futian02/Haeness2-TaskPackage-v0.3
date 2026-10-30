# P14｜老师验收导向的标准 PDF→Excel→JSONL 全量蒸馏方案
状态：OWNER_DESIGN / 数据写入仅在isolated staging，正式源文件冻结（2026-10-29）。
根目录：D:\作业\竞赛\计算机设计智能体\机械智能体

## 0. Owner 刚刚独立确认的现状（不要根据旧记忆改写）
- 12份PDF合计1385页。01_RBI标准6份PDF共461页（GB/T26610.1 34, .2 25, .3 14, .4 164, .5 53, TSG21 171），原摘录Excel有485条（原472+13未签核）。02_损伤机理参考6份PDF共924页（GB/T30579 163, GB/T150.1 51, 150.3 287, 150.4 67, GB/T151 339, GB/T21447 17），25列表格损伤机理Excel只有82条且全部来自GB/T30579；G-N八个内容列82/82非空，W抽取人82/82为姓名，X复核人82/82为空。5份补充标准0条直接进该表。
- 正式clauses.jsonl 554条=RBI472+损伤82；trajectories.jsonl200（multi144、single56、特殊三类各15）；guardrail_cases36、normal_cases60。老师validate.py --final此前通过格式/规模，不是内容正确证明。
- RBI已有210条“表X中”表格解释性转述的高风险候选，应优先核查F列是不是逐字原文；25格风险矩阵映射一致，但RBI K检验周期0，适用材质介质、温压结构化列几乎空。数字、单位、表格、页码和适用条件不能猜；风险矩阵不能用TSG安全状况等级替代RBI风险等级。
- GB/T30579中5/6/7/8/9章损伤模式数量分布：29/16/16/11/10。需要据标准的目录/附录对照判断82是否覆盖所有必抽模式，不可仅凭数字宣告全覆盖。
- 02里的GB/T150、151偏设计/制造/适用设备，GB/T21447偏外腐蚀控制。不要不加判断地变成“损伤机理”记录。可以产出辅助背景索引；只有确有损伤判据/适用条件/检测方法且符合教师contract时，才进DM或RBI表。补充标准需遵守老师白名单和convert.py标准码规则。
- 老师convert.py**确有 --inputs（多xlsx）--output（目标JSONL）**。必须用它在isolated staging转换，不另造字段/官方转换器，不直接覆盖upstream/05_提交区/clauses.jsonl。

## 1. 老师硬门槛（来源：upstream/README.md第八部分/04_接口文档/技术指标验证方法.md）
1) clauses>=300，DM和RBI双类；2) trajectories>=200、多步>=40、三特殊类型各>=15；
3) guardrail_cases四类各>=3全部挡住，normal_cases>=30全部放行；
4) teacher三个工具唯一且签名不变，Harness能>=5连续调用，日志100调用100%记录；
5) validate.py --final退出0；
6) **条款引用真实性：固定seed随机>=50条，人工交叉核对页码/条号、content_raw逐字、applicable_conditions不越界，准确率>=95%（抽50条须>=48条正确）**；
7) **真实Qwen等老师认可的模型执行100题，原生解析>=95%**。不能把RULE_DEMO/mocked/fallback成功算原生解析，若改为DeepSeek需要评审老师是否认可模型替换；
8) 模型解析/护栏报告包含BFCL或等价合法AST检查证据；
9) **ModelScope公开Studio页面和至少4类截图（单步/多步/护栏/越界）**。本机FastAPI fail-closed不等于ModelScope公开验收。
以上“数据核对”和“实际API测试”是两个不同硬门槛，互不替代。

## 2. 最简单可靠的四层数据组织
**L0 原始标准**：01+02两组PDF和两份原xlsx，全只读、绝不上传商业受版权保护PDF到公开模型；保存source文件名、印刷页码与PDF页索引（独立）、当前标准号年份、截图/区域坐标和图表序号。
**L1 页面结构化证据缓存**（新建`work/data_staging/p14/page_cache/`，项目忽略或不加入Git）：每PDF每页存原生text质量、段/表/图bbox、文字块、表格结构及必要时OCR与版面JSON；高风险按图像页可定位。使用PyMuPDF/pdfplumber文本先行；对乱码文本/扫描页/跨栏/公式表格优先PaddleOCR PP-StructureV3（版面、表格与公式），不是无条件OCR1385页。先20页pilot检查成本/质量再扩展。
**L2 精确候选记录**（`work/data_staging/p14/candidates/*.jsonl`）：`candidate_id, standard_code, clause_no, printed_page, pdf_page_index, source_bbox, raw_quote, quote_kind[text/table_cell/formula], table_id,row_id,col_id, target_sheet, target_field, normalized_conditions, evidence_level[unreviewed/machine_located/visual_checked/human_verified], extraction_method, uncertainty, reject_reason`。每一数值必须携带单位/上下限/开闭边界/来源表格坐标；不要把摘要或LLM推测写进F列。OCR改字必须人手对照标准图复核。
**L3 老师两份Excel候选副本**：`work/data_staging/p14/条款摘录表_RBI_candidate.xlsx`（23列）和`条款摘录表_损伤机理_candidate.xlsx`（25列），保留4个原sheet、表头、枚举/公式/列样式。F逐字原文<=300字，八段式G-N来自同一损伤模式的8个子条款；适用设备/材质/介质/温压未明示则空，绝不伪造。RBI风险映射只使用risk_level_mapping.xlsx；条件性检验周期要有对应来源且不得硬设所有行。
人类抽取人/复核人必须真实身份；机器/AI提取仅写备注与机器验收阶段；没有真实签名就仅作为staging，**绝不冒充正式发布**。

## 3. 分阶段规模化任务（先难点，再全目录覆盖）
P14-0只读诊断：PDF/page目录/条款覆盖matrix；Excel每列非空与异常值、同比正式JSONL diff；核实GB/T30579目录82条覆盖。生成`docs/data_quality/P14_SOURCE_COVERAGE_MATRIX.csv`每份PDF各章节状态及排除理由。
P14-1 20页pilot：至少8页30579损伤八段（不同章）、8页26610.2/.4/.5风险表格与限值、4页TSG/补充标准；双路抽取（原生text、必要时OCR+图表版面），每候选必须回到PDF原图校核。通过后才能批量扩展。
P14-2 DM主线：对所有**有明确损伤模式**的30579章/附录核查，82条旧记录不重造；优先修G-N关联不准确、同一模式跨页、源页和F是否逐字，补缺模式/有真实可证的定量适用条件；其余5份补充PDF逐章节扫描标注“支持材料/设备约束/不适合DM、不入官方表”的原因，而不是强行填DM全部25列。
P14-3 RBI主线：先高风险210表格转述逐条视觉核，26610.3图1 25格/26610.4频率及各表/26610.5面积后果数值/26610.2检验策略/TSG周期/26610.1待审13条。图表拆行保留-a/-b；当原文表格单元格不是自然句子，用F放原文字/单元格完整可核摘录，W放结构解释；格式难题记review_needed而不混造原文。
P14-4 隔离转换：`python upstream/04_接口文档/convert.py --inputs <经过复制的原RBI稳定基线.xlsx> <DM候选.xlsx> --output work/data_staging/p14/clauses_candidate.jsonl`。如果正式原RBI485中有U缺失13条，先用备份的合法472 baseline单独测试，**不可替13条假签U/V**；已核签的13条方可按真实签名进正式候选。再在隔离子目录中复制official validate所需文件，validate candidate，不动正式05_提交区文件；输出diff并测三工具兼容性；绝不手写official JSONL。
P14-5 人工复核：按老师规则固定随机seed从**准备提交的候选Clauses**抽>=50条，自动生成可点击来源定位与逐字对照页的复核表；A提取不能A自己核。人类B/C审核签实际姓名、记录具体字段差错。50条>=48通过才达95%，错3条必须修再新抽；校验器不会自动替代审核人。
P14-6 交付准备：只有审完、teacher convert/validate、准确率样本、冻结金标检索题/工具依据回归全PASS，且Owner另行批准发布，才可替换正式两份Excel/JSONL并更新索引。按老师官方第八部分核9项，未交ModelScope或真100题解析则仍BLOCKED。

## 4. 自动QA门禁与性能
- 必须通过：条款ID唯一、页码可定位、F逐字对照的机器定位+人工风险页审查、八段式字段合法、完整枚举、空值合法、表格数字和单位100%逐格复核高风险表、风险映射25格100%、所有候选basis指向该版clauses、原三工具17个基线+教师validate--final；实际效能测检索对比10~30条由人标过的题，有1个正确答案不能证明Recall@k达到95%。
- 批处理每批<=10-30页/10-30条，保存审计进度，任何异常自动停止候选发布而不是无限重跑；可以失败记录和人工待核队列，不能把未核的写verified。
- 性能指标建议：页抽取耗时P50/P95、OCR失败页数、混淆矩阵（字段命中/误填）、公式表格错误率、导出准确率、耗时与增量回放。客观指标不达要求则状态BLOCKED，不虚报“全部完成”。
- **多智能体并行边界**：来源盘和原xlsx只读；并行按标准/文件包不按字段：DM30579、RBI表格、补充标准分3子分支；一个集成者合并候选，另一个独立对照PDF审查。不要同时对同一xlsx写入；标准PDF原始渲染非OSS不能对外发布。

## 5. 参考成熟工具
- [PaddleOCR PP-StructureV3](https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/pipeline_usage/PP-StructureV3.md)：PDF版面/表格/公式，结构化MD/JSON，针对乱码页。
- PyMuPDF、pdfplumber：文本层、bbox和PDF页码定位；仍须图像核数值/表格。
- 老师`convert.py`：唯一最终转换；`validate.py --final`：合同检查；`harness_skeleton/run_guardrail_tests.py`：官方护栏验收。不要替换成熟工具造重复OCR或Schema体系。
- 若需提交PDF标准大段原文，请先确认引用授权；尽量只保存有权限的受控本地证据，不公开传播标准全文。

## 6. 任务范围
P14窗口可写`work/data_staging/p14/**`、`docs/data_quality/P14_*.md/csv`、`scripts/p14_*.py`、`tests/test_p14_*.py`；**不可写**`upstream/**`、`frontend/**`、`backend/**`、`orchestration/**`、`knowledge/**`正式索引、其他Codex窗口文件。仅生成候选及审计，Owner正式批准后另设唯一集成任务覆盖正式资料。
