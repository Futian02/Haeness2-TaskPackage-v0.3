# Owner文档总览、一致性检查及整改台账｜2026-10-29

**审计范围：** 真实 DevSpace 工程；`docs/`与`upstream/`关键 Markdown（排除第三方reference_code、二进制和缓存），脚本 `scripts/owner_docs_consistency_readonly.py` 只读扫描并补充Owner逐份阅读核心合同/运行文档；没有伪造签名、改动老师合同或将既有历史记录改成失败。

## 扫描快照
- 首轮扫描 Markdown **174** 份；新增本轮三份纠偏报告后复扫 **177** 份，Markdown显式本地链接仍**0断链**。首轮涉及100%/50/50表达的文档 **35** 份（复扫40份，含新增审计与引用说明）；这只是**含有这些词的数量，不表示35份有错误**（官方格式、护栏拦截率可合法为100%）。
- 发现含旧“当前稀疏未检出”“唯一当前状态”或`CONTRACT_LOCK`路径等信号的文档 **5** 份；归类为当前索引、历史执行计划和旧候选审计。
- 发现发布/审阅状态措辞的文档87份；包含用户展示/SSE/执行过程相关文字32份；这些是用途分类而非需要全量覆盖的清单。
- Markdown显式相对链接的当前扫描未找到断链（**不包括`code`中的纯路径、动态生成链接、Word/PDF内部链接**）；`docs/CONTRACT_LOCK.md`是一个真实**未创建**的纯路径引用，需要修正当前入口与AGENTS，历史任务文件记录不删除。
- 根部`README.md`、`docs/ARCHITECTURE.md`、`docs/DOCS_INDEX.md`、`docs/DATA_LINEAGE.md`、`docs/PROJECT_STATUS_CURRENT.md`已经检查。P15/P16报告、教师`README`/接口规范/技术指标验证、Q&A docx和历史抽样报告也逐项阅读，其他历史计划仅作关键字范围巡检，**不能宣称174份均完成逐句事实复核**。

## 纠偏发现及处置
| ID | 问题 | 正式处理 | 当前状态 |
|---|---|---|---|
| DOC-01 | upstream历史抽样写2026-10-27更正后50/50，缺当前可核实名字/交叉人签链，与P16新50条0签表面矛盾 | [教师50条口径对照](../data_quality/TEACHER_SAMPLE50_EVIDENCE_STATUS_20261029.md)说明两次样本种子/日期/分母不同，旧材料保留不改；当前准确率未知而不是0% | 已纠偏说明，**人审仍BLOCKED** |
| DOC-02 | 旧索引称标准PDF、XLSX还没检出 | 更新`DOCS_INDEX`、`DATA_LINEAGE`并标记2026-10-27历史段落 | **已改当前入口** |
| DOC-03 | 索引/AGENTS引用不存在的`docs/CONTRACT_LOCK.md` | AGENTS现行路径改指向`TEACHER_QA_CONSTRAINTS.md`+上游正式合同；历史Codex prompt和旧审计只保留历史 | **现行入口已改** |
| DOC-04 | `PROJECT_STATE.md`被旧索引说成唯一状态、P13独立报告称全绿与P16全量1FAIL并存 | `PROJECT_STATUS_CURRENT.md`前置当前Owner状态，注明P13历史时间范围；旧测试数字和结论保留原始版本 | **已添加最新事实** |
| DOC-05 | 26/82介质登记被误当简单录入错误；原上游八段式有值，但工具弱相关词触发误召回 | 新增[独立统计与根因报告](../data_quality/DM_APPLICABILITY_ROOT_CAUSE_AND_REFORM_20261029.md)，冻结老师工具/枚举，优先可版本化派生谓词与专业gold | **调查完成，待讨论后执行改革** |
| DOC-06 | 用户要求日常聊天跳图、三条业务通道、折叠思维过程但不输出SSE；旧架构写全部进图/完整事件对外可见 | `ARCHITECTURE.md`新增当前与未来双版本，`AETHER_CHAT_MODES...`历史头部加现行指针；原始帧留内部数据库/传输，用户只看公开阶段摘要与证据 | **设计冻结，代码未改** |
| DOC-07 | 旧R10 20/20 demo经现行P13环境重跑断言失败，历史测试不能重复声称现行全绿 | 当前状态注记，待定位mock/模型配置漂移；R8B PDF fallback为既有1FAIL | **待修复** |

## 所改内容（仅自有文档导航与审计工具）
- 当前导览和合同边界：`README.md`、`AGENTS.md`、`docs/DOCS_INDEX.md`。
- 当前结果及体系结构：`docs/PROJECT_STATUS_CURRENT.md`、`docs/DATA_LINEAGE.md`、`docs/ARCHITECTURE.md`。
- 历史数据解释防误引：`docs/TEACHER_REQUIREMENTS_AND_GAPS_20261027.md`、`docs/AETHER_CHAT_MODES_AND_COLLAPSED_PROCESS_20261028.md`（仅增加时间/状态指针，不改旧结论）。
- 新增`docs/data_quality/TEACHER_SAMPLE50_EVIDENCE_STATUS_20261029.md`、`DM_APPLICABILITY_ROOT_CAUSE_AND_REFORM_20261029.md`、本报告、两份只读巡检脚本。
- **明确未动**：`upstream/**`、老师原抽样报告/教师签名、PDF/Excel、`clauses.jsonl`、原版三个工具、`work/data_staging/p16/C_GATE`的人工CSV、SQLite、API密钥、在线服务及模型配置。

## 后续文档治理约定
1. 统一“一份当期Owner状态”：以`docs/PROJECT_STATUS_CURRENT.md`为入口；历史审计不大面积重写，另存新版补充说明，防破坏证据链。
2. 任何百分比必须同时写：测量日期、对象、分母/分子、机器/真人/真实模型/mock、原始/候选库版本、随机seed、来源哈希；没有签名写NOT VERIFIED，不能用准确率=0替代“未测”。
3. 老师合同与项目自定义加分要求分别列，原始未签条款只能在隔离候选目录流转。
4. 新增文档优先归属`docs/data_quality/`（来源）、`docs/audits/`（证据）、`docs/`（现行系统设计）、`evals/`（评测脚本/真值），不新建泛化`misc/docs2/docs_final`。
5. 安全的“小整理”目前只调整入口、状态标识和索引。物理移动旧项目、删除重名文件、删除缓存或合并报告须先做依赖解析/恢复点，另轮受控执行；**当前不执行**。

## 需要下一轮实际完成的目标
- 代码P0：`orchestration/intent.py`上的混合意图抢占漏洞和`backend/api.py`一般聊天绕图；用65困难题和独立新盲测，安全FN=0。
- UI P0：默认折叠公开决策过程，不渲染SSE原始事件/全量工具JSON，但DB持久化与replay不退化。
- 数据P0：82条机理的领域适用条件派生谓词小试点，老师白名单/原PDF人审为硬限制；P16真实50+42审核独立推进。
- 正式证据P1：模型原生100例、5轮实呼、ModelScope教师四场景、R8B测试1FAIL消除。
