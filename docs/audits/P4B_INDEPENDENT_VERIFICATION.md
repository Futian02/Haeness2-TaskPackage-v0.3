# P4-B 独立证据核查实施与验收记录

状态：**READY_FOR_OWNER_REVIEW**（未部署、未提交）。本记录仅覆盖 P4-B；RULE_DEMO 仍是确定性规则核验，不宣称真实多模型交叉审核、专家金标准精度或语义蕴含证明。

## 范围与未触碰项

本轮写入仅限：

- `orchestration/evidence_audit.py`
- `orchestration/semantics.py`
- `orchestration/graph.py`
- `tests/test_p4b_claim_verifier.py`
- `evals/p4b_negative_cases.jsonl`
- `evals/p4b_verify.py`
- 本报告

没有修改 `backend/`、`frontend/`、`upstream/`、原始 Excel/PDF、PROJECT_STATE、老师三工具注册/实现/五键协议；未部署、未执行 git add/commit。P4-A并行修改由其窗口负责，本报告不依赖其API变更。

## 实现结果

1. 标准元数据 `standard_code/clause_no/page` 显式输出 `matched/missing/mismatch/unknown`；完整 ID + 本轮 `standard_clause_search` source + 三项必需元数据全匹配才达到来源级 E1。缺失/未知/错值降到 E0、`provenance_status=partial` 并要求人工复核。可选source `version` 若出现冲突也降到 E0。
2. 只读可信 `upstream/05_提交区/clauses.jsonl` 按完整 clause ID 回查原文，输出未改写的 `content_raw`、canonical record SHA-256、canonical printed page/version 与本轮四字段 tool source。canonical ID不存在、原文空或source缺失均 E0；任何规则均不改写官方文本。
3. Skeptic 一方面把当前工具source ID与 canonical 原文重核，另一方面由原始 observations 与工况上下文直接在本地规范库中做第二路词法召回，返回候选条件、页码和哈希。检索不读 Diagnosis 自然语言作为证据；结果明确标 `lexical_only_no_semantic_entailment`，不能提升 E2/E3。
4. Claim kind 收敛到 `source_fact/engineering_hypothesis/equipment_diagnosis/risk_level`，既有 `mechanism_candidate` 做兼容映射。多值现场条件需全部在允许范围才是 matched；交叉/混合值标 `not_sufficient`，缺温度等信息标 unknown；observed_false 与 unknown 不混淆。risk_level 即使有来源条款，仅靠 RBI 单个标签仍 fail-closed 为 E0/unresolved。
5. SSE/evidence_ref新增字段均为附加字段；老师工具返回对象未变。已有 RBI 风险字段的 SSE 脱敏仍由原流程执行。

## 实际命令与结果

| 命令 | 实际结果 |
|---|---|
| `.venv-langgraph\Scripts\python.exe -B -m unittest tests.test_p4b_claim_verifier -q` | **16/16 PASS**；覆盖四态元数据、假标准号/错条款/错页、版本冲突、canonical正文和hash绑定、unknown/false、混合介质/多互斥值、温度未知、risk fail-closed、20案例来源状态与14条负例。 |
| `.venv-langgraph\Scripts\python.exe -B -m evals.p4b_verify` | `RULE_BEHAVIOR_PASS_NOT_EXPERT_GOLD`；20/20既有合成未审案例保持人工复核；14条负向/跨来源冲突case；canonical clauses=554；每个测试fixture模拟1次标准source调用；人工复核比率100%；审计函数样本 P50=0.018ms、P95=0.043ms（单机微基准，不是端到端API延迟）。 |
| `.venv-langgraph\Scripts\python.exe -B -m unittest discover -s tests -q` | **81项：80 PASS，1 FAIL**。唯一失败为下述P3B旧断言与本轮新硬门禁冲突。 |
| `.venv-langgraph\Scripts\python.exe -B upstream\04_接口文档\validate.py --final` | **PASS**：clauses 554/554，trajectories 200/200，终验通过。 |
| `.venv-langgraph\Scripts\python.exe -B -m scripts.check_sources` | **PASS**：19/19 官方来源文件存在。 |

事件入库：全量测试中的 P3B SQLite graph/store 集成测试通过（claim/disagreement/event replay和连续sequence断言），P4B新增字段随claim/reference事件向后兼容。P4B评估脚本不伪造事件吞吐或并发指标；它只报告核验微基准。合成案例均没有专家标注，召回率/精确率不能据此计算。

## 唯一未通过项 / 失败说明

`tests/test_p3b_evidence_audit.py:55` 的 `test_explicit_condition_mismatch_is_not_applicable` 仍期望 `result.grade == "E1"`。该测试传入的合成canonical只有 `clause_id/standard_code/clause_no/page/applicable_conditions`，缺少 `content_raw`、`version`；同轮source也没有原文。P4-B按任务硬门禁记录 `canonical_content=missing` 并返回 E0/unresolved/人工复核。为满足旧断言而填充假原文或放松“原文缺失必须E0”会违反本轮验收约束，因此保留该失败，不改P3B既有测试、不作伪兼容。

建议 Owner 在审查时决定是否更新这条过期合成断言：应把期待改为 E0，并另用带真实 canonical `content_raw` 的 fixture 验证来源级E1。其余P3B测试正常通过。此一项是明确scope冲突，不是未报告的绿灯。

## 限制与下一轮建议

- 条件匹配仍是结构化词面比较，不能判定标准文本是否蕴含具体设备诊断。E2/E3必须留给独立人工核实或经过独立评测的语义模型流程。
- 当前第二路检索为确定性词法搜索，主要价值是发现需要复核的遗漏候选，不保证穷尽召回，也不等于“已反证”。
- 下一轮由Owner先裁决上述旧测试断言；随后增加有专家签署的评测集、人工审核状态流转与审计身份/时间，不要把合成测试集包装为专家准确率。

**Owner审查门禁：READY_FOR_OWNER_REVIEW。**
