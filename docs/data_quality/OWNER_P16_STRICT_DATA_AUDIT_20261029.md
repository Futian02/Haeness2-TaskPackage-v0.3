# Owner P16 严格数据审计｜2026-10-29

**判定：P16 A/B/C 证据工程交付可接收；正式数据内容 NO-GO；检索实验仅 in-sample/PROPOSAL_ONLY；统一测试环境 NOT_GREEN。**
本轮DevSpace独立只读源 XLSX/JSONL/PDF文本层、A/B/C CSV、模型和检索代码、门禁日志，并独立运行 P16 B/C 10项、A pytest5项、教师正式及预览 validate、候选工具selftest17项。除本审计文档外，不改PDF/Excel/正式JSONL/模型、密钥、数据或在线服务。

## 1. 有证据的实际进展
- P16-A：42条/73个单元格变更全部可导航到42张审核卡；19张PDF物理原页图；机器审计28 MATCH、13 AMBIGUOUS、1 CONTRADICTS。真人42/42 pending。
- P16-B：221条解释性表格风险中，扣除P15的10条数值候选，剩余211；其中20条只做到定向页面OCR/行名候选，不具备单元格BBox+独立签核；191条仅源物理页定位，逐格真值未核。DM82×(8段+8条件)=1312个字段仍逐格待核；五补充标准56个待审章节中52判为暂定设备设计制造辅助、4外腐蚀控制辅助，标题/范围并未完整人核。新增6个内容修正建议+5个检索建议，仅stage，不属于已发布正确数据。
- P16-C：从既有seed20261029的随机50和修改42合并，交集2、共90唯一复核对象；随机50/50、定向42/42真实签名均为0。机器 gate 8 PASS、两关键门 BLOCKED。新预览Excel/JSONL与P15候选相同：554条、modified42、JSON字段变动44、added0、removed0。正式3份源文件SHA与冻结一致。
- 教师独立重测：正式clauses554/554与200轨迹PASS；P16 preview clauses554/554与200轨迹PASS；候选工具17/17 PASS；P16B/C unittest10/10、P16A系统Python pytest5/5通过。

## 2. 高风险问题分级
**P0-A 数据内容实际可能错误（下游会直接误导RAG/工具）**
- `GBT30579-2022-5.6` P16预览JSONL 的 `mechanism_detail.affected_materials` **确实含3Cr-0.5Mo**；P16-B原图机器核对建议源表可能应是`5Cr-0.5Mo`。注意候选其他自由文本含5Cr不足以证明字段I正确。
- 同ID的`mechanism_detail.influencing_factors`含**轻相酸值/轻相介质**，B指向原PDF可能为`烃相`；`susceptible_locations`含**注氨点之前**，B指向应为`注氢点之前`；原图需二人逐字判定，当前不允许用这些值作高可信工程判断。
- 同ID还有焦化轻/重蜡油位置候选漏列，以及F由5.6.1+5.6.2缩为仅5.6.1但H仍含形态。需按字段职责核实是否损失原文忠实性。
- `GBT30579-2022-5.23` 49–66℃是NH4HS局部气相析出情境，已从通用温区过滤移出（候选修正），但受影响/耐蚀材料名录与相对耐蚀程度仍需核。`GBT30579-2022-6.7` H2S气相分压0.0003MPa、溶液浓度、HIC/SSC不同温区与HB200对象边界需按子型分别验证。
**P0-B 可追溯性硬错误**
- P16-A指出TSG21 §8.3.12 P15来源台账index=78不对应印刷页79/条款标题；来源机读/原图指向index=83。错误在`source_locator`，不代表§8.3.12修改内容必错；P16-C明确BLOCKED而未静默覆盖。必须由独立审核者用原PDF index78与83确认后修正全部对应来源台账、卡片与引用。
**P0-C 所有人工签署仍缺失**
- random50中要求≥48真实正确才满足老师≥95%（50题离散门槛）。另42条变化必须42/42定向得到明确人工裁决/修正后复审；两个集合重复2条可共用真正审核证据，但不能仅抽50替代42。尚无人审故“准确率未知”，不是0%或100%。
**P1-A 源文真实性量级**
- 剩余211条表格F的原文连续性、单元格数值/上下限/单位/脚注未逐格完成；20 OCR只做导航。DM的1312条结构字段更不能靠自称656子条编号定位宣告正确。五份补充标准多数属辅助规范，不能凑数填DM。
- 30579 PDF原生get_text几乎乱码（本轮以PDF index14/15抽样，关键中文词均-1，片段为混乱编码）；自动Unicode文本匹配不可用于证明无错，需原图或独立精准OCR+真人核。
**P1-B 检索报告in-sample过拟合**
- B源码`scripts/p16_b_fidelity_retrieval.py::expand_case(cid,q)`对5个已知case_id明确硬编码专用扩词，实际浏览器用户不会有该case_id。实测同一query换新case_id只剩原文，没有追加“5E矩阵”等术语。因此46合成题37/42→42/42、Recall@20 1.000是带有测试ID先验的离线原型成绩，**不能声称实际泛化或部署生效**。另部分gold不充分或可能不相关（宽“风险矩阵图1”用单个7-a作为gold；likelihood_method到技术模块因子8.3.2），应交专家重做holdout评测。必须改为仅对query可见token和领域词典做扩展、冻结≥30全新blind题，防正例过拟合，统计NDCG/MRR/Recall和负例误召回。
**P1-C 统一测试环境未绿**
- 主`.venv-langgraph`无`fitz`和`pytest`。P16-C保存完整unittest discovery日志显示 `Ran 230 tests, FAILED(errors=1,skipped=3)`：`tests/test_p16_a_evidence42.py`顶层`import fitz`引发ModuleNotFoundError。A在系统Python单独pytest5项PASS、B/C在主venv10项PASS；**这叫多环境专项通过，不是统一全量0-error**。需锁定测试依赖/隔离PDF test extras或者将缺失依赖测试通过受控skip并在具备依赖的CI强制运行，不能把失败日志删掉。避免为QA环境升级全部生产依赖。

