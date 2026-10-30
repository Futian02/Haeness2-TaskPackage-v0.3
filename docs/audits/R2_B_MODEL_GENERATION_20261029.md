# R2-B2 专业模型生成适配审计

日期：2026-10-29  
状态：`MODEL_ADAPTER_IMPLEMENTED / MOCK_TESTS_PASS / LIVE_PLANNER_NOT_RUN / OWNER_INTEGRATION_REQUIRED`

## 文件边界

本Lane只改 `backend/deepseek.py`、`tests/test_r2_model_generation.py` 和本报告。未改 `professional_answers.py`、API、Graph、SQLite、upstream、前端或在线服务。未发起真实模型请求。

## 可接入接口与预算

### 模型规划器

```python
plan_professional_investigation(question, context, profile=None) -> GenerationResult
```

- 一次结构化JSON请求，`max_tokens=600`、网络超时 `min(config.timeout, 15s)`。
- 规划最多3步；程序侧应调用 `validate_professional_plan` 约束字段和教师只读工具白名单，模型不直接调用工具。
- 模型返回截断/网络失败/坏响应时，API应记录planner失败并降级到既定本地检索计划；不把回退算作模型计划成功。
- 输入仅有界问题、当前设备槽位、槽位来源和未知枚举；不发送附件、PDF全文、SQLite历史、秘密或任意context键。

### 专业解释与主回答

```python
generate_professional_explanation(question, context, source_catalog, profile=None) -> GenerationResult
```

- 一次结构化JSON请求，`max_tokens=1800`、超时不超过30s；DeepSeek关闭隐藏reasoning以保留可见输出预算。
- 根据请求区分概念解释与设备调查。概念题（含“什么是应力腐蚀开裂”）明确要求直接解释拉应力、敏感材料、腐蚀环境的协同作用及裂纹萌生/扩展，不要求用户先填设备参数；不得把概念解释冒充现场诊断。
- 设备问题要求提出条件性机理、竞争解释、区分它们的检查/观测方向和有针对性的缺失信息，而不是只重述确定性模板。
- 输出与B1当前结构化契约兼容：`summary`、`possible_directions`、`claims`、`checks`、`missing_info`、`safety_notice`、`standard_uncertainty`、`risk_level=null`、`device_diagnosis_confirmed=false`、`device_disposition="UNKNOWN"`。
- 每个 `SOURCE_SUMMARY` 必须绑定当前来源ID、精确原文片段、scope、prerequisites；模型仅看到当前source catalog中每条最多400字符的excerpt，完整支持性判断由服务端B1 source/claim gate依据原catalog执行。
- Provider的原始JSON不能直接渲染；调用方必须先用B1 `validate_professional_draft` 校验整个结构和每项claim，再用B1 renderer渲染。校验失败应记录有限错误码，回退到确定性一般指导，不可将模型候选记为通过。

## 修改与实现要点

- `generate_professional_explanation` 保持旧函数名和位置参数，未调整API签名。
- 只从 `context` 允许列表提取工况字段，字符串限长；不传任意额外context键。
- 标准来源限制最多8项、每个精确excerpt最多400字符；因此不是把完整收费标准或章节上传到模型服务。source ID存在不等于内容语义支持，后续由B1 Gate复核。
- 明确GENERAL_GUIDANCE / HYPOTHESIS / SOURCE_SUMMARY逐claim分型；概念性知识可无来源，但不能生成标准编号或设备状态许可。
- `finish_reason=length` 等Provider错误沿用 DeepSeek typed errors，不转为空成功。

## 本地Mock验证

命令：

```powershell
`$env:DATABASE_URL = Join-Path `$env:TEMP 'r2-model-test.sqlite'
.\.venv-langgraph\Scripts\python.exe -B -m unittest tests.test_r2_model_generation -v
```

B2原专项：`tests.test_r2_model_generation` 5/5 PASS；与DeepSeek adapter 合计7/7 PASS（Fake Provider）。主Agent在B1交付后独立复跑：`tests.test_r2_safety_claimgate tests.test_r2_model_generation tests.test_deepseek_adapter` **12/12 PASS**。覆盖SCC概念无设备参数直答、专业请求上下文最小化、source excerpt 400字符上限、损坏/虚假来源及设备许可由B1 gate拒绝、截断的类型化错误、无效JSON拒绝及Owner安全绕过。无真实Planner/provider调用、无新增费用请求。

## 集成回归观察

初次B2与P0联合回归时曾观察到案例A来源断言失败（当时B1同步修改中的瞬态）；B1最终复核已证明真实 `GBT30579-2022-5.23` E0条件来源仍能通过其ClaimGate/renderer测试。本次主Agent重跑当前 `tests.test_p0_expert_guidance` 的共享23项集时仍有4 FAIL、2 ERROR，涉及其他窗口更新后的API capability字段、context medium样本/接口、R9 fixture与P0 API合同，不属于B2权限；B2没有修改这些文件。故不把历史问题或Mock测试外推为P0全链PASS。

## 尚未验证与接口交接

1. 真实模型规划与执行端到端尚未发生；真实专业生成的综合准确性、Recall和用户帮助度未验收。
2. API的规划失败回退、生成失败安全回退、请求预算计数需由E集成并测试；B2没有编辑 `backend/api.py`。
3. source catalog的真实性、条款相关性和条件适用范围由B1/C/A候选来源管线校验；本模型函数只负责将当前run有限来源交给模型。
4. 无人工专家Gold，不能据此宣称专业模型验收通过。

最终状态：`LOCAL_MOCK_PASS / MODEL_CANDIDATE_ONLY / NO_LIVE_PROVIDER / NO_PRODUCTION_CUTOVER`。
