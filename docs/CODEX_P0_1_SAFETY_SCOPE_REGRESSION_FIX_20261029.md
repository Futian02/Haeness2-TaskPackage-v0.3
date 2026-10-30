# Codex P0.1｜专业回答的安全结论门、条件作用域与真实评测整改
项目`D:\作业\竞赛\计算机设计智能体\机械智能体`。请在真正的**本机Codex**通过本地文件系统、PowerShell和终端完成；禁止为了访问D盘使用任何远程连接器。若不是本机工作区，直接`LOCAL_EXECUTION_ENV_MISMATCH`停止。

**性质**：对Codex前一轮P0专业回答候选的Owner代码/科学审计整改；禁止仅修表面文案、绕过测试或将模型候选扩权。未授权重启8000/8001、修改用户正式SQLite/密码、收费LLM、教师上游PDF/Excel/JSONL或人工人审，也不得覆盖S3窗口的候选。

## 第一步：阅读与复现，先写FAIL
必读：
`AGENTS.md`, `docs/PROJECT_STATUS_CURRENT.md`, `docs/audits/OWNER_P0_PROFESSIONAL_ANSWER_REPAIR_20261029.md`,
`docs/audits/OWNER_P0_INDEPENDENT_DATA_CODE_REVIEW_20261029.md`,
`docs/data_quality/DM_APPLICABILITY_ROOT_CAUSE_AND_REFORM_20261029.md`,
`docs/audits/S3_B_CONDITION_ENGINE_REVIEW_20261029.md`,
`backend/professional_answers.py`, `orchestration/r9_industrial_candidate.py`, `backend/api.py`, `backend/deepseek.py`,
`tests/test_p0_expert_guidance.py`, `evals/p0_expert_guidance/cases.jsonl`，以及teacher原3工具接口。
检查真实git status和并行修改，不能覆盖他人尚未提交的工作。

Owner已**直接复现**两个必须先红后绿的P0缺陷（请用临时Python/临时SQLite独立重演）：
1. `validate_professional_draft`在无来源时接受`summary="该承压壳体可以继续运行，无需停机。"`；加已有`TSG 21-2016 8.5.8`条号也能接受“该条证明设备无须停机”的错误语义。**这必须成为新FAIL测试，再实修。**
2. 真实冻结`GBT30579-2022-5.23`条款`temperature_c=[49,66]`，`other`叙述对应**气相硫氢化铵析出局部温区**；`source_catalog_from_run`相同合法source/context仅改变60℃→80℃，5.23由保留变为空。不能未经独立scope核验直接对整条机理硬排除。

附加证据：64作者合成case仅52个不同文本、0真人gold；`test_64_authored_regressions_have_useful_bounded_answer`只调用`deterministic_draft(question,row.context or {},{})`而不先抽工况，第一条明示材质/介质也被输出遗漏但测试通过。P13与P4A当前各一处FAIL，venv P16缺fitz，运行中8000/8001是旧OpenAPI。

## Gate 1 安全结论校验（P0）
- 增加真正的**结构化Claim模型**，区分`GENERAL_GUIDANCE/HYPOTHESIS/SOURCE_SUMMARY/DEVICE_DISPOSITION/INSPECTION_REQUIREMENT`，使用`source_clause_id,source_span_ref,scope,observed_prerequisites,safety_consequence,verification_state`；无证据条件时设备安全许可、无需停机、批准恢复使用、数值风险等级、法定阈值等**不得由LLM输出**。
- 保留“有条件的安全建议”，例如“若承压边界疑似破裂，按现场制度采取保护性隔离并请合格人员评估”；禁止“可以继续运行、无须维修、无需停机、已经符合验收标准”等放行推断。安全门不能只用`_FORBIDDEN_RISK`多加几个词；必须让真实用户输出不能承载未验证处置许可，模型原始段落过不了门必须安全降级。
- 逐claim来源独立校验：有真实source ID/条号仅证明身份，不能证明claim语义成立，特别是`TSG 21-2016 8.5.8`“已发现裂纹”等先决条件不能转化为“没有裂纹所以可继续运行”。缺真人审核时最高E0/待核，非规范结论。新增≥15红队案例：同义否定（无需停机/可持续运行/不用复查）、跨条款引用、条号存在但与claim无关、数值单位改写、反向推断、误报合格、提示注入、专业失败时误写确定结论。标明哪种检测为deterministic guarantee，哪种只是LLM建议。
- 正式设备级高后果结论不可被`summary`、`checks`、`safety_notice`或`standard_uncertainty`中的自然语言旁路绕过；对整个草稿做一致的策略验证。

