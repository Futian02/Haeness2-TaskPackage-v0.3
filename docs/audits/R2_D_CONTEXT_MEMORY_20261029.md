# R2-D 上下文与记忆实现审计（2026-10-29）

**候选状态：`D_CONTEXT_IMPLEMENTED / TARGET_TESTS_PASS / FULL_SUITE_NO_GO / OWNER_REVIEW_PENDING`**  
本报告只记录 D Lane 本地候选实现和当前实际测试，不代表 R2 全链路可发布，也不代表设备工况已由独立测量或专家复核。

## 1. 文件边界与变更

仅修改 D 任务书允许路径：

| 文件 | 变更 | 最终 SHA-256 |
|---|---|---|
| `backend/context_slots.py` | 扩展显式工况字段与解析来源元数据，保持旧返回接口 | `27C91EF8D7062DAB0DE311F4065860ECB12673433ADD9A7C05B00C8D4F6AFD98` |
| `backend/conversation_memory.py` | 增加有明确授权与保留选项的派生记忆清理接口 | `9078D9587D90C77B8C9C1553BDE87A60C290FDE84DF22BEF279C54DFA18EB81F` |
| `tests/test_r2_context_memory.py` | 新增上下文解析、隔离 SQLite 与记忆回放测试 | `A71DE0889C7A1C5507C948C3ECB0E7E0D947E3EA128118B33B38778B66D06786` |
| `backend/store.py` | 未修改；保留既有 Store/SQLite schema 与迁移 | `885D7374F43C47D1CCC401BC4882196BF5FB228429EAD6DB42F5970026383208` |

未修改 `backend/api.py`、`backend/deepseek.py`、Graph、其他 Lane、`upstream/`、教师 PDF/Excel/JSONL、正式数据库、人审记录或在线服务；未运行真实收费模型、未重启 8000/8001、未提交。

## 2. 实现内容与接口兼容

### 2.1 工况提取

`extract_explicit_context(question, structured=None, prior_confirmed=None)`继续提供既有调用键：

- `values`
- `sources`
- `raw_values`
- `unknown_enum_values`

新增元数据均为附加字段：`raw_spans`（原文本偏移）、`field_details`、`units`、`object_scope`、`new_object_scope`、`uncertain_fields`、`negated_fields`、`unknown_fields`、`correction_detected`、`structured_raw_values`。

支持设备/设备类型、部位、材质、介质、工况温度、壁温、总压力、H₂S 分压、流速、壁厚、服役年限、损伤形貌。过程温度和壁温、总压力和 H₂S 分压分列保存；支持常见 ℃/℉、MPa/kPa/bar/Pa、m/s/ft/s、mm/cm 单位规范化。未知材料/介质保留原文但不冒充枚举规范值；不确定或否定的值不进入 `values`。测得措辞标成 `USER_REPORTED_MEASUREMENT`，并显式记录 `independently_verified=false`，不将用户转述称为独立实测。

已知案例 A 的解析结果包含材质 `300系列不锈钢`、介质 `碱式酸性水`、工况温度 `60.0 degC`，各字段都能追溯回原始文本 span。案例 B 映射到部位 `壳体`、损伤形貌 `磕碰损伤`，不将“壳体”擅自推断为设备类型。

### 2.2 会话记忆

既有 `ConversationMemoryService` 按 CID 读取事实和摘要；模型/助手候选必须保持 `candidate` 状态，不进入 `get_confirmed_facts`。明确更正会在 Store 保留旧断言并将其标记 `superseded`，同会话新值成为当前值；跨 CID 来源由数据库约束拒绝。

新增 `clear_memory_records(cid, authorized=..., retain_audit=...)`：调用必须授权，并显式选择是否保留事实审计。保留时撤回当前事实但保留断言记录；不保留时删除记忆断言。该接口不删除消息、Run、附件或执行记录；整段对话的删除与保留周期需由 API/Owner 另立授权流程。摘要模型调用仍需显式注入 provider 和 `allow_model=True`；关闭、异常、超长或非法摘要均回退有界原始可见历史。

## 3. 测试证据

### D 定向组

实际运行命令：

```powershell
.\.venv-langgraph\Scripts\python.exe -B -m unittest tests.test_r2_context_memory tests.test_p12_context_flow tests.test_v2c_conversation_memory -v
```

结果：**32/32 PASS**。

