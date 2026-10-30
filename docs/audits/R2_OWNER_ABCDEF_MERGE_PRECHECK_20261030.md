# Owner R2｜A–F合并前独立核查与G修复门（2026-10-30）

**状态：A–F_DELIVERABLES_LOCATED / G_INTEGRATION_FIX_ALLOWED / CURRENT_ISOLATED_UI_NO_GO / PRODUCTION_NO_GO。**
本轮不修改任何应用代码、教师源数据、生产SQLite、运行进程、密钥和业务人审。以当前磁盘读证和独立unittest复跑为依据；上一轮单模块“PASS”不可取代新的集成测试。

## A–F交付完整性

| Lane | 交付/真实位置 | 当前事实与限制 |
|---|---|---|
| A1源台账 | `docs/data_quality/R2_A1_SOURCE_AUDIT_20261029.md`、`knowledge/applicability/candidates/a1_source_audit/` | 554条唯一ID，72?不是：472 RBI+82 DM；PDF存在但原文人审核0，正式verified_by 554空 |
| A2派生检索 | `docs/data_quality/R2_A2_RETRIEVAL_20261029.md`、`knowledge/retrieval/r2_candidate_v1/` | 554条轻量源；64合成query的Top5非空由2→8，实际覆盖仍弱；无人工Gold；Graph尚未接入新索引 |
| B1/B2 | `docs/audits/R2_B_CLAIMGATE_REPORT_20261029.md`、`docs/audits/R2_B_MODEL_GENERATION_20261029.md` | B1 62作者安全攻击样例阻断，B2 mock生成接口；真实LLM/语义支持未验收 |
| C | `docs/audits/R2_C_GRAPH_RETRIEVAL_20261029.md` | Graph词法相关性，9项新测试，跨图100项报告PASS；尚未对接A2审核索引 |
| D | `docs/audits/R2_D_CONTEXT_MEMORY_20261029.md` | 32定向PASS，raw span/温压对象分离；匿名新设备scope API绑定未完成 |
| E | `docs/audits/R2_E_API_RUNTIME_20261029.md` | R2 health/flags/指纹、Idempotency-Key、shadow脚本、27项报告PASS |
| F | `docs/audits/R2_F_FRONTEND_E2E_20261029.md` | Vitest128/128、TS/build历史报告PASS，真实Edge尚未通过 |
| QA | `docs/audits/R2_QA_BROWSER_E2E_20261029.md` | mock协议9/9；旧shadow+disk source fingerprint漂移时fail-closed，**未发送真实浏览器Run** |

QA此前写“A报告缺失”是**路径/交接索引问题**：A的报告在`docs/data_quality/`而不是`docs/audits/R2_A_*.md`。请让G按以上真实路径核对，而不是要求A重做。

## 当前Owner实测
- `python -B -m unittest tests.test_r2_safety_claimgate tests.test_r2_model_generation tests.test_r2_graph_candidate tests.test_r2_context_memory -q` → **36/36 PASS**。
- `python -B -m unittest tests.test_r2_api_contract tests.test_r2_browser_e2e tests.test_p4a_api_safety -q` → **25/25 PASS**。
- `python -B -m unittest tests.test_p0_expert_guidance tests.test_r9a_industrial_candidate tests.test_p12_context_flow -q` → **48项、4 FAIL、2 ERROR**。该组不能宣称全绿/放行。
- 最新冻结老师`upstream/05_提交区/clauses.jsonl` SHA `a8151797ba15a6a7452dd83aaec9fab4c0a815724ca45062eb1e2bac7b4d49ef`未变。
- 当前源码SHA：
  `backend/api.py=86b1cad97aa5a2154a63889591e9302ee76c53a7fd9d4d5adea04f5aca5aecf7`；
  `backend/professional_answers.py=e5ddf58f4c11fae79dbb78982f7f38801ef42e40dde297d587fad208038e23e7`；
  `backend/context_slots.py=27c91ef8d7062dab0de311f4065860ecb12673433add9a7c05b00c8d4f6afd98`；
  `orchestration/r9_industrial_candidate.py=004c2bd2ca6fefc8d076bd1a311af232987dd8dbbe8bd5e685dc2bd884bfe224`。均与各Lane交付SHA匹配（不代表未来不会变动）。
