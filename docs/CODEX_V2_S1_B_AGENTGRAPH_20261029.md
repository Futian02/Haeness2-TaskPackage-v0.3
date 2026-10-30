# CODEX S1-B｜LangGraph模型规划/工具调用/证据门禁候选
项目根：D:\作业\竞赛\计算机设计智能体\机械智能体
性质：**独立新图实现与离线验证，不允许替换当前默认Graph、部署/调用真收费API**。
开工先读`AGENTS.md`、`docs/PROJECT_STATUS_CURRENT.md`、`docs/AETHER_V2_REQUIREMENTS_ARCHITECTURE_20261029.md`、`docs/data_quality/DM_APPLICABILITY_ROOT_CAUSE_AND_REFORM_20261029.md`、`docs/TEACHER_QA_CONSTRAINTS.md`、原教师工具接口/Schema；再看`orchestration/r9_industrial_candidate.py`、`orchestration/p6_parallel_audit.py`、`orchestration/semantics.py`、`app/runtime.py`、`backend/deepseek.py`与测试。以本机LangGraph 1.1.2 Python API为准。

## 独占可写
新建`orchestration/agentic_v2.py`、`backend/agentic_provider.py`、`tests/test_v2b_agentic_graph.py`、`evals/v2b_professional_cases.jsonl`、`docs/audits/V2B_*.md`；必要时新建`orchestration/agentic_contracts.py`。不得编辑现有`r9_industrial_candidate.py`、`backend/api.py`、`backend/store.py`、`orchestration/intent.py`、`frontend/**`、`upstream/**`、.env、真实DB或P16审核签章。绝不把新增功能冒称已在默认API上运行。

## 必须实现的结构
1. 新StateGraph：prepare_case→model_plan→policy_validate→execute_tool→source_ground→candidate_conditions→reflect→（有限再计划/两路复核）→claim_gate→report。允许稍简但须每一个节点职责可审计，状态中保留原始事实、真实工具调用、证据、成本与错误。
2. 使LLM planner负责**下一步调查目标/查询改写/工具选择/取舍**；实现可注入structured planner接口，使用Pydantic JSON schema/bounded tuples，默认mock/fake，不能仅把旧`_selected_tools`换个名字。
3. 执行器仍是**冻结的原版三工具**`damage_mechanism_query`,`rbi_lookup`,`standard_clause_search`。通过`app.runtime`的受控只读adapter调用；工具名/参数类型、范围、枚举、时间/重试、去重在模型输出之后**独立确定性校验**；工具响应必须校验五键`status,in_domain,result,source,message`及来源clause_id存在、标准白名单、hash相符；禁止模型引入第四工具。
4. 用户只给“某换热器发现裂纹”时，`damage_mechanism_query`缺材料/介质不能合法调用，允许用标准检索展开可疑机理类别、列出区分条件和补测优先级，`status=exploratory`，绝不把模型推断代填材料、介质或风险等级。用户明确给了条件时才根据官方枚举调用DM工具，非枚举词只能文本检索而不是随便改映射。
5. 支持假设对照/反证：每个claim有`source_ids`,`support`,`contradictions`,`unknowns`,`conditions`,`evidence_level`,`applicability`。不存在专业证据的LLM建议不得升级。对同一标准返回的宽相关候选按SUPPORTED/POSSIBLE/EXCLUDED/NOT_ASSESSED区分；如果自有条件层还未建好，应给UNKNOWN、待证，不能偷偷编硬阈值。
6. Auditor对引用/字段/来源一致性验收；Skeptic对缺条件/反例/错误材料/分压目标/错误设备环境提问。可用模型注入接口，但不要宣称同一模型不同prompt就构成真人交叉签名；对分歧fail-safe保留为人工待核。
7. 维持基线8 tool attempts、3 investigation、2 review retries，设置总LLM请求/Token/截止超时预算、明确budget exhausted返回部分完成状态。事件驱动重放时不可双调用/重复提交；保持run_id/thread_id上下文。为每一步产出`public_rationale`、`public_tool_summary`、`source_ids`和审查结果供C投影，禁止输出LLM隐藏CoT。
8. RULE_DEMO仍由原R9承担；V2由feature flag后续接线。真LLM100组老师指标独立于本轮mock代码测试，**无授权不读取/使用任何个人key、不得产生外部计费**。

## 最低验收示例（本地fake）
- 完整工况碳钢+湿硫化氢+110℃换热器：候选有支持/缺条件，不把燃灰腐蚀当确定结论；
- 裸问题“换热器发现裂纹”：至少可基于词面/标准工具给限定调查方向，不能伪造材质介质；若真没检索到来源说明未命中而非强答；
- HCl95℃管道与烟气露点：无烟气证据只能POSSIBLE/NOT_ASSESSED，不能SUPPORTED；
- 明确设备风险L1-L4但缺完整PoF/CoF数据：结论risk_level=null，给具体缺项；
- 模型推荐不存在teacher工具、非法medium、带提示注入JSON、跨会话source ref：执行器拒绝并产生可审计事件；
- 模型规划反复绕圈：预算上限阻断；失败和重复回放不发生工具副作用（冻结工具均只读）；
- reviewer分歧：有公开冲突说明，不输出“复核已通过”。
形成≥30正/负/未知/恶意候选用例、每条gold至少有预期状态与来源假设，单元/E2E TestClient fake可复现。不得把自造gold当人类专家真值或工业正确率。

## 交付
给Owner独立`docs/audits/V2B_AGENTIC_CANDIDATE_REPORT_20261029.md`：Node图、参数/状态schema、工具attempt总数、LLM mock调用数、候选证据样本、可复现命令、通过和失败、对比旧R9的可解释优缺点、需S2接线接口。**生产默认路线不得变，所有结果CANDIDATE_ONLY。**