# DeepSeek 本地配置与垂直切片验收（2026-10-28）

状态：`LOCAL_CONFIGURED_AND_LIVE_SMOKE_PASS`；网站仍只绑定 `127.0.0.1:8000`，未公网部署。

## 配置与边界

- 通过项目忽略的根目录 `.env.local` 设置 `DEEPSEEK_API_KEY`、`DEEPSEEK_BASE_URL=https://api.deepseek.com`、`DEEPSEEK_MODEL=deepseek-flash`、`DEEPSEEK_TIMEOUT_SECONDS=45`。已核验 `git check-ignore .env.local` 命中；实际凭据不进入本报告、API 响应、事件或代码 diff。
- `backend/deepseek.py` 通过 OpenAI-compatible Chat Completions endpoint 发出限长单次请求，验证 HTTPS 配置、设置超时、限制响应体，并对外隐藏上游错误正文。
- `DEEPSEEK` 只用于确定性 LangGraph 完成后的表达整理。请求包含用户本轮问题与严格截断的结论状态、候选、未知项、条款标识/页码和工况字段。不会发送附件、原始标准摘录、全量数据库、SQLite 文件、API key 或隐藏思维链。
- DeepSeek 文本明确标记为“表达整理（非独立研判）”；助手答复继续包含本地确定性结论、E0/E1 状态与来源摘要。HTTP 失败或空响应会让 run 失败并产生错误事件，不伪装为模型成功或静默回退。
- 健康端点只返回 `configured/provider/model/default_mode` 元数据，不返回凭据。无凭据环境的默认仍是 `RULE_DEMO`。三个教师工具、统一五键返回协议及 `upstream/` 均未改。

## 实际执行与结果

| 命令/动作 | 结果 |
|---|---|
| `git check-ignore .env.local` | 命中 ignore；密钥配置留在本机未跟踪文件 |
| DeepSeek Chat Completions 最小连通请求（`deepseek-flash`，不含项目文件/附件） | HTTP 200，完成状态 `stop`，测试答复 `API_OK` |
| `\.venv-langgraph\Scripts\python.exe -B -m unittest discover -s tests -q` | 136 tests，OK，3 skips（可选 Phoenix/OpenInference 专项） |
| `npm test --prefix frontend -- --run` | 9 files / 74 tests PASS |
| `npm run typecheck --prefix frontend` | PASS |
| `npm run build --prefix frontend` | PASS；Vite 提示 index chunk >500 kB，为既存体积提示，构建退出 0 |
| live HTTP：`GET /api/health` | `status=ok`、`mode=DEEPSEEK`、provider/model 可见；无 API key 字段；老师工具计数 3 |
| live HTTP：创建会话 → `DEEPSEEK` run → SSE → DB 对话读取 → events replay | run=`completed`，消息持久化 2 条，SSE/replay 4 事件，含 `llm_completed`，序号有序；事件/消息/health 公共负载中无密钥 |
| `GET http://127.0.0.1:8000/` | 当前服务运行并托管已构建 React 聊天网站 |

Live smoke 的无敏感字段汇总：

```json
{"mode":"DEEPSEEK","provider":"DeepSeek","model":"deepseek-flash","run_status":"completed","messages_persisted":2,"sse_and_replay_events":4,"llm_completed":true,"secret_absent_from_public_payloads":true,"teacher_tool_count":3}
```

## Diff 范围

- 新增：`backend/deepseek.py`、`tests/test_deepseek_adapter.py`、本审计文件。
- 修改：`backend/api.py`、`frontend/src/api.ts`、`frontend/src/App.tsx`、`frontend/src/EngineeringReport.tsx`、`.env.example`、`README.md`、`docs/PROJECT_STATUS_CURRENT.md`。
- 本地忽略配置：`.env.local`（不应加入版本控制）。
- 只读确认范围：未编辑 `upstream/`、教师工具、正式 JSONL、原始 Excel 或 PDF。
- 结束时 `git -C upstream status --short --branch` 显示 RBI 原表 modified、13 条工作副本及一份备份为 untracked；这些状态在当前 DeepSeek 配置任务之前的项目验收状态中已记录。本任务没有触碰或清理它们；变更归属仍按既有 Owner 审计事项处理。

## 失败/修正记录

1. 第一次 unittest 命令误用了 `..\\.venv-langgraph`，PowerShell 找不到解释器；修正为项目根 `.\\.venv-langgraph\\Scripts\\python.exe` 后完整测试通过。
2. 首次 TypeScript 检查发现新 UI 行的附件选择回调误引用未定义 `id`；改为正确的 `f.id` 后 typecheck、build 均通过。
3. Vite 构建仍提示主 chunk 575.43 kB 超过 500 kB 阈值，但构建成功；本轮不为此引入拆包架构。
4. 3 个可选 observability 测试依赖当前隔离环境未安装的 Phoenix/OpenInference SDK，标准 unittest 以 skip 计，不记作通过；R9 原独立环境专项结果仍见最终集成审计。

## 解释边界与后续

- 这证明真实模型 API 的一次最小调用以及本地网站到 DeepSeek 的一条真实端到端链路；不证明回答准确率、标准语义支持或现场适用性，不等于多模型交叉审查，也不是 10/100 题评测。
- 所有实际运行模式继续保留 `RULE_DEMO` 选项（API 请求中可显式指定）；DeepSeek 请求中不包含已上传附件。线上部署仍需独立身份/租户/认证安全设计。
- 用户提供的密钥曾出现在对话内容中，建议在服务商控制台轮换；新密钥只覆盖本地 `.env.local`，不写进 Git 或审计文本。
