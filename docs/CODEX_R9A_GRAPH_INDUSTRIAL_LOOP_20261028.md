# Codex新窗口A｜R9A 工业设备智能体简化Graph（只读开源取经、隔离候选）
你是Codex执行者。本任务不是UI，也不是RBI Excel。项目`D:\作业\竞赛\计算机设计智能体\机械智能体`。读`AGENTS.md`、`docs/R9_GRAPH_INDUSTRIAL_REUSE_DESIGN_20261028.md`、`docs/OWNER_R9_INDUSTRIAL_AGENT_TRACE_OSS_RESEARCH_20261028.md`、`orchestration/graph.py`、`orchestration/p6_parallel_audit.py`、`tests/test_p7a_merge_consistency.py`。
**工作范围只能**新建`orchestration/r9_industrial_candidate.py`及必要的`orchestration/r9_*`辅助模块、`tests/test_r9a_*.py`、`evals/r9a_*.py|jsonl`、`docs/audits/R9A_*`。**绝不写**`backend/`、`frontend/`、`upstream/`、`orchestration/graph.py`旧正式执行入口、原RBI表/JSONL或共同状态文件。R8A/R8B的Codex仍可能在跑，不允许碰他们的文件、不执行git clean/reset。

先到`https://github.com/wyjhfl/project-a-rag-platform`、`https://github.com/intel/predictive-maintenance-pipeline`、`https://github.com/ten10do/industrial-maintenance-copilot`、`https://github.com/Ameer-pasha/agentic-rag-predictive-maintenance`实际读**Graph实现文件/测试**、source tree、许可文件，记录owner/ref/commit和可复制部分。Project A GitHub页面未见明确License，**只借业务模式，未获许可勿复制实现代码**；Intel Apache-2.0/ten10do MIT可复用但保留NOTICE，不复制重型OpenVINO/OPC UA模拟项目。

目标造一个**短主图、可循环的独立StateGraph**：Route(无材质标准查询仍可正常检索)→Investigator(内部工具ReAct/策略循环, 仅官方恰好3个工具)→EvidenceGate→ReviewDispatch(仅必要时 Auditor ∥ Skeptic)→Merge→Report；Gate表示纯决策逻辑，不包装成LLM Agent。缺壁厚等待人或unresolved；低召回查询新变体，有新证据才循环；无信息增益不空转。上限调查3轮/审核修正2次/8个工具调用+budget耗尽安全结束。现`RULE_DEMO`是默认，不能说已接真正LLM；提供可注入未来provider接口，但别向系统申请真实API或伪造日志。

严格复用P7A保守冲突Merge，双支路分别从真实观测/官方source产生独立评价，不复制Investigator文字；E0/E1最高，未真人签核不能自动升E2/E3或输出设备风险L级。内部EventSink格式与现有SSE一致，只提案/在隔离执行记录`phase,iteration,step_id,parent_step_id,public_rationale,retry_reason,source_ids,duration_ms`，不修改backend或对外接口。
至少12负向/正向case验证：纯条款查询、输入不足、可重试检索、零增益、假页、条件冲突、同ID不同grade、并行2Review、无意义多Agent成本、LLM幻觉E3/风险L、工具异常、预算耗尽、重复run/worker lease不退化；测试实际证明至少一种循环和至少一种并行fan-in成功，顺序/候选图共用冻结tool snapshot与质量/延迟对照（实验样本非Gold）。正式生产图完全不切换；原全量测试有一个旧P6A first-wins断言需Owner独立收口，不得改旧测试以骗全绿。
交付`docs/audits/R9A_GRAPH_CANDIDATE_ACCEPTANCE.md`：真实运行日志/State转移、源码引用精确目录、许可证、功能点和延迟对照、阻塞项、回滚方案。状态`READY_FOR_OWNER_REVIEW`，不提交、不部署、不声称生产已上线。
