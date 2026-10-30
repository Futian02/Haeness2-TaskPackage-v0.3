# Codex R2-E｜FastAPI协议版本、SSE/并发、受控隔离服务与后端全链路
【统一约束】在本机Codex工作目录 D:\作业\竞赛\计算机设计智能体\机械智能体 直接使用本机终端和文件系统。勿使用DevSpace/远程连接器。先读 AGENTS.md、docs/PROJECT_STATUS_CURRENT.md、docs/R2_FULLSTACK_PARALLEL_CLOSEOUT_MASTER_20261029.md 和当前本Lane文件。此项目是父级大型Git工作树内的未跟踪项目，禁止git clean/reset、自动提交、清理upstream中的既有脏文件。不要修改教师upstream/PDF/Excel/JSONL、人工审批、真实SQLite、生产模型密钥。不要重启8000/8001在线服务。每个测试使用隔离临时DB，不能用真实付费LLM做无上限负载。严格遵守MASTER独占路径；发现别人同时修改同文件，停止写该文件，记录冲突，使用接口报告对接；不能为绿测删除/放宽旧测试。交付真实命令、PASS/FAIL、输入-输出对照、Git/源码hash和未完成风险。

**独占可写**：backend/api.py、scripts/r2_service_*.py、tests/test_r2_api_*.py、docs/audits/R2_E_*.md。不得改B/D的backend源或C的Graph；需与它们的schema协同时写adapter在自己的文件内，不能赌共享文件同时完成。

任务：
1. 当前实际8000/8001是旧服务：8000 /api/health缺contract_version、/api/model-profiles 404；8001 /api/health同样缺contract_version。以只读方式定位PID、工作目录、启动命令、DB路径（仅打印位置/指纹，禁止输出密钥）、静态前端asset hash、API OpenAPI schema差异。**不得重启/杀进程，不修改正式SQLite**。
2. 统一RunIn与frontend/src/api.ts可接受字段（web_mode,web_search_enabled,allow_sensitive_web_search,model_profile_id,mode,问题、设备等）。后端健康接口报告`contract_version`、`capabilities`、`build/source fingerprint`、active flags，使F/UI在不兼容时说明“版本不匹配”不是“断网”；不允许静默外发敏感设备资料。
3. 保证用户任何专业Run走`context_slots.extract_explicit_context`和D确认的事实记录，再由C合法Graph检索，再由B专业主答安全渲染；source E0/UNKNOWN/风险null等从E/SSE→SQLite→前端一致。默认隔离flag关闭与on切换必须有真实回归。
4. 429/5xx/模型超时和真实SSE断线：一次Run只Claim一次、重复订阅/重放不执行重复工具，Queued保留、幂等POST、出错无“成功”助手空消息；S2.5已有owner_pid/claim兼容；需要真正运行同CID双SSE、跨CID并发、失败注入。
5. 安全策略与功能边界：敏感web_search必须二次同意，普通时效问题只有正确条件才联网；专业候选/报告默认安全控制；不变更老师三工具，不对V2假plan绕过回退；模型计费/日志脱敏。
6. 提供`scripts/r2_service_shadow_run.py`或类似方式在**独立端口、独立临时SQLite、独立临时模型Profile目录**启动新候选进行本地E2E，且有健康握手、停机清理、无需生产进程重启。必须提供不含秘密的手工切换计划：备份/验证当前DB副本→运行新版本隔离端口→F Edge发送/刷新→Owner批准后再可能进行蓝绿切换；当前任务**不能执行生产切换**。
7. 完整相关旧测试：P4A/P5A/P13/R10/R9/V2/S2，API spec contract tests + 独立跨进程崩溃恢复；真实端口只GET检查，不对正式库POST。新增低负载100次mock隔离压力或可靠性验证，且说清每种接口执行真实LLM还是Mock。
验收：隔离端口与最新磁盘fingerprint一致、真正发A/B专业问题到隔离SQLite后assistant主答与事件一致、SSE合法重放，无数据串线；线上仍保留旧配置直到Owner批准。