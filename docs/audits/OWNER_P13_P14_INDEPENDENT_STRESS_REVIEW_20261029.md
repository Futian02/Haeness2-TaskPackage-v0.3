# Owner P13/P14 独立代码审查与二次压力复测（2026-10-29）

**裁决：P13 LOCAL_TESTS_PASS / P13_REAL_PROVIDER_BLOCKED / P14_CONTENT_REVIEW_BLOCKED。**
执行方式：DevSpace 从本地源码/报告/真实P14工件读取并独立执行测试。只新增两份隔离压力诊断脚本和本审计报告；不写生产会话DB、upstream源PDF/两份Excel/正式JSONL，不发真实DeepSeek Search/Chat调用，不重启用户现有8000服务。

## 1. P13-P14 官方与全量回归（本轮独立实测）
- 后端：`.venv-langgraph/Scripts/python.exe -B -m unittest discover -s tests -q` → 195 tests OK (skipped=3)，即192实际执行+3按可选依赖跳过。此时P14报告中的“194 tests/1旧P5A失败”为P13最终修复前快照；本次P5A failed终态现在明确追加run_failed，旧测试相应修正为failed->[1,2],completed->[1]，其安全语义正确，独立全量通过。
- 前端Vitest：17 files /115 tests PASS；tsc -b PASS；Vite build PASS（3124 modules, index JS 614.49KB，gzip188.39KB，超过500KB建议值，是非阻断的加载性能欠账）。
- 教师validate --final：554/554条款、200/200轨迹，多步144，三特殊轨迹各15 PASS；`_selftest_tools.py`：17/17 PASS。**不能说明标准文本真实性或真LLM 100题解析达标。**
- P14 `unittest tests.test_p14_pipeline_artifacts` 5/5 PASS；双教师模板原样副本RBI472、DM82，候选JSONL554条和正式JSONL**零字段差异**；未蒸馏新增真实可交付知识。

## 2. 压力复测的三种层级与真实指标
### 2a. Codex同一测试脚本独立重跑（SQLite基础 Run 生命周期）
- 1并发100：P50 84.834ms/P95 169.230ms/最大343.891ms/批次9766.938ms，0错误。
- 4并发100：P50 220.571ms/P95 482.198ms/最大800.231ms/批次6120.728ms，0错误。
- 8并发100：P50 255.586ms/P95 1367.065ms/最大3387.653ms/批次5368.697ms，0错误。
（第二次全量后端重测内又运行一遍此脚本，3组也全过，但受整机并发调度影响延迟不同；不可挑较好一组宣称服务SLA。）

### 2b. Owner独立新脚本（混合成功/失败、重放、租约终态）
脚本`scripts/owner_p13_p14_stress_review.py`，三组每120个，共360；288完成/72按设计失败；0非预期错误。每次检查：claim不可重复、事件序号[1,2]、失败只有run_failed不假装run_completed、失败无助手答复、已完成只有单一terminal、SSE断点重放offset正确、worker终止后不可再追加、用户/assistant消息数正确。所有DB为Windows TemporaryDirectory自动释放。
- C4：P50 288.53ms/P95 493.39ms/最大619.25ms/批量9158.66ms/13.10 runs/s
- C8：P50 534.21ms/P95 912.36ms/最大1624.67ms/批量8416.26ms/14.26 runs/s
- C16：P50 1099.59ms/P95 1938.04ms/最大2068.74ms/批量8923.80ms/13.45 runs/s
→ SQLite并发从8提高到16收益不增、长尾上升；应先管理worker上限与DB写入，而不是无界增加线程。指标只测本地资源。

### 2c. Owner独立新脚本（实际 FastAPI / Graph / SQLite / SSE 垂直链）
脚本`scripts/owner_p13_api_sse_graph_stress.py`，并发4，24条合成输入循环覆盖普通问候/GB/T风险标准检索/腐蚀工况。使用原FastAPI、真实R9 Graph和三个冻结工具、真实SQLite/SSE逻辑，RULE_DEMO，不发任何外网或模型请求，隔离临时DB；结果24/24成功，0错误，0事件缺序/终态重复/空回答，SSE after_sequence replay正确。
P50 1972.24ms、P95 2738.92ms、最大3172.89ms，完整批次11697.86ms。与2a/2b不同包含Graph和API堆栈；仍不能用作真实LLM响应延迟或公网压力结论。

