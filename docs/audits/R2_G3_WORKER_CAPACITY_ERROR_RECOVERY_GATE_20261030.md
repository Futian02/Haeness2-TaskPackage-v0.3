# R2-G3 Worker Capacity / Error Recovery Closeout (2026-10-30)

**结论：STOP_FIX_REQUIRED / G3_BROWSER_FAULT_GATE_INCOMPLETE / PRODUCTION_NO_GO。** 本轮实现了前端恢复状态机修复并完成Python、前端、教师回归；真实Edge桌面/移动RULE_DEMO普通UI旅程通过。由于尚未在真实Edge主界面完成真实后端WORKER_CAPACITY 429 queued恢复、用户UI内未配置模型503、以及工具超时/失败恢复旅程，不能申请`GO_ISOLATED_OWNER_RULE_DEMO_UI_TEST`。不得将普通聊天通过或前端单元测试替代缺失的浏览器故障证据。

## 修改

- `frontend/src/api.ts`
  - SSE HTTP 429仅在响应`detail.code=WORKER_CAPACITY`时映射为`run_queued_capacity`，保留`Retry-After`；该类型在`consumeRun`中立即上抛，不被当作普通断线反复重放。
  - 新增脱敏用户提示`run_queued_capacity`、`tool_timeout`；模型配置不可用HTTP 503显示明确的模型配置错误，不透出原始响应体。
  - POST请求错误保留`Retry-After`元数据。
- `frontend/src/App.tsx`
  - Run创建成功后清除POST幂等键，但草稿保留到收到成功终态；创建请求失败则保留精确请求体、幂等键、问题和草稿，重复提交使用相同key及相同body。
  - 已创建Run遇容量429时展示“任务已进入队列…重新连接不会重复提交”和“继续等待原任务”，仅对同一`run_id`重连SSE；`connection_lost`同样恢复原Run。
  - 终态失败按钮明确为“作为新运行重试”；不会把已创建的队列Run再POST一次。
  - 新输入/工况/联网方式变化会清理旧待提交幂等快照，避免相同key配不同请求体。
- `frontend/src/api.test.ts`、`frontend/src/App.failure.test.tsx`：新增容量429类型/Retry-After、不重复POST断言；将终态失败按钮断言更新为明确新Run语义。未删测试、未调整断言来隐藏失败。

## Gate A：状态机与专项

- `cd frontend; npm test -- --run`：**20 files / 130 tests passed**。
- 新增前端容量429用例验证：HTTP 429 `WORKER_CAPACITY` + `Retry-After: 2` → `RunStreamError(run_queued_capacity, 2)`，不会触发replay/新POST。
- 新增App用例验证：已POST创建`retry-run`后SSE容量失败；点击“继续等待原任务”再次消费同一RID，`createRun`仍仅1次。
- 创建请求网络失败测试既有覆盖仍通过；同一问题保留同一幂等键。请求体冻结在本地浏览器存储，仅含本轮输入快照，不含API密钥/模型返回。
- `npm run typecheck`：通过。
- `npm run build`：通过；保留既有Vite单bundle超过500KB提示。

## Gate B：真实Edge及隔离环境证据

Shadow服务由`scripts/r2_service_shadow_run.py --shadow --port 8879 --hold`启动，临时SQLite：`C:\Users\37813\AppData\Local\Temp\aetheris-r2-shadow-26qhtm3h\shadow.sqlite3`；凭据已清空，RULE_DEMO，V2与候选flag关闭。前端Vite独立端口5180，API代理8879；8000/8001未操作。

- Edge桌面 1440×900真实UI点击“你好”：Run `b7eac091-58cc-4c3c-8090-7de1a53fa110`，CID `abbd7e57-14a3-41fc-bc51-09678075bf6a`，HTTP POST/SSE均200，事件`1 context_resolved → 2 intent_routed → 3 run_completed`，SQLite user/assistant消息各1，答案落库并显示。证据：`docs/audits/evidence/r2_g3_20261030/Edge_desktop_20261030_203159.json`及同前缀PNG。
- Edge移动 390×844真实UI点击“你好”：Run `e3be67dc-42cc-4129-bf21-406e69098701`，同CID，事件序列1–3，SQLite user/assistant各1，composer底部与844px视口齐平、scrollWidth=390。证据：`Edge_mobile_20261030_203209.json`及PNG。
- G2专业旅程桌面复跑完成11个真实Run（RULE_DEMO恢复、SCC、专业A/B、A60→A80更正、来源复核、多轮事实更正、匿名设备隔离、匿名追问）；最后“跨会话隔离”在浏览器runner点击时，send按钮在等待后仍disabled，Node/CDP抛`send disabled after readiness wait`，证据保留在`Edge_desktop_20261030_203502.json`。不是通过删该用例或改预期收尾；本次G3完整浏览器旅程失败。
- 该专业runner中的`unconfigured_model_503`是其API直接探针；未在聊天UI真实点击发送并核对错误卡/草稿/恢复，故不计入G3 Model-503 UI通过。
- **G3未完成的关键浏览器故障项**：没有在服务端占满worker semaphore并从Edge实际观察`GET /stream` HTTP429、`Retry-After`及相同RID恢复；没有真实Edge UI验证POST 429无ghost run、模型配置503卡片/草稿保留及离线恢复、工具超时失败卡/新运行隔离。当前G3证据目录无这些HTTP故障响应。UI单元测试只证明分支逻辑，不等于浏览器验收。

