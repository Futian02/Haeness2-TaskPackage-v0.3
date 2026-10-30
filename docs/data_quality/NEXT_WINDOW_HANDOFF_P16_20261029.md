# 下一窗口连续交接｜澄衡 Aetheris / Haenness2 机械智能体 P16（2026-10-29 13:14 +08）
**先读状态，再执行；该文件是交接索引，不是比磁盘更新的真值。** 新窗口要走DevSpace实际本地读写，不要重复让用户提供路径，不要因为历史摘要猜状态。最新的Owner独立验收为`docs/data_quality/P16_OWNER_INDEPENDENT_AUDIT_20261029.md`；如果后续Codex已修改文件，以文件和实测为准。

## 0. 路径与操作边界
项目根目录：`D:\作业\竞赛\计算机设计智能体\机械智能体`。
- 根`AGENTS.md`、`docs/PROJECT_STATUS_CURRENT.md`、`docs/PROJECT_STATE.md`、`docs/data_quality/P16_OWNER_INDEPENDENT_AUDIT_20261029.md`为先读顺序。项目旧`PROJECT_STATE`前半是2026-10-27历史，不能当今日状态。
- `upstream/01_RBI标准/`六份PDF、`条款摘录表_RBI.xlsx`；`upstream/02_损伤机理参考/`六份PDF、`条款摘录表_损伤机理.xlsx`；`upstream/04_接口文档/`教师convert/validate/schema/enums/risk mapping；`upstream/05_提交区/`正式JSONL与三个教师工具。**全部冻结只读**，未经用户书面授权不得直接覆盖、移动、签署、清理Git或部署。
- 工具唯一老师可调用签名：`damage_mechanism_query`、`rbi_lookup`、`standard_clause_search`；统一五键`status/in_domain/result/source/message`；不添第四个老师工具。产品层外网搜索属于应用能力，不计老师工具。
- ChatGPT网页端要读本地内容使用DevSpace；允许写新的审计/交接文档在`docs/data_quality`，严禁另一个窗口改P16-A/B/C拥有的文件，任何正式数据库与模型密钥都不动。

## 1. 用户目标与工作方式
用户是计算机专业学生，接管老师机械智能体竞赛/实训项目，目标不仅满足老师验收，还希望专业可信的多Agent、清楚证据链、可靠工具、好看的对话产品，同时用于技术成长。偏好：直接执行本地只读核实→定位根因→小改→真实回归，能复用现成工具就不造重复轮子；多Codex窗口并行时必须划分唯一文件写入；老师合同优先，所有证据必须可核；不要把模型推理、机器OCR、合成金标、人审混作同一等级。
用户此次明确希望：严格持续审查P16 A/B/C尤其数据对下游研判、检索及最终交付的影响，并把交接状态/所有关键记忆带入新聊天。**不要只总结过去，要以项目实盘推进**。

## 2. 总体工程进度 P3–P13（只需了解，不重新造平台）
- FastAPI + SQLite WAL/SSE/幂等重放、React + assistant-ui/React Flow、可收起会话栏、设置中心、软归档恢复、当日统计、澄衡Aetheris品牌、可折叠真实执行过程、语音草稿按钮；LangGraph路由→调查→受限并行审核→报告，规则Agent真实执行，LLM/DeepSeek普通聊天与工程结果整理。规则Agent不等于已证LLM多Agent自主工具规划。
- P12可从自然语言抽取设备/材质/介质/温压并沿同会话工况追问；网页模型profile本机DPAPI安全存密钥，未正式多租户上线。
- P13加联网off/auto/on可选、同会话历史、长输出预算、模型失败卡与恢复、上下文污染修复、WebSearch adapter、按任务的模型参数；本地模拟并发、前端回归PASS，但真实付费模型/真实公网搜索/生产部署未验。P13曾有“联网默认off”与前后端实际auto不一致、8000端口常驻进程版本旧的历史隐患，新窗口若涉及服务先核查并征授权，不擅自重启；P16仅数据线，不改产品。
- 老师实际终验除schema/数量外，要求50条真人交叉原文核对≥95%（50条至少48条）、100题**真实LLM原生**工具解析率≥95%（不能用规则fallback/模拟代替）、至少5轮连续工具调用、100次日志100%完整、四类护栏与>=30正常放行，以及ModelScope公开演示与证据截图。P16数据合格也不表示老师全部终验通过。

