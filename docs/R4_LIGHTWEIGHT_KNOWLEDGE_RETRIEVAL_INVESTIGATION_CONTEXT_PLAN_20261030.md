# Aetheris R4｜轻量文档工程、可扩展知识、主动调查与分级上下文技术路线（2026-10-30）
**状态：TECHNICAL_DESIGN / EVIDENCE-BASED_OPTIONS / NOT_IMPLEMENTED / G3_STOP_FIX_REQUIRED / NO_GO_PRODUCTION。** 本文是Owner外部开源调研及本地源码/数据现状核查，不意味着模型已经安装或真实DeepSeek成功。保护老师冻结的12标准白名单、`upstream/**`、原正式PDF/Excel/JSONL、真实SQLite、个人会话及在线8000/8001。Codex本机执行必须使用原生文件和终端，不通过DevSpace桥接；本轮只讨论和设计，不下载模型、批量抓取国标或修改运行程序。

## 0. 项目当下实测基线
- `clauses.jsonl`正式条目554=472 RBI+82 DM，SHA `a8151797ba15a6a7452dd83aaec9fab4c0a815724ca45062eb1e2bac7b4d49ef`，teacher 554/200、17工具；已存在S3-A候选134谓词及S3-B三值引擎，但正式条款PDF逐页真人核验0、适用性批准0、领域独立Gold0。
- A2 `knowledge/retrieval/r2_candidate_v1` 只是离线派生索引，64 AUTHOR_SYNTHETIC题的Top-5**非空率**2/64→8/64，不是Recall@5，更不是正确适用率；尚未证明默认Graph接入与收益。内置`knowledge/lexical.py`用SQLite FTS5 trigram；查询切词极弱，直接把较长中文问题当整体导致不能召回。
- 现有`backend/context_slots.py`已能记录原文span、事实来源、介质/材料、壁温vs工况温、H2S分压vs总压等；`backend/conversation_memory.py`有CID事实、撤回、摘要候选。普通聊天`backend/api.py`最多12轮，`backend/deepseek.py`最多16,000字符、12轮原样截断；并非动态按真实Tokenizer预算。`frontend/src/App.tsx`持续使用localStorage缓存run-events和快照，缺跨CID配额/TTL压缩观测。
- G3本地Mock压测本轮重新跑 c1/c4/c8 各100 Run，0errors；p95分别146.529 /516.121 /1618.197 ms，总时9.25/5.82/4.31s。此结果**不代表实际模型吞吐**。G3仍缺浏览器WorkerCapacity429/故障注入验收，用户尚不能正式测试DeepSeek。

## 1. Docling最值得学的是什么？不克隆整仓
### 1.1 取核心思想而非复制重型ML模型
研究官方：
- `https://github.com/docling-project/docling-core`：MIT，统一文档Pydantic类型/结构与provenance。
- `https://docling-project.github.io/docling/concepts/docling_document/`：body/furniture、paragraph/list/table、parent-child、页与bbox，reading order。
- `https://docling-project.github.io/docling/concepts/chunking/`：HierarchicalChunker、HybridChunker、contextualize，给每块增加标题/表头而不是固定512字分块。
- `https://docling-project.github.io/docling/usage/advanced-options/`：OCR与table结构可选择开关。
**最值得复用/学习的三个机制**：
1. **PageProvenance模型**（每个chunk都带原PDF SHA、文件名、PDF实际页索引、印刷页候选、bbox、表格cell/行列、章节路径、抽取方式、置信/人工复核状态）；防止“有正确标准号但物理页其实错了”。
2. **版面与语义分块**：按标题、条款编号、章节、表格行列、表注、跨页续表、条件作用范围划分；合并时保持共同前缀，不破坏负条件/例外。独立全文出处指针而不是重复大段收费文本。
3. **两层抽取结果**：`raw_span`永远不可覆盖；`candidate_predicate`可推断但必须带source_ref、scope、human_review_state。无法解码CMap时标`UNREADABLE`并保留页图供人工核验，不把乱码标为事实。
实现建议：`knowledge/document_intelligence/{schema.py,pdf_text_spans.py,layout_chunks.py,provenance_verify.py}`；复用已存在的PyMuPDF 1.27.2.2作为首选PDF底层，不安装完整Docling；先审当前PyMuPDF许可（AGPL/商业双许可），未来对外分发需法务合规。只在**15条高风险机制的源PDF定位样本**测试按需局部OCR或抽取器比较，不自动OCR所有PDF。
**代码使用规约**：可以对照 MIT 许可的docling-core做一个本项目极简适配层，也可按需`pip install docling-core`；若复制MIT源码，应保留原许可/版权。不要复制训练权重和完整OCR/布局网络，不要声称只安装docling-core就有PDF版面OCR能力。需要布局模型时先基准验证，专门使用隔离研究环境。
预处理一次离线完成，聊天时只检索版面索引，**绝不在每个Run重新解析PDF**。

