# Codex S2.6｜真实LLM Agent、真实工具调用与专业/压力评估
本机项目`D:\作业\竞赛\计算机设计智能体\机械智能体`，直接用本机文件和终端；不能原生访问D盘则停止并报告LOCAL_EXECUTION_ENV_MISMATCH。**真实API测试只执行此任务明确的有界合成负载，默认服务不切V2**。
先读`AGENTS.md`、`docs/PROJECT_STATUS_CURRENT.md`、`docs/audits/OWNER_S25_RELIABILITY_LIVE_LLM_20261029.md`、`docs/AETHER_V2_MODEL_POLICY_GUARDRAILS_20261029.md`、`docs/TEACHER_QA_CONSTRAINTS.md`、`backend/real_agentic_provider.py`、`scripts/owner_s25_live_model_probe.py`、`orchestration/agentic_v2.py`、`tests/test_v2_s25_*.py`。
Owner已真实调DeepSeek：450-token JSON模式4条均成功解析、路由3/4一致；真实Plan/Reflect检索2次取5个source；另有policy拒绝和budget不足案例。**不能把Mock或规则fallback算真人原生成功，也不能自称真实专业正确率**。

## 范围及所有权
新增`evals/s26/**`、`scripts/s26_*.py`、`docs/audits/S26_*.md`；如确需修改Provider仅允许独立新研究适配器，不能直接编辑Owner正在修的`backend/execution_ledger.py`、`orchestration/agentic_v2.py`、`backend/api.py`和教师`upstream/**`。先检查是否有其他窗口持续写共享文件，默认只读。**不得启动/重启/部署在线服务、读/打印API密钥、使用正式用户会话、向供应商发送标准全文或企业资料**。

## Gate 0（先做，真实API小规模）
冻结公开合成问题集≥100，逐题gold以开发者手工审阅标记（后续独立盲标才成为质量gold）。建立`run_id,case_id,requested_route,model,provider,finish_reason,usage,prompt_hash,response_hash,parsed_native,fail_reason,model_tool,policy_accept,source_ids`字段，不保存隐藏CoT、私有凭据及原标准全文。先10例真实测试（原始供应商请求≤30），确认API余额、超时、返回JSON支持、Token耗量/价格级别和降级策略；所有真实请求有硬上限：单次max_output_tokens≤900、timeout≤30s、总tokens设预算、每秒请求率和总费用估计日志，触发上限即STOP。不对真实API直接进行100×c8并发压力。

## Gate 1 原生解析100组
在Gate0低成本且合规后运行100个**原生LLM工具选择**结构化响应（需有明示已知与未知工况、老师工具合法枚举、规则冲突、提示注入、混合任务、语言转述、长上下文、错误来源）。逐条统计模型原生Pydantic parse success（老师门槛≥95/100）、原生工具名/参数合法率、策略允许率、Fake/规则回退率(单列)、语义路线正确率(独立评分)、拒绝的错误类型。若用户没有认可预算上限/真实100调用风险，则默认可Mock复现并报告REAL_100_BLOCKED，不能擅自无限请求。

## Gate 2 真实Plan→Tool→Review 连续链
在真实`AgenticV2Candidate`只读工具与本地审计账本上测试：合法标准查询、无材质探索、完整材料/介质（碳钢+湿硫化氢等合成工况）、风险等级缺PoF/CoF归null、模型不允许第四工具等。证明至少一次连续5个**真实模型工具决策**，每次tool_call必须来自native模型输出并通过Pydantic/policy gate，不能由Fake/规则补齐。允许多个run累计？**必须遵从教师原版“连续调用”的精确含义**，在报告标明是否同一run并给出源轨迹，避免混淆。所有实际调用三个冻结只读工具，不生成实际风险等级或现场确诊；unsafe模型计划被拒应视为安全成功而非工具成功。

## Gate 3 压力、并发与专业门禁
- 真实供应商压力只做有界c1/c2/c4、小样本5–15次/组且有rate-limit退避/Retry-After、429/5xx/timeout/failure归因；不得将Mock c1/4/8×100的p95外推真实LLM。所有计费、latency p50/p95、tokens、供应商错误、服务端queued/SSE稳定性分别计。
- 本地Mock可继续100×c1/c4/c8并发，须冻结相同输入集，测429、queued无丢失、重试最终单assistant和序列连续性。
- 专业质量按source E0/E1/E2/E3及三值适用性单独报证据等级，不能拿模型语义自评分当专家金标。错误“烟气露点在无烟气HCl管道成立”“H2S分压混总压”“防护材料写成易感”“无PoF/CoF给L1–L4”均为P0。
- 一切费用/授权/网络/页面不可达均如实报告，不得通过手工改结果达到95%。

## 交付
`docs/audits/S26_REAL_LLM_AGENT_AND_STRESS_EVIDENCE_20261029.md`、机器可复现JSONL与脚本、现场实际计数和费用、失败错例、是否允许切开一个**临时隔离V2模型开关**的Owner决定。没有老师真人50签名、82适用性独立gold和正式鉴权时，仍不得对外发正式工程结论/发布。Codex本机执行不依赖任何额外远程连接器。
