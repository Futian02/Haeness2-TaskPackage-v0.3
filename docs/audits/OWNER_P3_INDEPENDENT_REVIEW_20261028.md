# P3 Owner独立验收｜工程证据审查（2026-10-28）

**决策：P3-A = ACCEPT_AS_LOCAL_VERTICAL_SLICE；P3-B = ACCEPT_AS_RULE_DEMO_EVIDENCE_SCAFFOLD；P4_GATE = BLOCKED。不是生产或公开域名放行。**
当前用户只要求审核；本轮未修改P3A/P3B业务源代码、教师三工具、官方数据或RBI原表；新增独立无损探针 `evals/owner_p3_regression_probe.py`。所有可复现BUG均区分“旧测试通过但未覆盖”。

## 1. 独立现场重跑证据

| 项目 | 实际命令/证据 | 结果 |
|---|---|---|
| Python | `./.venv-langgraph/Scripts/python.exe -B -m unittest discover -s tests -q` | 54/54 PASS（8.301s） |
| Teacher | `./.venv-langgraph/Scripts/python.exe -B upstream/04_接口文档/validate.py --final` | clauses 554/554, trajectories 200/200 PASS |
| sources | `./.venv-langgraph/Scripts/python.exe -B -m scripts.check_sources` | 19/19 |
| React/Vitest | `node ./node_modules/vitest/vitest.mjs run --reporter=dot` （cwd=frontend） | 6/6 PASS |
| TypeScript | `node ./node_modules/typescript/bin/tsc -b --pretty false` | PASS |
| Vite | `node ./node_modules/vite/bin/vite.js build` | PASS，3101模块，initial 278.22KB/88.66KB gzip，assistant chunk 485.81KB/142.67KB gzip |
| 前端视觉 | DevSpace只读图片内存解码：`frontend/evidence/p3a-e2e-desktop.png` 1280x900 与 `...mobile.png` 390x844 | 确为真实UI截图，桌面三栏/手机Tab布局存在；非本轮重新操作浏览器 |
| npm run | `npm test/typecheck/build` 在当前DevSpace远程bash的Windows npm脚本子进程无法识别 `node`（PATH上下文异常）；直接用node调用以上脚本均通过 | 环境入口问题，不是代码构建失败 |

P3-A报告还记录Edge真链路34个SSE事件、5张来源卡、刷新恢复2条消息和34条事件；本轮对报告、源码和已有截图做交叉检查，但**没有在本轮再启动Edge浏览器完整E2E**。P3-B仍全程 RULE_DEMO，不是假装真实LLM多agent。

## 2. P1阻断风险（已独立复现，见`evals/owner_p3_regression_probe.py`）
### P1-01 同run重复执行和assistant消息重复（真实安全性/幂等缺口）
`backend/api.py:stream_run`先调用`store.run(rid)`读取`queued`并把该状态闭包延迟到StreamingResponse的generate执行；只有generate中才`set_run_status(running)`。两个GET请求如果在流被消费前都取到了queued，就启动两次图运行。
复现：使用**仅临时SQLite**、两个预先构造的stream响应与模拟图，`graph_executions=2, assistant_messages=2`，同一个run_id。风险：重试/多端打开触发重复模型扣费、消息重复、SQLite事件写入竞争/图checkpoint交错。
修复 Gate：`Store.claim_run(rid)`单SQL `UPDATE runs SET status='running' WHERE id=? AND status='queued'` 以影响行数获得唯一工作权。非抢到的一方只能订阅/重放；worker故障需幂等终态和可恢复处理。追加2-10并发请求的独立集成回归：一个run最多一次执行/一次assistant消息。

### P1-02 原本缺失的页码元数据被报告为已匹配
`orchestration/evidence_audit.py:audit_claim`比较source中的standard_code/clause_no/page，当返回值为None时走`else -> matched`；来源缺页码当前仍`E1`。
实测：正式库标准页12，当前run source不含page，结果`metadata:page=matched; grade=E1`。
修复Gate：分别记录matched/mismatch/missing/unknown；仅在条款成员/同轮来源/强制元数据检验均满足时赋E1，否则E0或新子级“provenance_partial”，不得声称已核页码；每个字段设置负向单测。

### P1-03 FastAPI客户端遗漏工况时注入示例设备事实
`backend/api.py:RunIn`默认`equipment='常压塔顶空冷器'`, `equipment_type='换热器'`, `material='碳钢'`, `medium=['氯化氢']`。虽然React表单明确传空，直接API只POST question时会把例子当真实设备工况。
实测`RunIn(question='请判断设备风险')`自动包含上述非空事实。
修复Gate：所有设备/工况默认缺失（空或None），由Supervisor要求补充；example fixture只能在明确标明simulation/用户点选示例时注入，测试 direct HTTP POST 只有问题必走ask_for_context、没有具实质的设备损伤建议。

