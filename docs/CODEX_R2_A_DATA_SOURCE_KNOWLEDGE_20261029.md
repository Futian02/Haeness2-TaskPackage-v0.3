# Codex R2-A｜从原始数据到专业知识检索的封口
【统一约束】在本机Codex工作目录 D:\作业\竞赛\计算机设计智能体\机械智能体 直接使用本机终端和文件系统。勿使用DevSpace/远程连接器。先读 AGENTS.md、docs/PROJECT_STATUS_CURRENT.md、docs/R2_FULLSTACK_PARALLEL_CLOSEOUT_MASTER_20261029.md 和当前本Lane文件。此项目是父级大型Git工作树内的未跟踪项目，禁止git clean/reset、自动提交、清理upstream中的既有脏文件。不要修改教师upstream/PDF/Excel/JSONL、人工审批、真实SQLite、生产模型密钥。不要重启8000/8001在线服务。每个测试使用隔离临时DB，不能用真实付费LLM做无上限负载。严格遵守MASTER独占路径；发现别人同时修改同文件，停止写该文件，记录冲突，使用接口报告对接；不能为绿测删除/放宽旧测试。交付真实命令、PASS/FAIL、输入-输出对照、Git/源码hash和未完成风险。

**独占可写**：knowledge/applicability/candidates/**、knowledge/retrieval/**、scripts/r2_data_*.py、docs/data_quality/R2_*.md、docs/audits/R2_A_*.md。不得写backend、orchestration、frontend、upstream。当前S3-A/B schema属其他窗口成果，请先只读读取，若需修改schema给出字段契约建议，不抢写。

任务顺序：
1. 只读盘点正式554条（472 RBI/82 DM）与冻结PDF/Excel/JSONL，输出每条条款来源编号、卷/版本、印刷页、物理PDF页、source SHA、证据等级、校验失败原因；不要将自动摘录当真人审定。保留旧jsonl SHA。人工未签0/50、新数据批准0条标UNKNOWN。
2. 对用户任务类别建立知识覆盖矩阵：概念、机理、设备诊断、局部缺陷、壳体碰撞、检验、修理、验收、停机/复机、RBI。每类对照真实可检索源和缺失范围；不是含有“验收”词即有权给限值。
3. 针对A=300系列不锈钢+碱式酸性水+60/80℃；B=壳体磕碰损伤/维修验收；C=碳钢+95℃HCl非烟气侧；D=湿H2S分压vs系统压力；E=酸雾/烟气侧；构建源摘要和专业词汇映射/多个query候选，标“与问题相关”和“适用工况被证实”为不同字段。B的辐照脆化假召回必须显式标NEGATIVE且留下证据。
4. 衍生只读索引：基于正式来源结构分chunk，包含chapter/condition scope/subject/pressure or wall temp target/role/polarity/context/printed_page+source hash；不直接生成第四教师工具，也不复制整篇受版权限制的标准文本。令入口仅返回候选，与原教师三个工具并存。
5. 5.23的49–66℃为局部NH4HS析出条件；5.6、6.7及烟气露点机制必须把范围、物性、角色及单位拆分，不要将局部温度/总压误当整机理必要条件；未核验一律UNKNOWN，绝不由“自动标注”做硬排除。
6. 制造数据质量报表，按来源缺失、字段不支持、未审条件、枚举外介质、子机理歧义、法定标准覆盖缺口分类。S3-A 134谓词/110可导入的contextual/24隔离/0approved需和最新磁盘逐条核对，必要时扩展候选但不得改变已冻结格式。
7. 专项证明至少50条冻结query old vs new检索的可用召回，来源真假、错误相关、False Exclusion人工未知分开统计；标独立人工gold仍0，不编造precision数字。
验收：source manifest Sha不变；A/B能检索出正确信息且不冒充设备验收法规；局部条件的60/80皆不发生“无证据整机理排除”；所有输出可复现。给C接口文档和G最终Gold审查队列。状态若人审缺失标CANDIDATE_ONLY。