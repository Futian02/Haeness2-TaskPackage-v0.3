# Haeness2 机械设备风险研判 Agent｜项目协作规约

> 作用域：`D:\作业\竞赛\计算机设计智能体\机械智能体`（本文件所在目录及自有产品扩展层）。
> 原始任务包 `upstream/` 独立 Git 仓库；不得误操作父仓库、其他竞赛项目。
> 2026-10-27 初始化；必须结合 `docs/PROJECT_STATE.md` 与实际磁盘命令更新状态。
> 核心目标：**把项目当企业级多智能体工程实习来做，以技术成长为核心**。老师的单智能体+3工具是必须兼容的交付层，我们的多智能体产品平台、工程语义和网站是独立的学习建设层。每一轮都要求原理讲解、代码、实验与可核证证据。

## 0. 开始前的固定阅读顺序

1. 本文件 `AGENTS.md`
2. `docs/PROJECT_STATUS_CURRENT.md`（当前状态首读；`docs/PROJECT_STATE.md`是2026-10-27历史档案，不得覆盖最新实测）
3. `docs/MASTERPLAN_V1_TEACHER_FIRST_20261027.md`、`docs/TEACHER_REQUIREMENTS_AND_GAPS_20261027.md`（本项目总设计、任务门槛和学习分工）
4. `docs/TEACHER_QA_CONSTRAINTS.md`、`docs/DOCS_INDEX.md` 和 `upstream/README.md`（`docs/CONTRACT_LOCK.md`目前不存在，不应把旧引用当合同原件）
5. `upstream/04_接口文档/工具接口规范.md`、`upstream/04_接口文档/技术指标验证方法.md`
6. 若涉及标准数据，另读 `upstream/资料获取与摘录表填写指南.md`、`docs/DATA_LINEAGE.md`、`docs/data_quality/TEACHER_SAMPLE50_EVIDENCE_STATUS_20261029.md`、`docs/data_quality/DM_APPLICABILITY_ROOT_CAUSE_AND_REFORM_20261029.md`
7. 若涉及 Agent/RAG/前端，依次读 `docs/ADR_002_ENTERPRISE_MULTIAGENT_PLATFORM_20261027.md`、`docs/ENGINEERING_SEMANTICS_KNOWLEDGE_SPEC_20261027.md`、`docs/PRODUCT_UI_DATABASE_DEPLOYMENT_V1_20261027.md`、`docs/LEARNING_PLAN.md`，Codex首轮任务见 `docs/CODEX_LUNA_HIGH_P1_MULTIAGENT_VERTICAL_SLICE_20261027.md`。

如文档与实际代码/日志冲突：以**冻结教师合同 + 当前磁盘与实测**为准，并更新状态，不允许猜测为 PASS。

## 1. 官方合同冻结区

`upstream/` 是老师任务包的历史上游副本，不是废弃资料，不执行跨项目重排。默认只读：
- 根部 README.md、任务包问题答复.docx、资料获取与摘录表填写指南.md。
- 01_RBI标准/、02_损伤机理参考/ 下标准 PDF 与摘录 XLSX；03_案例样例/。
- 04_接口文档/ 的 convert.py、validate.py、schema/*、enums.json、material_family.json、risk_level_mapping.xlsx、工具接口规范.md。
- 05_提交区/ 的 clauses.jsonl、trajectories.jsonl、三个工具相关代码与证据报告。

只允许三个**老师可调用工具**，名字与参数**字节级保持**：
`damage_mechanism_query`、`rbi_lookup`、`standard_clause_search`。
不添加第四个老师工具，不改变统一五键返回外壳 `status/in_domain/result/source/message`，八段式字段、Schema、参数必填性和类型不变。
原文 `content_raw` 不改写；枚举只用定稿表；未知现场因子不虚构风险等级、检验周期或源条款。
确需修复上游缺陷：单独上游分支、先失败测试→定向小改→全部原验收回归→PR；不得直接在 master 上盲改，老师源表优先冻结不动。
未经明确授权不删除、覆盖、清理、搬动标准 PDF/XLSX、案例、备份、参考源码、 Git 元数据或个人资料。

## 2. 自有工作分层

- `app/`：Gradio及原 Harness 适配；UI 与官方数据格式隔离。
- `knowledge/`：检索评测用的实验性索引和后续 hybrid/RAG；**绝不是新老师工具**。
- `evals/`：冻结真值题、失效案例、独立运行脚本与比较报告。
- `tests/`：单元/契约/端到端/重放；不修改上游数据。
- `docs/`：合同映射、数据血缘、架构、研究路线、学习日志、实验记录。
- `scripts/`：重复性运维脚本；要标明只读和写入边界。
- `upstream/`：上游原版任务包；克隆/更新由其自身独立 Git 负责。

不得把原始 PDF 切片输出、临时渲染图、测试日志、API token、虚拟环境提交至自有代码仓库。

## 3. 每次修改必须完成的步骤

1. 先写最小目标：用户价值、合同约束、验证方式、失败撤销方式。
2. 复用现有成熟代码，解释选型与性能/复杂度权衡；只手搓最有教学价值的 Harness 核心机制，避免自己造 SDK、向量 DB、PDF parser。
3. 划清基线：rule、LLM、LLM+fallback、multi-agent 的调用及成本分别统计。
4. 修改前拍 Git 状态快照，保护用户其他项目；只在选定作用域写入。
5. 跑 `python -B -m unittest discover -s tests -v`；若改上游则再跑 `validate.py --final`、官方护栏、自测、两份 harness 一致性。PASS 需要真实运行输出。
6. 更新 `docs/PROJECT_STATUS_CURRENT.md` 并保留旧的 `docs/PROJECT_STATE.md` 历史原貌：完成、未验证、阻塞、证据、下次一步；不要把原始审计报告的 PASS 当本轮 PASS。
7. 交付后给用户一个与源码对应的学习点：历史动机→数学/状态模型→代码定位→最小实验→开放问题。

## 4. 数据/评测质量红线

- 轨迹生成脚本用模板/规则驱动，**不等于** 200 次真实模型自主规划；历史审计 PASS 不代表内容完全无误。
- 出处存在只是必要条件；要分开测“clause_id 存在”“从此次工具结果取得”“条款真的支持断言”“符合设备实际适用条件”。
- `LLMPlanner` 的解析错误会回退规则；**规则回退成功不得计入 LLM 原生解析成功率**。
- 检索比较用冻结同题金标准，报告 Recall@k、MRR、首字/端到端耗时及分位数，不能用训练的轨迹当唯一测试真值。
- 对高风险安全事项：只提供辅助判据、待核信息与检验建议，不执行任何设备控制操作；结果不能宣称替代资质工程师。
- 外部资料来源和标准 PDF 均应遵守版权/使用权限；不得上传企业台账、证件、邮件、密钥或整本收费标准到公开服务。
- 用户请求的是学习型协作：不要只有“一把梭”式改代码，优先解释原理和备选设计再迭代。

## 5. 当前第一优先级

补全 `upstream` 稀疏克隆的 01/02/03 官方文档与样例（不必拉入无关的大型 reference_code）；冻结导师验收清单与校验日志；打通规则 Harness→检索→引用→本地 Gradio 演示；然后比较 SQLite FTS5 检索、传统 BM25、embedding 与可选 rerank。
