# 数据血缘 / 文件分层 / 标准审计

## 1. 目录归类（物理位置维持现状，元数据进行分类）

| 类别 | 路径 | 处理策略 |
|---|---|---|
| **教师合同** | upstream/README.md、upstream/04_接口文档/*规范*、技术指标验证方法.md、任务包问题答复.docx | 冻结、索引，不随意重命名 |
| **原始标准** | upstream/01_RBI标准/**/*.pdf、upstream/02_损伤机理参考/**/*.pdf | 保持路径/原 SHA，用于人工逐页核证；禁止无授权公开 |
| **原始人工输入** | 01/条款摘录表_RBI.xlsx、02/条款摘录表_损伤机理.xlsx | 冻结；标准原文必须可对照 |
| **转换与主键约束** | upstream/04_接口文档/convert.py、schema/*.json、enums.json、risk_level_mapping.xlsx | 工具链源，变动要过 schema + 历史样本对照 |
| **可执行业务代码** | upstream/05_提交区/tools.py、harness.py、_df_rules.py | 上游修复走独立分支；外部产品层只通过 adapter 引用 |
| **冻结交付数据** | upstream/05_提交区/clauses.jsonl、trajectories.jsonl、guardrail_cases.jsonl、normal_cases.jsonl | 本轮终验通过；不直接原位重写 |
| **运行时证据** | upstream/05_提交区/guardrail_report.md、runs/、根目录各种 audit_*.md | 测试或审计记录；需标版本，不作为不可反驳真值 |
| **开发缓存与备份** | upstream/**/_rendered、upstream/**/*bak_*、upstream/04_接口文档/reference_code/* | 可再生/第三方快照，但“可再生”并不自动允许删除，需依赖审计及确认 |
| **扩展产品** | app/、knowledge/、evals/、tests/、scripts/ | 完全与官方提交合同隔离，必要时能按接口切回上游实现 |

## 2. 物理状态与版本：2026-10-29更新

> 本节下方“尚未检出/稀疏检出”的说明是**2026-10-27早期接管快照**，不可按当前执行。2026-10-29 DevSpace已实读`upstream/01_RBI标准`、`upstream/02_损伤机理参考`下PDF/XLSX、两份正式工具与检验文档。源RBI工作簿485条数据行（472原在正式JSONL + 13草稿未入正式），正式554条款(RBI472+DM82)。原RBI Excel在上游Git工作树已修改（历史状态）且有草稿和备份，未被本轮覆盖。见[当前状态](PROJECT_STATUS_CURRENT.md)、[老师50抽样证据状态](data_quality/TEACHER_SAMPLE50_EVIDENCE_STATUS_20261029.md)和[82机理结构化缺口](data_quality/DM_APPLICABILITY_ROOT_CAUSE_AND_REFORM_20261029.md)。
>
> 现有冻结问题：42条候选变更/73格尚未真人核签；P16 50随机0签，TSG21 §8.3.12来源PDF页索引错位；条款内容E2和工况适用E3不因`validate --final`通过而升级。主数据应保持只读，任何修订先隔离候选与审签。

### 2026-10-27历史快照（以下保留仅为溯源）
上游 `master` HEAD `d7877bf387482b2fa9b148d30860da59ccad48b3`；
截至检查，稀疏工作树包含根部 md/docx、04_接口文档的官方代码、05_提交区的完整数据和工具，但 `01_RBI标准`、`02_损伤机理参考`、`03_案例样例` **尚未检出**。
完整 Git 历史/对象是否含全部 PDF 不等于工作树当前已下载 PDF。请运行：
```powershell
git -C "D:\作业\竞赛\计算机设计智能体\机械智能体\upstream" sparse-checkout add 01_RBI标准 02_损伤机理参考 03_案例样例
```
单次运行会下载大体积文档（上游树总量约655MB，部分图片中间缓存较多）；网络允许时可分批：01后02后03。不要改 `git sparse-checkout` 白名单以引入不必要的 `04_接口文档/reference_code` 全仓源码。随后读档确认 xlsx/pdf 与 git 工作树完整性、目录哈希。

## 3. 血缘图
```text
GB/T / TSG 原始规范 [human verified]
       ↓ 人工摘录、存疑备注、复核签名
XLSX 两份 (RBI + 损伤机理)
       ↓ convert.py (校验字段/枚举/风险映射)
clauses.jsonl 〔clause_id -> source_code, clause_no, page〕
       ├─ damage_mechanism_query
       ├─ standard_clause_search
       └─ rbi_lookup
       ↓ ToolRegistry + Guardrail + RulePlanner/LLMPlanner
执行轨迹 {thought摘要, tool, args, result, observation, basis}
       ↓ reviewer 内容审查 + schema 校验
trajectories.jsonl → 可能供下游SFT使用（必须另核标签质量）
```

## 4. 不可混淆的四级证据
E0：条款ID存在；E1：条款在当前工具调用的 source 中；E2：原标准内容与引用子句相符；E3：适用于当前设备/材质/介质/压力/温度，且真正支持该推断。
现有 `validate.py` 主要覆盖 E0/格式；旁路 `app.runtime.check_trace_sources` 覆盖 E1；E2/E3 需要人工核验和智能审查，不能只凭向量相似度决定。

## 5. RBI 为什么不能仅靠向量库
GB/T 26610.3 的风险等级取决于多个现场因子与后果类别；向量检索只回答“哪些条款相关”，**不生成缺失的 EF/DF/IF/MCF/PF/MDF 等真实现场因子**。因此检索召回、条款事实、判级计算是不同层级。
