# R8 Owner审查｜RBI PDF完整性、简化循环Agent、透明轨迹与UI门禁
日期：2026-10-28。状态：OWNER_DESIGN_REVIEW_NOT_IMPLEMENTED。**本文所有“目标/设计”不可冒充已交付。**
当前本地工作区：`D:\作业\竞赛\计算机设计智能体\机械智能体`。教师固定3个工具 / 返回5键合同、PDF、官方数据暂冻结。

## 0. 实测事实摘要
- 6份RBI来源PDF共461页：GB/T26610.1 34p、.2 25p、.3 14p、.4 164p、.5 53p、TSG21 171p。正式RBI摘录472条：.1 0、.2 134、.3 141、.4 139、.5 26、TSG21 32。
- 原Excel `条款摘录表_RBI.xlsx` sha256=`38cf71bf9f9868cfa531729cda70dea2e2857b3a788ec1a67f56d27ef01512f9`；A2:W473已有472行，A474:W486预留13条GBT26610.1候选，但尚未写入。真实抽取人U及独立复核人V缺失；不得伪造签名。
- 472条源数据G可能性30、H后果45、I原始风险25、J统一风险25、K检验周期0，V复核人0。25个G/H均齐全的风险矩阵格子都有I/J；其他不应通过猜测填充。
- `scripts/audit_pdf_rbi_coverage.py`已运行**461页全文只读OCR-free正文字串查找**：GBT26610.2和GBT26610.4各0条text-exact/0条prefix，原因原PDF复杂编码文本抽取乱码，不能据此判定抄错。GBT26610.3 exact38、prefix_only92、no_simple_match11；GBT26610.5 exact1、prefix_only4、no_simple_match21；TSG21 exact17、prefix_only14、no_simple_match1。此比例仅表示**机器文本能否回找，不是人为标准原文准确率**；尤其GBT26610.4表格、公式需要渲染PDF逐页人工比对，不能用非精准PDF文本抽取断言完成。
- 老师工具`_selftest_tools.py`17/17，`validate.py --final` 554/554 +200/200，护栏36/36且正常60/60；旧200条轨迹步数1=26、2=30、3=144、≥5=0（五轮能力需单独实跑）。真实LLM100组JSON工具解析/BFCL未跑、50条随机人工核验未签、ModelScope未部署。
- P7B前端React+assistant-ui+xyflow，36/36；UI仍为本地RULE_DEMO。真实全链路当前有44事件含tool_calls/claims/disagreements，但这**不是模型内部完整CoT**。
- `orchestration/graph.py`默认7角色单趟顺序/部分跳节点，无反馈回环；AgentGraph._build_state_graph遍历self.order，每节点dispatch只向顺序后续候选。因此没有同一run反复调查→检验→修正的Loop，且缺工况路径仍走evidence_auditor/skeptic/reporting等节点造成浪费。
- `SupervisorAgent.run`先拒缺material/medium、后判纯“条款/标准”问题，因此纯条款检索无工况时错误要求设备数据；须改为先识别纯引用查询，再根据诊断与RBI意图区分必需上下文。

## 1. RBI 完整填表的**可证伪目标**（不同于“所有格子都填”）
### 1.1 逐PDF建立条款覆盖清单
以每个标准的目录/编号/图/表/附录为母体，记录`pdf_id, pdf_sha, edition, printed_page, section_no, table_fig_no, page_index, class(mandatory|informative|outside_scope), extracted_status, excel_row_id, quote_fidelity, risk_rules, conditions, formula_fields, reviewer, review_timestamp`。
- GBT26610.1：先13条已核方法学候选再全目录检查腐蚀回路、数据质量、评估类型、再评估条件；
- .2：检验方案/检验时点/附录C；PDF当前文字抽取乱码，**必须视觉读表**，不可强行复制乱码；
- .3：5×5风险矩阵(25格)；失效可能性/后果独立分级、因子赋值和适用条件。检查图表格子是否缺录/出错，而非无条件造risk L值；
- .4：F=FG×FM×FE×FL等因子、各设备与破口尺寸表、条件/失效概率；每个表格数据须人工比对数值、单位和区间，不把解释性综合描述写成`content_raw`原文；
- .5：面积、财务等失效后果分级和计算附录；仅26条不能据此推断够用/不够用，先列目录母体；
- TSG21：按“固定式压力容器”相关条款定 scope；安评等级与RBI风险L1-L4不是一回事；检验周期若条件分支必须独立规则和范围，不把最长周期当普适建议。
必须分别标`not_extracted`、`not_applicable`、`needs_human_visual_check`、`verified`，不混淆。

