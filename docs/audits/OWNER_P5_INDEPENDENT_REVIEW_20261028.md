# P5 Owner 独立审查 / 学习迁移（2026-10-28）

结论：**P5A和P5C作为本地研究工作台研发里程碑PASS**；未授予公开部署或工程风险最终定论权限。Owner独立读取两份报告与真实截图，并实测全量回归；没有修改原始老师PDF/XLSX、三个固定工具、五键协议、官方JSONL或P5业务代码。

## 已独立重跑
- `./.venv-langgraph/Scripts/python.exe -B -m unittest discover -s tests -q`：87/87 PASS（16.165s）。
- `./.venv-langgraph/Scripts/python.exe -B -m unittest tests.test_p5a_lease_event_integrity -q`：6/6 PASS。
- `./.venv-langgraph/Scripts/python.exe -B -m evals.owner_p3_regression_probe`：旧三个缺陷保持修复：缺页→missing/E0、双SSE单run→1次图执行/1条assistant、裸问题未注入设备事实。
- `./.venv-langgraph/Scripts/python.exe -B -m evals.owner_p4_integration_probe`：完整工况→44 SSE events/2 claims/2 disagreements/7 references；旧worker在failed后追加事件→`PermissionError`，正常。
- `node ./node_modules/vitest/vitest.mjs run --reporter=dot`（cwd=frontend）：30/30 PASS；TypeScript `tsc -b`和Vite 8.3.5 build PASS；3102个模块，主JS 288.21kB，AssistantMessages 485.81kB，AgentFlow 178.39kB（原始构建输出，需注意网络加载/异步拆包）。
- 官方教师 `validate.py --final`：554/554条款、200/200轨迹 PASS。
- 上游Git状态：只存在原先未跟踪的13条候选XLSX。教师RBI原表仍472正式条；未在当前P5修改。

## P5A审查
`Store.append_event`现在显式`worker_token`+running状态+SQLite`BEGIN IMMEDIATE`同一事务进行CAS核证、序号及所有投影写入；`recover_stale_run`在另一路特权系统路径生成唯一`worker_lost`，终态拒绝旧worker追加。最终`finish_run_with_message`的`run_completed`+assistant答复+状态切换原子提交。6个新测试+旧反例回归均通过。仍仅单机SQLite/loopback方案，不能将其等同跨主机强一致调度。

## P5C审查
真实Edge CDP原报告给出：完整工况(碳钢/氯化氢/换热器，pH5.8、Fe4.1mg/L、未测厚)→44连续事件、2 tool calls、7 reference_added、2 Claims(E0+E1)、2 disagreements；replay(5)得39条，刷新44条/2卡；跨会话无串线，真实Drawer及放大Graph。原报告和P5C JSON都吻合，Owner实看截图`P5C_E1_SOURCE_DRAWER_1280.png`、`E0_SOURCE_DRAWER_1280.png`、`MOBILE_390.png`、`GRAPH_EXPANDED_1280.png`；不是本轮重新操作Edge。
E1Drawer：引用页、CID、canonical记录哈希及待人审；E0Drawer：来源不足显示partial/unresolved。移动端文字段落过长、技术字段混杂，下一阶段需要“结果摘要→展开出处→审计JSON”的分层呈现。
`P5C_FULL_EVIDENCE_E2E.json`中的`reference_gate_counts={E0:7,E1:1}`并非共8个reference事件：查看源码`frontend/scripts/p5c_full_evidence_e2e.mjs`，E0统计的是ref events，E1统计的是claim grade，混了两个计数母体；**报告计数应改成`reference_event_gates`和`claim_grades`两项，不可把7+1当引用总数**。不是产品业务缺陷，但属于指标命名不严。

## 尚未放行的边界
- P5A事件保证“终态不可写”，但真实图状态并发fan-out尚未上生产；GraphState当前字段缺少reducer，启用并行会遇并发更新冲突。Owner在`scripts/lesson05_parallel_reducers.py`实际做了独立LangGraph实验：缺reducer→`InvalidUpdateError`；加`Annotated[list,operator.add]`和并行fan-in节点→PASS，无生产数据修改。
- 现仍`RULE_DEMO`。`E1`只是来源可溯，不是PDF真值、标准蕴含或设备适用性证据。E2/E3、真实模型/专家金标、审批身份责任链未完成。
- 本地demo API有loopback guard、production无认证则AUTH_REQUIRED；公开服务仍无鉴权、会话所有权、生产授权，不得发布公网。
- RBI Excel原始13新增候选待真实抽取人及独立复核签名；老师convert后官方JSONL仍554条，不能据此宣称485 RBI已写入。
- UI上应把结论/补充信息作为首屏，而把RID/UUID/hash/技术审计默认折叠；原始规范片段应仅在本地授权用户可见。

## 下一阶段
P6-A：先作**隔离LangGraph并行实验→有边界flag的灰度方案**，维持固定3工具、E0/E1与P5A worker lease不退化；不得仅套operator.add到所有State字段。A/B比较顺序与并行的工具计数、延迟、错误、不支持风险结论。
P6-B：前端专业交互：结构化摘要“现场已知/未知、候选机理与未证实、需补检测、来源与审查状态”；E0/E1在独立详情区，默认不铺20行IDs与英文码；保持真SSE、claim审查、移动完整E2E。与A分开目录。
P6-C：人工审核/评测方案先设计**身份与审阅契约**、Owner及机械专家校对记录、真实工况金标schema与盲评流程；未征得确认不导入真实个人/敏感工厂数据，不把 synthetic label 写成gold。
下一课`docs/COURSE_05_LANGGRAPH_PARALLEL_REDUCER_20261028.md`，配套真实通过的脚本`scripts/lesson05_parallel_reducers.py`。