- Owner独立向B1`validate_professional_draft`提交历史6条无来源设备安全许可/无隐患句：**全部拒绝**（ValueError）。这是已知安全反例PASS，不证明语义语言全覆盖。
- 8000/8001先前报告仍旧服务；本轮短时GET health探测**超时**，无法把当前端口版本记为成功确认或旧版肯定在线。

## 六个P0跨模块失败的原因和正确修复原则
1. `P0-N-01`“什么是应力腐蚀开裂?”：旧测试`actual_teacher_tools_required`，C现在CONCEPT直答0工具。需要判产品合同是否允许**合法直答F1且0工具**（按主合同允许）；若是，更新**场景期望的任务类别及可验证的概念要点**，而不是强迫无意义工具调用。
2. `P0-X-04`“压力是10MPa，所以H2S分压也按10MPa处理。”：旧题库要求保留`medium`但输入没有明确提供介质。D仅解析`pressure_mpa=10`、没有`medium`，并保留`h2s_partial_pressure_mpa`UNKNOWN；不能为了绿测凭用户的推断自动设置H2S分压/介质。修正冻结输入/期望并加反例“系统总压不能等于分压”。
3. `seen_hashes`原先预期52，实际中途两道子例失败导致集合50；不得简单把去重期望改为50，先保证所有64题真正跑到收尾，再查真实输入文本hash去重。
4. `test_health_exposes_separate_model_and_deterministic_guidance_flags`期望`health.capabilities.expert_guidance_candidate`，R2-E接口已经迁至`health.flags.expert_guidance_candidate`（Capabilities代表是否支持，flags代表是否开启）。按**新合同且保留旧功能语义**修接口测试，不要给capabilities伪造flag。
5. 2项隔离API E2E仍硬编码`aetheris-2026-10-29-p0.1`，R2-E合同已升`aetheris-r2.0.0`。首先更新版本断言到统一常量；**必须完整重跑子进程及所有后续断言**，检查真实A/B问答、工具次数、主答、Run终态和SSE，不得只修字符串就宣称E2E PASS。
6. 新的D无名设备`new_object_scope`未被E绑定到persistent scope；补API single-owner适配并测同CID“另一台设备”不会错误继承匿名设备事实。

## 应紧接着做的集成Gate
G0：所有A–F报告/源码SHA重新冻结，停止共享文件变更；更新路径索引，不重跑A。
G1：一个G实施者解决上述6失败，按失败->精确调整合约/实现->全套复测，保留P0老问题A/B现实价值与安全；不得删/skip坏测试。
G2：C接A2只读候选索引的shadow接口或明确DEFERRED并说明A2 8/64仍不足，**不能宣称检索已经全面覆盖**；B1 claim gate与E API真实主答一致。
G3：新版本隔离端口+临时SQLite+不携带付费keys，启动前/中/后统一health源码指纹、前端meta hash与磁盘；若漂移fail-closed。
G4：QA真实Edge 1440x900及390x844普通对话/A/B/SCC/同CID更正/跨CID隔离/版本错误/SSE断线；需有截图、Run ID和脱敏事件序列。
G5：整仓unittest、前端128起点+TS/build、教师554/200/17、真实Provider与真人专业Gold仍单列未完成。只有G0–G4通过才能`GO_ISOLATED_OWNER_UI_TEST`，**永远不得将人审0/50+0 approved写为生产GO**。

建议启动唯一G集成窗口，采用`docs/CODEX_R2_G_FINAL_INTEGRATION_OWNER_GATE_20261029.md`，并补读本报告。G开始后请停止其他窗口同时写shared source；QA可在G冻结后协助只读浏览器采证。
