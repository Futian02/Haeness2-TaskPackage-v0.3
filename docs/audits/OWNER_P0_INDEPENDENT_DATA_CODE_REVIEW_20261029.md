# OWNER｜P0专业回答与数据/检索独立审查（2026-10-29）

**审核裁决：P0_TARGETED_ACCEPTED / DATA_APPLICABILITY_NO_GO / REAL_MODEL_SAFETY_GATE_FAIL / WHOLE_SUITE_NO_GO / LIVE_BACKEND_STALE。**
本轮只读源文件、源码与先前报告，执行隔离命令和反例测试；**未修改**现有 P0 源码、教师正式数据、人工签字、真实SQLite或运行进程。原 P0 的 Codex 验收报告不是本报告的自动结论。

## 1. 可证实的进步
- `tests.test_p0_expert_guidance` Owner独立执行 **15/15 PASS**（约18秒）。真实冻结3工具、临时SQLite/FastAPI/SSE和主可见答案在A/B两题上有实质改善。
- A题（不锈钢+碱式酸性水+60℃）context snapshot含原始材料/介质/温度，5.23为E0来源候选；4次工具调用、主正文不再重复要求已给工况。B题多角度3次检索，能将TSG 21中机械损伤/表面检测/综合评定列为条件性候选，零来源时仍有一般工程安全调查建议。答案比此前模板拒答有用，但“源真实”不等于“适用于设备”。
- P0新增结构化Model计划/回答与默认关闭控制（只限制模型调用）；早前DeepSeek真实生成仍未足够达到原生工具/业务正确性门槛。
- 官方源`upstream/05_提交区/clauses.jsonl` SHA-256 `a8151797ba15a6a7452dd83aaec9fab4c0a815724ca45062eb1e2bac7b4d49ef` 与此前相同，teacher数据未动。上游RBI Excel的既有Git脏状态依旧，不归因本轮。

## 2. P0缺陷与必要修正（有实测证据）

### P0-A 危险输出绕过校验 — BLOCKER
在`backend/professional_answers.py::validate_professional_draft`的当前逻辑中：
- Owner实际执行`validate_professional_draft`的合法schema输入：`summary="该承压壳体可以继续运行，无需停机。"`、`source_catalog={}`，**被接受**，没有任何来源或设备完整性证据！
- `summary="TSG 21-2016 第8.5.8条证明该设备无须停机。"`，仅提供正确标准号/条号的 source_catalog 时也**被接受**，即使条文实际限定裂纹、检验评定等条件，完全不支持“无须停机”。
- 根因：`_FORBIDDEN_RISK`是局部正则（检查`允许|可以|批准` + `复机|恢复使用`等），漏掉“可以继续运行”“无需停机”“无需检验”等同义决定；`_validate_content`仅验证条号在source列表，不能验证每个claim的前提/结论蕴含；summary/checks传入的是**整个source_catalog**而非逐claim归属。
**要求**：输出安全许可/否定风险/复机的决定采用结构化`device_disposition`不可由LLM提交且强制unknown；不以加几条正则作为唯一修复；每个涉及规范的claim必须绑定`source_ids`及其确切scope/observed prerequisites，P0模型只能候选建议。新增同义绕过、无前提引文、引用张冠李戴、否定和隐含许可测试。未经人工/结构化必要证据门禁，禁止模型给设备安全状态/停复机批准。

