# 当前本地集成架构

> **状态标记（2026-10-29）：** 以下图是磁盘当前实现（普通聊天也会执行`IndustrialCandidate.graph.run`，再调用DeepSeek）；**不是下一版目标图**。参见[最新状态](PROJECT_STATUS_CURRENT.md)、[数据适用性改革](data_quality/DM_APPLICABILITY_ROOT_CAUSE_AND_REFORM_20261029.md)。

### 下一版目标：统一入口、三路业务与最小用户暴露

```text
React composer -> FastAPI access/intent gateway -> SQLite run + audit event store
                                     |-- general_chat -> DeepSeek.chat directly (normally 1 Chat API; web opt-in separately)
                                     |-- standard_lookup -> teacher standard_clause_search + provenance gate
                                     '-- engineering -> bounded LangGraph -> 3 frozen teacher tools -> evidence / eligibility gate
User view: final answer + needed citations + default-collapsed public decision summary
Internal: full SQLite event ledger + SSE as transport/replay only, not raw user text output
```

- **普通聊天**：不再进入LangGraph；保留同会话有界历史、失败重试、Token和模型元信息；关闭联网时正常仅一次DeepSeek生成，不能偷加第二次LLM分类费用。涉及设备安全的混合请求须进工程或拆任务，不得被问候/身份前缀截获。
- **标准查证**：调用老师现有标准工具（不加第四个），给条款、来源/页码、证据等级，不能仅有ID就称工程适用。
- **设备研判**：原图保留，但加来源条件的三值判定和独立审查；不凭弱相关关键词或空字段输出确定结论、L1-L4或固定周期。
- **显示契约**：用户面板只展示答案、必要证据、一个默认收起的“思维过程/判断依据”。展开仅展示**公开的执行阶段、工具名称、经过权限检查及脱敏后的参数/返回结果摘要、来源与排除/缺失依据**，不显示SSE raw JSON、完整后台事件记录、SQLite敏感内容或模型隐藏思维链。老师评审演示仍需满足逐步查看工具输入与结果的可核查性，采用人类可读的字段投影而不是原始SSE帧；敏感字段在授权审查模式下单独受控显示。全量真实事件保存在本地DB作为审计依据，通过SSE内部送达/断点续传；“不显示SSE”不等于取消SSE协议。
- **状态**：本段是待实施设计，不宣称已编码/测试；旧ActivityTrace当前仍可能包含原始技术事件，后续需要安全映射和可见性检查。

---

唯一正式本地演示路径只使用已有组件，不另建 Supervisor/事件总线：

```text
React (frontend/dist) ──HTTP──> FastAPI (backend/api.py)
       ▲                         │
       │                         ├── SQLite Store
       │                         │   conversations / messages(run_id) / runs / SSE events / uploads
       │                         ├── bounded R9-A LangGraph (RULE_DEMO)
       │                         │   route → investigate(≤3) → optional parallel review → report
       │                         └── exactly 3 frozen teacher tools
       │
       └──── SSE event replay + SQLite history ────────┘
```

## 数据流

1. 前端提交当前问题、显式填写的工况和会话附件 ID；服务端将输入快照保存到 SQLite `runs`。
2. worker 领取 SQLite lease 后运行 `IndustrialCandidate`。Graph 对缺失输入、工具错误、证据门禁、标准相关性和重试预算作有界路由；默认不是多 LLM。
3. Graph 产生的真实执行事件通过既有 EventSink 逐个写入 SQLite，SSE 以同一 `run_id` 和递增 `sequence` 推送/重放；助手回复与 run 完成状态原子提交。
4. React 将该 run 的持久化事件映射到对应助手消息的折叠 ActivityTrace。没有事件时显示空记录，不用 localStorage 伪造活动。
5. 结论只显示来源/待核候选和证据状态。`risk_level` 保持 `null`，直到有获准且充分的工程证据与人工确认。

## 冻结和边界

- `upstream/` 老师三个工具名称、参数和五键结果协议不变；不增加工具、不修改正式标准、Excel、PDF 或 JSONL。
- SQLite 是会话/运行/事件/文件的本地持久层；上传按会话隔离。SSE 是已有传输协议，不是第二套后台任务架构。
- `RULE_DEMO` 是显著标记的规则演示；没有配置和验证真实模型 API 时，禁止称为 REAL_LLM 或多模型交叉审核。
- 历史 `app/`、`web/`、`knowledge/`、旧评测目录保留，供回溯；当前唯一聊天入口是 FastAPI 托管的 React build。
