# P7-C Schema Parity / Authority Contract

状态：**READY_FOR_OWNER_REVIEW** / `SCHEMA_ONLY_NOT_HUMAN_VERIFIED`。本轮只对结构校验规则做了差分一致化；没有生成任何真人签署、专家结论、E2/E3或Gold记录。

## 实施变更

- `evals/p6c_review_schema.json`：补齐 extraction attestation 的 reviewer-role 与 attestation-role 一致约束；site confirmation 强制 `site_data_confirmant`；补充RFC3339时间字符串形状及nullable非空引用字段约束。
- `evals/p6c_validate_review.py`：stdlib校验与Schema对齐必需/额外字段、reviewer嵌套字段、角色、日期、SHA-256、状态、数组唯一性及verified-shaped字段。文档、CLI帮助和输出均明确 `require_verified=True` 只是形状预检，绝不是身份/签名认证或E2/E3/Gold授权。
- 新增 `evals/p7c_schema_parity.py` 与 `evals/p7c_test_schema_parity.py`：77条带 `SYNTHETIC_TEST_ONLY_NOT_HUMAN_REVIEW` 前缀的正负fixture交叉运行Draft 2020-12 Schema与stdlib校验器。
- 新增 `evals/p7c_synthetic_authority.py`：只供内存单测使用的合成mock；固定返回未认证，明确无密码学/身份验证能力、无持久化，不能被生产authority注册。
- 更新 `docs/P6C_HUMAN_REVIEW_PROTOCOL.md`：增加真实外部 `HumanReviewAuthority.verify_attestation(...)` 契约和fail-closed条件；明确真实身份、资质、吊销、原PDF及上下文哈希、双人独立、冲突仲裁需由受控服务完成。跨多条审核记录的签署人去重属于authority批次规则，单记录Schema不声称提供该证明。

## Owner问题复现与修复验证

修改前执行 `.\.venv-langgraph\Scripts\python.exe -B -m evals.owner_p6_adversarial_probe`，真实复现：

```text
DUPLICATE_SAME_KEY_FIRST_WRITE_WINS E1 E0 order_invariant= False
EXTERNAL_GRADE_E3_ACCEPTED E3
ROLE_MISMATCH schema_errors= 0 stdlib_errors= ['extraction attestation role must match standard_extractor or independent_reviewer']
SYNTHETIC_FALSE_ATTESTATION_SHAPE issues= [] NOTE=shape-only not authentication, never ingest as gold
OWNER_P6_ADVERSARIAL_FINDINGS_REPRODUCED; this is not a production acceptance test
```

该脚本中的P6A坏例不是P7C修复验收依据。本P7C只负责角色错配/身份边界部分；该脚本后续整体可能因P7A修复而不再满足其“复现旧缺陷”的断言。

## 实际命令与结果

1. `.\.venv-langgraph\Scripts\python.exe -B -m evals.p6c_test_review_schema -v`：**6/6 PASS**。
2. `.\.venv-langgraph\Scripts\python.exe -B -m evals.p7c_schema_parity`：`SYNTHETIC_DIFFERENTIAL_CASES=77 SCHEMA_STDLIB_MISMATCHES=0 EXPECTATION_MISMATCHES=0`，PASS。
3. `.\.venv-langgraph\Scripts\python.exe -B -m evals.p7c_test_schema_parity -v`：**5/5 PASS**（覆盖77条fixture、抽取角色错配、unsigned模板、假布尔/签名引用与synthetic mock fail-closed）。
4. `.\.venv-langgraph\Scripts\python.exe -B -m evals.p6c_validate_review --check-template`：`P6C_SHAPE_VALID_ONLY (not authenticated, not E2/E3, not Gold)`，exit 0。
5. `.\.venv-langgraph\Scripts\python.exe -B upstream/04_接口文档/validate.py --final`：**554/554 clauses、200/200 trajectories通过**；RBI 472、DM 82、多步144、三类特殊轨迹各15。
6. `python -B -m scripts.merge_rbi1_into_original --check`（系统Python）：`READY_TO_APPEND 13 A474:W486`、`EXTRACTOR_SIGNED False`、`CHECK_ONLY: no files modified`。

## 失败与限制

- 首轮77条差分发现8处Schema/Python接受状态不一致，集中于nullable引用空白、时间格式断言及一个fixture对象被后续原地修改；已在Schema/fixture中修正，再跑得0差异、0预期偏差。
- 首次在隔离venv运行 `.\.venv-langgraph\Scripts\python.exe -B -m scripts.merge_rbi1_into_original --check` 因缺少 `fitz` 报 `ModuleNotFoundError`；未安装依赖、未改变环境，改用已含PyMuPDF的系统Python执行同一只读预检并通过。该依赖入口差异是已知环境限制，不是Excel写入或数据失败。
- Schema `format: date-time`在当前 `jsonschema` 环境中没有可用格式断言插件，故Schema同时用pattern约束RFC3339形状；stdlib再用datetime解析器检查真实日历日期/UTC偏移。极端规范实现差异仍应由Owner在确定正式JSON Schema运行时版本后复核。
- `HumanReviewAuthority`仅为协议类型说明；当前没有生产身份系统/签名验证器，也没有可信资质、撤销、双签或Gold数据库。SYNTHETIC mock永远不返回authenticated=true。
- 没有运行 `--apply`、convert、部署或Git写操作。教师三个工具/五键协议、原始Excel/PDF、官方JSONL保持冻结；13条候选仍待真实抽取人与独立复核人签名。

## 文件边界

本窗口仅改：

- `evals/p6c_review_schema.json`
- `evals/p6c_validate_review.py`
- `docs/P6C_HUMAN_REVIEW_PROTOCOL.md`
- `evals/p7c_schema_parity.py`
- `evals/p7c_test_schema_parity.py`
- `evals/p7c_synthetic_authority.py`
- `docs/audits/P7C_SCHEMA_AUTH_CONTRACT.md`

验收状态：**READY_FOR_OWNER_REVIEW**。结构校验一致不构成身份认证或专业结论。
