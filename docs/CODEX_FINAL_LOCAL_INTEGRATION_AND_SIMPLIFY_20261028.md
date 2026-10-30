# 最终一次Codex集成任务｜收敛到能用、能学、能停的本地机械智能体
状态：READY_FOR_OWNER_APPROVAL；本任务书已生成，**本轮没有执行集成**。

项目根目录：`D:\作业\竞赛\计算机设计智能体\机械智能体`
第一步阅读`AGENTS.md`、`docs/OWNER_R9_FINAL_REVIEW_AND_CLOSEOUT_20261028.md`、`docs/audits/R9A_GRAPH_CANDIDATE_ACCEPTANCE.md`、`docs/audits/R9B_COLLAPSIBLE_TRACE_PHOENIX_ACCEPTANCE.md`、`docs/audits/R8B_UI_FULL_ACCEPTANCE.md`。两个R9工作窗口和R8B均已READY_FOR_OWNER_REVIEW，先检查文件没有再次并行编辑。

核心目标：**不要开发第2套系统，直接合并已有成熟成果为唯一正式本地演示。质量可测试、效率优先、文件结构易懂，达到本文件全部硬门槛后立即停止工作。**

### 任务1：只保留一个正式Graph（不是换框架）
- 把`orchestration/r9_industrial_candidate.py`的真正有价值行为接到`backend/api.py`现有run worker路径和SQLite/SSE EventSink：标准查询可不提供材质、设备机理调查最多3轮、必要时Auditor+Skeptic并行、证据足够才报告、缺现场测量直接要求补充或给未决。保留教师恰好三个固定Tool、5key返回协议，不能新增第4个工具或把真实标准打包送外网。
- 别把新Graph当作另一个`AgentGraph`选择长期维护，也别在正式代码里同时保留两套冗余Supervisor/Evidence/Diagnosis/RBI类；验证新版本后，**唯一正式运行路径**就是简短主图，旧实现可移动到`archive/legacy_graph/`作学习参考，但确认所有导入/回归不依赖后再移动，未经明确Owner批准不要删除。
- 别把所有设备诊断强制要求`wall_thinning`：机理候选可以在缺壁厚时提示“待核”，只有减薄确认/设备RBI等级才需要测厚等对应证据。标准检索不仅校验返回CID存在，还需要标准名称/关键问题相关性检查，零有效命中就诚实说明没查到。
- 真实Graph必须有至少一次受控重试和一次真实并行审查，工况不足和零增益能提前结束。默认仍`RULE_DEMO`，没有用户API时不能假装用了多LLM。不要引入复杂重试架构、新Hash服务/事件总线/缓存集群。仅保留现有SQLite租约一致性和来源归属必要字段。

### 任务2：把真实折叠过程直接放进R8B聊天
- `frontend/src/components/trace/ActivityTrace.tsx`已经可用；直接复用现有assistant-ui与`frontend/src/AssistantMessages.tsx`进行小范围接线。每次助手回复可折叠“执行了N步/检索了X次/审核状态”，点开能看到本轮真实工具调用、公开决策摘要、来源、审查结果、耗时。刷新/多会话恢复来自SQLite/SSE，不从localStorage制造没发生的活动。
- 保留R8B已经做好的左侧聊天目录/问题轮次跳转/真实上传/上下文快照；聊天主屏不显示大段hash/JSON。可用Phoenix独立本机页面开发者调试，启动`TRACE_BACKEND=none`时主聊天应全部可用；若Phoenix集成需要修改很多Graph核心，就**先保持可选Standalone**，不要强行做。
- 视觉上按R8B截图的简洁路线收敛，不大改框架/颜色。独立R9B demo页面可留archive，不当用户第二入口；别用iframe把Phoenix整个站点嵌进聊天页面。
- 文件上传保留必要的文件类型/尺寸/不同会话隔离，不为工程完备性添加新的安全平台或加密服务。未授权上传PDF不会自动成为官方标准条款或发给第三方模型。

### 任务3：一次性修小毛病和整理学习入口
- 旧`tests/test_p6a_parallel_evidence.py`一个过时断言期望E1→改为当前正确保守E0，并追加冲突hash仍保留的明确断言；不要改实际P7A安全合并算法。
- `tests/test_r9b_observability.py`用了可选SDK，在主Python env缺依赖会ERROR。选择最简单的方式区分**业务主测试**与**可选Phoenix专项测试**，不要求所有人为了跑基础聊天安装Phoenix；确保主业务测试全绿，专项仍在`observability/.venv` 6/6真实PASS。不可把真实失败通过笼统skip掩盖，报告各自命令。
- 仅更新根`README.md`（一页足够）和`docs/PROJECT_STATUS_CURRENT.md`、`docs/ARCHITECTURE.md`（一张短图+数据流），把`docs/PROJECT_STATE.md`首页标记2026-10-27是历史资料并链接CURRENT，不要重写上百份旧报告。
- 文件夹只需告诉Owner`frontend/backend/orchestration/upstream/data`五大核心，`tests/docs/observability`是辅助；`app/web/knowledge/旧evals`等仅在确认无入口引用时才允许移动进`archive/`，否则**优先只出清单、不要移动**。禁止`git reset/clean`，尤其不能碰父级Git仓其他项目。
- 原RBI Excel R8A草稿(485行、13条U/V无签)未获Owner本人核签，不要编辑/触发正式convert，也不要将源草稿声称入官方554条款。不要修改任何`upstream/`。

### 单次收工Gate
1. 一条启动说明：`npm run build`后通过本地FastAPI访问一个唯一聊天UI，创建会话→明确工况→启动新短Graph→2工具→必要时双审→有据报告，折叠展开活动；刷新恢复；再演示缺工况、纯标准查询、上传TXT/PDF。
2. 前端最新72条测试+新增集成UI行为测试、TypeScript/build真实PASS；业务Python原回归（旧断言更新后）PASS；Phoenix独立6/6；老师validate554/200 & selftest17/17 PASS。
3. SSE run_id/sequence与DB一致、无重复assistant消息和未授权最终风险等级；流程循环有预算、无无限退回，UI不存在虚构Agent与虚假思维链。
4. 报告真实案例每条路径、tools数、是否并行、端到端本地P50/P95（至少3场景每组5次、包括API/SSE和本地规则检索，且不含LLM要注明）、截图桌面1280/手机390。
5. 交付`docs/audits/FINAL_LOCAL_INTEGRATION_ACCEPTANCE.md`一份，不再创建P10/P11重复目录/十几篇差不多的门禁报告；未提供API则诚实报告`RULE_DEMO`为已完成演示版而`REAL_LLM`为BLOCKED。

达到上述Gate就**停止新增功能**并交Owner审查，不部署、不提交、不删除任何用户项目或老师文件。后续“真人签核标准/100次模型解析/ModelScope公开演示”属于单独老师验收，不能拿本地演示代替。
