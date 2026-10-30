# Codex R2-D｜会话工况提取、记忆/摘要/修正及SQLite隔离封口
【统一约束】在本机Codex工作目录 D:\作业\竞赛\计算机设计智能体\机械智能体 直接使用本机终端和文件系统。勿使用DevSpace/远程连接器。先读 AGENTS.md、docs/PROJECT_STATUS_CURRENT.md、docs/R2_FULLSTACK_PARALLEL_CLOSEOUT_MASTER_20261029.md 和当前本Lane文件。此项目是父级大型Git工作树内的未跟踪项目，禁止git clean/reset、自动提交、清理upstream中的既有脏文件。不要修改教师upstream/PDF/Excel/JSONL、人工审批、真实SQLite、生产模型密钥。不要重启8000/8001在线服务。每个测试使用隔离临时DB，不能用真实付费LLM做无上限负载。严格遵守MASTER独占路径；发现别人同时修改同文件，停止写该文件，记录冲突，使用接口报告对接；不能为绿测删除/放宽旧测试。交付真实命令、PASS/FAIL、输入-输出对照、Git/源码hash和未完成风险。

**独占可写**：backend/context_slots.py、backend/conversation_memory.py（存在时）、backend/store.py（必要时）、tests/test_r2_context_*.py、docs/audits/R2_D_*.md。不得编辑backend/api.py、backend/deepseek.py、Graph/frontend/upstream。任何迁移在隔离数据库和自有candidate脚本验证，不能操作现有生产SQLite。
任务：
1. 识别用户自然语言已显式给定设备/部位/材质/介质/温压/流量/壁温/测厚/损伤形貌；保留original raw span、规范值、来源、用户陈述vs独立实测状态、unit、object、scope。不同压力H2S partial与total、工况温度与wall temp要分开，不得混为单个float；不知道保持UNKNOWN，不强造0。
2. 同一对话事实继承及更正：更正先前介质/材料覆盖同CID旧值，保留审计历史；“另外一台设备”应新设备scope，不污染当前事实；跨会话隔离绝对严格；不把AI猜想或条文候选当User确认。普通聊天/天气不得附带历史设备数据到外网或prompt。
3. 按阈值保留有界最近消息+摘要：若模型总结失败/输出无效则原始事实安全回退；摘要具哈希/版本/出处/冲突记录，不得悄悄丢事实；会话删除与审计保留需有单独授权和数据保留语义。
4. 用真实回归问题A+B、中文括号、JSON方括号、未枚举medium、多个设备、否定/不确定词、并列多温度单位、用户改口、数值冲突、Prompt injection合成≥60个案例；每个都跑真正解析，不仅验证模板里有“已知工况”。
5. 提供E/API回填接口兼容`extract_explicit_context(...)->values/sources/raw_values/unknown_enum_values`，新字段可新增，但不破坏旧调用方。检查S3条件对象schema有无可以对接的已审核字段，仅加shadow metadata。
6. 独立SQLite原子事务、重开回放、并发隔离、摘要错误回退、对话删除权限边界等真实测试。新增/升级Schema须有幂等迁移与拒绝数据损坏；不得自作主张移动DB。
验收：用户已写的300系列不锈钢/碱式酸性水/60℃、后续修正均保留且提示准确；不同CID无历史泄漏；不存在未确认事实被提升为已测。报告跨模块对接说明/旧调用兼容测试。