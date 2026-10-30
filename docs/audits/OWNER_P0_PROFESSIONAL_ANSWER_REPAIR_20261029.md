# P0 专业回答修复｜检索—适用性—公开分析分层验收

日期：2026-10-29。状态：`LOCAL_CANDIDATE_VERIFIED_WITH_LIMITS / LIVE_BACKEND_STALE / PRODUCTION_NO_GO`。

## 1. 本轮范围与冻结边界

- 首读 `docs/audits/OWNER_P0_DATA_RETRIEVAL_GRAPH_CAUSAL_DIAG_20261029.md` 与 `docs/P0_PROFESSIONAL_ANSWER_RECOVERY_CONTRACT_20261029.md`。
- 仅在自有应用层修改专业回答/候选检索逻辑及P0专项测试；教师三个工具、正式 `clauses.jsonl`、Excel、PDF、枚举、转换/校验程序均未修改。
- 集成演示使用临时 SQLite、`RULE_DEMO`、真实冻结教师只读工具；未向 DeepSeek 发起付费请求、未重启8000/8001、未写入正式SQLite。
- 正式条款文件 SHA-256 前后为 `A8151797BA15A6A7452DD83AAEC9FAB4C0A815724CA45062EB1E2BAC7B4D49EF`，一致。

## 2. 已修复的P0缺陷

1. **专业意图与有界多目标检索**：壳体磕碰/碰撞/凹陷/变形识别为维护安全及标准调查；在候选模式下将安全检查、标准查证拆成最多3条实际教师检索，不再只把整句原样送入查询。经验证，即使粗粒度路由原本可能归为 `general_chat`，显式专业维护意图也会进入受限调查，而不是跳过教师工具。
2. **来源相关性和适用边界**：对本轮教师工具实际返回的source ID，再与冻结规范条款索引核对标准号、条款号和印刷页；来源级标记保守为E0，不把“ID存在”或“搜索命中”宣传为语义/适用性已证实。对B题输出条件范围和条文摘要：机械损伤条款只在原文限定条件（例如发现裂纹）下参考；检测方法条款不是凹陷验收标准；一般评定条款不是缺陷尺寸限值。无关的安全阀/爆破片、耐火材料、辐照脆化等结果不进入答案来源卡。
3. **检索零命中不等于零帮助**：两个问题均生成真实主答正文。无可核验条文时只提供明确标记的 `[GENERAL_GUIDANCE]`，补充风险信号、现场核查项、未知项及原因；不生成法定条号、凹坑阈值、设备风险等级、确诊、停复机批准。
4. **事实保留**：A题正文保留用户陈述的设备、300系列不锈钢、碱式酸性水和60°C；不要求重复填材质/介质，不推断304/316，且区分用户陈述和现场实测。
5. **反例拒召回**：Owner给出的“碰撞 凹陷”→ `GB/T 30579-2022 7.11 辐照脆化`被独立语义门拒绝；不能因为词面“碰撞”相同就作为证据显示。

## 3. 两道真实失败问题：前后与本轮实测

基线“前”来自Owner截图和其只读诊断记录，不是本轮新造的在线Run：

