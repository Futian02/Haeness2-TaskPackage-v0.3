# P4 Owner 独立代码审查与复核结果（2026-10-28）

**裁决：P4A / P4B / P4C 均通过本地研发阶段有条件验收；P4整体合并回归已修复至81/81；对公网、生产认证、真正多LLM审查均不放行。**

本审查是基于当前磁盘源码、真实命令和独立临时数据库实验，不等于仅复述Codex报告。未提交/部署；没有修改 `backend/`、`orchestration/`、`frontend/` 的业务源代码，没有改老师三工具、合同、原始RBI Excel/PDF、官方clauses或trajectories。

## 实际重跑（当前磁盘状态）
- 先实测 Python全仓：81项，80 PASS、1 FAIL。失败 `tests/test_p3b_evidence_audit.py::test_explicit_condition_mismatch_is_not_applicable` 源于旧fixture缺`content_raw`，却要求grade E1；新P4B E0是正确fail-closed而非运行错误。
- Owner已用`DevSpace.edit`对**测试夹具**加真实（仅测试用、非标准声称）`content_raw`，使旧断言实际检查“来源完整E1但条件不适用”，没有改变P4B业务规则。**全量复测81/81 PASS**，P4A单项11/11、P4B单项16/16。
- 修改 `evals/owner_p3_regression_probe.py` 的旧“重现BUG期待”断言为“BUG修复后期待”，再次运行：页码缺失→E0/missing；同一run双SSE→1次执行/1条assistant；仅question→材质None/介质空/设备类型None。原三工具`standard_clause_search`返回source四字段不含content_raw，仍在P4B从本地正式JSONL做只读回查。
- React执行：`node ./node_modules/vitest/vitest.mjs run --reporter=dot`（cwd frontend）**24/24 PASS**；`node ./node_modules/typescript/bin/tsc -b --pretty false` PASS；`node ./node_modules/vite/bin/vite.js build` PASS，3102模块、主chunk 285.05KB（gzip90.64KB）、助手chunk 485.81KB（gzip142.67KB）、Flow178.29KB（gzip57.46KB）。
- `./.venv-langgraph/Scripts/python.exe -B -m evals.p4b_verify`：`RULE_BEHAVIOR_PASS_NOT_EXPERT_GOLD`，20条synthetic未审+14条负例；P50 0.019ms、P95 0.048ms为单个审核函数微基准，绝非LLM或完整前端耗时。
- 官方 `validate.py --final` **554/554条款、200/200轨迹全部PASS**；`scripts.check_sources`19/19；上游教师Git tracked diff为0，且唯一上游未追踪文件是既有独立13条候选工作簿。
- 原Excel `upstream/01_RBI标准/条款摘录表_RBI.xlsx` SHA256 `38cf71bf9f9868cfa531729cda70dea2e2857b3a788ec1a67f56d27ef01512f9`，**未完成13条并入**（需要真人抽取人身份与复核）。保留472条RBI，官方554总条数。

## 后端真实正向E2E（不同于P4C的缺工况E2E）
新建`evals/owner_p4_integration_probe.py`，使用TempDirectory独立SQLite+checkpoint，直接`TestClient`触发FastAPI→LangGraph→三个官方工具→证据核验/反证→SSE→claim/disagreement持久化。给碳钢/氯化氢/换热器与pH、Fe、缺测厚现场文本：
- **44 SSE事件、7条reference_added、2条claims、2条disagreements**，run终态`completed`、一对user/assistant消息；Claims有E1、E0，但都`unresolved/requires_human_review`，不假充设备定论。
- P4C浏览器日志中**16个事件的那次运行**只有run/supervisor/审查/报告等边界路径，没有任何`claim_added`或`reference_added`；虽浏览器截图和SSE回放可信，**它没有验证前端复杂证据卡与真审查面板的浏览器全链路**。下一轮应补至少1条完整工况浏览器E2E，含Claim/E1/E0/反证/引用展开、刷新与模式标示。
- 已只读解码并检查P4C 1280×900与390×844实际截图：桌面聊天主区显著更宽，移动端无明显横向溢出，RULE_DEMO标签明确；右侧React Flow画布仍较小（~267px宽，文字难读），可增加放大/Drawer/全屏查看。P4C的运行图按真实`agent_started`事件拼接，较P3更可信。

## 新发现的异常/安全边界
**P1：失败终态之后仍可追加审计事件。**
Owner`evals/owner_p4_integration_probe.py`第二探针：临时DB里`claim_run`成功后把租约心跳改为过期，`recover_stale_run`写入持久`error`且run为`failed`；随后`store.append_event(rid, "claim_added", "old-worker", ...)`仍成功，产生sequence=2。此处不是P4A声称的双流启动回归，而是失效/租约回收**之后的孤儿事件写入**问题。若长时间阻塞的旧worker恢复并继续调用emit，会污染审计轨迹，且部分已关闭的SSE消费者不会收到它；应由有效worker_token+running状态对事件写入做原子CAS；failed/completed之后业务worker不得追加，recover_stale_run生成的系统错误事件例外。写负向回归，禁止把该问题从UI隐藏即可“修复”。

**P0：公网发布不满足条件。** `APP_ENV=production`中间件确实返回503 AUTH_REQUIRED；development/loopback可本机运行，但没有真正认证、个人数据隔离、访问控制或代理信任模型。localhost反向代理若公开暴露且忘配production仍有风险。不得将Vite或FastAPI dev server暴露到公网/域名；还须身份权限、CSRF/CORS、日志脱敏、请求体流式限制与备份/多worker策略审计。

**P2未解：真正专业判断**仍是RULE_DEMO、非独立大模型；Skeptic有词法二路召回与正式原文关联，但`E2`标准文本支持、`E3`设备适用性没有已验收人工签核或专家金标。20条synthetic不可计算真实专家准确率。
**P2界面完整性**：P4C 16条事件的浏览器E2E只走缺信息路线，缺完整正向Claim/Evidence UI/browser E2E；须补真实工况case。
**P2 Schema可持续性**：用户想要领域工作台，多用户权限前不得开放上传或原始标准PDF公共分发；过长原文/版权/商业数据不能直接公开。

## 修改文件清单（Owner）
1. `tests/test_p3b_evidence_audit.py`：旧fixture补content_raw以保留“完整来源但工况mismatch→E1仅溯源”的测试含义，未放宽任何门禁。
2. `evals/owner_p3_regression_probe.py`：三个旧BUG复现断言变为修复后回归断言。
3. `evals/owner_p4_integration_probe.py`：独立后端正向E2E和终态后事件的临时SQLite反例脚本。
4. 本报告。业务源码/老师数据均未改。

## 下一轮优先级/验收
1. Owner/P5A：`Store.append_event`持久化事件必须绑定run worker token（系统recover写error除外），run状态为failed/completed禁止旧worker写入；SSE终态无孤儿事件。扩展完整异常/消息回放/多订阅测试和EventStore读写事务。现有81测试全部通过。
2. P5C：完整工况真实Edge浏览器E2E（至少两个claims和真实引用展开），记录实际E0/E1、人工待核；在桌面右侧Inspector改善放大。
3. 真正人审+电价领域以外机械RBI真实场景Gold评估前，仍禁止把多角色确定性节点称“多LLM交叉验证”。
4. 后续独立Excel工作线：原表U/V真人签核后执行已预检的`scripts/merge_rbi1_into_original.py`；正式老师convert和validate通过后再合并。
