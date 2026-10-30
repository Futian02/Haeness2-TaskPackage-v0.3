# P11-A 设置中心 / 应用壳验收

**状态：`READY_FOR_OWNER_REVIEW`** · 2026-10-28

## 交付

- 设置面板：常规、模型、性格、会话与归档、外观、语音、关于；桌面侧栏导航和窄屏横向/网格导航，正文 14px+。
- 常规偏好按 `aetheris-preferences-v1` 写入本地存储：90/100/110% 字体、舒适/紧凑、事件时间线默认展开；不写密钥或隐私。
- 主题兼容旧 `aether-theme`，新增跟随系统并保持浅/深/系统选择。无会话数据迁移或清理。
- 模型页显示 `/api/health` 返回的实际模式、服务商、模型名和 `configured` 布尔值；不请求/渲染密钥。服务测试只探测本地 health 接口，不调用模型、不产生推理费用。未提供模型列表/切换接口，页面不虚构模型切换。
- 性格 4 档和 500 字自定义指令标注为本地偏好、服务端未接入；不覆盖工程审查提示词与证据门禁。
- 归档读取采用 `GET /api/conversations?include_archived=true`，恢复采用现有 PATCH `archived:false`；活动列表和归档列表即时更新，不做物理删除。
- 侧栏可折叠/恢复并持久化；手机仍使用原历史抽屉。顶部统计入口已接入 B 的 `UsageDashboard`，使用既有 `/api/stats` 接口和组件内加载/空态/错误状态。执行审查栏保持独立。
- C 的 `SpeechInputButton` 已接入输入工具栏，转写回填草稿，不自动发送；保留权限/不支持状态、主动启用和浏览器服务隐私提示。执行记录继续由现有 `AssistantMessages` 通过 typed `runId/events/processSummary` props 渲染 C 的 `ActivityTrace`，App 将实际事件传入。
- 品牌应用为“澄衡 Aetheris”，复用现存本地图标；浏览器标题同步为“澄衡 Aetheris · 智能工程助手”。

## 验证记录

| 检查 | 结果 |
|---|---|
| `npm run build`（TypeScript + Vite） | 通过；Vite 提示主 bundle 约 604 kB，未新增依赖 |
| `npm test -- --reporter=dot` | 16 个测试文件；108 项通过、1 项失败（现有 C `ActivityTrace` 测试断言问题，见下） |
| P11-A 定向偏好 / 侧栏 / 归档 API / 模型无密钥 / B-C 接线测试 | 3 个新测试文件、11 项通过 |
| Chromium 桌面真浏览器 | 1280×900；设置导航 7 项；页面错误 0 |
| Chromium 手机视口 | 390×844；设置导航 7 项均可见；页面错误 0 |
| 文件边界 | 未改 `frontend/src/styles.css`、`frontend/index.html`、`backend/api.py`、`backend/deepseek.py`、Graph、老师数据或模型密钥；未部署、未提交 |

## 截图

- 桌面：`docs/audits/P11A_settings_desktop.png`
- 手机：`docs/audits/P11A_settings_mobile.png`
- B 统计面板：`docs/audits/P11A_dashboard_desktop.png`
- 手机应用壳（含语音草稿控件）：`docs/audits/P11A_mobile_shell.png`

截图在 Chromium 中对 Vite 页面实拍。为避免触碰本地会话库，截图期间只对 `/api/health` 和会话列表使用确定性只读 fixture；交互组件、样式和布局均来自实际前端构建。

## 集成说明 / 阻塞项

- 统计与语音/执行记录组件已按现有 typed props 接入；语音设置页本身说明权限与状态由输入栏控件驱动，不复制造假状态。
- 实际 FastAPI 本地启动探测失败：当前 Python 环境中的 `tenacity` 导入引用已不存在的 `asyncio.coroutine`，异常发生在应用导入 LangGraph 时。故本轮未对真实 SQLite 归档记录做读写验收；归档 API 契约通过前端请求测试验证，后端既有路由实现已检查，截图和 UI 测试没有写本地数据或触发模型请求。
- 全量 Vitest 唯一失败：`frontend/src/components/trace/ActivityTrace.test.tsx` 的 “supports explicit light and dark themes” 用 `getByLabelText("本轮执行过程")` 查询唯一元素；ActivityTrace 同时给外层 section 与内层 details 设置相同 aria-label，导致查询多匹配。该文件属于 C 模块边界，本窗口未改动；P11-A 自身 11 项接线/偏好测试全部通过。
- `frontend/index.html` 已含澄衡标题但依任务文件边界未编辑该文件；应用运行时从 App 同步 document title。

**结论：P11-A 范围交付完成，统计、语音及既有 ActivityTrace 均已接入，停在 `READY_FOR_OWNER_REVIEW`。**
