# Owner 独立审查｜目录清理与教师数据合同核实（2026-10-27）

## 0. 当前事实与并发保护
用户本轮要求：清理朋友仓库的无关预留文件和历史废置、按官方标准约束改进工程语义与多Agent；本地 Codex 已在同一工作区执行。
**本文件仅完成文件归类与审核，不对 `upstream/` 移动、清理、删除任何文件**，以免和 Codex 当下运行的完整仓库校验/构建发生竞态。
最新只读观察：`upstream` 已非sparse checkout，`git status --short --branch` 返回 `master...origin/master`（无工作树修改）；`scripts/check_sources.py` 19/19；`git ls-files`计2535条。磁盘 `upstream` 追踪文件（当前扫描全部文件含必要渲染件）总约585,414,574 B（558.3MiB），不是未来开发运行时依赖必须全部加载。

## 1. 实际分类及处理顺序
| 位置 | 量级/本机观察 | 类别 | 决策 |
|---|---|---|---|
| `upstream/README.md`、`任务包问题答复.docx`、`资料获取与摘录表填写指南.md`、`04_接口文档/工具接口规范.md`、`技术指标验证方法.md` | 官方合同 | immutable | **冻结保留** |
| `01_RBI标准/*.pdf`、`02_损伤机理参考/*.pdf`、两份`条款摘录表*.xlsx` | 原始出处 | canonical | **冻结保留**；不能用历史备份替代现用版本 |
| `03_案例样例/*`、`04_接口文档/schema/*`、`05_提交区/*` | 验收与运行 | delivery | **冻结保留** |
| `04_接口文档/reference_code/{gorilla,LLaMA-Factory,Qwen-Agent,ToolAlpaca}` | 第三方源码 | reference | **保留在upstream作为学习资料**，不复制进正式Web运行包、不作为App启动时依赖 |
| `01_RBI标准/_verify/` | 数据抽样、修复核证链 | audit | 保留证据；不要把带时间戳的核验图和原始来源当“垃圾”删除 |
| `01_RBI标准/_render/`、其他`_render*`、`upstream/_pages/` | PDF渲染过程缓存 | archive_candidate | 先建sha/脚本引用清单，Codex空闲后可移到Git保留的离线归档，不直接删除 |
| 根部`_gen_*.py`、`_inspect.py`、`_pdf_text_dump.txt`、`_rbi_extract.txt`、`_26610_*.json` | 原始提取/调试中间物 | archive_candidate | 检查是否是生成器/数据重现唯一来源，再按可复现性选择归档 |
| `01_RBI标准/条款摘录表_RBI.xlsx.bak_*`、`05_提交区/*.bak_*` | 历史数据备份 | backup | 需保留至少最后一个可核对回滚版本；全量历史仅在已留哈希和Git可追溯时再归档 |
| `upstream/.workbuddy/`、历史`handoff.md`、`项目全量审查报告*`、`修复提示词*` | 工具记忆与旧报告 | obsolete_candidate | 不能作为现行状态源；可做历史存档，不应放进Agent的默认阅读列表 |
| 根`机械智能体_接管审计与执行蓝图_20261027.md`、`机械智能体_Codex_R0执行提示词_20261027.md` | 已过时的接管阶段文档 | archive_candidate | 由本地文件整理阶段安全迁移至`docs/archive/`并更新链接；当前保持原位以防旧会话引用 |
| `docs/CODEX_*.md`、`docs/ADR_*.md` 等大量近似标题 | 两个执行线程不同阶段计划 | documentation_debt | 通过`docs/DOCS_INDEX.md`设唯一**当前主文档**；其余标`historical`，合并内容前勿删 |

目录约占用：`04_接口文档` 236.3 MiB；`02_损伤机理参考`169.2MiB；`01_RBI标准`137.18MiB；根`_pages`9.22MiB；`05_提交区`5.83MiB。
**原则：**“开发主目录干净”不等于“历史证据删除”。上游原Git是可追溯冻结供应商/教师快照；正式应用的构建包应只包含我们必要的源码/索引/经过允许发布的数据，不含reference_code和几百MB中间PDF图片。