### 1.2 原工作簿不破坏、官方转换链冻结
用户要求只改原`条款摘录表_RBI.xlsx`的`摘录表`，不可改变其他3张sheet/23列表头/已有行/预格式/验证规则。编辑前Git/SHA、原件备份、记录增量cell/diff、并与Codex任务互斥。
新增条款既要`clause_id`全局唯一、`clause_no`文本、印刷页、原文F≤300文字、分级字段仅有同源上下文才填；说明/概括放另一个语义层，不能冒充官方`content_raw`逐字引用。
真实抽取人U、复核人V由真人填写，模型不可代签。13条RBI1不满足U时官方convert会拒绝，保持DRAFT状态。
真实源表→教师`convert.py`→隔离的JSONL diff→正式`clauses.jsonl`→`validate.py --final`→工具/轨迹回归→**随机50条双人交叉对原PDF**；超过两条失败（50的95%门槛）不得说合格。

## 2. 强烈建议的最简生产图：按需4阶段+两个有界回环
教师三工具仅3种，可在Investigator内部使用，不追加第4个官方tool。默认图保留旧版直到新A/B回归通过：
```
START -> Router
   |-- plain standard lookup --> Tool lookup + citation check --> Report --> END
   |-- out_of_domain --> Refusal --> END
   |-- engineering case --> Investigator (1-3 loops, LLM tools/planner)
          ↓ EvidenceGate [typed decision + reasons]
          |-- resolvable by more queries & attempts<3 --> Investigator
          |-- cannot be solved without field data --> interrupt(NeedMeasurements)
          |-- enough baseline evidence --> ReviewDispatch
                   |-- low risk/plain factual --> cheap source validator --> Reporter
                   |-- diagnosis/risk/ambiguous --> [Auditor || Skeptic] --> Merge
                                                               |-- repairable & review_round<2 --> Investigator
                                                               |-- no repair possible/approved --> Reporter
```
不要将“证据不足”理解为无限循环：**缺少用户测厚/腐蚀历史的信息，循环工具不会产生新测量**，应pause等待用户或输出未决；自动重复检索必须使用新query和具体明确的反馈，防止复制同一工具调用。
对每轮输出`route, phase, iteration, decisions, blockers, missing_fields, tool_calls, evidence_claims, review_findings, cost, elapsed_ms`。每轮处理预算：默认最多3个调查iteration+2个review revision，toolcalls<=8，另设真实token预算/超时；触顶输出pending/unresolved、不可硬判风险。RBI高风险始终要求失效可能性和后果可适用双证据，独立系统Review不可直接成为真人E2/E3。

### State最小契约
```python
class TaskState(TypedDict):
    run_id: str
    input_snapshot: dict
    task_type: str
    phase: str
    iteration: int
    review_round: int
    tool_budget_remaining: int
    observations: list[dict]
    sources: list[dict]
    claims: list[dict]
    gaps: list[dict]
    review_findings: list[dict]
    gate_decision: str
    answer: str
```
并行审核写角色独有`auditor_findings`/`skeptic_findings`或用reducer；Merge必须保守、顺序无关、保存冲突和来源hash。P7A默认并行实验不更改现有生产，A/B后才按需启用。鉴于当前本地纯规则并行慢于顺序，允许双审的只是需要真实专业质量收益的case。

### 两级 gate 应明确区分
EvidenceGate：用户有没有提供相关基础字段？工具source是否确实属于本run、能找到canonical、标准版本/印刷页是否一致？是否缺关键测厚等只能从现场获取的信息？下一步是检索/询问/审核/拒答。
ReviewGate：每个Claim源支撑和限制是什么？并行来源有无矛盾？缺失数据和模型假设能否解释？是否存在没有支持的具体风险定级？异议不可被后到意见覆盖。审核不合格但来源不可补→中止或人工审查，不可无限“自圆其说”。