### P0-B 温区子条件误扩张为全机制硬排除 — BLOCKER
正式`GBT30579-2022-5.23`的`applicable_conditions.temperature_c=[49,66]`，`other`明确记该温区关联`硫氢化铵从气相析出`局部现象，不能直接理解为酸性水腐蚀存在与否的全局必要温区。S3-A审计也标此scope unresolved。
- Owner用**同一冻结canonical index**和完全相同的合法source，调用`source_catalog_from_run`，用户温度60℃→保留5.23，80℃→**直接不展示5.23**。这不是证明80℃确实适用，而是未经scope核准就硬排除整个机理的风险。
- 冻结教师工具本身也含`_temperature_ok`硬过滤（注意80℃调用返回`out_of_domain`且source数组仍可能列出关联ID，不能当成适用结果）。
**要求**：P0新来源投影不得依据未经PDF/专家核验的温区做全机理硬排除；先以`POSSIBLE_WITH_CONDITION_UNKNOWN`并解释本温区对应的**什么局部现象**，不能偷偷放大/缩小原标准适用范围。教师冻结工具不改；S3-B有效三值引擎可先shadow annotations，S3-A 134 candidates/15 pilot中0 approved，不能作为硬必要条件。人工修复源范围时保留原JSONL和差异证据。

### P1-C 64条“通过”无效地估计答案质量 — BLOCKER FOR QUALITY CLAIM
`evals/p0_expert_guidance/cases.jsonl`：64条均`AUTHOR_SYNTHETIC`，**52条唯一文本**，0个人工expert gold。分组16+16+8+8+16。
`test_64_authored_regressions_have_useful_bounded_answer`实际传`row.get('context') or {}`到`deterministic_draft`，**不进行问题中工况抽取**，也没有调用检索工具/实际model/后台；只断言risk_level=null、未出现几个词、出现“缺项及原因”“安全边界”。
Owner实际复现其第一条包含300系列不锈钢、碱式酸性水、60℃的问题，直接模板输出**没有材质、没有介质**，该“64条正确”测试仍通过。
**要求**：修订评测脚本：每条`extract_explicit_context→route→真实三工具→source filtering→visible answer`，明确gold input facts与应保留字段，决不能把已给工况无故丢掉；每条至少比较关键事实保持、危险信号/无依据许可、来源准确性/错误相关性、内容价值，且独立人工抽样gold与developer synthetic分开，避免64条合成句式重复当64独立问题。

### P1-D 固定模板泛化缺口
默认`AETHER_EXPERT_GUIDANCE_CANDIDATE=0`只关闭模型Plan与Explain，不阻止`api.py`中的`professional_request`对旧Graph结论进行`deterministic_draft`替换，因此“关闭candidate”并**不完全恢复旧R9输出行为**。需要明确哪部分允许默认on，哪部分必须独立flag，否则回归责任难区分。
实际测试`deterministic_draft("什么是应力腐蚀开裂？", {}, {})`结果泛化模板约445字，却**没有**拉应力、腐蚀环境或裂纹等核心概念解释；这不能满足用户期望的广义专业概念回答。
**要求**：路由+知识任务族分别测试，默认off须明确是否仍允许安全的F1 general explanation及为什么；“概念解释”应给实质原理，不使用没有上下文就泛化模板的空回答。确实相关的标准依然独立核实。

### P1-E 证据片段与误召回过滤靠词法，不是专业证明
`source_catalog_from_run`以条款ID/标准号/印刷页验证身份，又用“标题含词”、部分raw_text regex排除误召回。只覆盖已见的“辐照脆化”特例，不是通用对照机制；可能误排关键危险，也可能让引用真但不支持的内容通过。
B题公开答案打印TSG 21-2016 8.5.8原摘录含“定为3级、4级或者5级”，虽然外层标注不代表适用，也容易被非专业读者误读为给出的本机风险等级。展示时应明示“**条款原文中的条件性等级，当前设备未满足/未验证前提，不能套用**”；尽量抽离与问题相关的局部短摘录，并标注来源核查层级。E0文段不应叫“已审定标准证据”。
- 缺少独立专家支持/反例gold；不能以命中数增加当Precision/Recall提高；应比较A/B、近义词、负例、跨专业意图和确实无标准覆盖等。

