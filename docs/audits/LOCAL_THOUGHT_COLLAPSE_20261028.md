# 本地聊天过程折叠验收（2026-10-28）

状态：`PASS_LOCAL_UI_AND_SSE`。仅本地 UI/展示层与 DeepSeek 受控表达流程调整；未部署，未修改教师三个工具、正式标准数据、JSONL、Excel、PDF 或 `upstream/`。

## 用户问题与处理

用户指出模型整理内容直接作为普通聊天长文显示，希望像豆包网页端一样可以折叠。现将助手气泡呈现顺序调整为：默认折叠的「思考过程 · N 步」卡片，然后是简洁、权威的最终答复。折叠卡片展开后查看真实持久化执行事件、公开阶段摘要、来源/审核摘要；DeepSeek 整理摘要再由内层 disclosure 单独展开。它们均为已记录执行证据或有界表达摘要，不宣称是也不展示隐藏思维链。

对于已有历史消息，解析旧版 `DeepSeek 表达整理（非独立研判）` 与 `本地确定性研判与证据状态（权威）` 分节：前者移入可折叠摘要，后者留作普通最终答复；旧版混在消息末尾的 DeepSeek 说明 footer 也会清理。普通问答和用户消息不变。

## 代码变更

- `backend/api.py`：DEEPSEEK 工程研判答复改为简洁的本地结论/缺失条件/状态提示；模型整理内容只以 `llm_completed.payload.summary` 随 SSE 持久化，不拼入最终 assistant 内容。普通 `general_chat` 仍是正常对话答复，不冒充“思考过程”。
- `frontend/src/AssistantMessages.tsx`：把同一 run 的折叠执行/思考摘要放在该轮答复之前，并对历史消息分节做 presentation。
- `frontend/src/messagePresentation.ts`：增加旧消息拆分和旧 footer 清理。
- `frontend/src/components/trace/ActivityTrace.tsx`、`activity-trace.css`、`frontend/src/trace-events/model.ts`：按是否真实存在模型整理事件选择折叠标题，增加“非思维链”说明与内层摘要 disclosure。
- 测试：`AssistantMessages.final.test.tsx`、`ActivityTrace.test.tsx`、`messagePresentation.test.ts`。
- 实测证据：`frontend/evidence/thought-collapse-live.json`、`frontend/evidence/thought-collapse-live.png`、`frontend/evidence/thought-collapse-legacy.json`。桌面/手机 composer 视口验收截图仍在 `frontend/evidence/scroll-fix-desktop.png` 与 `scroll-fix-mobile.png`。

## 真实端到端记录

本机 FastAPI health 返回 `mode=DEEPSEEK`、provider `DeepSeek`、model `deepseek-flash`。建立会话 `a9a11439-fa20-4eef-bb0b-d2c14903fe19`，run `d158f26b-23c8-41d6-b7f4-5de5350e68f7`，输入提供已知材料/介质（碳钢、湿硫化氢）并询问“请基于已知材料和介质说明当前可确认内容与待补条件”。实际 GET `/api/runs/{run_id}/stream` 消费 SSE 后，观察到 `llm_completed` 与 `run_completed`，最终 `draft_for_review`。

终端通过 API 回查 SQLite 投影：会话有 2 条消息，assistant `run_id` 与该 run 匹配；最终回复长 79 字，`/api/runs/{run_id}/events` 回放 35 个事件，含持久化 `llm_completed.payload.summary`（454 字）和摘要标签 `DeepSeek 表达整理（非思维链）`，terminal 为 `draft_for_review`。真实 Edge Headless + CDP 页面在 1440×900 与 390×844 展示：卡片默认关闭，标题「思考过程 · 35 步 · 检索 2 次 · 6 个引用」，最终回答在卡片外且简洁；展开主卡显示真实事件摘要，再展开内层显示模型表达摘要。DOM 断言两层 toggle 均可打开，主答复仍在卡片外；手机 composer 底边为 viewport 底边 844 px。详见 live JSON/PNG。

另在 Edge CDP 加载既存 `DeepSeek live smoke` 会话。4 个旧 assistant 回合均默认显示折叠执行卡；带旧版双分节标题的历史长文经前端解析后，折叠区标题为「思考过程」，最终可见答复只保留权威本地部分。回查文件 `thought-collapse-legacy.json`。

## 命令与结果

```powershell
npm test --prefix frontend -- --run
# Test Files 11 passed (11); Tests 79 passed (79)
npm run typecheck --prefix frontend
# tsc -b --pretty false：PASS
npm run build --prefix frontend
# Vite build：PASS；既有主 bundle > 500 kB 提示
.\.venv-langgraph\Scripts\python.exe -B -m unittest discover -s tests -q
# Ran 140 tests; OK (skipped=3，可选 Phoenix/OpenInference 环境专项)
node frontend/scripts/scroll_composer_e2e.mjs
# Edge CDP：桌面 1440×900、手机 390×844；滚动容器与固定 composer 均 PASS
```

验证第一次用纯 REST 创建 run、但未读取 SSE 时，任务保持 `queued`；随后读取其 `/stream` 端点后正常执行并落库。这是本服务按需由 SSE 建立 worker 的既有行为，不是模型或前端回归失败。Browser Extension 的 localhost 导航本次无响应；因此截图/DOM 检查采用真实 Edge Headless + 本机 CDP，且成功完成。

Edge 浏览器第一次真实点击还发现旧 disclosure 把 React 的显式点击状态更新与原生 `onToggle` 同时持久化会发生竞态，面板保持关闭。已移除冲突的 `onToggle`，由受控 `<details>` 点击更新 `open` 与 localStorage；Edge CDP 复测主卡和内层摘要的打开/关闭均成功，相关 Vitest 回归保留。

## 复核边界

- 这是过程 UI 和答案排版改进，不是模型质量/工程结论正确性的证明。
- DeepSeek 自然语言摘要只在用户展开内层折叠项时显示；普通最终答案是本地有界结论，不把模型自述当证据。
- 历史旧文本只在客户端显示时拆分，不回写 SQLite 历史消息。
- 当前变更停留本地，等待 Owner 复核；未提交、未部署。
