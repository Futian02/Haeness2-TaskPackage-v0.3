# Haeness2 接管工程路线 R0.1
日期：2026-10-27
上游审计基准：Futian02/Haeness2-TaskPackage-v0.3@d7877bf387482b2fa9b148d30860da59ccad48b3
状态说明：**本地只通过新增 adapter 的6条单元测试；上游未克隆；本地端到端、100组真实模型、ModelScope均 NOT VERIFIED**。

## 一、不可改变的老师合同

`upstream/README.md` 和 `upstream/04_接口文档/工具接口规范.md` 是提交口径。数据提交流 `标准PDF→抽取xlsx→convert.py→clauses.jsonl→官方3工具→Harness→trajectories.jsonl` 必须完整保留：
- `damage_mechanism_query`, `standard_clause_search`, `rbi_lookup` 名字与官方参数不变；
- 统一返回五键 `status/in_domain/result/source/message`，`ok` 时必须有出处；来源条款可真实回溯；
- 82个损伤机理八段式、原始文字、枚举、风险映射表、JSON Schema，不允许为了“漂亮”改成不同协议；
- 数量：条款≥300、轨迹≥200、多步≥40、三类特殊轨迹各≥15；异常护栏≥12且全拦、正常≥30且零误拦；≥5轮工具；LLM解析≥95/100；50条人工随机交叉核验准确率≥95%；最终 `validate.py --final` 退出0；ModelScope链接、四种场景截图。

当前远端报告称条款 554（DM82/RBI472）、轨迹200（多步144）、护栏36/36、正常60/60，但**这只是旧审计报告的历史证据**。不得把它当成本轮已经复验，更不能把规则模板轨迹叫“真实LLM生成轨迹”。

## 二、设计决策（避免重造轮子）

| 范围 | 保留/复用 | 新建设计 |
|---|---|---|
| 老师原始数据 | 两份xlsx、PDF、convert、Schema、clauses.jsonl | 只新增版本哈希、随机抽样审计和误差台账 |
| 知识工具 | 原 tools.py 及三工具协议 | 内部可选加 BM25、rerank、无来源拒答；不能暴露第四个官方工具 |
| Harness | ToolRegistry/Guardrail/RulePlanner/LLMPlanner/Trajectory | 不侵入式 adapter、审查、限时、trace，优先修路径依赖 |
| 模型调用 | 原有 OpenAI兼容 LLMPlanner | 增加“原生合法调用”与“回退”指标分离，不自行封装重型SDK |
| 可视化 | 原始轨迹结构 | 初期 Gradio；可用后才考虑 TS/React 重做 |
| 多智能体 | 已有 reviewer 可选回调 | 先规则审查，后模型交叉验证，确保质量增益超过时间成本 |
| 训练 | 已备 LLaMA-Factory 参考仓库 | 在模型真实闭环稳定后再考虑SFT，禁止把合成轨迹直接当正确标签 |

可借鉴：langchain-ai/langgraph（持久化图执行、检查点）、gradio-app/gradio（Web UI）、ShishirPatil/gorilla BFCL（工具调用评估）、vibrantlabsai/ragas（引用一致性评估）。原则：**优先接入包或方法，不复制他人整个源码进本项目。**

## 三、分阶段 Gate

### G0 获取和可复现性（优先）
- 独立克隆 `upstream/`，记录 commit、git status、根目录签名；
- 从原上游目录执行 `validate.py --final`、`_selftest_tools.py`、官方护栏、两份 harness hash 一致性、B2双重审计；
- 核实 200 条真实数据的轨迹来源、重复率、训练泄漏、annotator/checked 标志；
- 在独立分支上修 `tools.py` 的 `from _df_rules import` 路径依赖。负向先红后绿，外部cwd启动与正常cwd结果一致；
- Gate：基线全套退出0；例外逐项说明、保护原官方数据。

### G1 真正的单 Agent
- RulePlanner模式/LLM模式分离；模型不可用则显式显示 fallback；
- 先10组实测，覆盖多步、特殊、域外、未知介质、缺现场数据，再扩展100组；
- 指标：原生工具解析成功率≥95/100（fallback 不计成功）、工具调用过程留痕完整100%、强制遵守护栏；
- 使用标准内容只提供证据，不允许 LLM 输出没有依据的安全结论。

### G2 检索与证据
- 构建最小10–30条人工核对的 retrieval gold，测 Recall@k / Precision@k / 证据支持率；
- 增加可检索索引之前先跑原内置 `standard_clause_search` baseline；只有显著收益才加 BM25 或向量库；
- 引用校验分两级：存在性（程序校验）与真实性/蕴含关系（人工专家+独立评审）；
- 严格检查原文上下文，禁止离开适用范围外推温度、压力和介质。

### G3 可选多智能体
- 基线 agent + 来源审查体 + 反证体（在低确定性时触发），各自可单元测试；
- 合成打分不能取代真实答案：同一组冻结案例对照单Agent vs 双Agent vs 三Agent；
- 如准确率不升、成本显著增，则回退单Agent。
- 适合启用 LangGraph：循环状态复杂、暂停/恢复、人工审核需求已实测出现；否则沿用现有 Harness。

### G4 前端与公网上线
- 首先 Gradio 页面展示：用户设备工况、每步决策摘要/工具名/参数/返回/耗时、证据来源、拒答缘由；
- 四类官方场景必须截图：single, multi, guardrail, out_of_domain；公开部署到 ModelScope Studio，校验外网、手机端、超时、无token退化；
- 评价指标拆开统计：检索P95≤1.5秒、普通问答P95≤8秒、复杂多Agent P95≤25秒（建议目标，只有取得实测后才可写“达标”）。

## 四、第一轮已发现问题及处理顺序

1. **P0：原代码的模块导入隐患**：`rbi_lookup` 的 `_df_rules` 相对cwd/PYTHONPATH加载在外部执行时静默退化为 not_found。需上游修复、加外部 cwd 子进程回归；本扩展层只是先通过 sys.path 保证加载，未消除原隐患。
2. **P0：LLM解析失败的回退污染**：上游在非法工具/JSON/API错误时自动 RulePlanner 回退，容易把完成案例错误计算为模型解析成功。界面目前单独报告 `parsed_ok/parsed_fail`，还缺真实评测冻结集。
3. **P1：200条轨迹不是200次独立真实LLM规划**：生成脚本由规则拼接 `thought` / `conclusion`，仅工具 result 真实；要验证轨迹的工程正确性和学生审核状态。
4. **P1：历史交接文档不一致**：早期《项目剩余交付步骤表》声称5条demo，而晚些B2报告声称200条；以当前数据、脚本重跑为准。
5. **P1：仓库体积约655MB/2960树项**：参考代码LLaMA-Factory、PDF渲染图、备份等占大量空间。先做文件列表与可复现性分类，禁止大规模`git rm`。后续通过文档+外部链接替代完整参考仓库应与教师核对。
6. **P2：RBI风险等级**：缺失现场六因子不能在同一机理名上凭空套用风险矩阵，应该提供判定路径与待补充项；结果null是诚实输出，而非单纯“不好看”。

## 五、实践开发纪律

- 功能变化必须对应测试用例与证据，先小集后全量。
- 优先可复用小模块和现成成熟库；禁止全量复制开源依赖仓库。
- 原任务包和增量产品层边界清楚，入口文档单一。
- 学习每个 Gate：先问为何而不是先引入框架；保留对照实验、失败样本与性能曲线。
- 本项目只用于技术教学与辅助评估，不做自动设备停运、安全放行等真实世界控制。