## 3. 完整透明过程与“CoT”要求的安全/事实区分
**允许且应该展示**：run创建与输入快照、phase/iteration、每次工具的合法函数名/参数/完整授权返回与耗时、source clause_id/pdf印刷页/quote/hash、观察事实与模型推断分开、短的`public_decision_summary`（模型或规则的决策依据摘要）、Gate的命中规则与反馈、冲突、哪次重试用了新证据、人工审批身份状态及终局报告。这是**可审计的完整外部执行轨迹**。
**不能承诺**读出、保存、展示模型未对外暴露的私有内部逐token chain-of-thought。教师`Trajectory.Step.thought`是显式输出的“公开决策理由/简述”，并非模型所有内部推理。真实模型也应生成可公开的短结构化理由，而非索要隐藏推理。不得直接向前端暴露密钥、长篇私有PDF、隐藏提示或敏感工厂资料。
事件schema如`{run_id,sequence,phase,iteration,agent,kind,tool_name,args_summary,result_digest,source_refs,public_rationale,gate_decision,retry_reason,latency_ms,model_usage,cost}`。后台可持久化更详细的受授权tool payload，前端默认分层展示。现阶段`decision_summary`只有计数；`token_delta`只在run尾发最终文本，不是真正逐token LLM流。未来需要接上真实模型后增量stream及token计数。

## 4. 实测/质量门槛对比
- 老师 `validate --final`、17官方工具、护栏36/36+normal60/60已绿，资料数554/200。50条随机PDF人工交叉/100真实LLM JSON解析≥95/5轮完整Harness run / 100次含异常轨迹完整计数/ModelScope四类真实截图与公网演示尚未完成。
- 目前仅有`basis`ID存在检查，**不是**专业准确率。引用准确应评`citation_id_correct`、`exact_quote_correct`、`printed_page_correct`、`supports_claim`、`conditions_applicable`分项；E1不足以推出后四项。真实百分比未测，不报数字。
- 现本地用户完整工程工况RuleDemo P50约2.36s（8个样本）不含外部LLM/浏览器；模型上线后需记录TTFT、P50/P95总时延、每轮tool与LLM成本、branch distribution。采用预算约束与以同一证据快照公平A/B。
- 前端已引入`@assistant-ui/react`和`@xyflow/react`、React+Tailwind及局部shadcn基础组件；现审查抽屉E0/E1、长中文报告、移动响应式通过本地E2E。后续重点“首页阅读：结论+不确定性+行动建议；展开：阶段流、引用、反证/回退”，无需重新造聊天框。为新循环图展示实际phase/iteration，不画固定7节点必经；逐轮事件/人员中断与恢复进度清晰。

## 5. 实施顺序（先合同/数据后真实LLM，不并发争文件）
1. **数据审计工作线**：本机PDF视觉清单（0文本提取可疑页用可视化）、候选增量与来源双人签名；原RBI XLSX只改摘录表（必须安全的二进制Excel编辑工具+无并发写者），然后老师converter→validator；不可宣称已更新原表。
2. **Graph工作线**：先在`orchestration/`隔离搭简化循环Router/Investigator/Gate/Review/Reporter，mode明确RULE_DEMO，不影响当前后端旧事件；20+负例包括纯条款查询/复查不通过/缺实测中断/跨run污染/冲突/超预算；在全量测试通过且性能不过度恶化前不切默认图。
3. **API工作线**：提供provider名称、base_url、模型名、工具调用/JSON支持和预算信息，Key仅本机`HARNESS_LLM_API_KEY`受控变量；先老师单智能体10个真实请求→100个解析评测，fallback单计；再将INVESTIGATOR/可选SKEPTIC挂LLM，API工具仍官方3个。真实输出**只**可用脱敏非敏感任务、未授权付费原文不得外传。
4. **前端UI工作线**：等待事件schema冻结后增量改页面；展示每轮外部可审计decision summary/tool/source/review/interrupt，不把hidden-CoT作为可见能力。保留36前端测试+浏览器E2E。
5. **老师正式交付**：随机50条真人核验、5+轮轨迹演示、100次完整率计数、100模型AST/BFCL与ModelScope部署（在可公开数据与鉴权隔离设计下）全套附件；不为了过关改三个工具。