## Gate C：回归

- `.venv-langgraph\Scripts\python.exe -B -m unittest discover -s tests -v`：**451 tests，0 FAIL/ERROR，3 SKIP**，`OK (skipped=3)`；含现有真实临时SQLite容量429后端测试及64条专业回归。耗时80.368s。
- `.venv-langgraph\Scripts\python.exe -B -m pytest tests\test_p16_a_evidence42.py -q`：**5 passed**。
- Teacher `upstream/04_接口文档/validate.py --final`：554/554 clauses、200/200 trajectories通过。
- Teacher `upstream/05_提交区/_selftest_tools.py`：17/17通过。
- 以上upstream仅作只读验证。本轮不修改教师数据、不运行人工审阅、不访问正式SQLite。

## 指纹、测试记录与边界

- Edge/API shadow后端磁盘/运行指纹一致：`sha256:51dcdca504fc13eb4ae4e884ee3b35ec2018cec81d25a9b95c51ded60968b7be`（后端源码未改）。
- Vite前端本轮源码指纹：`132b8e3498dbe8ba8d1c770b6c6fbc82faab8cc017797b4fe114c38eb5f6d2c6`。
- 测试入口输出保存在当前执行会话；Edge JSON/截图保存在`docs/audits/evidence/r2_g3_20261030/`。保留了Node失败JSON，不覆盖G2证据。
- 未连接DeepSeek，不调用收费模型；RULE_DEMO仅作为隔离交互烟测，不表示模型能力或工程安全结论已验收。生产/正式数据库与部署维持NO-GO。

## 最后具体阻塞项 / 下轮恢复方案

1. 复查并有界重跑现有专业Edge runner最后一段跨会话切换；若仍disabled，记录DOM中`running`及目标CID状态，修具体竞态后桌面和移动各复跑一次，不动已成功旅程。
2. 在仅development、loopback、临时SQLite的影子进程中建立受限故障注入：占用4个worker槽导致真实stream路由429；一次性POST rate limit；model-profile未配置503；worker内合成tool timeout。故障开关默认关闭、仅测试runner进程可控，不增任意工具执行入口。
3. 浏览器每个故障用例保存request/response headers与body、Run/CID、事件序列、SQLite消息计数、DOM截图，并核对前后源指纹；桌面1440×900、移动390×844都真实点击恢复动作。
4. 关键浏览器Gate通过后重跑上述Python/前端/教师回归，再由Owner复核后才可重新评估隔离GO；工程/生产仍需单独审批。


## 最终源码指纹复验增补（20:40）

前端源码最终指纹经重启本轮自建Vite影子服务后刷新为`132b8e3498dbe8ba8d1c770b6c6fbc82faab8cc017797b4fe114c38eb5f6d2c6`，最终UI build的Edge桌面/移动截图和结果分别为`Edge_desktop_20261030_204028.json`、`Edge_mobile_20261030_204037.json`。桌面Run `722f7a25-3c0a-4e86-976b-503947ffa46b`，移动Run `45fcb3e6-6b9e-4ca5-bd44-0bfb5fddcb9b`，同CID `a4cf19a4-91e0-40b3-a864-5298de7b9794`；两者均completed、序列1–3、各1 user+1 assistant，Edge console errors=0，桌面scrollWidth 1440、移动390。之前的203159/203209证据仍保留，但不作为最终指纹。

## 本轮失败项与恢复记录

- 一次补丁操作误删了包含composer的JSX整段行，Vitest报4个suite解析失败，TS报告未闭合`section/main`。未删/改测试：按真实组件结构恢复composer（结构化工况、输入、联网、附件、语音、发送控件），重新运行完整Vitest/TypeScript/Vite后20 files、130 tests全部通过。最终浏览器也在重启Vite后复验，front fingerprint对齐。
- G2专业Edge回归的最后跨会话发送仍复现“send disabled after readiness wait”，原始Node/CDP异常及完成的11个旅程保留，未通过修改预期/跳过用例掩盖；原因需下一轮从selected CID、running state和按钮disabled的DOM状态继续定位。
- G3服务端故障注入尚未搭建，故本轮不伪造429/503/工具超时的Edge截图、响应头或Run记录。恢复步骤按下节1–3执行。
