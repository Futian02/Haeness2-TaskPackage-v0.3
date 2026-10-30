# 澄衡 Aetheris｜P16 最终定向修补（三窗口续任务，不新开P17）
2026-10-29。依据 `docs/data_quality/OWNER_P16_LIVE_HANDOFF_AUDIT_20261029.md`。全部任务只在各自唯一写入域完成。先`git status`并保留未提交变更；不执行 reset/clean/add/commit，不碰父仓、upstream、P15源候选、正式SQLite、秘钥与在线服务，不主动部署、不产生真人签名。按最新磁盘状态而非历史报告执行。

## 任务A续修｜高危源图证据与TSG定位
仅写 A 专属 `work/data_staging/p16/A_CHANGED_42/**`、`docs/data_quality/P16_A_*.md/csv`、`scripts/p16_a_*.py`、`tests/test_p16_a_*.py`。不要覆盖C人审CSV。
1. 只读确认TSG 21 §8.3.12 PDF index78、83和印刷页79，修A候选审核卡/locator提案中的错误页码链。保留旧错索引和纠正理由，不修改P15原台账、上游PDF/Excel。
2. 针对 GB/T30579 §5.6 以PDF index14/15原图逐项给可复核图窗：材料`3Cr-0.5Mo`/ `5Cr-0.5Mo`；`轻相`/`烃相`；`注氨点`/`注氢点`；焦化轻/重蜡油回路、F与H对§5.6.1/§5.6.2覆盖。每个疑点列Excel字母栏、旧/新、原PDF印刷页、0-based index、局部图/表格上下文、逐字短引用、OCR/视觉可信级、待人审。
3. §5.23核49–66℃的局部NH4HS析出范围及材料耐蚀vs易感；§6.7核H₂S气相分压0.0003 MPa与总压、溶液浓度、不同子型温度与HB200对象。不能把数字出现当通用阈值。
4. 保留42条/73格完整关联和现有审核样本；新图像只作AI_VISUAL_CANDIDATE，真人栏不可修改，不写发布数据。若真正视觉不能清晰判定标AMBIGUOUS。
验收：以完整源图和可核对格坐标证明定位或留不确定；针对上面每个问题有具体结论；A 5专项及独立计数重跑；报告保留所有未决。

## 任务B续修｜检索评估去泄露与候选专业疑点
仅写 B 专属路径，禁止修改C/A或正式工具。
1. `scripts/p16_b_fidelity_retrieval.py` 的 `expand_case(cid,q)`目前按照五个已知case_id硬编码扩词：这是eval label leakage。重构为仅依赖用户自然查询q、事先冻结词典、真实索引字段的 query expansion；同一q换任意case_id，top-k及query-plan必须逐字一致，编写红→绿测试；删掉测试ID先验并保留旧in-sample 42/42为历史对比，不虚报为新结果。
2. 扩词词典不能从本次gold条款ID反推答案。用独立≥30个未见过的blind查询，覆盖矩阵25格家族问题、材料牌号、H₂S分压vs总压、轻相/烃相、注氨/注氢负例、TSG与检验周期混淆、OOD。金标来源状态明确分机器/专家，未人工核准只报合成代理指标（Recall@20/MRR@20/NDCG/误召回/延迟），不报专业准确率。
3. 原五未命中逐项分析：`likelihood_method`和`matrix_mapping`gold存在不可靠定位，保留待领域裁决，不调gold让指标全绿。可以用同义词、结构字段索引、RRF，但基线与候选相同输入及评测口径，展示全量误报/负例。
4. P16-B现有6条来源语义建议只增加可核证局部图/引文或标PENDING，不合并老师Excel。
验收：改case_id不改结果；盲测正反例和时延完整；B专项PASS，报告明确改造前后指标、可信限制和真实服务尚未集成。

## 任务C续修｜P0人工审签门禁不可用与审核数据覆写
仅写C专属路径；**此任务优先级最高**。严禁改A/B、正式数据、教师工具、真实SQLite。
1. 先验证并修复 `scripts/p16_c_machine_gate.py`：`human_signatures_not_fabricated`目前以真实签名全空为PASS；`human_release_gate`只读冻结`manifest['human_signed']`、不计48/50和42/42；最终`human_review_signed`常量0。这些不允许以去掉门禁来“修绿”。分离`machine_did_not_autosign`（不可篡改证据）与`human_verified_review`（真实人工审阅流程）；对审签真实性的核实必须依靠Owner确认并留验证链，不能把字符串非空直接当真人。
2. `scripts/p16_c_prepare_human50.py`当前重跑会以open('w')清空`P16_C_HUMAN_REVIEW90.csv`中的签名和决策。设计稳定的不可变机器卡索引+单独审核人有权写的ledger/追加修订机制；存在任何真实审签时再运行必须非破坏性（保留原值、旧hash、冲突拒绝），不得让准备脚本清空或自行补全人审。
3. 新增离线fixture，仅测试用虚构姓名/签名**不得写正式审签表**：47/50、48/50、42缺一、42错录未复审、2交集一致/冲突、双人签署冲突、重复覆盖、源PDF错页/索引越界、先签后重跑仍保留、源SHA变化、没Owner授权等。机器通过、真人核签、Owner批准是三个不同门禁；即使fixture达到48/50+42/42也绝不自动覆盖upstream或发布。
4. 给源图index加入0≤index<PDF page_count及源hash绑定；不要将已渲染PNG存在作为人工逐字正确性的证明。机理字段冲突、TSG错误locator仍处于BLOCKED时不能放行。
5. 检查P16-A主venv缺fitz导致230项1 ERROR的问题；在测试依赖锁/隔离测试环境中最小修复，不得删减强制PDF测试或静默skip来称全套通过。执行教师正式和候选各554/200、候选工具17/17、P16专项和全量回归并完整写日志。
6. 任何正式数据和真实审核人填署一律保持冻结；最终报告必须展示READY_FOR_REAL_HUMAN_REVIEW或BLOCKED，绝不能把机器自测或fixture当真人完成。
验收：非破坏性人审ledger、签署流程在没有授权时不能自称通过、所有负例确实阻断、全量环境无错误、正式数据SHA不变。
