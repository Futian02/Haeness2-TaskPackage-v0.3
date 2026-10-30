# 2026-10-28 Owner 严格验收与收工条件｜R8A/R8B/R9A/R9B

**阶段裁决**：R8B聊天UI本地功能 = PASS；R9A循环并行图 = PASS_AS_ISOLATED_CANDIDATE，正式入口未接；R9B可折叠追踪+Phoenix = PASS_AS_STANDALONE，正式入口未接；R8A Excel = 13行草稿已写原表，但全PDF内容真实性和签名未完成。项目**尚未集成完成**，不需要开启新架构项目。
要求：效率优先、只保留必要可靠性，别堆安全/哈希/中间件；老师三工具固定合同和原始PDF有来源要求，保留必要的引用证据，但不要为了哈希本身增加任何产品功能。

## 1. Owner 本轮独立复测
- `./.venv-langgraph/Scripts/python.exe -B -m unittest tests.test_r9a_industrial_candidate -q`：16/16 PASS；
- `./.venv-langgraph/Scripts/python.exe -B -m unittest tests.test_r8b_upload -q`：7/7 PASS；
- `node ./node_modules/vitest/vitest.mjs run --reporter=dot`（cwd=frontend）：72/72 PASS；
- `node ./node_modules/typescript/bin/tsc -b --pretty false`：PASS；
- `node ./node_modules/vite/bin/vite.js build`：PASS，主包574.76kB/gzip175.18kB，超过500kB Vite提示（非运行失败），可以后期懒加载不阻断演示；
- `./observability/.venv/Scripts/python.exe -B -m unittest tests.test_r9b_observability -q`：6/6 PASS；
- 同样R9B测试在项目主`.venv-langgraph`中因未安装`opentelemetry.sdk`/`openinference`出现导入ERROR；这是**可选追踪依赖隔离**，但主全量unittest discover当前不全绿。
- `tests.test_p6a_parallel_evidence`仍有一条旧断言期望同键E1+E0得到E1，实际P7新正确保守合并为E0：7项中6 PASS/1 FAIL；应只修改该旧断言和增加冲突记录断言，不改业务算法。
- `upstream/04_接口文档/validate.py --final` 554/554条、200/200轨迹PASS；教师工具selftest 17/17。
- 仅因可选观测测试依赖未装主环境与一条旧断言，当前**不能写“主Python全量PASS”**。可在主环境跳过`test_r9b_observability.py`后复测业务全部，同时R9B在其隔离env独立6/6。
- 原Excel `upstream/01_RBI标准/条款摘录表_RBI.xlsx` SHA`e43f7b0d3381a38fa648c2505e27d1c87893af5aea89aa119097dbfc49c6b7bf`：报告证明正式源表RBI472→485行，新增474:486共13条，U/V真人签名空、均DRAFT；非摘录表3sheet不变。官方`clauses.jsonl`仍RBI472+DM82=554。R8A只完成461页OCR索引，449页needs_visual_review、12页needs_human_review；20项数值/表格未视觉确认。不能宣传“6份PDF全部核完”。
- R8B Edge真实3会话×3轮（9runs，16SSE/run，刷新/会话跳转/上传TXT+PDF/SQLite文件关联成功），Owner实际查看1280桌面和390移动截图；清爽简洁、左会话栏和右侧可收起审查已具备，不需要再重建UI。
- R9B独立演示页真实SQLite61个事件可折叠/刷新恢复、Phoenix本机一个trace6 spans+2真实教师工具调用；Owner实际查看截图：追踪技术页内容偏密，应该挂到主聊天的单个折叠区，而非使用整页技术台。它没有写入主Chat的`App.tsx/AssistantMessages.tsx`；Phoenix未接正式Graph。
- R9A候选图16测试含真实fanout/fanin、工具预算与循环；但`backend/api.py`与`orchestration/graph.py`均没有引用`r9_industrial_candidate`；默认还是原437行7角色顺序RULE_DEMO。新候选445行+独立parallel模块213行，**逻辑流程简单了，但代码仓复杂了**。测试只有3例one-shot延迟，5~16ms是候选内部规则微基准、不能当完整请求耗时。
- R9A逻辑应更好地决定`wall_thinning`何时必须：目前所有`diagnosis`一律要求`context.evidence.wall_thinning`，对于一般机理假设过严；应按问题类型判断“提出候选”与“确认壁厚减薄/RBI结果”，而非硬性阻断所有设备问题。
- `standard_clause_search`只核本轮CID的来源，不代表条款与用户标准名称/问题语义相关；为纯标准查询加最小标准代码过滤与相关性拒答，不增加第四工具。
- 现在文件夹顶层有`app,web,frontend,backend,orchestration,observability,knowledge,evals,scripts,tests,docs,upstream,data`共13个主要目录；docs根下66份直接文件，累计多版方案会干扰学习。父Git根在更高层，**不要盲目git reset/clean和移动upstream**。

