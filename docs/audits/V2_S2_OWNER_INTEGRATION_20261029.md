# Aetheris V2 S2 Owner 集成记录与评审（2026-10-29）

## 结论

**NO-GO（仅隔离候选，不具备默认切换/发布条件）**。已落地并回归一部分 S2.0–S2.3：统一测试入口、修复旧 R10 mock/profile 接口兼容、将 V2 fake candidate 接入现有 API/event schema、启用临时 SQLite LangGraph checkpoint、接入同会话已确认事实、完善公开 trace 参数脱敏。V2 仍由 `AETHER_V2_AGENTIC_ENABLED=0` 默认关闭；启用时还要求当前 Store 路径位于系统临时目录，拒绝向正式/业务 SQLite 写 checkpoint。R9/RULE_DEMO 保持默认路径。没有调用收费模型、部署/重启服务、修改教师 upstream 或正式数据。

Owner 在 `backend/intent_router_v2.py`、`orchestration/intent.py`、`tests/test_owner_v2_routing_regressions.py` 的 S1 修复均保留，未覆盖或回滚。

## 分阶段执行

| 阶段 | 状态 | 实际结果 |
|---|---|---|
| S2.0 测试环境/R10兼容 | **PASS（当前机器回归；clean-env重建未验证）** | 新增固定依赖清单与 `scripts/test_s2.py`。项目 venv 原先缺 PyMuPDF、R10 对旧 profile/mock 合约有失配；未安装/升级全局包，通过测试入口组合 venv 与已存在的本机包并隔离 OpenTelemetry 命名空间；干净环境依锁文件重建未执行。统一入口最终 282 unittest 通过、3 个可选 Phoenix/OpenInference skip，P16-A pytest 5/5；新 R10 mock 矩阵 20/20 且 SQLite/event replay 一致。旧的 `r10_offline_chat_matrix_20261028.jsonl` 未覆盖。 |
| S2.1 路由/业务路径/混合任务 | **PARTIAL** | 保留 R9/RULE_DEMO，API 接受显式 V2 candidate 并转换至现有 run/message/event；新的候选调用 Fake Planner，未读取 API key。纯标准/工程/普通路径的既有回归仍在全量测试范围内。混合任务当前只写 `MIXED_SUBTASKS_DEFERRED_CHECKPOINT_GATE`，没有执行 general→standard→engineering→synthesis DAG；无独立盲标集综合评测证据。 |
| S2.2 检查点/幂等/超时/恢复 | **PARTIAL / Gate FAIL** | `AgenticV2Candidate` 支持 checkpointer，并在临时 SQLite 测试中观察到 thread-scoped checkpoint。尚无进程重启后恢复/继续执行、跨进程幂等副作用、取消底层阻塞工作、超时后资源回收及 queued/429/Retry-After 恢复的验收证据；不能据 checkpoint 存在推断这些门禁已通过。 |
| S2.3 会话记忆/公开 trace | **PARTIAL** | 已按 conversation_id 读取已确认事实，限制只向工程路由补上下文；新增测试验证 CID 隔离及普通闲聊不继承工况。公开工具 trace 仅投影白名单字段：查询 keyword 以“已记录（查询条件已脱敏）”呈现，设备/介质/温压以脱敏占位，结果仅保留来源和公开摘要。V2 摘要流程尚未端到端集成验收；本轮未取得真实 Edge 桌面/移动交互回放，浏览器 E2E **BLOCKED**（不能以 Vitest 替代）。 |

## 实际验证命令与结果

所有命令均在本地执行；教师验证只读：

1. `.venv-langgraph/Scripts/python.exe -B scripts/test_s2.py`  
   **282 tests / 0 failures / 0 errors / 3 skips**，运行 99.984 秒；skip 为可选 Phoenix/OpenInference SDK 专项。其内含本地压测 fixture：并发 1/4/8 各 100 次，三组均 0 errors；这不等价于指定的429背压/断点恢复门禁。随后 pytest：**5 passed**。
2. `export PYTHONPATH=.; .venv-langgraph/Scripts/python.exe -B evals/r10_offline_chat_matrix.py`  
   **20 runs**（RULE_DEMO 10、DEEPSEEK mock 10），输出 `evals/r10_offline_chat_matrix_s2_20261029.jsonl`，`all_replay_consistent=true`；DEEPSEEK 为 mock，没有真实请求。
