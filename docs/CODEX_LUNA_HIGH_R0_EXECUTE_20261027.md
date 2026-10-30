# 交给本地 Codex（Luna High；Fast模式如支持）｜R0任务书
2026-10-27。必须作为一个**有界任务**执行，输出实际结果再由ChatGPT独立验收。不是允许无限自主改动。用户授权：全量同步仓库、按教师文档梳理、建立工程基线和分工。

## 0. 作用域与要求
唯一工程路径：
`D:\作业\竞赛\计算机设计智能体\机械智能体`
上游独立Git：
`D:\作业\竞赛\计算机设计智能体\机械智能体\upstream` （remote `Futian02/Haeness2-TaskPackage-v0.3`；当前 master@d7877bf387482b2fa9b148d30860da59ccad48b3）
禁止对父级 `D:\作业\竞赛\计算机设计智能体` 仓库运行 `git add -A` / `reset` / `clean`，也禁止修改旁边的其他竞赛项目。
先读根部 `AGENTS.md`、`docs/MASTERPLAN_V1_TEACHER_FIRST_20261027.md`、`docs/FULL_SYNC_AUDIT_PLAN_20261027.md`、`docs/TEACHER_REQUIREMENTS_AND_GAPS_20261027.md`、`docs/PROJECT_STATE.md`。
教师规格唯一权威：`upstream/README.md`、`04_接口文档/工具接口规范.md`、`技术指标验证方法.md`、`任务包问题答复.docx`、两份XLSX的模板及schema。
模型模式：如果当前 Codex 原生可选 Luna High/Fast，使用它；不要为了所谓Fast自行切换未经用户授权的模型或绕开可信执行门禁。

## 1. 完整全仓同步（P0）
- 先核 `git -C upstream status --porcelain=v1 -b`、HEAD、remote、可用磁盘空间，工作树应无用户待保存更改。若实际有更改，**停写并报告**。
- 用户要求全量HEAD Git文件，执行 `git -C upstream sparse-checkout disable`（非 `git clean`）；如遇下载失败可有限重试，不能虚报完成。
- 核 `git -C upstream ls-files` 条数、`git -C upstream status`、`python -B -m scripts.check_sources` 必须19/19（如仓库实际路径差异则据README订正检测脚本，保留证据）。
- 建 `docs/audits/R0_REPO_MANIFEST.md`：记录HEAD、源文件总量、01/02/03标准与原始表、04/05官方合同、reference_code、缓存与备份的分类；保留所有文件物理位置，不移动/删除/覆盖教师材料。对于 PDF 仅验证页数、存在性、抽样可渲染与哈希，不批量OCR（字体已知有乱码）。
- 如全仓包含嵌套参考Git/大文件：登记版本与来源，避免重复clone；不擅自重写原Git history。

## 2. 教师合同全量核对（P0）
- 完整扫描 v0.3 官方老师合同、教师问答（docx）和机器Schema；生成 `docs/audits/R0_TEACHER_ACCEPTANCE_MATRIX.md`，包含9项提交物、四项指标、命令、预期/实际/缺口/证据。
- 两份xlsx源表：检查损伤机理25列、RBI23列、clause_no必须文本、八段式；`risk_level_mapping.xlsx` L1-L4; 标记人审尚未交付，**绝不伪造核验人**。
- 重新运行且保持上游数据字节不变：
  `python -B upstream/04_接口文档/validate.py --final`
  `python -B upstream/05_提交区/_selftest_tools.py`
  `python -B upstream/04_接口文档/harness_skeleton/run_guardrail_tests.py`
  `python -B upstream/05_提交区/_check_harness_sync.py`
  `python -B -m unittest discover -s tests -v`
  `python -B -m evals.benchmark_retrieval`
- 运行会写入`upstream/05_提交区/guardrail_report.md`等官方脚本输出时先比对原文件并对更新作显式记录；**不覆盖抽取XLSX、clauses.jsonl、trajectories.jsonl**。
- 任何异常写BLOCKED，不能以旧报告“已过”代替。

## 3. 本轮上限为“闭环R1准备”（P1，只允许小步）
- 在不触碰源数据前提下，检查 `app/runtime.py` 中 `LLMPlanner` 构造是否准确，模型parsed_ok/fail与fallback是否正确；
- 检查 `app/web.py` 是否按官方要求展示：第n步/公开决策摘要/tool/args/result/observation/阻断、结论basis对照、标准号/条款号/页码/短原文；列出缺项；
- 如Gradio包未安装，可在单独虚拟环境安装 `requirements.txt` 后本机启动 smoke，不进行未经确认的公网发布；所有密钥从已有环境读取，严禁读出或打印其值；
- 修复仅限我们产品层 `app/`、`tests/` 中明确可以先红后绿验证的小缺陷，不新造第四个官方工具，不引入庞大编排框架，也不要把Full LLM Parse 100例虚报为完成；
- 如果工期许可，`upstream/05_提交区/tools.py` 的 `_df_rules` 外部cwd问题只能在独立分支先复现后修，并将 `04_接口文档/harness_skeleton/harness.py` 的对应约束保持一致；若风险大则留为下一轮待审。

## 4. 本轮验收输出（文件+结论）
输出 `docs/audits/R0_REPO_MANIFEST.md`、`docs/audits/R0_TEACHER_ACCEPTANCE_MATRIX.md`、`docs/audits/R0_EVIDENCE_LEDGER.md`，每份报告必须含精确命令、exit code、条数与发生的修改文件；`docs/PROJECT_STATE.md` 更新完成/部分/阻塞状态。
验收标准：
C0 说明HEAD全量 Git 文件是否真的已检出（若失败写BLOCKED并给缺失清单）；
C1 官方19项重要资产全部可读；文档、PDF、Excel物理存在并做格式抽查；
C2 官方validate --final、tools、guardrails、sync、13项产品测试重新PASS或明确阻塞；
C3 机器报告能逐条对应老师9项交付，真实LLM/API/人工签字/ModelScope未完成必须醒目标记；
C4 未改老师合同、源表、风险映射、原始标准、格式与三个Tool协议，原文件变动提供diff；
C5 列出下一轮R1开始的3个最关键工程任务、各自验收条件、学习知识点；
C6 没有将认证凭据、私有设备数据、收费PDF上传公网，没操作别的项目。
完成后停止在 `READY_FOR_SUPERVISOR_REVIEW`，把证据路径给ChatGPT审核；不要擅自扩到完整大模型、向量库或多体重构。

## 5. 当本地本机 Codex API执行器不可用
不要冒充任务已分发、已运行或已部署。用户可以在本机 Codex CLI/桌面项目中打开该目录，直接把本文件全文作为任务。Fast若不可用，标准Luna High即可。所有长运行作业要保留本机日志和退出码（日志不得含隐私）。