## 3. P14 → P15 → P16 数据进度（确切数字）
- 两组12份PDF合计1385页：01 RBI六PDF=461页；02损伤及补充六PDF=924页。P14逐页来源矩阵/章矩阵和试验缓存已做；20页OCR pilot未达逐字精度门槛，不应无界OCR。原RBI.xlsx 485行（旧472+未签13），DM.xlsx 82个GB/T30579损伤模式共25列且八段式G–N每格非空；五份补充设计/制造标准多数属于辅助，**不是空着没蒸馏就必须塞进损伤机理表**。
- 原RBI23列：A-F485/485, G30, H45, I/J25, K0, L54, M/N0, O-R0, S32, T472, U472, V0; DM25列：82模式，G–N=656非空，O74/P26/Q20/R13/S/T0/U81/V82/W82/X0。这些空值有合法不适用，也有可能漏提取；要看来源支持的字段召回，不要盲填。
- P15 A修RBI 64 cells；P15 B修DM 9 cells；P15 C逐格对账73/73、正式候选554条（RBI472+DM82），相对老师正式库42 clause_ids变/44 JSON字段变，新增0、删除0，未签13草稿仍隔离；teacher convert/validate554/200、tool selftest17/17 PASS。P15候选不能直接发布。
- P16 A：42张本地证据卡 / 19张不同PDF页面图；机器判定28 MATCH、13 AMBIGUOUS、**1 CONTRADICTS（TSG21 §8.3.12来源定位台账PDF index78错误，index83/印刷页79候选）**。Owner额外直接用PyMuPDF对源TSG PDF做独立文本检查，index78含§8.2.3却不含§8.3.12，index83包含§8.3.12和“安全附件检验”，证实物理页错误；印刷页页脚和完整截图仍应真人核验。GB/T30579 PDF文字层乱码，Owner无法用text搜索独立证明材料牌号/注入点词语，仍属机器视觉提案。42条真人签署空，不能发布；30579 §5.6 F从§5.6.1+部分§5.6.2缩为仅§5.6.1，仍需裁定F/H引文范围。
- P16 B：仍有211条高风险RBI表格记录未双人逐格核验，82模式G–N/O–V共1312字段审查队列，补充PDF 56章待核；20条定向OCR仅导航；11条隔离建议（6源数据/语义+5应用检索），**未正式合并**。具体疑似错误包括 §5.6材料`3Cr-0.5Mo` vs PDF`5Cr-0.5Mo`、`轻相` vs `烃相`、`注氨点` vs `注氢点`，部分焦化蜡油回路遗漏；§5.23受影响材料与耐蚀强弱混淆；§6.7 H₂S分压/浓度与总压、各子型温区不能混用。机器视觉证据候选需独立真人核图，禁止直接“已确认”为事实。
- P16 B隔离检索：冻结合成gold 38题共42相关ID，正式teacher工具37/42（Recall@20 0.881/MRR@20 0.816），应用层全字段+查询扩展+RRF候选42/42（MRR@20 0.952）。`likelihood_method`和`matrix_mapping`的gold本身需专业重核；**这不是专家准确率，应用新检索尚未接进P13，不可拿它宣传100%召回**。
- P16 C：固定seed20261029随机50条PDF证据卡（34张不同PDF页图），与A定向42重合2 => 人审90个唯一对象；0真实审核签署。隔离预览同P15候选（SHA256 `7efebc07786fd6232da05d21c43323486f3b15d1ff4edd731075755fe419d196`），554条、42变更、0新/删；P16-B新建议全部未合并。teacher原版validate预览554/200 PASS、冻结工具17/17 PASS；`P16_C_MACHINE_GATE.json`阻断TSG来源矛盾与真人0签，发布状态`BLOCKED_PENDING_HUMAN_REVIEW`。
- 2026-10-29 Owner独立复验：`python -B -m scripts.owner_p16_independent_readonly_audit` 得42/73/50/90/211/1312/56/11计数、哈希及37/42→42/42相符；P16 A系统Python pytest 5通过、B/C .venv unittest10通过、正式和预览teacher validate各554/200通过、工具正式和候选各17/17通过。**统一venv完整`unittest discover -s tests -q`运行230项有1 ERROR、3 SKIP（A测试顶层import fitz而venv没有PyMuPDF）；不是全套PASS**。源PDF/XLSX/正式JSONL未被Owner改动。

