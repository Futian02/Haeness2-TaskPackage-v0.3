# P7-B Known Facts / Run-Bound UX — 审计报告

**状态：READY_FOR_OWNER_REVIEW**。本报告只验证本地 `RULE_DEMO` 展示层与浏览器端 run 关联；不构成设备事实认证，不提供跨设备快照恢复，不改变后端 API 或证据等级。

## 修复内容

- `EngineeringReport` 不再从 `messages` 中取 conversation 最新 user 消息填入已知事实，也不再把任意 Agent `summary`/未确认 observations 冒充现场事实。
- 创建 run 后，前端把当次 `question` 及发送的设备/工况字段以 `run_id + conversationId` 为键存入 `localStorage`。报告只消费与选中 `runId` 完全匹配的快照；本轮用户提交统一标为“用户报告/未独立验证”。
- 事件摘要均归入折叠的“Agent 推断与过程摘要（待核）”。只有 SSE 明确携带 `provenance=user_confirmed` 或 `source_status=confirmed` 且属于当前 run 的观察才进入“经确认观察”；当前生产规则图未提供该确认信号，因此没有把任何 Agent 观察升级为 confirmed。
- 缺少快照、run 不匹配、旧记录或缓存被清除时显示“来源待确认”，不从当前会话最后一条消息猜测。按当前 run 过滤 SSE 事件、Claim、反证，切换历史 run 时恢复匹配快照。
- 长反证全文按 run 展示在折叠区；全部条目仍保留在 DOM 展开内容中，没有隐藏/删除审计来源。细节保留 Run ID 与事件序号于证据抽屉及时间线。
- Owner P6 的两条 `it.skip` 反例改为正确的负向期待并启用；新增 run 快照不匹配、历史run切换、跨run事件隔离、非确认观察不升级等回归。

## 运行身份绑定方案与边界

Run 身份来源为 FastAPI `POST /api/conversations/{cid}/runs` 返回的 `run_id`；本轮输入快照由前端在收到该 ID 后，以 `aether:run-snapshot:{conversationId}:{runId}` 存储。事件端通过 API 返回的 `event.run_id` 隔离，已有 `/api/conversations/{cid}/runs` 只提供 run ID/status/timestamp，不提供 question/context。没有可靠匹配时失败关闭为“来源待确认”。

该方案是**本地客户端缓存绑定**，不是服务端签名快照或不可篡改审计记录：用户可编辑浏览器 localStorage；清除缓存/换设备后，P6 既存 run 没有可恢复输入映射。本阶段不假装可以恢复，也不向后端偷偷添加字段/路由。下一轮如需跨设备可靠恢复，应经单独 API 合约评审，增加经服务端写入、只读返回、绑定 conversation/run 的输入快照，并设计权限/保留期/隐私策略。

用户输入只代表**用户报告**，不等价于真实现场测量；字段不升级为 `observed` 或专业结论。RULE_DEMO、E0/E1 等级、待人工复核状态均维持原协议，不声明真实多模型验证、E2/E3 或设备风险级别。

## 实际验证

执行目录：`frontend/`。

```powershell
node ./node_modules/vitest/vitest.mjs run src/owner_p6_ux_adversarial.test.ts --reporter=dot
node ./node_modules/vitest/vitest.mjs run --reporter=dot
node ./node_modules/typescript/bin/tsc -b
node ./node_modules/vite/bin/vite.js build
node scripts/p6b_ux_e2e.mjs
```

结果：

- 新增/翻转的 run-bound adversarial tests：**5/5 PASS**。
- 完整 Vitest：**36/36 PASS**，没有 skip。
- TypeScript `tsc -b`：exit 0。
- Vite build：exit 0，3103 modules transformed。
- Edge + Vite + FastAPI + LangGraph RULE_DEMO + SQLite + SSE：**PASS**。主 run `64f535f2-4dfc-4983-97f8-634e121c8810`：44 条连续 SSE、2 Claims（E0/E1）、7 references、2 disagreements；`after_sequence=5` replay 39 条并从序号6开始。第二 run `b65043a8-1304-4489-9cfa-ecffb10c0b25`：39 SSE、2 Claims。两个 run 同会话切换后各自用户输入/工况恢复，未把第二轮奥氏体不锈钢/现场证据串入首轮碳钢工况；刷新后恢复第二 run 的39事件及2 Claims。会话切换无 Claims 串线。
- 浏览器 API 请求全部 HTTP 200；console/page exceptions **0**；桌面1280/1440、移动390、E1/E0来源抽屉、reference抽屉及审查图截图均生成。
- Vite stderr 在 Edge 多次切换视口时记录 `ResizeObserver loop completed with undelivered notifications` 开发期诊断；CDP 捕获的页面 exception/console error 仍为0。此 ResizeObserver 信号未通过忽略或过滤浏览器console来伪造PASS，Owner可在下轮单独判定是否需处理图布局观察器。

E2E机器记录：`frontend/evidence/p7b/P7B_FULL_EVIDENCE_E2E.json`。截图：`frontend/evidence/p7b/P7B_*.png`。临时服务绑定 `127.0.0.1`，测试完已停止；端口8000/5173/9222复查无监听。测试数据库为 `data/p7b_e2e.sqlite3`，避免覆盖项目默认SQLite数据库。

## 失败与修正记录

1. 首次E2E等待第二 run 时从浏览器页面跨源 `fetch(127.0.0.1:8000)` 轮询，被浏览器CORS阻止。改为E2E Node进程直接轮询本机API；浏览器本身的Vite代理/SSE链路仍由Edge实测。
2. 第二轮首个问题文本未触发机制 Claim，工程报告组件因无 Claim 不渲染。将场景修为明确询问“可能的损伤机理”，而非改变门禁；后续第二 run实际得到2 Claims/39事件。
3. 首轮历史恢复断言使用了与E2E现场证据不同的文字，测试脚本自身超时；改为精确匹配已输入的“塔顶水样pH 5.8”。
4. 刷新后脚本误用首轮44事件数校验当前默认第二 run；改为比较第二 run SQLite回放长度39和Claims数量。最终真实E2E通过。
5. 本地服务回收脚本第一次使用PowerShell保留变量 `$PID` 导致清理代码报错；改用 `$procId` 后进程树停止，复核端口无监听。

以上失败均为E2E场景/清理脚本的问题，不是通过放宽证据门禁消除。进程树停止后端口8000/5173/9222均无监听。为隔离默认数据库，测试期间指定了 `data/p7b_e2e.sqlite3`；测试结束删除该独立数据库文件的PowerShell命令被执行环境拦截，文件目前仍保留（未包含真实业务/源表，只含合成工况）。需 Owner 或允许清理的阶段移除该测试数据库。Vite stderr在服务停止时另记录Node `read EPIPE`（进程关闭阶段），未影响已完成的断言和API日志。

未修改 `backend/`、`orchestration/`、`upstream/`、教师三个工具、原始Excel/PDF或官方JSONL；未部署、未提交。
