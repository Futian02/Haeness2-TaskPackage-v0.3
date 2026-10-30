# OWNER｜S2.5执行可靠性封口、真实模型首测与S3方案（2026-10-29）
**裁决：S2_5_ENGINEERING_RELIABILITY_CANDIDATE_PASS / V2_REAL_AGENT_RESEARCH_ONLY / V2_DEFAULT_NO_GO / S3_CANDIDATES_READY_TO_DELEGATE。**
Owner直接在本地自有源码实施、回归；不是Codex报告转述。未重启在线服务、未修改upstream任何教师正式源/合同/人审核签/生产SQLite，默认R9与`AETHER_V2_AGENTIC_ENABLED=0`不变。真实LLM调用仅发生在Owner显式运行的研究探针/注入式Graph，不在默认API/CI启动或后台任务中自动执行。

## 1. 本轮已修改自有文件
- `backend/execution_ledger.py`：Schema幂等迁移加`owner_pid,owner_claim`（动作）、`owner_pid`（子任务）。动作必须检查前所有者是否在运行；活进程不能被别的执行者误报UNCERTAIN/重试。每次领取有随机`owner_claim`和进程PID，结果提交/失败提交以`AND owner_pid=? AND owner_claim=?`围栏及`changes()==1`校验；死进程才按既有只读重试规则恢复。Windows使用OpenProcess(SYNCHRONIZE)/WaitForSingleObject，访问拒绝当“仍存活”（fail-closed），ERROR_INVALID_PARAMETER 87当死亡。Linux用os.kill(pid,0)。子任务RUNNING也不能从仍存活的进程抢占。
- `orchestration/isolated_teacher_tool.py`：新的独立Python子进程执行入口，只接受老师冻结三工具和受限JSON参数，无第四工具。注意老师源保持只读。
- `orchestration/agentic_v2.py`：默认原版三工具采用`subprocess.run(timeout=...)`的**可终止子进程**边界，替代仅退出等待而遗留线程的弱超时；对测试注入的function registry仍保留显式线程适配，不可称这些测试函数具有强杀保证。子进程只传环境白名单，不继承model key/token，入参最多16KB，stdout受限1MB。到达真实Provider请求/壁钟预算时产生有界finish状态，不重复继续规划；未改变原版teacher工具实现。
- `tests/test_v2_s25_lease_fencing.py`：真实独立进程“活所有者→不被抢占→单次结果重放”的动作/子任务2案例。
- `tests/test_v2_s25_sse_concurrency.py`：同Run双SSE连接只领取一次Worker、同/异CID并发3 Run消息隔离与回放2案例。
- `tests/test_v2_s25_tool_process.py`：原版教师工具隔离进程真实返回、极短超时杀子进程、未授权工具拒绝3案例。
- `scripts/owner_s25_live_model_probe.py`：显式研究入口，真实API但最多4请求、响应限450 tokens、全部合成无私人数据，stdout仅安全元数据。
- `backend/real_agentic_provider.py`：真实DeepSeek结构化Plan/Reflect受限Provider研究适配，默认不接入API，单实例最多4-6请求，输出预算、URL超时、Pydantic解析、不发送原PDF或密钥到日志。**不能声称已达老师“100次原生解析”门槛**。

## 2. 本轮本地真实复验
### Python回归
按原S2.4同一unittest发现范围的三个**互不重叠**组执行，加入本轮3个新测试模块：
- 组1：77项 OK（包含原本地Mock负载）。
- 组2：99项 OK（报告P16人签仍为0/50，机器没补签）。
- 组3：146项 OK（3 optional skips；即143 PASS）。
总计**322 tests =319 PASS +3 SKIP，0 FAIL/ERROR**。这不等于单一`scripts/test_s2.py`全量启动命令已跑成功，报告清楚分组口径。
专项：本轮核心R9+V2+S2.4+S2.5子集96/96 PASS；隔离进程与门禁7新增案例全部PASS；实际官方工具子进程`standard_clause_search`一次success、1个source；5ms以下极短超时真实返回deadline exceeded。
P16-A pytest **5/5 PASS**；前端Vitest **118/118 PASS**，TypeScript检查PASS（本轮未重新跑Vite build，S2.4历史已通过）。
老师程序：`validate.py --final`**554/554条款+200/200轨迹PASS**，`_selftest_tools.py`**17/17 PASS**。全部只读。
### Mock压力测试
`tests.test_p13_local_load`单次负载对照并发1/4/8，分别100 Run，0 errors：
- c1 p95 **165.665ms**；c4 p95 **396.58ms**；c8 p95 **1050.819ms**（一组同时运行S2其他测试，因环境压力有波动；不是线上容量指标）；
- 单独TestClient里还测了429会显式返回且Run保留queued，而不是无丢包的无限队列；
- 未执行真实供应商付费的100/100并发压力；不将Mock吞吐外推成真实模型p95/限额表现。

