# P6-C 人工审核 / Gold 规范交付证据

状态：**READY_FOR_OWNER_REVIEW**。本轮仅新增协议/schema/校验器/测试；无真实人审、无签名、无专家Gold、无上游写入。

## 已读输入与事实基线

- `docs/audits/P2_RBI1_LANGGRAPH_EVIDENCE.md`：13条GB/T 26610.1-2022候选由P2脚本匹配并按印刷页/条款/引文核对；候选副本U/V抽取人与复核人均空。原始RBI表472条；正式`clauses.jsonl`合计554条。P2的机器匹配/页面核对不是签核。
- `docs/audits/P4B_INDEPENDENT_VERIFICATION.md`：20个未审核合成case+14个负例是规则行为测试，不是专家金标；E2/E3需要独立人工审查。其全量测试历史为80通过/81项，存在一项与新E0缺证门禁冲突的旧P3测试，不能伪写全绿。
- `docs/audits/P5C_EVIDENCE_UI_E2E.md`：真实Edge/API/SSE/SQLite证明事件和E0/E1可追溯呈现；Claim仍`unresolved/requires_human_review`，不代表工程结论或损伤机理获专家认可。
- `docs/audits/OWNER_P5_INDEPENDENT_REVIEW_20261028.md`：13条标准摘录不定义特定设备失效可能性/后果/风险级别；G–J留空；真实抽取人与复核人签署尚未获得。不得把RULE_DEMO称为多LLM。

## 本轮变更（仅P6-C允许范围）

| 文件 | 用途 |
|---|---|
| `docs/P6C_HUMAN_REVIEW_PROTOCOL.md` | 角色分离、E2/E3边界、脱敏case、盲评、指标、仲裁及13条真人签署SOP |
| `evals/p6c_review_schema.json` | Draft 2020-12 schema，区分expert assessment、现场事实确认、摘录责任 |
| `evals/p6c_review_template.json` | 明确`template_only`占位记录，identity=false、signature=null、draft |
| `evals/p6c_validate_review.py` | stdlib轻量结构/签署门禁，不创建人审证据 |
| `evals/p6c_test_review_schema.py` | 6项schema/角色分离/未签署拒绝门禁检查 |

**未修改** `backend/`、`orchestration/`、`frontend/`、`upstream/`、教师三工具/五键合同、Excel、PDF、正式JSONL；未调用`--apply`、`convert.py`或部署服务。未新增或填充真实身份数据。

## 命令与实测

最初测试命令误写为 `..\.venv-langgraph\Scripts\python.exe`，PowerShell提示路径不是cmdlet；随后更正到项目venv。首次更正后发现schema JSON有一处括号语法错误（行47），修正schema后复跑如下：

```powershell
.\.venv-langgraph\Scripts\python.exe -B -m evals.p6c_validate_review --check-template
# P6C_TEMPLATE_GATE_PASS (schema parsed; placeholder remains unsigned; no gold record created)

.\.venv-langgraph\Scripts\python.exe -B -m evals.p6c_test_review_schema -v
# Ran 6 tests in 0.001s; OK

.\.venv-langgraph\Scripts\python.exe -B -c "import json; from jsonschema import Draft202012Validator, FormatChecker; from pathlib import Path; p=Path('evals'); s=json.loads((p/'p6c_review_schema.json').read_text(encoding='utf-8')); t=json.loads((p/'p6c_review_template.json').read_text(encoding='utf-8')); v=Draft202012Validator(s,format_checker=FormatChecker()); errors=list(v.iter_errors(t['records'][0])); print('jsonschema_template_errors=',len(errors)); [print(e.message) for e in errors]; raise SystemExit(bool(errors))"
# jsonschema_template_errors= 0
```

六项定向测试包括：schema parse/必需字段、unsigned draft结构可用但不得verified、身份/签名缺失关闭、现场用户确认不可替代专家审查、E2/E3角色限制及`unresolved`保留、模板不含已签Gold。JSON Schema由当前隔离venv的`jsonschema` `Draft202012Validator` + `FormatChecker`实测通过模板记录校验。脚本的范围是形状/字段门禁；它**不**验证外部签名密码学、专家资质、事实真实性或条款语义。

## 结论、阻塞与建议

- schema和测试模板通过；当前没有任何review记录处于`verified/adjudicated`。这符合无真人输入的预期，不是缺省通过。
- P2的13条摘录继续等待真实抽取人与独立复核人逐条签署。执行原表任何写操作前按协议使用`--check`，仅经Owner书面批准并取得签署后讨论`--apply`。
- 首批建议10–20个可独立判定、最小脱敏case，至少双人盲标，冲突交第三人仲裁。20+14 synthetic数据只作开发负例/回归；不能作为专家Gold、准确率或真实质量增益报告。
- Owner需指定受控身份核验与签署存储后，方能把本schema挂接实际审核工作流；当前未修改API、数据库或UI。

**验收状态：READY_FOR_OWNER_REVIEW；无部署。**
