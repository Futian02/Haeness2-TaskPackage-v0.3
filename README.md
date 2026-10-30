# Haeness2｜机械设备风险研判本地演示

> 最新进度与验收结论以 [当前状态](docs/PROJECT_STATUS_CURRENT.md)、[教师抽样证据口径](docs/data_quality/TEACHER_SAMPLE50_EVIDENCE_STATUS_20261029.md)及[文档索引](docs/DOCS_INDEX.md)为准。历史50/50不是本轮真人审签，当前正式数据仍冻结。普通聊天直连DeepSeek、标准轻量检索、工程LangGraph三路分流及简化折叠展示为**待实现目标**，不是本版已完成的功能。

本项目是一个本地、可追溯的工程研判演示：React 聊天工作台 → FastAPI → 有界 LangGraph → 老师冻结的三个工具 → SQLite/SSE。未配置凭据时使用 **`RULE_DEMO`**；配置 DeepSeek 后使用 **`DEEPSEEK`** 表达整理模式：本地确定性图仍负责检索、来源门禁与审核，DeepSeek 只改写有界摘要，不决策风险等级。附件不发送给模型。输出仍是待复核候选，不给出未经证据支持的设备风险等级。

## 本地启动

在项目根目录执行。首次安装后端依赖只需一次：

```powershell
python -m pip install -r requirements-langgraph.lock.txt
npm ci --prefix frontend
npm run build --prefix frontend
```

可选：复制 `.env.example` 为项目根目录 `.env.local`，填写 `DEEPSEEK_API_KEY`。该文件已被 Git 忽略；密钥只在本机环境使用，不要提交或粘贴到日志。配置后 FastAPI health 会显示 `mode=DEEPSEEK`（只公开 provider/model/是否配置，不公开密钥）；没有凭据仍自动保持 RULE_DEMO。

启动 FastAPI（静态托管 `frontend/dist`，这是唯一聊天入口）：

```powershell
$env:DATABASE_URL = 'sqlite:///./data/haeness2.db' # 可选，默认值
$env:UPLOAD_ROOT = './data/uploads'              # 可选，默认值
\.venv-langgraph\Scripts\python.exe -m uvicorn backend.api:app --host 127.0.0.1 --port 8000
```

浏览器打开 <http://127.0.0.1:8000/>。创建会话后，可直接提问、填写工况、上传 TXT/PDF；每条回答的执行过程默认折叠，展开查看本轮真实工具调用、来源与审查事件。刷新页面后，会从 SQLite/SSE 恢复历史。不要通过 Vite dev server 启动第二个正式入口。

### 快速演示路径

1. **缺工况**：只问“分析设备风险”——应先要求补充材质/介质，不调用工具。
2. **纯标准检索**：提出带标准号或主题的条款问题——不要求填写材质；没有相关命中就明确报告未命中。
3. **机理调查**：填写设备、材质、介质和现场证据后提问——工具预算有界；需要时并行审查，缺测厚时将减薄确认保持待核。
4. 刷新当前会话并展开助手消息的“执行记录”，核对实际工具、来源与审查状态。

## 目录导航 / 学习顺序

先读 [`docs/LEARNING_ENTRY.md`](docs/LEARNING_ENTRY.md) 与 [`docs/PROJECT_STATUS_CURRENT.md`](docs/PROJECT_STATUS_CURRENT.md)。五个核心目录：

| 目录 | 用途 |
|---|---|
| `frontend/` | React、assistant-ui、聊天/附件/可折叠执行过程 |
| `backend/` | FastAPI、SQLite 会话/消息/事件、上传与 SSE |
| `orchestration/` | R9-A 有界 LangGraph 与工程语义提取 |
| `upstream/` | 老师原始工具、标准资料及正式数据；冻结只读 |
| `data/` | 本地数据库与上传文件，不是正式标准数据源 |

辅助目录：`tests/`、`docs/`、`observability/`。旧的 `app/`、`web/`、`knowledge/`、`evals/` 等保留供历史/实验追溯，不代表第二个正式入口；未经审核不移动或删除。

## 验收与事实边界

```powershell
npm run build --prefix frontend
\.venv-langgraph\Scripts\python.exe -B -m unittest discover -s tests -q
observability\.venv\Scripts\python.exe -B -m unittest tests.test_r9b_observability -q
python -B upstream/04_接口文档/validate.py --final
python -B upstream/05_提交区/_selftest_tools.py
```

当前状态与本轮真实验收记录见 [`docs/PROJECT_STATUS_CURRENT.md`](docs/PROJECT_STATUS_CURRENT.md) 和 [`docs/audits/FINAL_LOCAL_INTEGRATION_ACCEPTANCE.md`](docs/audits/FINAL_LOCAL_INTEGRATION_ACCEPTANCE.md)。老师工具合同、正式 JSONL 和上游文件以 `upstream/` 为准；13 条未签核摘录仍是草稿状态，不因上游现有数据验收通过而自动成为正式数据。REAL_LLM、公网部署、人工签核及 PDF 全页视觉审查不属于本地演示通过项。