## 3. 与后续Agent能力的关联
- 现今产品运行的是正式旧JSONL，不是P16预览。正式旧数据未更新；即使P16预览改善5.23、5.6两个误过滤，UI还没继承。用户不能看到B提出的内容修正或检索RRF效果。
- 教师官方三工具与风险矩阵有效；但当材料牌号、流体术语、注入点或不同温压/分压边界被错误写入结构字段，模型看似“有标准来源”也可能提供错误候选。证据必须至少区分`record_exists/source_located/visual_machine_checked/human_content_verified/applicability_verified`。不要把AI_VISUAL映射成专业E2/E3。
- 检索算法要先验证source支持断言：出现某材料不等于它易腐蚀，出现某温度不等于整个机理过滤阈值。证据不足时可以列“待查候选/鉴别条件”，不可确定风险等级/检验周期。
- 由于老师原JSONL Schema冻结，如果要部署仅批准过的内容，可建立附属只读`clause_verification_manifest.jsonl`以ID、源哈希、审查级别、签署来源、适用性审核分类进行sidecar gating，不新增第四个老师工具/改teacher schema。对未审内容限制为探索性来源，不出确定诊断。

## 4. 推荐当前动作（不启动P17）
**紧急整改队列：** (1) PDF原图核TSG index78/83；(2) 30579 5.6材料3Cr/5Cr、轻相/烃相、注氨/注氢、焦化蜡油回路与5.6.2 F/H；(3) 5.23与6.7子型温压/分压/耐蚀性；(4) 26610.5表2/3十行、26610.3图1 25格风险；(5) 第一批20条26610.4失效频率表OCR行列+FG合计及其余211队列。
先在人审卡对这些高风险项核判，再完成42定向和50抽样，领域专家签署必要条件；若无人复核，不能发正式数据。
**工程修补：** 修source locator和离线检索评估按case_id扩词的实验偏差；统一测试依赖环境。只做这些有界修补，不重新OCR1385页。
**放行：** 50随机≥48经真实交叉核验且42修改各有签核；所有已发现P0语义/页码错误修复；teacher convert→validate→17tool + 真实查询负例回归，文件哈希/差分完整；Owner书面批准后**唯一发布执行者**覆盖正式Excel/JSONL并更新索引。老师100真实LLM解析和ModelScope发布是另外两条独立Gate。

## 5. 复现与范围
- P16 B/C专项`unittest tests.test_p16_b_fidelity_retrieval tests.test_p16_c_human50_gate -v`：10/10 PASS。
- A证据卡`python -B -m pytest tests/test_p16_a_evidence42.py -q`：5/5 PASS（系统Python）。
- teacher`validate.py --final`正式和候选分别554/554及200/200 PASS；候选probe `_selftest_tools.py`：17/17 PASS。
- 源哈希正式RBI`e43f7b0d3381a38fa648c2505e27d1c87893af5aea89aa119097dbfc49c6b7bf`、DM`8bb05d1d0dacbe542a1713a317a769f064a9c6c7ad34053417f0dbba01a0d62e`、JSONL`a8151797ba15a6a7452dd83aaec9fab4c0a815724ca45062eb1e2bac7b4d49ef`；P16预览JSONL`7efebc07786fd6232da05d21c43323486f3b15d1ff4edd731075755fe419d196`。
- 本轮没有真实专业审核人核PDF，原文乱码不能靠文本比对替代。没有真实LLM、外部搜索或在线服务压力测试。
