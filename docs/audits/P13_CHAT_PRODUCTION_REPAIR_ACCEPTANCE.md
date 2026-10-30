# P13 聊天可靠性、联网与条件性候选验收

状态：**READY_FOR_OWNER_REVIEW**（本地代码、离线回归与真实 Edge 浏览器检查完成；真实 Provider 和真实联网调用未验证，因此不构成最终验收）。
日期：2026-10-29（Asia/Shanghai）

## 1. 范围与冻结声明

依据 `docs/CODEX_P13_CHAT_RELIABILITY_WEB_AND_HYPOTHESES_20261029.md` 与 `docs/P13_ADDENDUM_WEB_CONTEXT_LENGTH_AND_STRESS_20261029.md` 执行。修改仅限 P13 定义的后端模型/API/存储、意图与候选、联网适配、前端聊天、专项测试及审计/状态文档。未改 P14 数据蒸馏文件、`upstream/` 教师三个工具、五键返回协议、原始 Excel/PDF、正式 JSONL；离线 API/压力测试均使用临时 SQLite；未提交、部署、公网发布或清理历史文件。

开工检查时，上游仓库已存在既有状态：`条款摘录表_RBI.xlsx` 为 modified，`RBI_GBT26610_1_13candidates_for_review.xlsx` 与备份为 untracked。此状态早于/独立于本 P13 操作，本轮没有触碰上述路径，也没有尝试回滚。该事实与上游归属仍需 Owner 独立审计。

## 2. 实现结果

### P0 模型、历史、API（A）

- 普通聊天只从当前 conversation、当前 Run 输入之前读取最近最多 12 轮可见 user/assistant 消息；历史文本按条和整体有界；不混入其他会话、附件、标准全文、事件或 `reasoning_content`。最近一次失败 Run 仅加入同会话的用户问题摘要与有限错误类别。
- DeepSeek Chat Completions 增加 `finish_reason`、真实 usage、响应模型 ID与耗时记录；通用对话默认 4096、代码默认 8192（可配 8192–16384）、报告默认 3072；保留 Provider/模型专项 thinking 配置，默认关闭，响应上限不吞掉代码长输出。
- `length`、content filter、空响应、认证/请求/速率/超时/网络故障分类为稳定有限错误码；不回传供应商原始 body、密钥或私有 reasoning。失败 Run 作为 failed 持久化并发 error SSE，不写空 assistant 消息。工程表达整理失败不覆盖已有的确定性本地报告。
- 联网模式为 `off/auto/on`，聊天栏按会话保存选择，创建 Run 时写入 SQLite 上下文并回显到运行快照；`auto` 只对明确的公开时效问题搜索，`on` 执行公开查询。工程敏感文本不自动外发；显式敏感外发需独立二次确认，且不会发送设备表单、附件或标准全文。来源含标题、URL、检索时间与外网非教师标准来源标识。Search 失败显式展示在回答和 SSE 事件中。

### P0/P1 路由、工况与条件性候选（B）

- 先按当前轮意图路由，再决定是否使用同会话历史工况；天气、HTML/SVG代码、一般概念不会被历史材质/介质污染。
- 支持标签包装方括号、介质数组及合法别名归一到老师冻结枚举；模糊“酸性水/水”不自动提升为确定介质。
- 路由区分 `general_chat`、`standard_lookup`、`hypothesis_exploration`、`device_diagnosis`、`deterministic_rbi_grade`。
- 有真实条款来源时允许输出有条件适用的 E0 探索候选、适用/排除条件、反证/鉴别检查与补证项；无来源不造候选。候选不含伪概率/置信度，不产生设备风险级别。缺少材质、介质、设备类型、压力、服役年限等必要值时保持风险未知并询问用户，E0/E1与人工复核门禁不变。
- 专项覆盖 20 个合成意图样例与正式 `clauses.jsonl` 10 条来源追溯样例。十条核查仅验证引用/元数据追溯，不声称条款语义已人工核验或适用于具体设备。