新加 17 项测试中的解析测试实际调用 parser，矩阵有 **72 条输入**：12 材质别名/枚举、12 介质别名与未知值、12 温度与单位、12 总压力与单位、12 流速与单位、12 厚度与单位；另测 A/B 案例、来源 span、壁温/工况温度分离、总压/分压分离、UNKNOWN 保留、否定/不确定、跨轮更正、新对象隔离、结构化表单优先级。

记忆测试覆盖候选不能晋升用户事实、显式更正与审计历史、CID 隔离、非法摘要回退、SQLite 关闭重开回放、迁移重复初始化、删除授权与审计保留选择、双线程跨 CID 写入隔离。

### 整仓回归

Owner 独立运行结果：**447 tests，4 FAIL、3 ERROR、3 SKIP**；整仓为 **NO-GO**，不得记作全量通过。失败/错误均非 D 新测试：

- FAIL：`test_64_authored_regressions_have_useful_bounded_answer` 子例 P0-N-01 工具调用数为 0（该场景要求真实冻结检索）；同方法聚合 `seen_hashes=50`，预期 52。
- FAIL：`test_api_sqlite_end_to_end_uses_temporary_database_and_visible_response` 子进程返回码 1 / 断言失败。
- FAIL：`test_owner_two_failed_questions_use_frozen_teacher_tools_and_visible_api_answer` 子进程返回码 1 / 断言失败。
- ERROR：上述 64 题回归子例 P0-X-04 抛 `KeyError: 'medium'`。
- ERROR：`test_health_exposes_separate_model_and_deterministic_guidance_flags` 抛 `KeyError: 'expert_guidance_candidate'`。
- ERROR：`test_p16_a_evidence42` 导入失败：`ModuleNotFoundError: fitz`。
- SKIP：3 项（整仓记录为 skipped=3；不是 PASS）。

系统 Python 对 Graph/R9 相关旧测试曾因环境依赖异常失败：已安装 LangGraph/Tenacity 路径尝试访问 Python 中已移除的 `asyncio.coroutine`。使用项目 `.venv-langgraph` 的 D/P12/V2C 定向组为 32/32 PASS。整仓上述 P0/API/依赖失败仍需各自 Lane 修复和 Owner/G 集成复审。

## 4. API 对接与未决风险

磁盘现有 `backend/api.py` 的 `_submit` 路径确实调用 `extract_explicit_context`，从同一 CID、`role=user` 历史提取先前值，保存 Run context snapshot，并在 Run 创建后仅将当前消息/结构化表单明确字段写入 `ConversationMemoryService`。助手文本和模型候选没有通过该 API 确认写入路径。此处通过源码与 `test_p12_context_flow` 定向测试验证；本 Lane 未改 API，也未重启服务或做网页实例版本握手。

**阻断性接口风险：匿名新设备 scope 尚未闭合。** parser 能在“另外一台设备”时停止继承 prior，并给出 `new_object_scope/object_scope`；但现有 API 持久化调用的 `object_scope` 仅取设备名/设备类型，否则使用固定字符串 `conversation equipment`，没有传递 `resolved.object_scope`。因此未命名的新设备的记忆事实可能与此前匿名设备共用 scope。需要 E/API 单一所有者调整绑定后再做跨设备端到端回归；D 不越界修改 API，故该项为 `OPEN / NO-GO`。

另外，适用工况抽取仍是有界规则/别名解析，不承诺覆盖任意自由文本；未识别表达应留在 UNKNOWN/raw，不能据此表示信息已完整。D 的 PASS 不覆盖 B 的安全门禁、A 的来源审核、C 的检索/图行为、E/F 的真实服务与浏览器、专家 Gold、人审或正式上线审批。

## 5. 复现与候选状态

```powershell
# D + 既有上下文/记忆回归
.\.venv-langgraph\Scripts\python.exe -B -m unittest tests.test_r2_context_memory tests.test_p12_context_flow tests.test_v2c_conversation_memory -v

# 整仓（当前实测不是绿）
.\.venv-langgraph\Scripts\python.exe -B -m unittest discover -s tests -v
```

最终 D 候选状态：**实现完成、定向 32/32 PASS；整仓 447 项仍 4 FAIL / 3 ERROR / 3 SKIP；匿名跨设备持久化 scope 有未决 API 对接风险；Owner/G 复核待完成。保持 `NO_GO`，不宣称生产可用或正式验收通过。**