| 场景 | 旧答案/表现 | 新隔离端到端结果 |
|---|---|---|
| A：`设备：塔顶碱液管线弯头，材质：300系列不锈钢，介质：[碱式酸性水]，温度：60°C，问题：该减薄属于哪类腐蚀？` | 网页要求“请补充材质与介质后再检索”，与用户已提供字段矛盾。 | FastAPI→临时SQLite→SSE→Graph→真实三工具白名单→assistant主消息完成。工况被保留；主答给出酸性水腐蚀与弯头冲蚀/腐蚀-冲蚀协同为**待核方向**，强调测厚分布、pH/组分、流速、壁温等未知。无风险等级、无确诊。4次工具调用（1次damage-mechanism、3次standard search）；可核验候选源1条：`GBT30579-2022-5.23` / GB/T 30579-2022 5.23 / 印刷页32。工具原文主题及结构化条件覆盖碱式酸性水、300系列不锈钢、管道和49–66°C；仍仅是用户输入字段相符和E0候选，不代表现场确认。 |
| B：`设备发生壳体磕碰损伤，什么情况需要停机维修？验收判定标准是什么？` | 网页回答“未取得可追溯出处；无法形成受证据支持的结论。” | 0-source仍给出有界工程分析：泄漏、裂纹迹象、持续变形/密封异常/压力边界完整性不明时按现场程序保护性隔离并由合格人员评估；列损伤形貌/尺寸/NDT/设计资料/修理方案/修后检验清单。明示具体强制验收条款未核实、无统一凹坑值、不得据此批准复机。3次standard search；语义过滤后保留5条**条件性/方法性候选**：TSG 21-2016 8.5.8（已发现裂纹条件）、8.1.7.1（损伤且已开裂时缩短周期）、8.3.6（表面缺陷检测）、8.3.7（焊缝埋藏缺陷条件）、8.5.1（压力容器评定原则）。它们均不直接给出磕碰凹陷验收值。 |

Owner复现实验的原始工具对照仍一致：整句B 0条；“机械损伤”5条；“表面缺陷检测”2条；“压力容器 检验”5条；“碰撞 凹陷”1条但为辐照脆化误召回。P0候选通过多目标查询提高了可用覆盖，同时不是把这些5条误说成全部回答依据。

### 本轮错误断言核对

- A：确认material/medium/temp事实在snapshot和答案均存在；答案未再次索要材质/介质；未将300系列改写成304/316；“减薄”未当作测厚结果；0个设备风险/停机等级。
- B：没有生成具体GB/T/TSG法定凹陷阈值、无来源条款号伪造、无RBI L1–L4、无允许继续运行/批准复机结论；7.11误召回未展示。
- 全部回答将来源卡写成实际工具返回且source ID/元数据吻合的E0候选；不宣称人审、条款适用性认证或人审签名。

## 4. 检索缺口台账

| 需求 | 当前覆盖 | 结论 |
|---|---|---|
| 磕碰/撞击后的壳体局部凹陷或永久变形判据 | 教师库召回到机械损伤、NDT、压力容器评定的条件性/通用条款；未检出可用于本设备的统一凹坑深度/形状验收值。 | `STANDARD_NOT_VERIFIED`；不填造值。 |
| 修理方案批准、壳体局部修复工艺及修后验收 | 本轮检索未获得明确覆盖该具体损伤的直接修理/验收条款。 | `KNOWLEDGE_COVERAGE_GAP`；须按设备类别、监管路径、原设计/制造文件及批准方案另行核验。 |
| 停机/隔离及恢复运行的法规依据 | 现有候选仅覆盖受限条件下的检验/评定；不能由本轮来源支持对该设备发出确定命令或复机放行。 | `STANDARD_NOT_VERIFIED`；一般安全排查与法定决定分层。 |

上表是当前冻结教师语料内的检索/覆盖缺口，不表示行业法规不存在。建议后续以合法授权法规/检验规程建立独立来源层，明确发布方、版本、适用对象、印刷页和核验责任；不得把生成文本加入老师标准库。

## 5. 真实测试及失败

