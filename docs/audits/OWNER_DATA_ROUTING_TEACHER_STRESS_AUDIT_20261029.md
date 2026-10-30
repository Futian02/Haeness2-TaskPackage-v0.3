# Aetheris | Owner 数据血缘、业务质量与双通道路由独立深度审计（2026-10-29）

**结论状态：TEACHER_SCHEMA_PASS / BUSINESS_SEMANTICS_REVIEW_BLOCKED / ROUTER_GATE_FAIL / CONCURRENCY_BACKPRESSURE_PARTIAL / REAL_LLM100_NOT_VERIFIED / PREVIEW_ONLY。**

## 0. 只读工作范围与凭证声明
本轮使用 DevSpace 在真实项目工作目录对教师README、工具接口规范、技术指标验证方法、任务包问题答复docx（121段、2表）、资料填写指南、upstream/05_提交区、RBI源Excel、教师转换器、检索工具、P15/P16数据质控报告、backend/api.py、orchestration/intent.py、P13质量报告、现有离线评测脚本做实际读取/运行。未修改upstream任一文件、正式JSONL、PDF、Excel、人工审签、模型配置、运行SQLite、API密钥、前端和上线服务。新建本审计文档和独立路由诊断脚本。所有负载测试均临时SQLite、RULE_DEMO，本轮不调用付费DeepSeek真实API。

## 1. 教师权威验收门槛
来源：upstream/04_接口文档/技术指标验证方法.md、工具接口规范.md、upstream/README.md、任务包问题答复.docx。
- **引用正确率**：必须随机50条PDF交叉真人核原文/条款号/页/适用范围，≥48/50，否则不通过；不能由模型或上传证据代签。
- **真实大模型工具调用解析**：100组真实模型回放≥95组合法（原生合法工具名和参数），fallback成功不能计入原生解析。
- **完整轨迹**：包括异常执行的100次尝试，100%记日志；至少5轮真实连续工具调用。
- **护栏**：四种异常各≥3（至少12）100%拦截，正常≥30全部放行；不得以简单演示代替。
- **格式数量**：≥300条款、≥200轨迹、多步≥40、三特殊各≥15，validate.py --final 全过。
- **公开演示**：ModelScope Gradio可访问、真实工具过程、终稿证据，至少单步/多步/拦截/出域四图。React/FastAPI本地验收不替代公开部署。
- **官方工具接口严格不变**：damage_mechanism_query/rbi_lookup/standard_clause_search三工具，status/in_domain/result/source/message五键和八段式、枚举、映射表一致。API RP580/581/571等不得加入正式条款库。
- Q&A强调损伤机理的八段式来源，OCR乱码必原图逐字核，clause_no文本不可自动变浮点，TSG21第1号修改单、材质族只上行映射、风险矩阵3D=L3，GB/T 26610.3不能推固定检验周期。

## 2. XLSX→JSONL来源血缘实测
读取源Excel：upstream/01_RBI标准/条款摘录表_RBI.xlsx，90,842 bytes，SHA256 e43f7b0d3381a38fa648c2505e27d1c87893af5aea89aa119097dbfc49c6b7bf；23列A-W，真实有ID 485行，末行486，包含473-486的13条GB/T26610.1草稿。正式clauses.jsonl的RBI472行，不包含未署抽取人U的13条；damage_mechanism82，总554。
RBI全485行：A-F均485；G失效可能性30，H后果45，I/J风险等级各25，K检验周期0，L推荐检验方法54，M适用材质0、N介质0、O/P温度界0、Q/R压力界0，S设备类型32，T其他条件472，U抽取人472，V复核人0，W备注485。13新草稿U/V全空；已在工作树但未入库，符合DRAFT_UNSIGNED。
之前Owner只读审计确认485行没有ID重复，25矩阵与映射表0不一致；正式472条核心列与对应原Excel无差异。不能据此称原文逐字正确、条件正确或从未被人工错填。
P15/P16隔离状态：A42条/73单元格、机器28 MATCH/13 AMBIGUOUS/1 CONTRADICTS（TSG21 §8.3.12 index78错，实际index83），真实人签0；B剩余211条表格需要原格复核，82×16=1312 DM八段式及条件槽需核原文，补充标准56章节待复核。42变更/44字段差分的preview仍554条，正式数据冻结。
**重要：适用性字段全空不能直接当错误/凭空补；需区分原文未规定 vs 信息留在F/T/八段式里未结构化 vs OCR未核证。对于材料、介质、温压多分支条件建立predicate/上下文来源，无法明确提取则unknown，不猜填。**
正式上游RBI Excel相对其自身Git HEAD已经M，另有未跟踪13候选和旧备份；属于历史状态，本轮不归因、不重置。

