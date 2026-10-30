# Codex P16-A：42条真实变更逐条证据卡与人工核验工作台
根目录：D:\作业\竞赛\计算机设计智能体\机械智能体
依次完整阅读AGENTS.md、docs/data_quality/OWNER_P15_ABC_INDEPENDENT_REVIEW_20261029.md、docs/data_quality/P16_CLOSEOUT_MASTERPLAN_20261029.md，以及教师原版填写指南/convert/validate。只读 upstream/**、原P15 A/B/C候选与正式JSONL。不可改后台/前端/正式数据库/老师工具，不提交、不部署、不删除，不伪造真人签名。你有独立写入域；三个Codex窗口并行但绝不能同时写相同文件。任务完成要提供可复现命令、实际进度与失败、证据级别，真实人工签署缺失时不得声称发布完成。

**文件唯一写入权**：work/data_staging/p16/A_CHANGED_42/**、docs/data_quality/P16_A_*.md/csv、scripts/p16_a_*.py、tests/test_p16_a_*.py。不得修改其他P16的B/C区或P15候选。
你的目的不是再补大量条款，而是让真实审核者在一张卡里直接判对错。来自P15-C的42条修改过的clause_id、A/B的73个Excel cell变更、P15原标准PDF（私有只读）。
1. 独立交叉核对P15_C_CANDIDATE_JSONL_DIFF.csv的42个ID，联结A64/B9变更，**确保每条记录的多个变更字段一张卡全部展示**。生成42个本地HTML可打印核验卡、汇总首页与42行CSV审签表；卡中旧值→新值→修改动机→可信度→原始PDF真值页，必须同时展示印刷页码、0-based PDF物理页、对应图/表行列与局部截图；无定位不得假造bbox，标BLOCKED_SOURCE_LOCATION。图像不外传。
2. 最先处理10个26610.5表2/3数值行、4个TSG适用范围、30579 5.6/5.23/6.7、25个26610.3风险格。特别检查5.6 F中原本同时有5.6.1/5.6.2，候选删去5.6.2但损伤形态H仍在；不要单纯把F变短当成功。对每个修改给源PDF视觉支持的精确结论：MATCH / CONTRADICTS / AMBIGUOUS / PAGE_UNREADABLE / PENDING_HUMAN。机器结论不得写成人审PASS。
3. 数值/单位/指数/开闭区间/脚注逐格比较。PDF真实位置如果不支持机器结论，就把候选状态设REVIEW_NEEDED并记录无法判定的原因；不得覆盖任何候选源表。所有数字截图保留足够邻近表头、单位和脚注，不能只截数值。
4. 生成 P16_A_REVIEW42.csv，真实审核人签署与日期字段全部留空，支持独立审核人在每卡填写pass/fail、是否支持条款适用、纠错意见。若机器找到显著错误，放入P16_A_PROPOSED_CORRECTIONS.jsonl供C合并审核，不要直接改P15 A/B。
5. 写docs/data_quality/P16_A_CHANGED_RECORDS_REVIEW.md，包括42/42是否有页索引、能否看到表头与数值、已有实质错误例证、仍需人工裁决数目。至少跑针对所有42条的自动验证，不用截图数量冒充准确率。

停在MACHINE_REVIEW_PACK_READY或REVIEW_BLOCKED，不得写HUMAN_VERIFIED。