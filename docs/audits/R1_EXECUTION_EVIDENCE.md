# R1 实际执行证据与独立审查入口

执行日期：2026-10-27（本地 Asia/Shanghai）。工作目录：`D:\作业\竞赛\计算机设计智能体\机械智能体`。R1 仅触及本产品目录内自有源码/文档与 `upstream/` 的稀疏工作树物化；无标准/教师代码内容编辑、无父项目 Git 索引写入、无公网部署/API 外发。

模型/执行器：本轮沿当前单写者会话直接执行，避免另起CLI争抢工作区；当前可用的 local Codex executor schema 只有 `luna_high`，没有 `luna_high_fast` profile，未虚报 Fast 配置或模型身份。

## P0｜同步全部 upstream HEAD 追踪文件

1. 检查：`git -C upstream status --porcelain` 初始为空；`git -C upstream rev-parse HEAD` = `d7877bf387482b2fa9b148d30860da59ccad48b3`；`git -C upstream remote -v` = `origin https://github.com/Futian02/Haeness2-TaskPackage-v0.3.git`。D: 可用约 138.5 GB；初始 `core.sparseCheckout=true`、追踪清单2535条。
2. 首次执行 `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\SYNC_ALL_UPSTREAM.ps1` 遇到异步Git partial-clone批量取blob；短期看到 `.git/index.lock` 与 `sparse-checkout disable` 锁错误、shell调用未正常返回。没有删除lock、reset或clean；等待 Git 的 blob fetch/checkout 结束后重试。
3. 同一脚本重试真实结果：`FULL_TRACKED_HEAD_SYNC=PASS`，`TRACKED_FILES=2535`，HEAD未变化，`DIRTY_ITEMS=0`，19/19关键官方源文件 PRESENT。
4. 独立对数：`git -C upstream ls-files | Measure-Object -Line` = 2535；`git -C upstream ls-tree -r --name-only HEAD | Measure-Object -Line` = 2535；`git -C upstream config --bool core.sparseCheckout` = false；`git -C upstream status --short --branch` = `master...origin/master`，干净。
5. `python -B -m scripts.build_upstream_manifest`：tracked=2535 / inventoried=2535；17个PDF、3个XLS/XLSX（其内包括参考代码样本；业务官方PDF共12份，官方xlsx 3份）；清单 `docs/audits/upstream_head_manifest.jsonl`，SHA-256 `85cda2745c343bbc2661c8337fa11f23c1f89c7383b4b7405e1c421bae95e3a2`。每条路径记录字节数、SHA-256、归属分类、upstream HEAD origin、editable=false。PDF/XLSX逐文件哈希在清单内。
6. `python -B -m scripts.check_sources` = 19 PRESENT / 0 MISSING。

## 教师合同核对

检查 `upstream/README.md`、`04_接口文档/工具接口规范.md`、`技术指标验证方法.md`、`任务包问题答复.docx`。文档与运行注册表合同均为三个工具：`damage_mechanism_query`、`rbi_lookup`、`standard_clause_search`；统一外壳 `status/in_domain/result/source/message`，`status=ok` 必须 source 非空，机制内容仍八段式。规则 Harness 实际 `reg.names()` 集合由已有集成测试固定为这三个名称。

命令：`git -C upstream diff --exit-code HEAD -- README.md 04_接口文档/工具接口规范.md 04_接口文档/技术指标验证方法.md 04_接口文档/enums.json 04_接口文档/risk_level_mapping.xlsx 05_提交区` → exit 0；`git -C upstream status --porcelain` → 空。官方终验 `python -B upstream\04_接口文档\validate.py --final` = 554/554条款、200/200轨迹、144多步、exclusion/insufficient_info/out_of_domain各15，100%结构校验，PASS。

## 产品垂直切片实现

- 新建 `orchestration/` 小型可插拔状态图：Supervisor、Evidence、Diagnosis、条件式 RBI Specialist、Evidence Auditor、Reporter 六节点。REASON: 已有 Teacher Harness 是 source of truth；轻量图比立即引入复杂 runtime 更利于说明 state/edge，且本轮 API key/LLM 未提供。节点是可运行的 RULE_DEMO 逻辑，不伪称多LLM实验结果。
- 新建 `backend/store.py` sqlite3/WAL仓库：conversations、messages、runs、agent_events、tool_calls、evidence_refs、knowledge_documents。事件 run 内 sequence 唯一递增；SSE首跑持久写事件，再次请求按事件 replay；不重复执行图。
- 新建 `backend/api.py` FastAPI REST/SSE；`web/index.html` 三栏聊天网站（history/chat/trace+evidence drawer）。只监听 localhost，不公开部署。
- 新建 `orchestration/semantics.py` 四种严格Pydantic模型、三值现场观测、同义词与单位归一化；生成10条源条款支持候选草稿与10条自然语言样例，全部 needs_review/non-gold。

## 命令、测试及失败/修正记录