### P0 前端失败/代码（C）

- SSE `error` / `run_failed` 不再作为成功结束；终端失败拒绝为有限 `RunStreamError`，SSE错误数据经过安全归一，错误原文不进入执行轨迹或 UI。
- 失败 Run 以用户可见错误卡呈现并提供重试；恢复会话时从 SQLite Runs 状态及 SSE 重放恢复失败状态；失败时不显示“本轮执行已结束”。
- 聊天栏提供关闭/自动/开启三个联网选项并按会话持久化；新 Run 的真实服务端快照含所选模式。敏感工程文本的独立确认默认为关闭，附件/表单/标准原文不随搜索请求外发。
- 长 HTML/SVG 代码块不被“长篇报告”占位替换，并提供“复制代码”按钮；长篇普通文字仍可展开，P12设置与既有历史兼容保留。

### P1 WebSearch adapter（D）

新增内部 `DeepSeekWebSearch.search/fetch`，仅应用级服务，不注册为老师第四工具。默认 offline，钉死官方 HTTPS host，限制请求/响应/条数/时间/调用预算，拒绝 localhost/私网/非 HTTP(S) URL；天气缺地点时先报 location_required；错误脱敏。来源保留 title、URL、retrieved_at、scope，并标明外网资料不是老师标准条文权威。接口及其未验证项见 `docs/audits/P13_WEB_SEARCH_INTEGRATION_NOTE.md`。

## 3. 变更文件

- `backend/deepseek.py`
- `backend/api.py`
- `backend/store.py`
- `backend/web_search.py`
- `orchestration/intent.py`
- `orchestration/r9_industrial_candidate.py`
- `backend/context_slots.py`
- `frontend/src/api.ts`
- `frontend/src/App.tsx`
- `frontend/src/AssistantMessages.tsx`
- `frontend/src/EngineeringReport.tsx`
- `frontend/src/styles.css`
- 新增 `frontend/src/App.failure.test.tsx`
- 更新 `frontend/src/api.test.ts`、`frontend/src/AssistantMessages.final.test.tsx`
- 新增/更新 `tests/test_p13_model_reliability.py`、`tests/test_p13_router_hypotheses.py`、`tests/test_p13_search_service.py`、`tests/test_p13_local_load.py`；更新 `tests/test_p5a_lease_event_integrity.py`
- 新增 `tests/test_p13_local_load.py`；本地容量、SSE终态并发矩阵 100 runs × concurrency 1/4/8
- `frontend/src/App.failure.test.tsx`、前端全量 115 项测试
- `docs/audits/evidence/P13/`：Edge 实际浏览器回放 JSON 与桌面/移动截图
- 新增 `docs/audits/P13_WEB_SEARCH_INTEGRATION_NOTE.md`
- `docs/audits/P13_CHAT_PRODUCTION_REPAIR_ACCEPTANCE.md`（本报告）
- `docs/PROJECT_STATUS_CURRENT.md`

## 4. 真实命令与结果

工作根：`D:\作业\竞赛\计算机设计智能体\机械智能体`。Python 环境：`.venv-langgraph`。以下“PASS”仅表示对应本地测试含义，不等价于实际付费模型质量或专家验收。