### 1.2 对Aetheris最关键的原始数据修复
- 先建立`source_manifest`+版本/标准状态（现行/废止/替代/未查）、官方链接/权限、文件hash、授权状态、原PDF页候选/核定、摘录hash、human-review队列。
- 优先人工对照5.23的49–66℃（NH4HS局部析出窗口）、5.6多子工况、6.7分压/总压、TSG 8.5.8安全等级前提、非烟气HCl等至少15组专业高风险样本；重复抽样/双审冲突应明确保留。
- 对任何源批准到正式知识前，单条记录满足 `SOURCE_PRESENT → TEXT_MATCHED_TO_PHYSICAL_PAGE → SEMANTIC_SCOPE_REVIEWED → OWNER_APPROVED`。缺一级不得用于“已审适用/设备合格”判断。

## 2. 数据量是否够？优先“知识范围与粒度”，再上向量
### 2.1 核心判断
554记录不足以覆盖“开放的机械工程/维修/验收/失效/法规”等所有问答；但对12份老师限定源的**有限专题问答**，554记录足够先研究可复现、高质量检索。索引量增加不自动提高答案质量，反而可能提高误召回。
- 确认课设/老师3工具必须用的12标准**白名单完全冻结**，新知识**单列`external_reference_catalog`**，不可入老师的`upstream`、不能伪装成第13个教师标准，也不能以外部资料虚构正式验收限值。
- 合法扩充顺序：先**标准目录/现行有效性元数据**（标准名称、号、发布/实施/废止日期、官方来源）；再补公开授权的通用机械工程知识、权威说明性资料、行业失效案例；最后需要全文时逐项核查授权与使用限制。
- 官方入口：`https://std.samr.gov.cn/`（标准目录、版本、现行状态等元数据）；`https://openstd.samr.gov.cn/`（符合站点权限的在线阅读或下载）。不能把“网站可预览/个人研究免费”视作任意抓取、汇编、再发布全文的许可；遵守访问策略和标准著作权。某些推荐性/采标标准仅供在线阅读或目录，不可擅自批量下载。
- 数据需求按用户任务矩阵，不按数量堆积：机理/检验/停用与恢复/维修验收/材料及化学/压力容器/一般概念；每类标`SUPPORTED_BY_TEACHER`, `EXTERNAL_INFO_ONLY`, `MISSING`, `REQUIRES_CERTIFIED_REVIEW`。
- 先编≥50条不同意图与难度的Gold（建议20机制、10标准查证、10停机/维修、10概念及负例），独立留出≥20做holdout；每题标条款ID、相关性、该条对结论支持/反对、适用前提、不该答什么。专家未审时标`DEVELOPER_LABEL_PENDING`，不能称专业Recall准确率。

### 2.2 四级检索开关（由评测数据选择，不预设全开）
**R0（0MB模型）**：旧老师查询+标准号/条号精确索引 + SQLite FTS5 BM25 + 中文字符n-gram/alias + 标题/章节/对象过滤；不同query变体融合后dedup，来源hash去重。
**R1（0MB模型）**：加入权重与RRF倒数排序融合`RRF(d)=Σ_i 1/(k+rank_i(d))`，k可实验初始60；添加`source_coverage`, `device_scope`, `standard_status`, `ambiguity`的**非宣判**候选重排。与严格semantic scope不同，RRF只是排名不是真实适用。
**R2（约24MB权重）**：仅R0/1在独立Gold有明显漏召回时，使用`BAAI/bge-small-zh-v1.5` 的 ONNX INT8轻量版。原fp32 `model.safetensors`约95.8MB；`Xenova/bge-small-zh-v1.5/onnx/model_int8.onnx`实测文件列示约23.9MB，模型约24M参数、512维；字典/运行时/中间内存另算。554条×512维float16约0.54MiB；INT8向量约0.27MiB，向量文件小不等于运行时RAM小。统一一个单实例CPU ONNX推理池/离线批编码，生产不让每个Agent加载权重。下载须明确Owner批准，缓存路径与hash。
**R3（额外模型非默认）**：仅当Gold证明有精排收益再评估cross-encoder reranker。通用中文reranker-base权重可超1GB，不符合本阶段轻量目标；先用不依赖神经网络的条件/关系/文本span重排，或低频调用已存在LLM完成针对性语义审查（不能将LLM意见冒充审核、限成本）。
**注意**：KB级没有通用可靠的中文Dense神经模型可作为合理默认推荐；KB级可以是中文字符索引/专业alias词典/压缩向量子集，但不具备完整语义泛化。不要宣称R0/1已有“神经Reranker”。
**何时升级**：候选来源的**Gold Recall@5、危险漏召回、hard-negative precision、p95延迟、CPU/RAM增量**同时优于R0且错误硬排除=0，才上线R2；不以Top-5非空率或语义余弦分数作为设备适用判据。