## 3. 正式工具弱相关风险（不是人工错误率）
重跑原版_teacher_selftest：17/17 PASS，但仅说明样例返回满足测试断言。碳钢/氯化氢95℃管道候选包含盐酸腐蚀及烟气露点腐蚀；碳钢/湿硫化氢110℃换热器返回湿硫化氢破坏、微生物腐蚀、硫酸腐蚀、燃灰腐蚀、碳酸盐应力腐蚀开裂。后四者可能是宽召回而非现场结论；没有领域专家gold不能直接称错。
代码upstream/05_提交区/tools.py:296说明只有26/82机理登记适用介质；当结构化介质空时通过description/influencing_factors/susceptible_locations/other中的别名子串作为弱信号。按材质、强弱介质、温度和证据打分，最多返回6候选。弱字符串命中不等于该机理在此设备上E3适用。
后续在自有产品层做post-tool eligibility/relevance gate，存每条支持条件、反证、缺失/排除理由，避免伪有把握。正式三个教师工具不改。独立评估：mechanism precision@k、unsafe assertion rate、refusal correctness、E0/E1/E2/E3、RBI级别空值保持率，不以schema命中率替代。

## 4. 双通道路由实测：65道对抗用例
新增只读无网络脚本：evals/owner_mixed_intent_route_audit.py。
实跑65题，期望普通知识/创作23、标准查证15、工程分析27；48/65分类一致，17不一致：普通误转专业4、标准误转其他5、工程误转普通8。为人工设计的hard-case诊断集，不是随机流量准确率估计或模型评测。
严重例：
- “你是什么模型？顺便判断这台容器的风险等级”→general_chat，安全工程需求被身份正则截断。
- “设备出现氢鼓泡，应该核查什么？”、“现场发现裂纹，接下来应该检测哪些参数？”、“近三年测厚数据下降，容器还能安全运行吗？”→general_chat。
- “检索损伤机理的第5.23条款”→hypothesis_exploration，丢失明确的标准查询意图。
- “帮我写一篇关于腐蚀机理的科普文章”、“把这段腐蚀报告翻译成英文”→hypothesis_exploration，不应调专用工具。
接口源码 backend/api.py:580对**所有run**一律执行graph.run，graph内部对general_chat走route→report，之后backend/api.py:651才调用DeepSeek.generate_chat。当前普通模式确实无需老师工具且一次聊天模型生成（web搜索off时），但并没有**绕过LangGraph运行**。
建议FastAPI入口分三路：general_chat → 直接DeepSeek（无需图，无老师工具，但沿用run_id/SSE/SQLite预算/失败回放）；standard_lookup → 独立单工具轻路线+E0/E1来源门禁；engineering → 原LangGraph证据/鉴别/复核图；混合问题尤其有具体设备安全请求者不允许身份/问候/创作优先吞掉工程子任务。可以任务拆分或交互确认，优先fail-closed。上下文隔离、web隐私和同会话最近12轮逻辑保持不退化。
路由器短期可使用**安全优先规则+强创作意图检测+标准查证意图**，不需要为每个一般聊天先多花一次LLM调用；低置信案例可标需澄清，模型分类只作可选分支并独立计成本。新盲测题禁止只对这65例特调。

## 5. 压力测试实跑
实际执行脚本 scripts/owner_p13_api_sse_graph_stress.py，临时SQLite、FastAPI TestClient、实际本地teacher tool、web_mode=off、RULE_DEMO，不出网/不使用用户密钥；混合3类输入（一般介绍、标准风险矩阵、碳钢换热器/氯化氢诊断），验SSE序号/终态唯一/DB答复一致。
- 24次并发4：24/24完成，0 API失败，p50=1851.07ms，p95=2460.10ms，max=3083.18ms；
- 100次并发4：100/100完成，0 API失败，p50=1994.87ms，p95=3233.07ms，max=6028.54ms，52.85秒批次；
- 100次并发8：73成功、27 SSE HTTP429，DB73 completed+27 queued，成功部分p50=3066.31ms，p95=4947.66ms；该现有压测脚本未在429后重试，因自己assert100/100而exit1。**这不是27个数据库记录丢失，也不是证明它们能自动完成**。backend/api.py第44行worker槽4，829-830槽满时stream返回429，已创建run仍排队；当前API需明确Retry-After及前端排队刷新/退避/自动重连，并测试至终态、不重复执行。并发8现有基准不通过。
- 历史R10离线10场景×两模式脚本当前调用run_matrix()在assert persisted completed处FAIL；需查是旧mock与P13 model_profiles接口变化还是生产行为回归，不可拿旧20/20报告作本轮当前值。
- P16-C新门禁专项本轮重跑14/14 PASS；当前TSG页冲突和人审0仍BLOCKED。
- 原版teacher validate --final 554/554 clauses、200/200 trajectories、multi_step144、exclusion/insufficient_info/out_of_domain各15 PASS；teacher tools17/17 PASS。
- 上游guardrail_cases.jsonl有36条（unknown_tool6/missing_param8/bad_format15/out_of_domain7），normal_cases.jsonl有60条；guardrail_report.md报告均符合，但本轮仅核文件与报告，未重新跑原生 guardrail runner（会写原报告）；仍需确认最近完整日志及模型真实解析/工具步骤证据。
- P16-C交付报告称全项目238项1FAIL3skip：R8B极简PDF文字fallback，未在本轮重新全量测，不能虚报全绿。

