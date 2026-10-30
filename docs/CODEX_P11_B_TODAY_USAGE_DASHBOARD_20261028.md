# Codex 窗口 B｜今日会话与模型用量真实统计（独立工作线）
项目根目录：`D:\作业\竞赛\计算机设计智能体\机械智能体`。先读`AGENTS.md`、`docs/P11_AETHERIS_PRODUCT_POLISH_DESIGN_20261028.md`、`backend/store.py`、`backend/api.py`、`frontend/src/api.ts`、`frontend/package.json`。
**允许写**`backend/usage_stats.py`、`frontend/src/dashboard/**`、`tests/test_p11_usage_*.py`、`docs/audits/P11B_*.md`；可创建`backend/usage_router.py`封装独立APIRouter；**不得写**`backend/api.py`、`backend/deepseek.py`、`frontend/src/App.tsx`、`styles.css`、`frontend/src/api.ts`、`settings/**`、`voice/**`、`trace-events/**`、`upstream/**`。把要在FastAPI主app include_router的2行代码和Dashboard props类型写给A集成者，不越界抢文件。
目标：做一个Codex风格“今日活动”简单面板，包括今日/近7天/近30天切换、会话数、发送消息数、完成的Run、模型调用数、有效工具调用数、平均耗时、成功/待补证/失败占比，2张饼图(任务类别/运行模式或状态)，1张按小时Run柱状图（可选，只在真实数据支持时加）。先保证真实数值，图表越少越好。
1. 数据源**唯一业务SQLite**：SQL按时间/已归档标志处理，空值不崩；不从前端localStorage推断全局数据。API`GET /api/stats?period=today|7d|30d&tz_offset=...`返回明确字段、统计范围、模型usage统计是否可得。
2. 当前后端`llm_completed`可能只提供模型名和duration_ms，没有token。准确Token值只在provider API的真实usage存在时可聚合；否则显示`未记录`或`—`，不能用字符数猜作真值；模型费用没有真实单价时不要估算成真实收费。可以设计最小增量usage事件字段给后续模型owner接线，但**不能修改当前正在部署的deepseek.py**。
3. 复用成熟`recharts` MIT 包的ResponsiveContainer/PieChart/BarChart，如依赖安装不适合本轮，可用CSS进度条代替，不许把饼图造为无效装饰。避免同一分布重复两个图。数据<=1000消息时性能正常；SQL聚合和索引不要复杂化。
4. 从前端提供`UsageDashboard({period,fetchStats})`或同等typed组件，设置入口由窗口A合并；提供loading/empty/error/有数据四态。SQLite归档会话不能因此丢统计，明确规则（归档仍属于历史使用记录）。
5. 自动化测试：临时数据库创建2会话、3轮、1失败与2工具调用、不同时间、归档后的保留；统计返回一致、昨日与今日边界正确、没有usage的显示NULL而非0。
6. 完整后端旧测试、前端B专项Vitest/TypeScript都应通过；独立状态`READY_FOR_OWNER_REVIEW`，B/C各自落一份简短审计。严格不改老师3工具或所有上游。