| 命令 | 实际结果 |
|---|---|
| `\.venv-langgraph\Scripts\python.exe -B -m unittest tests.test_p13_model_reliability tests.test_p13_router_hypotheses tests.test_p13_search_service tests.test_p13_local_load -v` | 专项覆盖：≥30条路由断言、36类HTTP/协议错误形状、finish_reason/长输出矩阵、20个mock搜索场景、同会话历史与跨会话隔离、100并发run矩阵 |
| `\.venv-langgraph\Scripts\python.exe -B -m unittest discover -s tests -q` | **195 tests OK，3 optional Phoenix/OpenInference tests skipped** |
| `\.venv-langgraph\Scripts\python.exe -B -m scripts.audit_p13_dialogue_diagnostic` | 13项诊断运行；天气/HTML/图灵机在旧工程上下文下为 `general_chat`；方括号介质归一为 `碱式酸性水`；缺工况风险请求为 `needs_user_input`、0工具、风险空；`finish_reason=length` 被安全识别；临时 SQLite API/SSE 失败状态为 failed，只有安全错误事件、无 assistant 空消息；没有 Provider 网络请求。`CLIENT_SSE_ERROR_TREATED_TERMINAL False` 表示旧静态代码模式已不存在，前端专项 SSE 失败测试另行通过。 |
| `\.venv-langgraph\Scripts\python.exe -B -m unittest tests.test_p4a_api_safety.P4AApiTests.test_question_only_request_has_no_fabricated_context_or_tool_calls -v` | **1 test OK**；补正历史断言并把“分析设备风险”作为风险分级请求识别，缺项时不调用工具、不输出等级 |
| `npm test -- --run`（cwd=`frontend/`） | **17 files / 115 tests PASS**；随后变更重试断言的专项 `npm test -- --run src/App.failure.test.tsx` 为 **2/2 PASS** |
| `npm run typecheck`（cwd=`frontend/`） | PASS |
| `npm run build`（cwd=`frontend/`） | PASS；Vite 提示 `index` 614.49 kB、AssistantMessages 275.07 kB 超 500 kB chunk 建议；构建成功 |
| `\.venv-langgraph\Scripts\python.exe -B 'upstream/04_接口文档/validate.py' --final` | **PASS**：条款 554/554，轨迹 200/200，多步 144，exclusion/insufficient_info/out_of_domain 各 15，0条结构错误 |
| `\.venv-langgraph\Scripts\python.exe -B 'upstream/05_提交区/_selftest_tools.py'` | **17项通过，0失败**；仅运行教师工具只读自测 |
| `\.venv-langgraph\Scripts\python.exe -B 'upstream/05_提交区/_check_harness_sync.py'` | PASS；两份 harness.py SHA-256 一致 |

诊断结果显示显式“碱式酸性水”候选仍是来源条件性探索/待复核状态；无来源时不输出候选。具体能否语义适用必须由工程人员根据现场工况审查，测试不替代专家判断。

## 5. 压力、浏览器与未验证项

### P13 Addendum 压力结果

| 场景 | 实际结果 |
|---|---|
| 路由 | ≥30 条路由样例；当前测试含 30-case cross-topic routing matrix、当前轮/历史工况反串线断言与既有13项诊断脚本 |
| 模型异常 | 36类 HTTP/协议错误响应 mock；覆盖空内容、length 截断、content filter、400/401/402/429/5xx、响应结构异常、超时/断连及 finish_reason；无供应商错误正文泄漏 |
| 本地并发 | 100 runs × concurrency 1/4/8，3组共300次；0异常，Run终态唯一且SSE序号有序。测得：C1 P50/P95 51.446/65.191 ms，C4 106.258/700.589 ms，C8 198.619/506.896 ms。P95离散受共享Windows测试机调度影响；这不是模型吞吐或生产容量承诺 |
| 联网 | 20个隔离 fake-transport 搜索用例；覆盖来源元数据、off/auto/on、敏感信息二次确认、缺地点、URL allowlist、预算和错误脱敏。测试不建立公网连接 |

### 真浏览器证据

使用隔离本地 FastAPI (`127.0.0.1:8015`，临时 SQLite、无模型密钥) + Vite (`127.0.0.1:5175`) + Microsoft Edge `Edg/142.0.3595.53` + Playwright/CDP。浏览器中的数据为本机 SQLite 合成夹具，不含真实用户对话或模型输出。

