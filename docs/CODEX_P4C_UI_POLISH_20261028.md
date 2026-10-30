# Codex P4-C｜React信息架构与证据审查可读性精修（仅改frontend）
先读docs/audits/OWNER_P3_INDEPENDENT_REVIEW_20261028.md、docs/audits/P3A_FRONTEND_ACCEPTANCE.md与frontend/src/App.tsx/api.ts/AgentFlow.tsx/styles.css。当前前端Vitest6/6、TS Build PASS，但只有一个单会话E2E。固定后端现有SSE字段不变。
**允许写：** frontend/、docs/audits/P4C_*.md。不得改backend/、orchestration/、upstream/原RBI Excel。可以在backend P4A稳定后读取并联调新的 `GET /api/conversations/{id}/runs`，但本轮先不要依赖其上线。

核心目标：
1. 桌面1280三栏窄导致正文和Trace图拥挤：做可折叠Inspector及专注聊天模式；正文阅读区宽≥600-700px，细节面板在窄窗口转Drawer；中文长报表、空白、Markdown表格/公式正确换行。配色维持高级克制，不引入昂贵收费UI库。
2. React Flow应展示“实际执行状态与实际跳转”：从真实SSE里的agent_started/agent_completed建立本次观测边，状态skip/started/completed/failed清晰。若展示预期的可能路径，需要单独说明，这是plan不是发生过的运行。两类不得混淆；给不同路径截图。
3. Evidence cards按`claim_id`合并latest claim_checked/required review；历史事件继续在timeline展示。点卡呈现关键字段（支持出处条款ID、标准号、印刷页、条件、metadata matching、审核级别），默认不展开原始JSON而作为debug panel。
4. 多会话并发UI：发送后切换其他会话、快速点击不同历史记录、reconnect、离开和返回页面时，旧请求不得覆盖当前selected/detail/events；用AbortController/请求epoch，单run显示进度不跨会话污染。后端仍对同run唯一执行负责。
5. 历史恢复：等待P4A的list runs接口后接入全量运行索引；目前保持localStorage后备而非误声称跨设备恢复。保存每个run的事件按sequence去重，断连单次重放测试。
6. 键盘无障碍/移动屏390、桌面1280/1440/超长中文/黑暗模式实测；不要以静态截图冒充API E2E。跑vitest/typecheck/build，新增≥8条实际UI行为回归、浏览器控制台0异常、真SQLite/SSE实时链路并出具截图（可用本机Edge）；停在READY_FOR_OWNER_REVIEW。

输出 docs/audits/P4C_UI_EVIDENCE.md，包含功能验收与具体截图路径，禁止添加无必要的第二套重型Agent UI runtime。