## 2. 舍友审计的源码真值（已读 `upstream/04_接口文档/convert.py`）
**源代码确认正确：**
- `STANDARD_NAMES` 精确12项：GB/T 30579-2022；26610.1/2/4/5-2022、26610.3-2014；TSG21-2016；21447-2018；150.1/.3/.4-2024；151-2026。GB/T 10123 不在白名单，只能用于校对用词，不能通过convert直接入`clauses.jsonl`。
- 列表拆分 `SPLIT=re.compile(r"[;；\n]+")`：中文顿号、英文逗号不会拆， enum_list会将合并的字符串判为非法；损伤机理八段式自由文本列表也不会分开，虽未必触发枚举报错，但数据质量仍受损。
- `clause_id` 为规范前缀+`(-[a-z]{1,2})?`；拒绝`-abc/-A/-a1`等。
- `content_raw`只强制≤300字符，页码整数，温度/压力及检验周期数值；上下限不能倒置。
- `HEADERS` 强制列名/顺序完全一致；XLSX必须有`摘录表`工作表；DM的`损伤描述及机理`不能为空。
- `ANNEX_A`按`clause_no`前两段匹配GB/T 30579标题；`WRONG_NAMES`对title和相关或伴随损伤检查6类禁用叫法。
- `material_family.json`做牌号向所属类上行展开，受影响材料照原文、适用材质用白名单。
- RBI的统一等级只允许任务包L1-L4，L5单独报错；26610.3有可能性和后果时查映射，其他符合低/中/中高/高用语的26610记录做对应；不能任意推断检验周期。
- 两份真实源XLSX本轮read-only查看：RBI表23列（max_row=602）、DM表25列（max_row=600）；行数含空白/格式行，**不代表实际有效条款数量**。enum实际material=22、medium=19、equipment_type=6；`stream_type=12`是额外枚举，不应把它算入这三类。

**需要纠正或加旁路预检的表述：**
1. `title`并非字节级一字不差：`norm_name`忽略空白、并将全角括号换成半角；正式数据仍应忠实标准原名。
2. `抽取人`仅校验非空，代码**没有**验证“学号_姓名”正则，也没有强制“复核人”非空或复核人与抽取人不同。人工审计必做。
3. `clause_no`当前仅 `isinstance(..., float)`时报数值类型错误，不保证所有Excel数值类型都被捕捉。需要前置单元格类型审计，尤其不要丢失`5.10`尾零。
4. `备注`是否写明无法映射的风险用语当前**未被校验**。人审规约不能误称自动强制。
5. `risk_level_mapping.xlsx`缺失时先有Warning，但若存在26610.3矩阵行，后续`risk_map.get(...)`会返回None并报错；不能概括为“缺映射表仅提示且全程放行”。
6. “25个校验点/4个warning”属于舍友分析时的一种分类，不是官方明确定义的一组固定25断言，业务用例以真实代码分支+官方测试为准。
7. 规则不能检测原文润色、真假条文、误记PDF页码、装置适用性超范围、重复换参数凑多步、虚假人审；需人工PDF查证与相互独立的验证器。

## 3. 立即建立独立 XLSX预检器的建议（不修改convert.py）
- 专门标识含`、`或`,`的枚举单元格，反馈为“多个项请用;或；分隔”，不要误导成缺枚举；
- `clause_no`Excel cell类型严格为text，且保留小数位字符；按ANNEX_A解读`5.10`；
- 抽取人与复核人记录可验证者、日期及交叉核验状态，但不代替真人核原标准；
- 拟入库来源必须在12白名单，其他公开工程资料进入`knowledge/public_references`，与官方`clauses`隔离；
- Excel所有问题回写**报告**而不改xlsx；新数据修复必须返回真实来源表，最终通过官方convert与validate；
- 未人工证实的新增机理卡使用`review_status=draft`、`verification_level=E0/E1`；不得混入官方已认证条款。

## 4. 独立运行过程新发现（当前Codex正在编辑，未擅自修业务代码）
- 规则类自然语言探针：`python -B -m evals.semantic_probe`，5/5 个较长现场描述在官方关键词查询与FTS5完整字符串查询中均无命中。这是未标专家Relevant的探索性测试，**不是检索准确率0%**；先做语义拆词/标准术语映射再测Dense检索，不盲目加向量数据库。
- 本轮并行运行产品层单测时发现**中间开发态失败**：`orchestration/graph.py` `AgentGraph.run` 路由序列含 `rbi_specialist`，但其构造时默认 `nodes` 列表缺少 `RbiSpecialistAgent()`；`tests/test_store_and_graph.py` 对应节点注册/运行失败，且 `test_api_vertical_slice` 受连带影响。该报错来自正在进行中的Codex写入期间，复核完结前不能宣称36项全PASS。建议让当前Codex同线程检查和修复**节点注册表与run路由一致**，再重跑完整测试（如其已修复则以最终实测为准），不要手动修改老师的上游Harness。
- 来源：本轮直接读取 `orchestration/graph.py` 及 `tests/test_store_and_graph.py` 相关行；没有修改这些业务文件。

## 5. 清理与Codex当前并发
- 当前上游master干净，恰好适合**只读快照**；但是Codex仍在编辑同一产品层。不要同时移动它可能读写的`AGENTS.md/docs/README.md/app/backend/tests`。
- **已做**：目录占用/版本/关键文件和文档状态扫描、教师转换器逐条核对、生成本审计报告。
- **未做**：文件移走、删除、git rm、git reset/clean、老师合同改动。已授权的DevSpace bash仅允许只读检查/测试与特殊构建，不用它执行删除或重排命令。
- 下一阶段：Codex交接后先确认`git status`及当前文件引用、创建带SHA-256清单的离线归档包、仅对明确冗余且可通过Git恢复的缓存做可逆搬迁，在`docs/DOCS_INDEX.md`取消其默认入口，重跑老师官方验证。