本轮累积独立新增脚本（2b+2c）**384条**测试执行，此外复跑已有300条（及全量unit中重复加载）；避免重复计数为单一线上吞吐。

## 3. P13真实性/能力审核与新问题
- 业务代码已实现on/auto/off选择、SQLite snapshot、同会话多轮记忆、长文本4096/8192/报告3072、finish_reason/usage可记录、失败卡重放、含来源的E0候选/工程风险仍未知；真实浏览器Edge142截图来自Codex报告，Owner本轮未启动图形浏览器进行二次视觉验证。
- `backend/web_search.py`支持Search/Fetch adapter，但在`backend/api.py`只调用一次`DeepSeekWebSearch(...).search`，**没有任何`.fetch(...)`在会话业务流程中调用**；不能宣称网页全文抓取已经接线。
- **新发现P0：联网默认状态矛盾**。`backend/api.py::RunIn.web_mode`的默认是`auto`；`frontend/src/App.tsx`初始`useState<WebMode>("auto")`。P13提交说明有“联网默认关闭”；实际上新会话默认自动模式，公开时效问题可能自动触发联网（敏感工程自动有拦截）。如用户希望外发必须主动选择，这与预期不一致。应统一默认off并从会话存储恢复用户选择，额外确认启用auto/on的费用、隐私提示；在新Run中真实验证“不选联网=0请求”。
- Search Chat/Fetch **均只有模拟/接口级测试**，未有真实供应商账号连接、真实计费响应、实际搜索相关性或引用质量。真实外部网络错误只能在用户授权后小样本验证。
- 旧常驻8000从P13报告仍未重启，先前GET /api/model-profiles=404、磁盘新版路由存在。本轮GET /api/health=200；当前尝试profiles仍返回HTTP error（DevSpace仅输出异常片段，不能证明现时具体status）。**当前真实用户页面可能仍连接旧服务，需单独Owner明确授权的有界重启后验接口版本**。
- P13的压力记录未包括真正外部网络LLM运行或公网多用户压测；不存在已合格的生产吞吐SLA。

## 4. P14真实性与当前未完成的工作
- 独立扫描CSV：1385来源页且1385个唯一(source_pdf,pdf_page_index)；99条章节条目；20页pilot OCR诊断；568项机器候选（65 machine_located/503 unreviewed），人工visual_verified=0，human_verified=0。
- Pilot 30579样本OCR标题6/8，正文有错漏；未建立人工逐字gold，不能报正文precision，不能扩大自动录入。当前两份候选Excel只是原472+82，candidate JSONL与正式554零字段差异。
- 原工作树RBI485(原472+未签13)，正式RBI472；DM82仅30579，其他五个补充标准还未入正式资料。RBI表格转述高风险221条需真视觉核，另有材料/介质/温压/周期的合法空值与可能漏填需要按来源条件审查，**不要机械填满23/25列**。
- 老师标准准确率≥95%需要随机50条交叉人工核对(至少48/50通过)，真实LLM解析成功率≥95%需要100道真实模型输入，ModelScope公共部署及现场演示必须另验。这里没有任何人签E2/E3，无法宣布完成专业数据集。

## 5. 处理建议（按性价比）
**立即P0：**
1) 将聊天联网默认`off`统一到前端state、后端RunIn、会话恢复及测试；明确用户启用auto/on并有外发/费用提示；当前服务是否旧版先验证`/api/model-profiles`再仅重启这一个明确授权服务。
2) 真实Search/Chat按Owner批准的微量预算分别做5–10题，包括模型长输出、上下文和来源；明确硬失败/费用/TTFT，不能拿模拟数据替代。
3) 向Codex-P14安排20页各自独立真人手动核对，先形成真实OCR gold和表格/数值真值；未达门槛不扩批。优先221项表格转述+DM82八段适用条件，不重复刷条款数量。
**接下来P1：**继续外网Fetch加入用户显式流程（若有必要）；SQLite C8→C16长尾及较大JS包优化；严格证明老师100真实模型解析+50人审+ModelScope公开演示。

总体：P13工程本地可演示与离线回归**PASS**、真实模型/公网搜索/生产压力**BLOCKED_NOT_TESTED**、P14大规模数据原文真实性 **REVIEW_BLOCKED**。没有进行额外外部费用或上游数据写入。
