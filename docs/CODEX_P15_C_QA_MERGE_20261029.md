# Codex 窗口 C｜P15 独立数据QA、两份Excel集成、老师终验和检索质量（并行窗口三）

工作根：`D:\作业\竞赛\计算机设计智能体\机械智能体`。先读`AGENTS.md`、`docs/data_quality/P15_FIELD_CLOSURE_MASTERPLAN_20261029.md`、`docs/data_quality/P15_OWNER_FIELD_AUDIT_20261029.md`、老师填表指南、`convert.py`、`validate.py`和P14候选质量审计。
A/B与本窗口同时工作。**先独立做QA工具和原554条基线审计；A/B输出出现后再执行唯一合并。不要修改或抢A/B文件、不要轮询后台挂起，不要要求用户重新提供路径。**

## 目标
只有“数据内容真实可靠、字段语义匹配、官方转换无破坏且能改善检索”的候选才能交Owner。C是机器独立核验者，不是人类签名审核员。重点检查A/B是否真的产生有来源的修复，而不是又复制554行。

## 第一阶段：现在可立刻并行执行
1. 基于`scripts/owner_p15_field_coverage_readonly.py`/teacher模板制作独立`P15_C_FIELD_POLICY.py`规则（可在`scripts/p15_c_*.py`实现），对23/25列标`required/conditionally-supported/not-applicable/source-unspecified/review-needed`，不要把空值率当准确率。抽查并记录5.23、5.6、6.7、.4/.5数值、26610.3矩阵、TSG条件周期/材料耐蚀性等危险案例。
2. 构建不依赖AI信任声明的可执行数据门禁：每项source locator存在、PDF页合法、标准年份/条款/标题、F<=300、禁止将AI转述伪装F逐字原文、数字单位与边界（明确变量类型）核对、枚举转换、风险矩阵正确、两表4sheet与23/25列完全未改、主键唯一、旧554任何删行/变更必须显式列。source定位字符串非空不等于视觉原文核验；可疑内容进入review queue。
3. 从原正式554条冻结50条随机人工交叉核查样本（固定seed和抽样脚本），生成易操作`P15_C_HUMAN_REVIEW50.csv`：含clause_id、抽取人、待核PDF位置、原文/条件、核对人、通过与原因待填，**不代填结果/不签署身份**。老师验收>=48/50，正式抽样应从最终冻结候选重新进行，原样本仅pilot。
4. 建立检索验收至少40道题（正/反/缺字段/温区/分压/跨标准），重点`GB/T26610.5 表2面积后果`旧E0漏召回、5.23其他温度条件、RBI区间与风险等级错配；冻结label与来源，未获专家验证的label标synthetic，测试使用老师现有三个工具，**不改老师工具**。
5. 对未来合并准备纯staging merge与原`upstream/04_接口文档/convert.py --inputs ... --output ...`、`validate.py --final --clauses ...`的隔离校验命令/测试，不需要重写convert、不用生成新schema。

## 第二阶段：只在A/B候选已存在时执行唯一合并
1. 读取A的`A_RBI/条款摘录表_RBI_P15_A_candidate.xlsx`与B的`B_DM/条款摘录表_损伤机理_P15_B_candidate.xlsx`，按各自change log检出**无出处更改/字段误分类/新增无签名**，不合格变更打回各自人工审核队列，不直接修A/B原件。
2. `work/data_staging/p15/merged/`生成两份融合候选。未签的新13条不能通过teacher convert，分成`preview_full_unreleased`（包含draft）与`convert_eligible`（只包含符合真实抽取人字段要求的正式记录），**不能发明姓名填入U/V**；需要真人验核的记录可单列staging而不进入convert_eligible。
3. 使用老师原convert输出`merged/clauses_candidate.jsonl`，与正式554按clause_id输出`added/modified/unchanged/removed`计数及具体差异；任何未授权删除禁发布。运行teacher validate--final、17工具自测、合同哈希/返回结构一致性，以及上述synthetic检索回归。可能需要在隔离工具环境临时指定候选文件，绝不写正式upstream数据。
4. 每个改变都以
`pdf_file+printed_page+pdf_index+bbox/cell+evidence_quote+review_status`
可复核。OCR/视觉AI可标AI_VISUAL_CHECKED但不冒充HUMAN_VERIFIED。高危数值/矩阵/条件变化必须进入独立人工队列，不能因validator PASS释放。
5. 输出`docs/data_quality/P15_C_INTEGRATION_ACCEPTANCE.md`与`work/data_staging/p15/merged/DIFF_LEDGER.csv`、`P15_C_HUMAN_REVIEW50.csv`及测试日志，准确报告有多少缺口真正解决、多少尚不可验证。若A/B当前尚未生成候选，则完成阶段1+待集成脚本并标`MERGE_PENDING_INPUT`，不得宣称已合并，也不要守护后台等待。
6. 不必重新启动/修改P13、frontend、backend；不部署、不覆盖原表/正式JSONL。待Owner决定正式签署后再安排最终唯一发布者。

## 独占路径
`work/data_staging/p15/C_QA/**`、`work/data_staging/p15/merged/**`、`docs/data_quality/P15_C_*.md/csv`、`scripts/p15_c_*.py`、`tests/test_p15_c_*.py`；全部其他目录只读，包括A/B。不得回滚/清空/全局Git修改/移动老师源文件。
收工条件为机器可核的门禁PASS且人工待核清单完整，实际变更和仍阻塞要明示。Teacher引用95%与真实模型100题解析不可由本次模拟或AI代签。