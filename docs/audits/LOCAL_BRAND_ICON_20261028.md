# AETHER 品牌图标接入记录（2026-10-28）

状态：`PASS_LOCAL`。将用户提供的徽标设为本项目正式图标；未修改上游资料或教师工具。

## 文件与使用位置

- 资产：`frontend/public/assets/aether-icon.png`（1254×1254 PNG，2,164,723 bytes）。原 Temp 图片与项目副本 SHA-256 完全一致：`A634F323E7EC297E4F15194D1C4428C87CA2E37929AF12ACE16795B74E95EE17`。
- 网站 favicon 与 Apple touch icon：`frontend/index.html` 指向 `/assets/aether-icon.png`。
- 品牌侧栏标识、欢迎态、助手消息头像与执行中头像均改为复用该图；CSS 以容器圆角裁切并保持 `object-fit: cover`。
- Edge 实测截图：`frontend/evidence/brand-icon-live.png`。

## 验证

```powershell
npm test --prefix frontend -- --run
# Test Files 11 passed (11); Tests 78 passed (78)
npm run typecheck --prefix frontend
# PASS
npm run build --prefix frontend
# PASS；主 bundle 有既存 >500 kB 提示
Invoke-WebRequest http://127.0.0.1:8000/assets/aether-icon.png -Method Head
# HTTP 200
```

真实 Edge Headless + CDP 检查：`document.title` 为 AETHER/ENERGY；侧栏和助手头像的 PNG `naturalWidth=1254`、`complete=true`；favicon href 为 `http://127.0.0.1:8000/assets/aether-icon.png`。截图中侧栏与助手头像均显示新图标。

首次把图片放在 `frontend/public/aether-icon.png` 时，Vite build 虽复制成功，但 FastAPI 仅挂载 `/assets` 静态路径，因此根路径图片返回 404。已将资产放到 `frontend/public/assets/` 并更新链接，重建后 HTTP 200、Edge 加载成功；无遗留错误。

## 当前范围

本次只修改 `frontend/index.html`、`frontend/public/assets/aether-icon.png`、`frontend/src/App.tsx`、`frontend/src/AssistantMessages.tsx`、`frontend/src/styles.css`、此审计文档及 `docs/PROJECT_STATUS_CURRENT.md`；不提交、不部署。