## 3. Agent主动设计调查：不是更多Agent，而是一个闭环Planner
参考`https://arxiv.org/abs/2401.15884` Corrective-RAG（低质量检索触发纠正），LangGraph state/node/conditional edges（`https://docs.langchain.com/oss/python/langgraph/graph-api`）；**借鉴原理，不复制大型训练方法**。
**单Agent多节点有界状态机**：
`AnalyzeQuestion → ExtractFacts → BuildHypotheses → EvidenceGapLedger → SelectNextAction → ExecuteReadonlyTool → EvidenceCritique → UpdateHypotheses → (Continue | AskPreciseQuestion | AnswerWithLimits)`。
- `InvestigationState`独立字段：`confirmed_user_facts`, `unknowns`, `hypotheses`, `evidence_gaps`, `tool_history`, `evidence_spans`, `adversarial_conflicts`, `budget`, `stop_reason`。每个假设必须有“支持证据、反证、未知条件、需要的观测”，不能直接给损伤概率或设备等级。
- 初步排序可以用确定性`priority(a)=expected_uncertainty_reduction(a) × safety_relevance(a) - latency_cost(a) - money_cost(a)`（仅工程启发，需评测调参数）。如壳体磕碰，优先确认“是否承压边界/是否裂纹或泄漏”，而不是问颜色或直接查全部国标。
- 先给一个严格工具行动枚举：`TEACHER_STANDARD_SEARCH`,`TEACHER_MECHANISM_LOOKUP`,`TEACHER_RBI_LOOKUP`,`LOCAL_CANDIDATE_RETRIEVAL`（仅shadow不算第四老师工具）, `ASK_USER_ONE_TARGETED_FACT`, `FINALIZE_WITH_UNCERTAINTY`。本地检索不能绕过老师边界。
- Planner初始预算：1次意图拆解、至多3–5只读查询、至多2次策略修订、单Run有硬墙钟/Token/成本上限；被拒绝工具不能通过反复提示绕过。无来源时转`GENERAL_GUIDANCE`与缺口说明，不能伪造规定，也不全盘拒答。
- 举例B“壳体磕碰，何时停机验收”：提出塑性变形/隐裂等**竞争假设**→检索机械损伤及NDT→验条文是否针对承压壳体与裂纹→发现尚不知压力、损伤深度，提示可能危险征象、询问信息价值最高的一个量，并给通用安全核查建议；**不能模型自己批准继续运行或复机**。
- 真正的Critic只检查`support, scope, contradiction, source identity`和是否足以回答。不能让第二个LLM说“看上去合理”就当审核。
- 先用Rule Planner/ScriptedMock与≥30条不同困难任务进行闭环评测，之后只给真实DeepSeek受限的PlanProposal权限，通过现有Pydantic及工具门禁，真实模型请求和模拟必须分账。

## 4. 四层上下文与前端/内存治理
### 4.1 上下文编译器不是扩大模型context上限
`L0 Policy & Task`（权威规则、当前任务、预算，不可摘要覆盖）
`L1 Confirmed Device Facts`（CID与设备scope、用户更正、物理量单位、时间、UNKNOWN和来源；优先保留）
`L2 Relevant History`（最新原始轮次+按需召回旧消息+失败后的公开摘要；summary只作`untrusted_hint`）
`L3 Evidence Pack`（与本问题相关的最少标准span、正反证据、原页/出处/适用性限制，不直接复制整份标准）。
新增`ContextCompiler`依模型tokenizer估真实token，`context_budget`由模型实际支持窗口和输出预留推导；初试可设输入预算8k或12k tokens并保留≥20%回答/工具余量，但不能假定供应商所有模型都支持同一窗口。L0/L1优先不可截断关键事实；L2/L3按质量和token比选取，密度低或重复span删减，只保留source ID+短证据摘要。每条token都按来源/用途账单记录。
严禁将专业设备与工况历史泄漏到普通general_chat或别的CID，用户明确未授权的敏感附件/标准全文不对外发送。模型摘要损坏/超时回退原始事实，不能把摘要推断冒充用户确认。

