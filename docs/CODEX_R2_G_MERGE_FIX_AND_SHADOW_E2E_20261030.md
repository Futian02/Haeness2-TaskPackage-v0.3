# Codex G｜R2六路交付后的唯一集成与真实网页门禁（2026-10-30）
本机工作根：`D:\作业\竞赛\计算机设计智能体\机械智能体`。本机Codex用原生文件/PowerShell，**不要使用DevSpace或远程连接器**。主G负责实施，允许子Agent做**只读检验/新增独立eval**；源码写入仅由单一G来做以避免指纹漂移。不要重启8000/8001、改正式SQLite、修改upstream PDF/Excel/JSONL或人工签核，不启用未经批准的真实收费模型。
**请直接实施，禁止停在写计划**。

依序完整阅读：
1. `AGENTS.md`、`docs/PROJECT_STATUS_CURRENT.md`、
2. `docs/R2_FULLSTACK_PARALLEL_CLOSEOUT_MASTER_20261029.md`、
3. `docs/audits/R2_OWNER_ABCDEF_MERGE_PRECHECK_20261030.md`、
4. `docs/CODEX_R2_G_FINAL_INTEGRATION_OWNER_GATE_20261029.md`，
5. A1/A2: `docs/data_quality/R2_A1_SOURCE_AUDIT_20261029.md`、`docs/data_quality/R2_A2_RETRIEVAL_20261029.md`，
6. B1/B2/C/D/E/F/QA: `docs/audits/R2_B_CLAIMGATE_REPORT_20261029.md`、`docs/audits/R2_B_MODEL_GENERATION_20261029.md`、`docs/audits/R2_C_GRAPH_RETRIEVAL_20261029.md`、`docs/audits/R2_D_CONTEXT_MEMORY_20261029.md`、`docs/audits/R2_E_API_RUNTIME_20261029.md`、`docs/audits/R2_F_FRONTEND_E2E_20261029.md`、`docs/audits/R2_QA_BROWSER_E2E_20261029.md`。

**立即停止“缺A报告”的假阻塞**：A1/A2位于`docs/data_quality`而非`docs/audits`；它们已交付，不可因glob命名不匹配重做。B、C报告也真实存在，各文件在Owner独立复验中SHA与交付报告一致。首先记录git状态和当前所有关键SHA；从此由唯一G管理源码写入，QA待源码稳定时再起浏览器。

**独立复现发现的集成断言失败，先别改测试期待凑绿**：
Owner真实复跑B/C/D定向36 PASS、E/QA/P4A 25 PASS；旧P0+R9+P12 48项→**4 FAIL、2 ERROR**。
1. `P0-N-01`是“什么是应力腐蚀开裂？”，产品允许概念F1不调用teacher工具，但旧案例把`tool_policy`标为必须调用；应按产品语义审查并更新该案例及真正的概念知识断言，不得强迫无意义工具调用。
2. `P0-X-04`“压力是10MPa所以H2S分压也按10MPa”，旧期望要求preserve medium，但未提供medium，D只抽总压力，不等于H2S分压，属正确保守处理。先fix错误fixtures，同时增加“不误传分压、无介质不伪造”的红队断言。
3. `seen_hashes`实际50不是数据真的只剩50：有两道子case失败导致set漏添加；先跑完全部64项再核对原52个去重SHA，不可改期望为50。
4. R2 health将`flags.expert_guidance_candidate`与`capabilities.professional_guidance`分离；旧测试依赖`capabilities.expert_guidance_candidate`需按真实协议修合约断言，不为绿测添加误导业务能力。
5. 两个临时SQLite/API/SSE子进程E2E写死旧合同`aetheris-2026-10-29-p0.1`，当前合法R2为`aetheris-r2.0.0`。先修版本判定，再**真正执行后续所有断言**并修出现的真实问题，特别是工具次数、同CID上下文、实际主回答和终态。
6. D已报告`new_object_scope`在E的API持久化scope没有闭合。同CID“另一台未命名设备”不得继承上一设备事实；补API绑定并新建临时SQLite完整回归。

**知识闭环**：A2 554候选指针和专业alias/UNKNOWN、Hard-negative离线有效，但64个合成query Top5非空只从2到8（不是Precision）。C尚未集成A2索引；G可先在shadow只读插件接口接线，必须保留3老师工具、source身份、E0不等于适用和未知不硬排除。若剩余准确性不足，应明确不具备合格专业召回，不能刷绿统计。尤其B壳体磕碰假召回“辐照脆化”，HCl非烟气侧错误烟气露点，5.23的局部49–66℃不能硬排除80℃整个机理。

**模型安全**：B1的Owner六条无来源设备安全许可本轮独立执行全部被ValueError拒绝；请自拟新≥50句/多字段/来源错配攻击，再验证风险null、处置UNKNOWN，普通SCC概念正常答。模型Planner并未在真实API连通与专业正确性上获得许可，不要让Fake测试冒充真实能力。

**G隔离端到端**：只用新独立端口、临时SQLite、模型密钥清零的E shadow runner；启动前/期间/结束 health.build_fingerprint 与磁盘源hash完全一致，F Vite代理指向该shadow，不打8000/8001。Edge桌面1440x900、移动390x844真实输入、发送、A/B/SCC、同CID更正、不同CID隔离、来源详情、断线与SSE回放、模型Mock失败回退、429与queued后续恢复；附截图、RunID、HTTP/事件序号、唯一assistant消息证据。真实浏览器没跑不可报PASS。

**全量**：完整unittest（注明fitz venv环境差异）、前端128基线+TS/Vite、老师554/200+17、S2恢复并发。所有自动指标与领域专家审定分离：PDF页审0/554、verified_by全部空，S3机理审核0 approved、独立专家Gold0，因此最多`GO_ISOLATED_OWNER_UI_TEST`，不能正式设备处置/生产发布。

产出`docs/audits/R2_G_FINAL_FULLSTACK_RELEASE_GATE_20261030.md`，内含实际运行命令/原日志路径/输入与主答/证据/源码hash/失败及回滚，更新`docs/PROJECT_STATUS_CURRENT.md`为最新版。若任一实质Gate不通过，返回`STOP_FIX_REQUIRED`并只分配精准剩余缺陷；若全部隔离门通过返回`GO_ISOLATED_OWNER_UI_TEST / NO_GO_PRODUCTION`。不得未经Owner批准更换正式在线服务或使用真实业务库。