## 4. 读文件目录（新窗口必须立刻实际读取）
1. `AGENTS.md`；`docs/PROJECT_STATUS_CURRENT.md`；`docs/data_quality/P16_OWNER_INDEPENDENT_AUDIT_20261029.md`（Owner最新实测）。
2. `docs/data_quality/P16_A_CHANGED_RECORDS_REVIEW.md`、`P16_B_SOURCE_FIDELITY_AND_RETRIEVAL.md`、`P16_C_FINAL_RELEASE_GATE.md`。
3. `work/data_staging/p16/A_CHANGED_42/index.html` + `P16_A_REVIEW42.csv`；`work/data_staging/p16/B_REMAINDER/P16_B_CHANGE_PROPOSALS.jsonl`、`P16_B_PRIORITY_TRIAGE.csv`、`P16_B_DM_FIELD_REVIEW.csv`；`work/data_staging/p16/C_GATE/index.html`、`P16_C_HUMAN_REVIEW90.csv`、`P16_C_MACHINE_GATE.json`。
4. `work/data_staging/p16/merged/P16_CLAUSES_PREVIEW_ONLY.jsonl`；`upstream/05_提交区/clauses.jsonl`（只读），对照hash。
5. 教师`upstream/04_接口文档/技术指标验证方法.md`、`upstream/资料获取与摘录表填写指南.md`。

## 5. 新窗口优先执行，不问用户重复信息
**第一步：** 先只读复核P16 A/B/C产物；尤其TSG locator index78→83，§5.6的材料牌号/烃相/注氢等疑点应在PDF原图和列字段上核实，记录证据等级和能否不经人工更新候选；C门禁内签核0保持阻断。可以继续写新的Owner审计，而不是直接修改P16候选或正式PDF/Excel。自查环境一致性：统一venv缺PyMuPDF导致完整测试230项1 ERROR，提出最小环境修复方案且不可为了绿灯掩盖检查。
**第二步：** 规划高效率的人审：随机50及修改42共90卡，引导真正审核人核条号、印刷页、原文逐字、单位/适用性，签身份/时间、处理分歧；42必须每条有裁决，随机50至少48/50真实通过。有确定错录时，隔离P16-next候选，逐字段从标准原文改正、保留完整diff和旧哈希、禁止无人审批直接放行。
**第三步：** 教师合格候选必须经历convert/validate/三工具、自有前后端回归和应用检索正反例；P13真实LLM/tool parse与ModelScope后续另验。先内容可信，后提高召回及公开发布。

## 6. 不变原则
- 绝不能编造标准原文、材料物性、周期、风险等级、假引用、人工复核签名或“已达到95%准确率”。
- OCR的页数、证据页图存在不等于逐字真值；合成gold42/42不等于专业检索100%；schema/teacher17通过不等于风险诊断准确。
- 不要因为M/N/K/Q/R字段空就填值；GB/T150设计类不自动是损伤模式。
- 不对用户已有历史DB/服务、上游源文件、Codex其它窗口文件做未授权覆盖；保存diff、snapshot、Owner gate。
- 项目重视技术成长：给出“现象→根因→证据→修复→测试”的解释；不要无限创建阶段P17/P18，仅收口真实质量缺陷。

## 7. 复现命令（可不发费用）
```powershell
.venv-langgraph/Scripts/python.exe -B -m scripts.owner_p16_independent_readonly_audit
.venv-langgraph/Scripts/python.exe -B -m unittest tests.test_p16_b_fidelity_retrieval tests.test_p16_c_human50_gate -q
python -B -m pytest -q tests/test_p16_a_evidence42.py
.venv-langgraph/Scripts/python.exe -B -m unittest discover -s tests -q
.venv-langgraph/Scripts/python.exe -B upstream/04_接口文档/validate.py --final
.venv-langgraph/Scripts/python.exe -B upstream/04_接口文档/validate.py --final --clauses work/data_staging/p16/merged/P16_CLAUSES_PREVIEW_ONLY.jsonl --trajectories upstream/05_提交区/trajectories.jsonl
.venv-langgraph/Scripts/python.exe -B upstream/05_提交区/_selftest_tools.py
```
