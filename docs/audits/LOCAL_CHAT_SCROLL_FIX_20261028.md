# 本地聊天输入栏与对话滚动修复（2026-10-28）

状态：`PASS`。本轮仅改前端布局/CSS与浏览器回归脚本，没有改 API、数据库、教师工具或标准数据。

## 复现与根因

用户截图中历史对话占满工作区下方，输入 composer 不可见，滚轮也无法将其找回。`.app-shell` 固定视口高度并 `overflow:hidden`，而 `.chat-scroll` 虽为 flex 子项/overflow:auto，却缺少 `min-height:0`。默认 `min-height:auto` 允许历史内容撑大滚动区，把同级 composer 推出 app-shell 的裁剪区域；外层页面本身又被裁剪，产生“不能下滑”的现象。

## 修复

- 根应用使用 `100dvh` 与 `grid-template-rows:minmax(0,1fr)`；html/body/root 的高度显式约束。
- workspace 与 `.chat-scroll` 设置 `min-height:0`；对话区成为独立纵向滚动容器，`overscroll-behavior:contain`，composer 始终占据同一视口底部区域。
- 移动端沿用内部滚动，将 composer 底部留白与安全区结合，避免底部导航覆盖输入按钮。
- 新增 `frontend/scripts/scroll_composer_e2e.mjs`，连接本地 Edge CDP，自动检查桌面/移动的滚动容器、页面外溢和 composer/input 可见边界，并输出截图。

## 实测证据

命令：

```powershell
npm test --prefix frontend -- --run
npm run typecheck --prefix frontend
npm run build --prefix frontend
node frontend/scripts/scroll_composer_e2e.mjs
```

结果：Vitest 10 files / 75 tests PASS；TypeScript PASS；Vite production build PASS（主 bundle >500 kB 体积提示仍在）。真实 Microsoft Edge CDP 实测：

| 视口 | 页面滚动高度 | 对话区 | composer | 结果 |
|---|---:|---|---|---|
| Desktop 1440×900 | body 900/900，无外层滚动 | top 57, bottom 708, clientHeight 651, scrollHeight 949, overflow-y auto | top 708, bottom 900；输入框 762–827 | PASS |
| Mobile 390×844 | body 844/844，无外层滚动 | top 51, bottom 607, clientHeight 556, scrollHeight 1163, overflow-y auto | top 607, bottom 844；输入框 657–722 | PASS |

浏览器执行命令：

```powershell
& 'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe' --headless=new --disable-gpu --no-first-run --remote-debugging-port=9222 --user-data-dir="$env:TEMP\haeness-scroll-e2e-profile" http://127.0.0.1:8000/
node frontend/scripts/scroll_composer_e2e.mjs
```

截图：

- `frontend/evidence/scroll-fix-desktop.png`
- `frontend/evidence/scroll-fix-mobile.png`

## 文件差异范围

- 修改：`frontend/src/styles.css`
- 新增：`frontend/scripts/scroll_composer_e2e.mjs`、本审计文件、上面两张 Edge 截图
- 更新：`docs/PROJECT_STATUS_CURRENT.md`

没有修改 `backend/`、老师三个工具、`upstream/`、Excel、PDF 或官方 JSONL；没有提交或部署公网。网站仍运行于 `http://127.0.0.1:8000/`。