### P1-04 规则Skeptic实际上拿不到原文
本机实际调用冻结`standard_clause_search(keyword='盐酸腐蚀')`，返回source每项仅`['clause_id','clause_no','page','standard_code']`，**没有content_raw**。`orchestration/evidence_audit.py:skeptic_findings`只从`state.tool_results[*].result.source`读取`content_raw`，所以会常态报告“缺少可检查的content_raw引文”而无法按文本审查。
这是功能完成度门槛而非老师工具bug；**禁止修改冻结教师3工具返回**。应先核正式source ID+metadata，再本地只读`clauses.jsonl`从canonical index取得已摘录的`content_raw`并留证据链；新Skeptic要能自己检索替代候选/反例，而不能只在Diagnosis引用的ID里循环。文本蕴含仍不可自动宣称E2，E2/E3需独立验证流程。

## 3. P2质量/可用性问题（代码审阅发现，尚未单独复现）
1. frontend/src/App.tsx 的`graphEdges`是按固定roles顺序生成，节点状态来自真实事件，但**图连线并不根据真实条件路由重构**。应使线源于本轮执行`agent_started/completed`实际跳转；not triggered用淡化/虚线，而非展示固定全连接；网页应明确“观测图≠计划图”。
2. frontend/src/App.tsx:postRun与loadConversation闭包使用selected；用户流中切换会话后，旧请求响应可能覆盖当前detail/events。缺少 per-conversation request token/AbortController及 stale completion guard。端到端需测“运行时切换会话”、“快速点击两个会话”、“重连/刷新”。
3. 侧栏历史只有最近一个run_id在localStorage，未提供GET /api/conversations/:cid/runs；跨设备/清理本地存储后SQLite虽保留所有事件，UI无法枚举历史runs。不阻断本地演示，但应补兼容只读列表API和server-side索引。
4. P3A桌面截图在1280宽三栏后正文列明显狭窄、正文较密、图canvas微小；建议可折叠右侧、聊天宽度≥640px视窗策略、引用逐条卡片和审查drawer；mobile截图文本密度仍高，适合折叠技术报告正文。
5. E0/E1 claim的多事件可能重复成为多个citation卡；应按claim_id归并最新审查状态，以审计时间线保留历史。
6. P3B `_condition_checks`当前多个实际介质与多个允许介质是`any`交集，不能把`matched`直接当装备适用性（它仍只是E1，当前未伪升E3），应为混合介质和范围交集加显式not_sufficient审查。
7. `backend/store.py` 事件序列生成采用`MAX(sequence)+1`后写，未来真正并行Agent节点同时提交事件可能竞争；若启用fan-out需事务化单run event writer。
8. `frontend/src/api.ts` SSE重连有有限次数且按run_id+sequence去重（优点），但现在`stream_run`服务端启动重入风险远高于前端去重，先修P1。

## 4. P0公开部署安全门禁
`backend/api.py`目前无认证/用户隔离/请求速率约束，`GET /api/conversations`、`GET /api/conversations/:id`、`GET /api/runs/:rid/events/claims/disagreements`等接口一旦公开，会允许其他网络访问者查看全部会话、设备工况和审计记录；health还暴露数据库绝对文件路径。
**本地127.0.0.1演示可继续，禁止在未鉴权和访问控制前绑定0.0.0.0/自定义域名对外开放。**部署另须CSRF/CORS/请求体上限/上传权限/生产日志脱敏/SSL/持久化备份检查。不要把“npm audit 0 vulnerabilities”误认成Web数据安全完成。

## 5. 通过项与接受定义
- P3-A：本地React/TS组件、助手UI运行态、SSE解析、相同run去重、移动响应式、已有Edge截图与报告符合`accept_as_local_vertical_slice`；不等于生产部署准备完成。
- P3-B：冻结3工具、E1来源级（但细节仍有bug）、Claim/Skeptic/SQLite后端扩展、异常时不生成unsupported risk claim，符合`accept_as_rule_demo_scaffold`；独立专业反证/真实LLM审查未完成。
- 教师原始资料和初始合同本轮未改。原始RBI.xlsx尚未合并13候选，待真实抽取人/复核人签核和原表合并脚本的本地执行。
- 只有修完P1-01~04，且P0部署安全检查通过，才讨论公开域名。若仍只有RULE_DEMO，则网页和论文中不得声称“已实现多模型交叉验证”。

## 6. 分工建议
P4-A只改 backend/, tests/test_p4a_*.py，修原子run claim、工况默认值/安全、run列表、部署安全门禁与health隐私；P4-B只改orchestration/, tests/test_p4b_*.py与evals/新评测，修原文取证、元数据检查、独立反证、可证伪场景；P4-C只改frontend/，优化可读性、真实边、claim聚合、切换会话竞态、历史列表，等P4-A提供新API后做联调；Excel原表另以`scripts/merge_rbi1_into_original.py`在真实签名后单独处理，不能并发覆写。
