# Codex R2-C｜LangGraph路由/多目标专业调查/工具准确性与可靠执行
【统一约束】在本机Codex工作目录 D:\作业\竞赛\计算机设计智能体\机械智能体 直接使用本机终端和文件系统。勿使用DevSpace/远程连接器。先读 AGENTS.md、docs/PROJECT_STATUS_CURRENT.md、docs/R2_FULLSTACK_PARALLEL_CLOSEOUT_MASTER_20261029.md 和当前本Lane文件。此项目是父级大型Git工作树内的未跟踪项目，禁止git clean/reset、自动提交、清理upstream中的既有脏文件。不要修改教师upstream/PDF/Excel/JSONL、人工审批、真实SQLite、生产模型密钥。不要重启8000/8001在线服务。每个测试使用隔离临时DB，不能用真实付费LLM做无上限负载。严格遵守MASTER独占路径；发现别人同时修改同文件，停止写该文件，记录冲突，使用接口报告对接；不能为绿测删除/放宽旧测试。交付真实命令、PASS/FAIL、输入-输出对照、Git/源码hash和未完成风险。

**独占可写**：orchestration/r9_industrial_candidate.py、orchestration/agentic_v2.py、tests/test_r2_graph_*.py、docs/audits/R2_C_*.md。不得改backend/**、frontend/**、知识源；先读R2-A接口报告，若A未完成用read-only可注入接口模拟，保证以后可对接。

任务：
1. 精细意图图（GENERAL/CONCEPT/STANDARD/MULTI_STEP_DEVICE_INVESTIGATION/MAINTENANCE_SAFETY/RBI/MIXED）。识别多意图DAG及安全优先输出；“早上好，设备渗漏”不能因问候进入general；“什么是SCC”无需材质也能先解释。
2. Context输入仍从现有`extract_explicit_context` JSON读，不得二次抹掉原始介质/材料；未知字段不假造canonical；同个prompt已给事实不得仍ask material/medium。新版Graph API必须保留老`graph.run(question, context, *, run_id, on_event, ...)`参数兼容及返回老格式。
3. 原教师3只读工具策略：自动词汇规划/有界同义扩展、semantic rerank（不能仅新增“辐照脆化”特例）；从原问题B“磕碰损伤需要停机与验收?”得到机械损伤、表面NDT、综合评定，但必须把“条款关于裂纹”只作为条件性来源而非当前设备规则。困难负例：HCl普通管道误召烟气露点；湿H2S误召燃灰/硫酸/微生物；这些已知错例要可追溯地判source relation但不得凭未审核条件硬删除高危候选。
4. V2独立Planner有真实模型Provider可注入但默认关闭。计划JSON必须过Pydantic、query/keyword一致、三个老师工具白名单、子任务范围/参数门禁、每一步重试/Token/墙钟上限；生成失败→确定性专业调查回退，但不能把失败归为真实模型原生成功。
5. 混合DAG最多4子任务，有依赖、一致性来源和摘要，对错误子任务作阻断；保持已有持久执行账本owner_claim、只读子进程timeout和run lease的幂等性，不引入双SSE执行重复或崩溃接管。
6. Frozen系列真实老师工具隔离回归A/B/SCC/80℃/未枚举medium/B假来源、突发超时、并发双Run/重连；至少50个含专业语义错误的开发题。真正`zero_source`还要产生专业待核建议，不能输出伪标准。
7. 交付给E的返回字段`output.status/conclusion/citations/hypotheses/unknowns/tool_calls`、structured reasons、每步证据与sourceID必须保留向后兼容。勿直接调用付费模型压测；若模型上线需要预算批准，标BLOCKED。
验收：同一词语不同语境不同检索；不漏关键危险、无条件不强行排除；R9+V2+S2并发回归PASS，记录p50/p95工具延迟和上下文成本，保留原R9回退flag。