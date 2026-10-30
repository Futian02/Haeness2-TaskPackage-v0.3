# R2-F 前端/API协议交互与浏览器验收

状态：`READY_FOR_OWNER_REVIEW`（F代码与前端自动化完成；真实Edge limited smoke由R2-QA单独采证，完整R2全链路仍待A–D/E集成）。

## 边界与文件

仅修改`frontend/**`和本报告。未修改backend、Graph、教师upstream、数据库、人工记录或8000/8001进程。前后端协议统一为`aetheris-r2.0.0`。F没有运行付费模型。

## 实现

- `src/runtimeContract.ts`统一contract版本、健康状态判定、版本差异说明和指纹显示；无合同的旧API标记为“旧版后端”，不同版本/缺字段分别显示，不当作断网。
- `vite.config.ts`以有序源清单SHA-256独立生成64位前端源码指纹，并在Vite dev/build注入HTML meta：`aetheris-contract-version`与`aetheris-build-fingerprint`。指纹覆盖递归`src/**/*.{ts,tsx,css,html}`及`package.json`、`vite.config.ts`、`index.html`，每个排序项按`relative-posix-path UTF8 + NUL + source bytes + NUL`哈希。后端指纹独立使用其`/api/health.build_fingerprint`，两者不混称。
- Vite代理增加`VITE_API_TARGET`覆盖；E2E显式转发至隔离shadow端口，浏览器继续调用相对`/api`，不会意外绕到8000/8001。
- 新建Run带稳定`Idempotency-Key`；仅创建响应确认返回Run ID才清pending key并清除未改动草稿。网络失败后，按CID在localStorage保留草稿/幂等键；更改问题或工况会旋转pending key，重复提交同一问题复用键。
- 对话重新载入先回放SQLite事件；若Run仍是queued/running且回放没有终态事件，前端以既有Run ID重新订阅SSE，绝不再POST创建Run。事件按run/sequence去重。
- HTTP 422/429/5xx有明确请求错误文案；草稿和幂等键保留。既有安全内容清洗、来源卡E0说明、审查折叠、隐藏推理与密钥不展示路径保留。
- 设置“关于”显示协议兼容状态、独立后端指纹与前端指纹。小屏兼容说明改为可换行布局。

## 自动验证

在`frontend/`执行：

```powershell
npm test -- --run
npm run typecheck
npm run build
```

实际结果：Vitest **20个测试文件/128项通过**；TypeScript **PASS**；Vite production build **PASS**。主bundle `621.26 kB`（gzip `190.87 kB`），仍触发>500 kB告警；已存在AgentFlow/AssistantMessages动态chunk。下一步可拆分统计、Markdown/来源详情等非首屏模块，不在此次扩大架构。

重点新测试：旧后端显示版本握手问题；运行请求失败时草稿保存且下次请求复用相同Idempotency-Key；R2新Run客户端发送header而不污染冻结Run body；版本匹配/缺失/错配/incomplete；前端source fingerprint长度64。

## 浏览器与运行版本证明

- 当前磁盘Vite production build的`dist/index.html`：`aetheris-contract-version=aetheris-r2.0.0`；`aetheris-build-fingerprint=826730eb3224622ed24fa54789a6caad35e08db3e137c30a5647eeca86e567b0`。
- QA已被授权仅执行E shadow `127.0.0.1:8877`上的limited真实Edge welcome/握手/普通“你好”Smoke。Vite命令：

  ```powershell
  $env:VITE_API_TARGET='http://127.0.0.1:8877'
  npm run dev -- --host 127.0.0.1 --port 5174 --strictPort
  ```

- 前端实现就绪后，QA两次受控runner均在Edge启动前因shadow运行fingerprint与当前后端源码manifest漂移而fail-closed；未进行网页操作、未发送Run、无截图。QA随后停止自己的临时shadow/Vite，当前8877/5174无监听；8000/8001仍在且未触碰。之前读取到的8877服务指纹`sha256:90554cef98e21b67cc0876480929d03c32d21355a9cfb84a7737186e747baa87`属于较早shadow，不作为当前前后端一致证明。必须由E按其最新shadow脚本重新启动，确认health SHA与源码manifest匹配后再跑真实Edge。
- **此limited smoke不代表**A/B专业问题、真实跨会话/更正、用户模型profile、敏感联网、移动端完整可用或六窗口G Gate已经通过。它只证明前端与E shadow版本握手、初始聊天收发的受限路径。

## 未完成/风险

- 等A–D其他窗口产物后再按G执行全链真实Edge端到端；在此之前不能认证专业回答、A/B真实答案、跨会话隔离、多轮事实修正、模型异常回退和完整移动端。
- 生产8000/8001保持原进程，未重启；当前前端开发服务器只应配置`VITE_API_TARGET=8877`用于isolated测试。
- 缺人工专业gold、82条机理适用性人工审查和真实付费LLM授权预算，仍是产品NO-GO项。

## 指纹

前端source fingerprint：`826730eb3224622ed24fa54789a6caad35e08db3e137c30a5647eeca86e567b0`（64 hex，见production `dist/index.html` meta）。最新后端shadow fingerprint与源码manifest一致性、Edge截图和实际UI Run均**未验证**；先前读取到的临时实例指纹不得作为当前证明。