- 深色桌面失败恢复卡：[`P13_browser_desktop_dark_failure.png`](evidence/P13/P13_browser_desktop_dark_failure.png)
- 深色移动失败恢复卡：[`P13_browser_mobile_dark_failure.png`](evidence/P13/P13_browser_mobile_dark_failure.png)
- 浅色桌面长代码/复制态：[`P13_browser_light_desktop_long_code.png`](evidence/P13/P13_browser_light_desktop_long_code.png)
- 浅色移动长代码：[`P13_browser_light_mobile_long_code.png`](evidence/P13/P13_browser_light_mobile_long_code.png)
- 探针数据：[`P13_browser_probe.json`](evidence/P13/P13_browser_probe.json)；交互数据：[`P13_browser_interactions.json`](evidence/P13/P13_browser_interactions.json)
- 实测联网 off/auto/on 存储往返、切换会话刷新后重新选中当前 conversation 恢复 mode=on；失败Run重放恢复错误卡和服务端快照 `联网 on`。长代码从 SQLite 回放 121,030 字符；复制按钮显示“已复制”，剪贴板与代码在 Windows CRLF/LF 归一后完全一致。移动视口 390px 时 document/body scrollWidth 均为390；Playwright记录0 page errors。
- 重试点击行为由 `frontend/src/App.failure.test.tsx` 覆盖并断言重新提交原问题和当前联网模式。浏览器截图中确认按钮可见；真实 Edge 点击重试并执行到最终完成态未做，因为本地夹具为失败态且测试不应触发真实Provider。

### 失败/工具记录

- 首次 full backend test 的 location_required 子用例期待 `web_search_failed`，实际策略正确发出 `web_search_skipped` 并在回答里显式指出缺地点；修正断言按“跳过”语义区分后全套 **195 tests OK**。
- 初次用 raw CDP setter 调联网 `<select>` 未触发 React onChange；后改 Playwright真实用户选择动作验证 off/auto/on持久化。
- 复制代码验证发现 Windows 剪贴板将 `\n` 转成 `\r\n`；按换行符归一后与完整代码相等，按钮状态“已复制”。
- Desktop browser bridge曾超时；改用隔离 Edge 的 CDP + Playwright，已形成上述真实浏览器截图和交互证据。
- 本轮临时开发服务只在专用 8015/5175 端口启动，未重启旧用户服务 8000。旧 PID 59120 的 `/api/model-profiles` 返回404，磁盘与线上版本仍不一致；未做真实用户服务E2E。

### 必须保留为未验证

- 未发送真实 DeepSeek Chat/Search/Fetch 请求：未验证账户配额/计费、真实模型长文完整率、实际usage/finish_reason/TTFT、真实搜索响应/引用质量。用户明确要求未经同意不做收费压力测试，本轮所有模型/provider验证均为离线 mock；真实模型项为 **BLOCKED_NOT_TESTED**。
- 搜索服务端到端通过 API fake transport 和真实 Edge UI选择/快照验证；实际公网 Search/Fetch 的认证、网络故障与来源质量未验证，为 **BLOCKED_NOT_TESTED**。
- 教师 validate 和 17项工具自测均通过，不等于标准原文专家复核或 RBI 结论审批；已有 Excel modified/untracked 的上游状态独立存在，本轮未触碰且未回滚。
- P14 数据蒸馏、原始 PDF/Excel、正式知识库、旧服务与其他 DevSpace 均未更改/重启。

## 6. 验收状态与下一步

- **代码通过：PASS**：后端195项（3项仅可选Phoenix/OpenInference环境测试skip）、前端115项/typecheck/build、教师554/554条款、200/200轨迹与17/17工具自测；local load 0错误。
- **真实浏览器通过：PASS（隔离本地合成数据）**：Edge桌面/移动截图、刷新/会话mode、SQLite失败回放、长代码copy、无溢出/无页面异常。
- **真实模型验证：BLOCKED_NOT_TESTED**：无真实provider请求、无费用或模型性能结论。
- **真实联网验证：BLOCKED_NOT_TESTED**：20项是mock transport，不是公网真实请求。
- **最终验收：未完成**。仅按交付要求停在 **READY_FOR_OWNER_REVIEW**；不部署、不提交、不重启旧服务。Owner可在批准具体付费预算后另做少量真实模型采样；在此之前保持当前标注，不将本报告解释为生产验收。