- P0专项：`& '.\.venv-langgraph\Scripts\python.exe' -B -m unittest discover -s tests -p 'test_p0_expert_guidance.py' -v` → **15/15 PASS**。包括64条作者合成边界样例的通用答复门禁、来源/风险防幻觉、64条下的零Source降级、跨FastAPI/SQLite/SSE两个失败问题、实际教师工具调用、来源误召回过滤、Mock结构化模型规划/生成。
- 全项目：`& '.\.venv-langgraph\Scripts\python.exe' -B -m unittest discover -s tests -q` → **392项：386 PASS、2 FAIL、1 ERROR、3 SKIP**。未掩盖失败：
  - `test_web_search_stays_off_by_default_and_sensitive_outbound_requires_second_opt_in`：期待敏感工程问题触发web search，实测调用0次；与该测试的旧路由预期不一致，P0不改外网策略。
  - `test_two_simultaneous_streams_execute_once_and_both_subscribe`：mock Graph运行次数断言期望1，实测0；非P0专项路径，未为P0扩展修改共享API/并发实现。
  - `test_p16_a_evidence42` 导入 `fitz` 时 `ModuleNotFoundError`：当前 `.venv-langgraph` 缺 PyMuPDF；不临时安装或改动其他任务环境。
- 前端回归：`npm test -- --run` → 18 files / **123 PASS**；`npm run typecheck` PASS；`npm run build` PASS，有既有主chunk >500kB提示。本轮无前端源改动。
- 教师只读终验：`& '.\.venv-langgraph\Scripts\python.exe' -B upstream/04_接口文档/validate.py --final` → 554/554 clauses、200/200 trajectories PASS；`.../upstream/05_提交区/_selftest_tools.py` → **17/17 PASS**。

## 6. 实际运行版本Gate（网页尚未修复确认）

代码侧新增健康信息是 `contract_version=aetheris-2026-10-29-p0.1`，能力字段包括专业回答候选flag；代码源码默认 `AETHER_EXPERT_GUIDANCE_CANDIDATE=0`。但实际运行端口不是此版本：

| 端口 | PID | 进程启动 | `/api/health` | `/openapi.json` | `/api/model-profiles` |
|---|---:|---|---|---|---|
| 8000 | 59120 | 2026-10-28 21:54:56 | 没有 `contract_version` / capabilities | `0.1.0` | 404 |
| 8001 | 65000 | 2026-10-29 08:00:05 | 没有 `contract_version` / capabilities | `0.1.0` | 404 |

因此只证明**最新磁盘代码在隔离测试中的候选行为**；没有依据宣称用户网页已经载入新后端或页面已修复。为遵守隔离边界，本轮不对线上本地端口写真实SQLite、不发真实DeepSeek请求、不重启服务。实际浏览器确认仍待Owner批准备份/隔离库和受控切换后单独验收。

## 7. 修改文件与源码指纹

- `backend/professional_answers.py`：意图/检索计划扩展；关联性重排、条件标注、E0保守等级、回答正文及证据摘要。
- `orchestration/r9_industrial_candidate.py`：防粗路由将有界专业意图错送general_chat而跳过检索。
- `tests/test_p0_expert_guidance.py`：两个真实失败题完整隔离E2E与语义误召回回归。

SHA-256：

- `backend/api.py` `C0E502BFA1CB48603BCC4064830FF928D410864EA1A4C0B42FA60650D3ABDF94` (本轮未修改)
- `backend/professional_answers.py` `939CE422E6E24F9BAF856C96B72D7BE207E08D30E5474FB1B9F4713AF24F0B02`
- `orchestration/r9_industrial_candidate.py` `BB32502B6C95598BD7B37A09BFD8FFA82945D798431BA1FFC29590F4B859995E`
- `tests/test_p0_expert_guidance.py` `E35EDA22719BB2474F8E01A7958FD7BC3945AFEEA9C0BF3B195DCCD99E629FAD`
- frozen `clauses.jsonl` `A8151797BA15A6A7452DD83AAEC9FAB4C0A815724CA45062EB1E2BAC7B4D49EF`

## 8. Gate结论与下一步

本地候选可供Owner审查；生产保持NO-GO。解除阻断至少需要：修复/解释上述全量回归项、在同一冻结知识库对更广查询集做人工标注的相关性/适用性评测、确认最终服务PID加载的源码合同版本、再以批准的隔离数据库做Edge实际发送/刷新恢复验证。未有人审条文适用性前，候选E0不升级为标准结论。