## 3. 真实API及专业AgentGraph研究（真正付费/非Mock；全为合成案例）
本机配置`deepseek-flash`、HTTPS`api.deepseek.com`已就绪（密钥未输出）。
- 不带JSON模式的第一条模型路由请求返回非合规JSON，原生解析FAIL。
- JSON模式、200-token限额：普通与标准解析成功，但复杂工程问题finish_reason=length，空输出、解析失败。
- JSON模式、450-token限额，**4条路由全部JSON可解析，但3/4符合预期**。错例：无材料/介质的设备裂纹分析被分为MIXED而非ENGINEERING，模型未违规建议调用需材料的DM工具。延迟约1.7–2.5秒，非正式盲标/准确率。
- 真实Planner→真实`standard_clause_search`实验：首次策略门禁拒绝query/keyword不一致，确认确定性门禁生效；提示词明确一致性之后，实际4次模型Plan/Reflect、2次标准检索、5个来源引用、风险等级null、5个工况unknown。原先达到真实模型4次请求预算时误报planner_error，代码已修成明确的budget-exhausted有界finish。
- 完整条件例：真实模型生成的计划被policy gate拒绝，0工具执行、0引用、风险等级null；仍有prompt/schema/工具规划质量问题。
- 上述真实Model测试**不是**正式LLM原生解析100组≥95%、原生工具调用5步、设备专业准确率、真实API负载或真实multi-agent结论。原始问题均为公开合成场景，原标准PDF没有上传。
- 当前V2正式API仍默认使用`ScriptedFakePlanner`且V2关闭；实验Adapter没有自动替换现有后端配置。

## 4. 残余安全与发布Gate
1. PID存活检查与claim CAS避免本轮复现的抢占，但PID复用、异常权限状态均采用fail-closed，部分遗留STARTED如无owner_pid需人工/显式恢复流程；尚未做长期随机故障、Windows进程树/Job Object资源清理证明。独立子进程超时只保证直接子进程被终止；若工具主动派生孙进程，需Job Object额外处理（原冻结工具不应启动子进程）。
2. S2.5双SSE与三个Run隔离、跨进程抢占均已专项通过；还缺上百个真实交错事务随机故障、真实模型429/重试/超时长期压测及跨进程API多实例负载。**当前工程可靠性阶段比S2.4更成熟，但未达生产全链路GO。**
3. 真实DeepSeek Planner仍会给policy拒绝方案，不能因某些调用JSON解析成功就默认开启。先扩充独立路由盲标与受控真实Planner评测，测语义准确率、工具允许率、错误断言、tokens/latency/成本。
4. 源数据人审50/50尚未完成：现冻结样本真人签署0/50，更改42条真人0/42；专业Recall/Precision/False Exclusion没有可信领域holdout。
5. Edge桌面/移动本轮未真实浏览器复验，现网后端是否与磁盘新代码同步仍待单独验收。未经Owner明确授权不重启任何在线服务或改业务SQLite。

## 5. S3方向已由Owner冻结，Codex承担批量实现
- `docs/S3_DM82_APPLICABILITY_RESEARCH_AND_ENGINEERING_SPEC_20261029.md`：只读原库82扫描、三值条件/角色/对象本体、危险召回/错误排除、PDF定位SHA、先15再82、专家holdout、shadow-only放行门禁。
- `docs/CODEX_S3_A_DM82_SOURCE_CANDIDATES_20261029.md`：Codex A只读82条、10–15机制溯源/候选谓词/负例，拥有candidate文件。
- `docs/CODEX_S3_B_TRISTATE_ENGINE_20261029.md`：Codex B Pydantic Schema+Kleene三值条件引擎+≥35负例单测，独占自己的源码文件；可与A并行。
- `docs/CODEX_S3_C_EVAL_AND_FULL82_GATE_20261029.md`：A/B结果验收后执行成对旧新对照、独立盲标模板与82覆盖门槛；不先直接全量写回老师数据。
本机Codex按用户约定**直接使用本机文件与终端**，无需任何本地远程桥接插件；若本机执行环境没有D盘访问应明确报告权限/环境不符。
