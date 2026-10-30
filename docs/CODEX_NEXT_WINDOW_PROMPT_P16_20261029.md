这是机械智能体/澄衡 Aetheris 项目的连续Owner严格审查窗口，请直接使用已连接的DevSpace。
项目根目录：D:\作业\竞赛\计算机设计智能体\机械智能体

**必须先完整读取本地同步文件**：
1. AGENTS.md
2. docs/data_quality/NEXT_WINDOW_HANDOFF_P16_20261029.md
3. docs/data_quality/P16_OWNER_INDEPENDENT_AUDIT_20261029.md
4. docs/data_quality/P16_A_CHANGED_RECORDS_REVIEW.md
5. docs/data_quality/P16_B_SOURCE_FIDELITY_AND_RETRIEVAL.md
6. docs/data_quality/P16_C_FINAL_RELEASE_GATE.md
7. docs/PROJECT_STATUS_CURRENT.md、老师的资料填写指南和技术指标验证方法。

这份交接文档保留了截至2026-10-29 13:14（北京时间）的P3–P16工程状态、具体文件路径、哈希、实测数字、未决问题、教师验收门槛、测试命令及全部数据红线。若记忆和磁盘冲突，优先当前磁盘与实测；不要重新问我项目路径或重复启动已经完成的阶段。

**最新已实测**：P16 A42证据卡（28 MATCH/13 AMBIGUOUS/1 CONTRADICTS）；B211个RBI表格待核、DM1312项字段待审、56补充标准章节、11条隔离修正/检索建议；C 50固定随机+42已修改（重合2）=90个待真人签署项目。P16预览554条、与正式库相比42条修改/0增删，所有P16-B新建议尚未正式合入。原/候选teacher validate554/200、工具17/17通过；统一venv完整230项测试有1个fitz导入ERROR、3项SKIP，A用系统Python单独pytest5通过，B/C10通过。正式发布BLOCKED_PENDING_HUMAN_REVIEW，0条真人签名。代码测试PASS≠标准原文真值PASS。

**开始后直接执行**：
A. 严格审查TSG21 §8.3.12物理页索引78→83矛盾，以及GB/T30579 §5.6的3Cr/5Cr、轻相/烃相、注氨/注氢、设备漏项、F/H来源拆分；§5.23材料耐蚀/易感、§6.7 H₂S分压/浓度及子型温区。以标准PDF原页和每个字段证据为准，不把OCR/模型推测当人工核实。
B. 独立复查A/B/C的11条提案是否真实解决内容错误，检查C的42变更审核是否遗漏；先制作可验证差异/补证/修正建议，再组织两个实际审核人处理50随机+42定向的真实核查，不能擅自签名。
C. 修正测试环境的PyMuPDF依赖问题并完整复跑（尽量最小、隔离，不能删除测试掩盖失败）；官方convert/validate、17工具和检索反例继续作为硬门禁。
D. 如果内容可核，先在独立staging生成可审新候选和日志；没有真实人审/Owner授权，严禁覆盖上游PDF/Excel、正式clauses.jsonl、产品数据库或部署。给我具体的下一步执行结果、剩余阻塞、是否能够发布；避免无界开P17/P18。

我希望你是工程审计负责人，而不是单纯总结Codex报告。能直接做的只读核查/隔离测试现在执行；大规模任务可以设计明确提示词给Codex。禁止真实收费外部模型测试、删除文件、Git清理、重启服务，除非我另行授权。