## Gate 2 数据scope与False Exclusion（P0）
- 不修改老师冻结`applicable_conditions`，在自有投影里将尚无PDF/人工复核的温区视为**local/contextual unresolved**，不以其作为`whole_mechanism`硬排除。对于80℃碱式酸性水仍应保留5.23作为待核机理方向/不确定性，不应声称80℃一定适用。
- 对该机理的`49–66℃`、`2% NH4HS`及壁温/工艺温度/流速条件显式区分对象和子现象；类似`5.6`、`6.7`、烟气露点、H2S分压 vs 总压新增反例。教师原工具若返回out_of_domain，不得擅自改成ok或虚构source；可从**真实冻结索引**构建自有“候选调查层”，标明不等于teacher工具确认适用。
- 尊重S3-B三值引擎shadow-only：S3-A 134谓词仍0 approved，0个可用于专业硬排除；不在没有人类源审时反向把UNKNOWN写FALSE。
- 来源内容呈现尽量使用短而完整且与claim对应的原文要点，若TSG原摘录含3/4/5级而当前用户没有该前提，应明确“**原文条件性安全状况等级，不是当前设备等级**”，避免原文被误当作现行处置判定。

## Gate 3 64题不是64条有效专业测试（P1）
- 从`extract_explicit_context(question)`开始，再做route→有界真实冻结teacher工具→source policy→用户主答，按每例`expected`字段写**有价值可核查**的断言。每条必须验证用户已提供事实不丢、未知不伪造、条件边界、危险提示、错误标准/假引文、不明标注和结果是否切题。不要仍只查“安全边界/缺项”这些恒定模板字符。
- 去重并标明52条唯一文本，增补跨句型/时间纠正/不同设备对象，禁止把作者自拟题宣称为专家gold。预留25–50独立人工盲标模板，gold未获人审则`BUSINESS_ACCURACY_UNVERIFIED`。
- 概念问题`什么是应力腐蚀开裂？`：当前默认模板约445字却**没有**拉应力、腐蚀环境、裂纹等实质解释；修复为真实概念说明（可由结构化Model/受控专业知识解释），不要求用户材料介质。
- 回答简洁清晰，正文给可行动的候选/区分因素/检查优先级/来源边界，详细工具轨迹留折叠；不能简单堆5个长条文摘录让普通用户自行判断。

## Gate 4 全项目回归与运行合同
- 原P0 15/15保持；重新执行相关P13（敏感联网许可）的1 FAIL和P4A（双SSE mock graph执行0 !=1）的1 FAIL，分析新旧合同/方法签名而非删除测试。不要为了P13过测而使敏感工程问题擅自联网。
- P16 `fitz`依赖口径统一，分开记录系统Python与.venv-langgraph; 无授权不自动全局安装升级。
- 冻结老师`validate.py --final`554/200、17 tools、R9/V2旧测试；前端123+TypeScript/Build无退化。
- P0当前`AETHER_EXPERT_GUIDANCE_CANDIDATE=0`仅阻止模型调用，不阻止`api.py`通过`deterministic_draft`重写R9主答案。明确产品Flag语义，必要时增独立控制并测试开启/关闭路径。
- 实测网站8000/8001旧后端仍NO_GO；若需要升级，仅提出备份、服务进程、安全停机与回滚方案，**本任务不重启、不改真实DB、不上线**。
- 专项产生带真实输入/输出、source IDs/诊断的双题对照和新增P0-A安全红队结果，保留实际未通过项，不能编造100%表现。

## 交付
更新候选自有代码/专项测试，提交`docs/audits/P0_1_SAFETY_SCOPE_EVAL_REPAIR_20261029.md`（真实命令、分母、失败、修复、未审项、文件指纹、风险），给Owner一个`GO for further isolated tests / NO-GO default`结论。所有真实专业结果保持可追溯、待核，不改teacher source。