## 6. 数据质量/路由/演示分离门禁（建议硬性）
**Gate D0：源** 工作树SHA+官方JSONL版本+P15/P16冻结审签绑定，标准范围白名单，待审绝不被发布。
**Gate D1：抽取准确** 50随机+42定向复核，50至少48、42全部裁决，跨人签名+PDF原图/页码/bbox、子条款条件；历史报告upstream/05_提交区/条款抽样核对报告.md曾自述50/50=100%，但无对应受信的独立交叉真人身份签署，不能当教师最终准确率成绩。
**Gate D2：路由** 65现有对抗题全部合理+新增≥100未知盲题、纯一般/纯标准/混合安全/连续上下文；安全工程→普通的false-negative=0，普通→工程误路由显著降低，标准意图不被腐蚀字眼覆盖。成本：普通问题直接一次模型API（在关web时）。
**Gate D3：检索** 生产同一数据SHA上，lexical/BM25/hybrid+rerank公平对照，held-out专家gold Recall@k、MRR、evidence precision、相似无关负例、p50/p95，避免P16-B已知case_id驱动专用扩词导致的合成gold泄露（未见完成修复）。
**Gate D4：工况应用** 材质/介质/子型/温压适用条件三值逻辑；错误温区/分压对象/材料序列/TSG周期必须negative测试；只问风险不给装置因子不能输出L1-4/周期。工具候选不自动升级专家结论。
**Gate D5：模型** 100组真实配置、真实API原生工具函数解析（区分fallback），≥95；至少5轮连续真实调用，100调用轨迹完整100%，异常和非异常guardrail100%；Token/成本/时间与mock分开。
**Gate D6：负载** 并发1/4/8，每档至少100混合run，SSE429重试，最终100%完成或明确拒绝并有可恢复状态，P50/P95、SQLite事件序号、唯一终态、回放一致；一般聊天与工程分别计模型调用次数。
**Gate D7：UI和公开演示** ModelScope可公开访问并符合身份/租户安全，老师要求四场景可复演和截图。当前api.py生产模式auth_required 503，不能绕过认证直接公开部署。

## 7. 最短执行方案（不动上游，分离文件所有权）
1. **P0 Route + Backpressure**：仅自有backend/orchestration/frontend相关所有者实现general快速路由，不调用graph.run，仍有SQLite/SSE一致性；混合问题最高风险优先；补 65+≥100 blind路由，修429重试/队列待运行。测试现有R10矩阵失配及R8B PDF预览。不可触碰upstream。
2. **P0 Data/source gate**：围绕原Excel A-W列，优先A已有42变更和TSG错页、B211表格和高风险DM 5.6/5.23/6.7，由真人核实与独立签名；禁止凭空填K及M–R。修字段级适用谓词/来源绑定，只在隔离候选链验收。
3. **P1 Gold & harness**：构造真实专业专家gold及反例、专业引证正确性与false-recall评测；原生100次DeepSeek tools parser证据+5轮连呼需Owner许可计费和模型配置，未授权不实际调用。
4. **P2 产品**：有安全认证后公开部署ModelScope，Gradio官方交付/React展示职责分离，前端执行记录真实但不显示模型私有思维链。

## 8. 硬结论
不能用“成功转换”“554/554”“17/17”“历史50/50”宣称工业专业准确率。先降低路由漏判及不适用机理候选，再验证经过人审的真实来源引用，最后独立跑真实100组与公开部署。当前版本适合作为本地可演示研究原型，不应称已满足老师最终所有技术指标。