## 2. 现实中的收工定义，分两种
### A. 本地演示版 DOABLE (建议下一次统一集成后收工)
- [ ] **唯一正式Graph**：新短路径工作流接到FastAPI，用三工具；至少演示(标准无工况)/(设备诊断有证据)/缺测量拒判/复查冲突/有界重试。去掉七角色重复调用，保留确实有用的两个并行审查分支。不同机理不要硬要求wall_thinning；不输出无依据的装置风险等级。
- [ ] **同一个聊天前端**：左历史+轮次跳转+上传附件与服务端事实快照+助手消息的`ActivityTrace`折叠展开，刷新后SQLite replay一致；无需另行进入独立demo页面。
- [ ] **一条启动命令**：Node构建前端/后端直接提供静态资源，默认无Phoenix亦可用；真实1次端到端包含完整工况、Tool、审查、Trace、文件选择与结果。SQLite数据和Checkpoint留存在data。
- [ ] **一次清爽回归**：修复旧P6A断言/可选observability测试路径，主Python非Phoenix所有业务测试通过，Phoenix单独env6/6，前端72+构建/类型通过，教师554/200不变。
- [ ] **文档收口**：根README改为最新简明的“怎么运行、怎么用、Graph三阶段、数据在哪里、限制”；保留`docs/ARCHITECTURE.md`和`docs/PROJECT_STATUS_CURRENT.md`为两个主要入口，过期版本/脚本/证据移动到`docs/archive/`（先建立索引/逐链接查验，不删除）。
达到上述本地演示功能可停止继续UI/Graph开发，不强制Phoenix生产化、Langfuse、MySQL、账户系统、微服务或额外SHA工程。

### B. 教师/正式专业指标（单独验收，不能因为本地Demo完成就声称通过）
- Excel13条新增草稿仍缺真人U/V+ PDF抽核；所有六份PDF准确率不能靠OCR推断，至少50条随机人工交叉、数值表格关键抽样必做；官方转换数据仍554，未把草稿合法加入。
- 真实LLM API尚未给出服务端/模型/密钥，主图仍RULE_DEMO，不等于真实多模型。User提供API后10题真实原生调用→100题老师工具解析指标（fallback不计）；至少5轮真实连续工具调用、100次轨迹完整率；教师指定的ModelScope/Gradio公开Demo及四类场景证据仍未完成。
这些受真人签核/外部API/学校交付要求约束，**不应该继续做泛化工程来代替**。

## 3. 推荐最简单目录原则（只做无损归档，不搞大搬家）
```
机械智能体/
  frontend/        # 唯一聊天UI：React/assistant-ui，ActivityTrace合入消息
  backend/         # FastAPI、SQLite、附件
  orchestration/   # 唯一生产图 + 工具/审核适配（隔离候选归档）
  upstream/        # 教师数据、三个工具及验收脚本，绝对不重构
  data/            # SQLite、uploads，保持.gitignore
  tests/           # 当前正在执行的核心回归
  docs/            # README + ARCHITECTURE + PROJECT_STATUS_CURRENT为阅读入口
  observability/   # 可选Phoenix开发工具，默认不启动
  archive/         # 旧web UI/不再用的演示、探索性代码与过期报告（移动前确认导入/引用）
  app/             # 若Gradio教师交付入口仍用则保留；不要为了目录好看拆教师脚本
  scripts/,evals/  # 开发期可保留，不必大搬家；将不再用的文件下沉各自archive/
```
**结构精简目标是使用户只需了解 frontend/backend/orchestration/upstream/data 五个目录**，不是把所有历史测试和源码一夜之间物理重排。不要删除元数据或复核用PDF/XLSX，也不把备份搬到公网。

## 4. 明确不做
- 不安装Langfuse；Phoenix只作本地可选观测，暂不在所有生产Graph节点埋10层span。
- 不新增MySQL/PostgreSQL、消息队列、K8s、多租户服务、独立向量数据库；SQLite+checkpoint满足本地Demo。
- 不追求每个上传格式都能模型理解（现在txt/pdf基础预览+多种格式安全保存），也不对所有23列为了填满而虚构等级。
- 不继续开每轮P10/P11无限版本；最终只做一次精简集成+用户验收。

## 5. 接下来若授权Codex做最终集成，单一窗口任务
- 全面只读对比旧图与R9A，然后将**原短图行为移到唯一正式运行路径**，使真实API调用它；EventSink持久化仍由P5A store/API保证，保证SSE每条`run_id/sequence`。
- 把R9B`ActivityTrace`直接挂到R8B最新`AssistantMessages`的assistant消息位置，复用现有run events、历史恢复；保留本机Phoenix独立CLI可选，不能以Trace导出失败阻断聊天。
- 修旧P6A期望、处理optional测试env，不改业务E0冲突安全规则；统一README/STATUS，过期材料先列inventory，Owner审阅后才允许归档。
- 禁止改原PDF、XLSX、教师三工具、官方JSONL或删除任何用户文件。完整验收真实Edge+SQLite/SSE/文件和单命令可启；交付一次合并验收，不再产生十几个相同主题报告。
