# OWNER｜全栈与教师四项指标实测审查（2026-10-28）

**审查目标**：向项目 Owner 准确说明前端成熟OSS复用/视觉、真实SQLite、LangGraph多Agent、整链路延迟和导师验收四项指标。不要把RuleDemo/格式成功/静态快照冒充LLM原生成功或人工审核。

## 1. 前端及复用（已读源码及P7截图）
- `frontend/package.json`: React19+Vite8+TypeScript7，`@assistant-ui/react`, `@xyflow/react`, `react-markdown`+`remark-gfm`, Tailwind4, Radix, CVA, lucide-react；`frontend/src/components/ui/`仅见`badge.tsx, button.tsx`，因此shadcn为**部分设计模式/少数组件**，不是完整组件库。
- `frontend/src/AssistantMessages.tsx`通过`AssistantRuntimeProvider/useExternalStoreRuntime`使用成熟线程组件，但`onNew`是no-op，实际消息发送通过独立App/FastAPI API；不能宣称官方Runtime全栈托管。
- P7B Edge真实44/39 SSE双run，消息历史与run绑定快照；Owner重跑`Vitest 36/36`；截图P7B移动390含已知输入状态标记和报告折叠。外观一致、较美观但移动摘要文本密集、右侧执行图/JSON需缩减默认暴露。输入快照只在localStorage，不是可信服务端签名、非跨设备。
- Frontend build曾P6实测JS chunks main 295.56kB、assistant 486.29kB、agentflow 178.39kB（未压缩），应继续测真实首屏TTI/LCP，而非只测build。

## 2. 真实后端与SQLite
- `backend/api.py` 是真实FastAPI endpoints：conversation/message、runs、SSE、replay、claims、disagreements；`backend/store.py` SQLite WAL、foreign_keys、lease CAS、events unique(run_id,seq)、终态assistant消息+run_completed原子提交、失败租约旧worker拒写。
- 9表：conversations/messages/runs/agent_events/tool_calls/evidence_refs/knowledge_documents/claims/disagreements；LangGraph SQLite checkpoint是另一个数据库。
- **24次临时SQLite TestClient E2E**：`evals/owner_p7_fullstack_latency.py`；数据库PRAGMA integrity_check=ok、foreign_key_check=0、journal_mode=wal、24 runs，SSE帧数与DB event数全部一致。未访问/修改正式业务数据库。
- 尚无SQL迁移版本框架、备份演练、用户身份/租户数据权限、正式生产部署/认证。当前APP_ENV=production无认证fail closed；本机demo可用但不可公网开放。

## 3. Agent层真实现状
- `orchestration/graph.py`是真StateGraph七角色：Supervisor/Evidence/Diagnosis/RBI Specialist/Evidence Auditor/Skeptic/Reporter；全部`RULE_DEMO`节点，路由条件与SQLite事件可审计，不能等于7个真实LLM。
- 实验`orchestration/p6_parallel_audit.py`由P7A新冲突E0门禁保护，但**未接到生产默认图**；P7A新7测通过，合并Python101旧断言1项仍待调整，不为绿灯放宽E0门禁。
- E0/E1来源级、E2/E3无真人/专业认证；独立Skeptic当前确定性词法/规则反证，非真正独立模型审查。RBI不在缺因子时自动给L1-L4是正确的。
- **真实路由Bug**：`SupervisorAgent.run`先做`material/medium`缺失检查，后检查标准查询，因此未带设备上下文的“请检索xxx标准条款”会跳ask_for_context、不调用`standard_clause_search`。Owner本次24次TestClient实测“standard_search”8/8均0工具调用。应把独立纯条款搜索在缺设备检查之前分流，同时限制是否是纯标准查询，负例防止“帮我在设备上判风险”的绕过。

## 4. 本机后端整链路耗时（本轮新实测，不是LLM与公网）
命令 `./.venv-langgraph/Scripts/python.exe -B -m evals.owner_p7_fullstack_latency`。
24次：3场景×8次，独立TempSQLite/Checkpoint，TestClient→FastAPI POST→Worker→LangGraph→工具→SQLite→SSE GET完成，不含真实浏览器、网络、LLM、冷导入。P95采用nearest-rank。
|Case|P50 POST到SSE结束|P95|tool_results|events|
|---|---:|---:|---:|---:|
|缺工况|1092.74ms|1422.46ms|0|16|
|完整工况|2362.16ms|2869.72ms|2|40|
|不带工况的标准查询|1013.77ms|2410.43ms|0（发现路由缺口）|16|
所有SSE帧与DB events数量一致，图执行P50 981.28ms/P95 2418.7ms。性能剖析待完成，不能把耗时自动归因于SQLite/LLM。曾有纯规则节点P50~63.91ms不含同样全链路，指标不能混比。

## 5. 老师4项指标：逐项事实
四指标来自`upstream/04_接口文档/技术指标验证方法.md`；交付9件见`upstream/README.md`第八部分。
1. ModelScope Studio公开链接及Gradio过程展示与单步/多步/护栏/域外4类截图：**BLOCKED/未验收**。本地React+Edge浏览器存在但没有公开魔搭链接或教师明示等价替代。
2. ≥50条随机、双人交叉核原PDF、准确率≥95%（50条中最多2错）：**未有真实签署和正式报告；NOT VERIFIED**。Schema的E1不能替代人工原文蕴含。
3. Harness≥5轮**真实连续调用**：Harness MAX_ROUNDS=8是能力上限，不是已跑完5轮的证据；Owner只读现有200条`trajectories.jsonl`计数分布1步26、2步30、3步144，**0条≥5步**，需额外5轮 live demo 录屏/log。轨迹完整率100%需额外100次（含异常）逐步计数日志：目前仅200数据格式PASS，不可冒称完整性验证。护栏36/36阻断、normal60/60通过（Owner实际执行官方run_guardrail_tests、文件行数复核）：**PASS**；真实LLM100组、原生工具解析≥95%和BFCL AST：**NOT RUN/NOT VERIFIED**。
4. `validate.py --final`：**PASS** 554/554 clauses(RBI472,DM82)、200/200 trajectories、多步144/≥40，三个特殊各15/≥15，结构/枚举/ID可追溯全部通过；不代表原文每条内容人工核对通过。
附：官方三工具`_selftest_tools.py`17/17 PASS；两个Harness镜像SHA检查一致；老师的三个工具签名/五键返回冻结。
原RBI Excel still472，有13条候选在独立工作簿，U/V真实抽取人/复核人未签，原表不改、正式条款总数未变化。

## 6. 优先级
P0：本地冻结现有三工具/数据；只修测试陈旧断言，不放宽新P7 E0冲突门禁。
P0：改Supervisor纯标准查询路由并补负向测试。
P0：接真实OpenAI兼容provider的官方单Agent Harness，**先10题再100题**，只拿不含真实敏感工况/未授权收费标准全文的测试输入。统计`native_parsed_ok/fail`、合法工具、fallback、延迟、价格。
P0：验证导师单Agent的≥5轮连续调用、100次轨迹完整率、50条真人双交叉审阅，建立9项交付证据矩阵。
P1：测完整UI browser E2E性能（TTFT、事件到达、P50/P95），profiling LangGraph checkpoint与SQLite事件写入；不要仅优化0.6ms并行microbenchmark。
P1：打造不泄密的ModelScope/Gradio最小可公开演示独立入口，不直接放开缺认证的React+SQLite本地工作台。
P2：有真实模型和人工Gold后，单Agent vs 序列审查vs并行审查 A/B；收益可证后再打开生产并行。Human-in-loop审批仍需要受控身份。