## 3. 回归实测
- 独立P0：`python -B -m unittest tests.test_p0_expert_guidance -v` **15/15 PASS**。
- 独立P4A：`python -B -m unittest tests.test_p13_search_service tests.test_p4a_api_safety -q` → 19项**1 FAIL**，`test_two_simultaneous_streams_execute_once_and_both_subscribe`中原mock Graph.run调用0，期望1。原测试`SlowGraph.run(..., run_id,on_event)`不接受当前Graph新参数`professional_mode/professional_plan`，疑似接口签名失配；先审日志/事件终态，再决定补兼容adapter或修正反映新合同的test double，不能直接删/skip。
- 独立P13：`python -B -m unittest tests.test_p13_model_reliability -q` →14项**1 FAIL**，`test_web_search_stays_off_by_default_and_sensitive_outbound_requires_second_opt_in`对web_search_enabled敏感业务预期一次搜索，实际0。先确认现在的`web_mode`与安全同意约束，不能为了让测试过绿而偷偷联网/对外发工程信息。
- P16-A venv缺fitz属于测试环境差异；系统python独立pytest5/5的历史结果不代表当前venv全量发现通过。
- P0 Codex原记录最新`392 tests=386 PASS+2 FAIL+1 ERROR+3 SKIP`，此整仓分母是**Codex报告口径，非Owner本轮复跑全量**。
- 运行中8000/8001旧Python后端未加载当前P0，不能因为本地FastAPI和临时SQLite通过就宣布用户网页实际已修复。未重启在线服务/写正式数据库。

## 4. 数据工程现状与合理次序
正式554=472 RBI + 82 DM，工具17/17、数据/轨迹合同通过只是结构门禁，不能证明机械通用问答范围。当前82条八段式内容非空，但medium structured26/82、温区23/82、pressure0/82、verified_by0/82。系统有词法召回及来源匹配、应用层过度使用局部硬阈值，造成既有漏召回/假相关风险。
S3-A：82条source manifest、15条pilot、134条proposed predicates、61 synthetic反例，0 approved/0真人gold。S3-B：54合成测试PASS，保守导入110条仅作为contextual annotation、24条隔离，0必要/排除已获准。**这是正确的隔离方向**；不要为了提高回答率直接把134条机器候选当硬规则或扩入冻结official JSONL。
核心下一步：
1. **P0.1 Safety ClaimGate：** 结构化设备处置许可安全门，逐claim来源+条件蕴含，模型无权限宣布安全可运行/自行复机；先红队修复已实证漏洞。
2. **P0.2 Data scope：** 5.23、5.6、6.7等高风险局部温压条件先逐源审阅scope，禁止用schema外推全机制硬排除；字段不足则UNKNOWN。
3. **P0.3 Expert evaluation：** 64合成case全真实管线，并建25–50人工独立盲评专业正反例；衡量关键危险召回、误硬排除、无依据断言、来源相关、有效调查率和p95/模型成本。不给非人工gold伪精度。
4. **P0.4 Live runtime：** 先修P13/P4A接口回归，再制定带备份/回滚/版本握手的8000受控切换；本轮不做。
5. **知识覆盖矩阵：** 将损伤机理(RBI/DM)与压力容器壳体维修验收规范、通用工程原理、设备法规核查四层分开，合法授权独立来源入索引，不生成“标准条款”。先问题分类和缺口再补数据。

## 5. 当前裁决
- P0专项源码与两例：**ACCEPT WITH CONDITIONS**（改进真实）。
- 结构化专业模型直接用于高后果回答：**NO-GO**（安全门可被绕过）。
- DM机理温区进行硬排除：**NO-GO**（局部温区错误外推）。
- 64条测试用作“专业正确率”：**INVALID CLAIM**（模板/合成/重复文本/0人审）。
- 全量回归/新版线上运行：**NO-GO**（P13/P4A/P16、旧后端）。
执行移交建议见`docs/CODEX_P0_1_SAFETY_SCOPE_REGRESSION_FIX_20261029.md`。