### 4.2 UI性能和持久化
- localStorage仅存**有界近期**Run索引/序号/草稿和轻量checkpoint，不持久化大量events正文、附件内容、模型内部trace；SQLite是权威事件源。
- 初始研究上限建议：单CID最多最近2–3个Run完整渲染缓存、每Run≤100条客户端事件或≤256KiB（哪项先到即去服务端分页）；全origin上限实验目标≤2MiB（不是浏览器硬配额）。过期LRU/TTL（例如7天）需要测试刷新与离线语义，不能删除服务器事实。
- `performance.mark/measure`采集事件回放耗时、输入到首次token/主答渲染、React长列表渲染耗时、EventHistory加载、`JSON.stringify`总时；Chromium CDP内存和堆采样的p50/p95/峰值/曲线，避免依赖跨浏览器不支持的`performance.memory`。不记录隐私内容。
- UI虚拟化长会话与证据列表，增量SSE去重，按需只加载展开的原文短span；减少全量`JSON.parse(localStorage.run-events)`和持续复制整个数组。控制指标需先测空转和100/1000 events场景，设无回归门槛（例如峰值内存不增长超基线20%、首次渲染不恶化超过20%，均为暂定目标）。

## 5. 实施顺序、文件归属、Gate
**P0可靠性**：G3 Edge WorkerCapacity429 / POST rate429 / model503 / tooltimeout 类型卡和同run重连必须先完成。用户真实DeepSeek仍NO_GO。
**P1文档与知识（2个独立研究分支，可并行但不接默认）**：
- `R4-DOC`：仅`knowledge/document_intelligence/**,scripts/r4_doc_*.py,docs/audits/R4_DOC_*.md`，15条标准页定位/表格块/页坐标与CMap降级、来源哈希、复核队列。与Docling官方少量源码对照，未经授权不全量拉仓库/权重。
- `R4-RET`：仅`knowledge/retrieval/r4_*,scripts/r4_retrieval_*.py,docs/audits/R4_RET_*.md`，50+独立标注候选Gold，R0/1索引与RRF + 小ONNX模型可选离线A/B，先不修改Graph与教师工具。只在实测明显增益并通过false-exclusion门后由集成者接线。
- `R4-STD`：仅`knowledge/external_reference_catalog/**,docs/data_quality/R4_STD_*.md`，官方标准元数据与授权状态，按现行有效性及专业缺口排名；不得批量获取不允许再使用的标准全文。
**P2调查与上下文**（可以与P1并行规格，但运行接线后置）：
- `R4-PLAN`：独占`orchestration/r4_investigation_*.py,tests/test_r4_investigation_*.py,docs/audits/R4_PLAN_*.md`，规划/证据缺口/有界工具执行接口独立实验，不修改默认Graph。
- `R4-MEM`：独占`backend/r4_context_compiler.py,frontend/src/r4_metrics/**,tests/test_r4_context_*.py,docs/audits/R4_MEM_*.md`，token预算+CDP内存/LocalStorage压测；与API接口先模拟、后统一集成。
**P3最终单集成者**负责将多个模块shadow flag接入，真实Edge A/B/SCC/429与有界模型真实20–30题对照（仅Owner批准费用/隐私后执行），统一数据身份/量化安全门，全量回归。不得并行抢写`backend/api.py`、原R9、现有前端App源码。
**Gate分级**：
G0 teacher源hash、12白名单、PDF许可、人审状态不变；
G1 人工审订来源必要前提后才能升格正式标准；
G2 Gold区分检索相关、真实标准支持、适用设备，危险FalseHardExclusion=0；
G3 当前G3可靠性缺项彻底真实浏览器验收；
G4 内存/Token/冷启动/查询延迟报告，重模型需量化本地资源收益；
G5 真实LLM计划与决策质量独立有界测试+输出安全红队，不偷换Rule Demo；
G6 只有研究预览通过可交Owner UI试用；正式设备结论仍须人审与业务审批。

## 6. 外部技术来源（2026-10-30核查）
- MIT Docling core `https://github.com/docling-project/docling-core`
- Docling documents `https://docling-project.github.io/docling/concepts/docling_document/`
- Docling chunker `https://docling-project.github.io/docling/concepts/chunking/`
- PyMuPDF许可FAQ `https://pymupdf.readthedocs.io/en/latest/faq/index.html`
- BGE small 24M `https://huggingface.co/BAAI/bge-small-zh-v1.5`
- INT8 ONNX 23.9MB `https://huggingface.co/Xenova/bge-small-zh-v1.5/tree/main/onnx`
- 国标信息查询`https://std.samr.gov.cn/`
- 国标全文公开`https://openstd.samr.gov.cn/`
- 国家标准委公开办事指南`https://www.sac.gov.cn/bsfw/bszn/art/2020/art_1a1bb5efef0e4cdbb5f2f0cf91435504.html`
- LangGraph State/Node/Conditional Edge `https://docs.langchain.com/oss/python/langgraph/graph-api`
- Corrective RAG `https://arxiv.org/abs/2401.15884`
- 版权注意：公开免费阅读≠授权复制、商业整合与再发布。正式标准必须核查标准现行版本及真实许可。