| 命令/动作 | 实测结果 | 失败说明/处置 |
|---|---|---|
| `python -B -m scripts.check_sources` | 19/19 PRESENT | 稀疏检出消除 |
| `python -B -m scripts.build_semantic_drafts` | 10 cards + 10 cases；源 SHA `a8151797ba15a6a7452dd83aaec9fab4c0a815724ca45062eb1e2bac7b4d49ef` | 无 |
| 首轮 `python -B -m unittest discover -s tests -v` | 26项过，7项Store用例失败 | 初版Store将显式 pathlib DB path误识别为非SQLite URL；后续修复path逻辑。Windows临时DB cleanup又暴露连接上下文仅提交未关闭；实现 `Store.session()` finally close，测试全面通过。 |
| `python -B -m unittest discover -s tests -v` 首轮Store修正后 | 33项 PASS | 之后新增 schemas/cases/RBI节点覆盖时，第一次 38 项跑出2个失败+1个错误：RBI节点漏加入默认图，导致Graph KeyError与API assistant message缺失；测试因此正确暴露接线遗漏。补入默认节点并重跑。 |
| 后续增强回归 `python -B -m unittest discover -s tests -v` | 38项起初2失败+1错误，随后加测 | 新增RBI工具调用条件与节点插入测试时又发现 `bool` 在 Pydantic `float | str` 联合类型被转为0.0，可能把 observed_false 变成数值；将布尔放入显式联合类型优先位置，并加 `assertIs(False)` 回归。
| route覆盖回归 `python -B -m unittest discover -s tests -v` | 43项初跑1项失败 | 新增标准/OOD/缺上下文三路由后，显式pH观测被Supervisor误归到OOD；修正为观测字段与任务词共同路由。
| 最终 `python -B -m unittest discover -s tests -v` | 43项 PASS（原有13 + 新增30：semantic/schema 12、store/graph 15、API 3） | RBI条件调用、节点扩展、缺上下文/OOD/条款查询路由、false/unknown类型边界均全绿。 |
| `python -B upstream\04_接口文档\validate.py --final` | PASS | 老师工具/数据没有被更改 |
| `TestClient`: GET `/`, `/api/health`; POST conversation/run; GET SSE/replay | 主页200、health 200；事件按序持久化/重放；消息 user+assistant | 无 |
| `python -m uvicorn backend.api:app --host 127.0.0.1 --port 8000 --log-level warning` + Python urllib smoke | health 200；live run stream 33帧；6个Agent均有started事件；replay 33条；sequence严格递增；尾事件`run_completed` | 服务停止后端口释放；全程只监听127.0.0.1 |
| `python -B -m py_compile ...` | 源码编译检查通过 | 本命令会创建`__pycache__`，在产品忽略规则内；正式提交前不纳入Git |
| Playwright浏览器插件打开 `http://127.0.0.1:8000/` | 工具调用挂起，主动停止；未取得截图/浏览器console证据 | 以 FastAPI `TestClient` + live HTTP 200作替代验收，浏览器视觉验收未验证 |

## 修改清单（仅外层自有目录）

新增：`backend/{__init__.py,api.py,store.py}`、`orchestration/{__init__.py,graph.py,semantics.py}`、`web/index.html`、`tests/test_api_vertical_slice.py`、`tests/test_engineering_semantics.py`、`tests/test_store_and_graph.py`、`scripts/{build_semantic_drafts.py,build_upstream_manifest.py,export_semantics_schema.py}`、`knowledge/semantic_drafts.jsonl`、`evals/semantic_cases.json`、`docs/audits/{R1_MULTIAGENT_ARCHITECTURE.md,R1_UI_EVENT_PROTOCOL.md,R1_ENGINEERING_SEMANTICS.md,R1_ENGINEERING_SEMANTICS_SCHEMA.json,R1_EXECUTION_EVIDENCE.md,upstream_head_manifest.jsonl}`。修改：`requirements.txt`、`.env.example`、`.gitignore`、`README.md`、`docs/PROJECT_STATE.md`。

执行环境的顶层Git仓库是父级作业目录，初始已有大量 unrelated dirty/untracked 项（含其他竞赛/论文/下载中素材）。遵守 `AGENTS.md`，**未执行 `git add`、commit、reset、clean、分支操作**。本报告的修改清单就是待审查的路径范围；不可将父仓状态误读为本轮所有文件变更。

## 未完成/Blocked

1. 没有真实模型凭据，不运行真实 single-agent/multi-LLM 对比、不测 token/cost/LLM latency；RULE_DEMO不等于真实 agent quality。
2. MySQL driver/server与可移植 SQLAlchemy adapter没实现。SQLite database URL 可配置并已实测；非 SQLite URL fail-fast，明确不冒充MySQL可用。
3. 视觉 Playwright验收未完成（connector挂起）；未启动 Gradio验收、未部署域名/公网。
4. PDF人工逐页对照、印刷页/PDF页映射、E2/E3审核未执行；semantic drafts不构成法规机理金标，暂不参与风险定级。
5. 若要求把产品代码纳入自有独立Git提交，需要先建立/确认独立仓库边界。当前父级工作树处于保护状态，本轮只交本地证据，不操作父仓索引。
