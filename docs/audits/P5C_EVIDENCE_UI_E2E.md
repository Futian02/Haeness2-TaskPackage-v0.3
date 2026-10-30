# P5C — 完整工况来源与审查 UI 的真实浏览器验收

**状态：READY_FOR_OWNER_REVIEW**（本机真实 Edge E2E 已通过；无部署、无 Git 提交）。

## 变更范围

仅修改 `frontend/` 与本审计目录内 `P5C_*` 证据。前端增加可放大的独立 Agent 图；Claim 聚合保留最新审查状态，同时从此前最完整事件恢复原 Claim 的条款ID、E0/E1、引用、canonical hash、原文、检查结果和现场 unknown；来源抽屉以可读字段呈现来源门禁和反证，时间线仍保留所有原始 SSE 事件。Agent图 ResizeObserver 更新已使用 animation-frame 合并，减少布局变化时的重复反馈。

没有改 backend、orchestration、老师三工具/五键合同、原始 RBI Excel 或任何 PDF。P5A另行修改 backend 并独立验证；P5C E2E 连接该 FastAPI 版本，但没有修改其代码。

## 真实Edge + FastAPI + LangGraph + SQLite + SSE

运行脚本：`frontend/scripts/p5c_full_evidence_e2e.mjs`；Edge启动脚本：`frontend/scripts/start_p5c_edge.ps1`。应用通过真实 UI 输入完整工况和问题，未 mock 工具或 SSE。FastAPI 连接到 `%TEMP%` 独立业务 SQLite；LangGraph checkpoint 也位于 `%TEMP%`，结束时关闭本机测试服务。Edge CDP、Vite和FastAPI均绑定 `127.0.0.1`。

最终验收 run_id：`281a6000-d8a3-48e9-a2a5-28580eb465a6`，会话ID `510a7960-4e1a-4243-8324-7a27ec4f57ea`。最终浏览器验收是在P5A completed+SSE原子提交修复后的代码上重新执行；完整请求：

- 材质：碳钢
- 介质：氯化氢
- 设备类型：换热器
- 问题：塔顶水样pH 5.8，铁离子 4.1 mg/L，尚未测厚，可能的损伤机理？
- 现场证据：塔顶水样pH 5.8，铁离子 4.1 mg/L，尚未测厚

真实结果来自本地冻结工具与本地 `clauses.jsonl` 只读canonical回查：run 状态 completed；SSE 44条，连续序列1–44；含2次 tool_called/result、7个 reference_added、2条Claims、2个独立disagreement，最终run_completed。Claim为E1×1、E0×1，均 `unresolved/requires_human_review`。E1引用 `GBT30579-2022-5.1`，印刷页2，canonical记录SHA-256 `ecc5fadb56aa1efda0d3df4a2f821dca46ad93745dd7b977e2aa7d64db09f89c`；E0引用 `GBT30579-2022-5.18` 未能从本轮source验证，故显示partial/missing，不提供canonical原文/hash。未知温度、压力保持unknown。没有E2/E3或设备L级风险结论。运行/来源详情实测 JSON：[P5C_FULL_EVIDENCE_E2E.json](P5C_FULL_EVIDENCE_E2E.json)。

SSE replay `after_sequence=5` 实际返回39条，起始序号6并连续；页面刷新后重新通过 SQLite replay 恢复44条事件及2张Claim卡。浏览器切换至第二会话时Claim卡数为0，切回第一会话恢复该run数据，没有会话交叉串线。浏览器记录的所有 `/api/*` 状态为200；Console错误数组为空。

## 浏览器交互和截图

浏览器确实点击E1/E0 Claim卡、reference_added时间线事件和放大执行图；来源抽屉内检查打印页码、标准号/CID、canonical hash、原文引用、E0/E1、`requires_human_review`、检查状态、unknown与反证。放大图实测7节点、1058×658；侧栏原图只有约252px宽，另有放大入口。无观测到的跳转不会被补画。

截图（均由本机 Edge CDP `Page.captureScreenshot` 保存）：

- [桌面1280](P5C_DESKTOP_1280.png)、[桌面1440](P5C_DESKTOP_1440.png)
- [E1来源抽屉](P5C_E1_SOURCE_DRAWER_1280.png)、[E0缺源抽屉](P5C_E0_SOURCE_DRAWER_1280.png)、[reference_added来源卡](P5C_REFERENCE_DRAWER_1280.png)
- [放大执行图](P5C_GRAPH_EXPANDED_1280.png)、[刷新恢复](P5C_REPLAY_RESTORED_1280.png)
- [移动390](P5C_MOBILE_390.png)、[移动端来源抽屉](P5C_MOBILE_SOURCE_DRAWER_390.png)、[深色1280](P5C_DARK_MODE_1280.png)、[长中文输入](P5C_LONG_CHINESE_1280.png)

1280布局 `bodyWidth=1280` 无横向溢出；移动390与1440视口均完成截图交互；长中文输入612字符。DOM与服务端Claim JSON检查均未发现E2/E3、L1–L5或“低/高风险”结论。原始canonical片段只在本机来源抽屉与本地证据文件展示，未发送到外部服务。

## 命令结果

```text
node ./node_modules/vitest/vitest.mjs run --reporter=dot
Test Files 4 passed (4); Tests 30 passed (30)
node ./node_modules/typescript/bin/tsc -b --pretty false
PASS (exit 0)
node ./node_modules/vite/bin/vite.js build
PASS; 3102 modules transformed; built in 1.18s
node ./scripts/p5c_full_evidence_e2e.mjs
PASS; run_id=e53eb101-8f33-4e05-9458-8bf030a5fd0a; events=44; claims=2 [E1,E0]; disagreements=2; references=7; replay(5)=39; console_errors=[]
```

此前P5C首轮浏览器尝试捕获到UI聚合缺陷：`requires_human_review` summary event使卡片把丰富Claim source payload覆写为精简事件包，UI显示E?，但服务端Claim仍有E1/E0。通过前端 `aggregateClaims()` 在不牺牲最新状态的前提下合并最完整事件，补齐E1/E0和原文/哈希/unknown后，30项测试与最终真实浏览器验收均通过。另有一次脚本在移动切换后刷新默认选中最近会话，调整测试脚本刷新后明确选回原会话再验恢复；并未改产品会话选择语义。

## 可审查实现与学习点

- `frontend/src/uiModel.ts`：按 `claim_id` 聚合，最新事件负责当前复核状态，最完整事件提供稳定Claim身份和来源字段，历史不丢。
- `frontend/src/App.tsx`：Claim详情用 canonical_evidence 展示 CID、hash、页码、原文、来源状态、未知工况和反证；时间线可单独打开原始reference事件。
- `frontend/src/AgentFlow.tsx` / `styles.css`：保留侧栏小视图，提供可读独立大图；真实边仍从相邻agent_started事件推导。
- `frontend/src/App.behavior.test.tsx`：原24项保留并新增6项（共30），覆盖放大图、E1/E0来源、hash/quote/unknown、复核历史、风险字段不泄漏及reference_added来源抽屉。

观察性回归与专家准确率是两回事：这一轮证明数据真实通过冻结工具、SQLite、SSE和UI一致显示，不证明RULE_DEMO的损伤机理结论已获专家认可；Claims仍是待人工复核的工程假设。
