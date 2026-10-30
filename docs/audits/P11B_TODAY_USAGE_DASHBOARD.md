# P11-B 今日活动与 Token 使用统计

状态：**READY_FOR_OWNER_REVIEW**（独立模块已实现；尚未并入主 FastAPI/UI，未部署、未提交）。

## 交付边界

本窗口仅新增/修改：

- `backend/usage_stats.py` — SQLite 只读聚合、时间窗和独立 `APIRouter` 工厂。
- `frontend/src/dashboard/` — typed Dashboard、独立 fetcher、图表、状态 UI、Vitest 测试。
- `tests/test_p11_usage_stats.py` — 临时 SQLite/API 专项验证。
- 本审计记录。

未修改 `backend/api.py`、`backend/store.py`、`backend/deepseek.py`、`frontend/src/App.tsx`、`frontend/src/api.ts`、全局样式、教师上游或实际用户数据库。

## 数据口径

- 统计来源只用当前业务 SQLite：conversation、message、run、agent_events、tool_calls；没有从 localStorage、聊天字数或模型名推算统计。
- API：`GET /api/stats?period=today|7d|30d&tz_offset=<minutes>`；`tz_offset` 是**东于 UTC 的分钟数**（JS 端传 `-new Date().getTimezoneOffset()`）。范围返回 UTC ISO 格式 `[start, end)`。today 是给定 offset 下的本地自然日；7d/30d 是含今天的连续 7/30 个本地日，使用请求时给定的固定 offset。
- 对话数定义为所选期间内至少有一个 run 的不同 conversation 数；发送消息数按 `role='user'`，总消息另列 `messages_total`；运行数按 `runs.started_at`。归档 conversation 仍计入使用历史。
- 模型请求按真实持久化 `llm_started` 事件数；工具调用按真实 SQLite `tool_calls` 行数；状态依据 run 的最终状态以及 `run_completed` 的业务状态分类；任务类别从真实 route 阶段事件读取；时延由 run 起止时间差计算，包含已结束成功/失败 run。
- Token 字段只聚合 `llm_completed.payload.usage.{prompt_tokens,completion_tokens,total_tokens}` 中真实整数。无 usage 时字段为 `null`、availability=`not_recorded`，前端显示“未记录”；不通过字数估算，不展示虚构费用。
- 目前模型适配事件不承诺保存 provider usage，因此现有数据很可能为“未记录”。未来只需在 owner 的 model adapter 真实拿到 provider `usage` 时把其原值加入 `llm_completed` 事件；此窗口没有触碰适配器。
- 两张简约 SVG donut：任务类别、运行状态；今日小时柱状图只在 today 展示。空结果进入明确空态，不渲染装饰性假数据。loading/error/data/empty 四态已有测试。

## A 集成接线

### FastAPI：在 `backend/api.py` 中导入一行，并在 `app = FastAPI(...)` 创建后 include 一行

```python
from backend.usage_stats import create_usage_router
# after app = FastAPI(...); `store = Store(...)` is already initialized above
app.include_router(create_usage_router(lambda: store))
```

路由工厂接收现有 `Store`，不另建数据库，不改变现有API模块或Store初始化。两行在两个适当插入点；交接时由A在允许范围内实施主 app include。

### 前端：在 App 的统计页/面板入口挂载

```tsx
import { UsageDashboard } from "./dashboard";
<UsageDashboard />
```

组件默认请求本地 `/api/stats`。如果 A 需要受控时间范围，也可传 `period`、`onPeriodChange` 与符合 `UsageStatsFetcher` 的 `fetchStats`。Props 与数据合同位于 `frontend/src/dashboard/UsageDashboard.tsx`、`frontend/src/dashboard/types.ts`。

## 验收

- `tests/test_p11_usage_stats.py`：临时 SQLite 构造2个会话（一个已归档）、3个run（含1个失败）、2次真实工具调用、模型请求和路由事件；验证本地时区今天/近7天、昨日到今日边界、归档保留、状态分布、空Token和真实Token精确求和、无效参数、独立API。
- 前端 `UsageDashboard.test.tsx`：loading/error/empty/data、时间范围切换、token未记录文案和usage精确值。
- 本轮完成专测后仍需 A 完成与主服务的集成浏览器验收；独立组件未声称已在正式聊天 UI 中运行。

### 2026-10-28 本轮实测结果

- `\.venv-langgraph\Scripts\python.exe -B -m unittest discover -s tests -v`：**145 tests OK，3 项可选 Phoenix 专测 skip**。
- `npm test -- --run src/dashboard/UsageDashboard.test.tsx`：**5/5 PASS**。
- `npm run typecheck`：PASS；`npm run build`：PASS（输出一个超过 500 kB 的 Vite chunk warning）。
- 完整 `npm test -- --run` 汇总为 **94 passed / 9 failed（4个文件）**；失败分布在不属于 B 写入边界的 `src/trace-events/model.test.ts`（duration断言）、`src/components/trace/ActivityTrace.test.tsx`、`src/AssistantMessages.final.test.tsx`（R9-B trace文案/测试契约）和 `src/voice/SpeechInputButton.test.tsx`（浏览器语音错误映射）。本轮没有更改这些模块；需要由 trace/voice 对应窗口或 A 统一处理。

可复现命令：

```powershell
.\.venv-langgraph\Scripts\python.exe -B -m unittest tests.test_p11_usage_stats -v
cd frontend
npm test -- --run src/dashboard/UsageDashboard.test.tsx
npm run typecheck
```

## 未完成 / 下一步

1. A 将 router include 到主 FastAPI；接线后用主 app 的同一 SQLite URL 实测 `GET /api/stats`。
2. A 将 dashboard 挂到统计入口并做桌面/移动/深色浏览器验收；本组件阶段不改 `App.tsx`，所以没有捏造整页截图或浏览器联调结论。
3. 如果将来要出现真实 Token 数，模型 owner 应在已有 `llm_completed` 中附带 provider 返回的精确 `usage`；当前缺少 usage 时的正确 UI 是“未记录”。
4. 固定offset法按调用时当前设备 UTC offset 计算本地日，跨DST切换的历史日窗口若要严格按IANA时区校正，可在后续合同明确后再扩展。

## 方案权衡

不加 Recharts，使用 SVG `strokeDasharray` 环图和 CSS 柱状图：当前只有2种分布+24小时时序，避免安装新依赖和改锁文件；图表由 SQLite 实际计数驱动，空数据时不画。SQL 在服务端聚合，只返回摘要，不把消息/事件表全量传到浏览器。