3. `cd frontend && "D:/Program Files/nodejs/node.exe" node_modules/vitest/vitest.mjs run`  
   **17 test files / 118 tests passed**。首次运行暴露敏感字段 regex 将 `keyword` 子串误判为密钥；修正为匹配 `api_key` 并将查询值做脱敏占位后重跑通过。
4. `cd frontend && "D:/Program Files/nodejs/node.exe" node_modules/typescript/bin/tsc --build --pretty false`  
   **exit 0**。
5. `cd frontend && "D:/Program Files/nodejs/node.exe" node_modules/vite/bin/vite.js build`  
   **exit 0**；Vite 仍报告 index JS chunk 约 614.49 kB（gzip 188.39 kB）超过 500 kB 建议阈值。
6. `.venv-langgraph/Scripts/python.exe -B upstream/04_接口文档/validate.py --final`  
   **554/554 clauses、200/200 trajectories PASS**（RBI 472、damage mechanism 82、multi-step 144、三类特殊轨迹各15）。
7. `.venv-langgraph/Scripts/python.exe -B upstream/05_提交区/_selftest_tools.py`  
   **17/17 PASS**。

## 失败与有界修复记录

- 原始全量 unittest 在项目 venv 报 PyMuPDF `fitz` 缺失，导致 1 ERROR；没有删测试或改预期。加入锁定测试依赖记录及 runner，复用本机已存在的 PyMuPDF，不安装包；最终 suite 0 ERROR。
- 旧 R10 脚本在当前 profile resolver / mock 调用参数下留下非 completed 状态。将离线 profile 与 mock provider 显式注入，兼容当前 `safe_profile` / `resolve_snapshot` 和 provider kwargs；改用新的 dated 输出文件；20/20 replay 通过。
- 前端首次 Vitest 发现 `keyword` 因敏感 key regex 子串误匹配而被丢弃；修复后又按隐私要求隐藏实际查询词，只显示脱敏标记；完整 118/118 通过。
- 候选 checkpoint 首版若仅基于运行时 feature flag，有机会打开默认业务 SQLite。添加 fail-closed 临时目录约束；候选测试均用临时 SQLite，未写入业务 DB。

## 当前候选变更清单

- `backend/api.py`：默认关闭 V2、fake candidate/API/event adapter、CID 事实上下文接入、临时 SQLite 限制及 PDF 空文本 fallback。
- `orchestration/agentic_v2.py`：可注入 checkpointer 与 thread/run checkpoint 配置。
- `evals/r10_offline_chat_matrix.py`、`evals/r10_offline_chat_matrix_s2_20261029.jsonl`：离线兼容修复与新结果，不覆盖历史 JSONL。
- `frontend/src/trace-events/model.ts`、`frontend/src/trace-events/model.test.ts`：公开查询条件脱敏投影及回归。
- `tests/test_v2_s2_integration.py`：flag、candidate adapter、SQLite checkpoint、conversation memory 的隔离集成测试。
- `scripts/test_s2.py`、`requirements-s2-test.lock.txt`：可复现测试入口和版本记录。

具体变更归属仍以源文件为准；项目位于父级 Git 仓库且项目目录本身在父仓库状态中呈未跟踪，不能从父级 diff 独立归因本轮文件，也未做任何 Git 索引/提交操作。上游现有 dirty/untracked 文件保持原样。

## NO-GO 阻断项

1. 混合 DAG 还未真实执行，当前明确 deferred。
2. checkpoint 之外的运行幂等、崩溃恢复、超时取消/资源清理、重试副作用证明缺失。
3. 165+（65旧题、120作者样本、独立盲标）综合路由门禁及新盲测证据未齐；不能以测试数量冒充准确率。
4. 429/Retry-After、queued 终态、断点恢复的 c1/c4/c8 指定验收缺失。
5. 端到端临时 SQLite 三路径+混合路径、消息/SSE恢复、恢复/失败重试完整浏览器验收未完成。
6. S2.3 摘要阈值/摘要来源hash和公开 trace 的 Edge 桌面/移动E2E未验收。
7. Python依赖的clean-env按锁文件重建未实跑，当前测试入口依赖本机base-site-packages组合。

## 评审决议

**GO：只限保留此隔离代码候选并继续本地离线测试。**  
**NO-GO：默认切换 V2、开启面向真实业务库的 V2、在线服务重启、部署、真实/收费 Provider、正式数据写入或教师人审声明。**

下一步须由 Owner 指定并审核：混合DAG执行方案、恢复/取消/幂等协议及对应故障注入测试、独立盲标集、真实浏览器可用窗口；在上述门禁通过前保持 Feature Flag OFF。
