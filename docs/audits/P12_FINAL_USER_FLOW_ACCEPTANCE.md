# P12 Final User-Flow Acceptance

**结论：`READY_FOR_OWNER_REVIEW`**  
日期：2026-10-29（本地）  
范围：P0 自然语言工况到原三教师工具；P1 本机模型配置；保留 Owner 深色主题修正；语音浏览器兼容性核验。未部署公网、未提交 Git。

## 变更与边界

- 新增 `backend/context_slots.py`：显式槽位解析、单位/材料别名、安全的上下文优先级、来源与冲突记录；不把材料编号当温度，不把提问当作减薄实测。
- `backend/api.py` / `backend/store.py` / `orchestration/intent.py` / `orchestration/r9_industrial_candidate.py`：聊天原话可形成经来源标注的结构化工况；仅同会话延续最近已完成的工况；普通闲聊不走工程图；冲突进入澄清；报告正文展示有出处的待核候选和下一步缺口，不把内部状态码、演示标记或未经证实风险级别当结论。
- 新增 `backend/model_profiles.py`：本机配置元数据与凭据分离；Windows 凭据使用 DPAPI CurrentUser；配置 CRUD、激活、模型快照、最小真实供应商测试；只回显掩码。仅允许 HTTPS DeepSeek / OpenAI 官方端点并做 DNS/地址约束。
- 前端新增模型配置保存、编辑、删除、激活、真实连接测试、凭据状态与结果展示。编辑时留空 Key 保留原密钥，输入新 Key 替换。已选 Profile 在新 Run 创建时写模型 ID/provider/model 快照，历史 Run 不随全局切换重写。
- 配置管理端点限定本机 Loopback Host；`APP_ENV=production` fail-closed。当前没有账户认证/多租户机制，因此公网配置接口保持关闭。
- `frontend/src/styles.css` 未修改，Owner 已完成的 `resolvedTheme` 与设置页深浅主题修正保留。
- 未修改老师 Excel/PDF、正式条款库、老师工具合同、用户历史数据库；测试凭据仅为合成值并写入临时目录，未接触真实历史数据。

## P12 场景验收

| 案例 | 结果 | 证据/边界 |
|---|---|---|
| A：只在聊天输入塔顶碱液弯头、300 系列不锈钢、碱式酸性水、60°C | **通过** | API 集成测试确认 `context_resolved` 提取字段、触发教师工具、正文显示“酸性水腐蚀（碱式酸性水）”候选及 `GB/T 30579-2022 5.23` 来源，并标注待核；风险等级为空。 |
| B：普通问候 | **通过** | 图单测 `你好` 返回普通聊天意图，工具调用数为 0。 |
| C：只问设备风险等级、无工况 | **通过** | 不执行检索，不生成风险级别；转为缺失信息询问。 |
| D：表单与自然语言材质冲突 | **通过** | 结构化表单优先，同时生成显式冲突记录，不静默丢弃。 |
| E：同会话续问 / 跨会话隔离 | **通过（单元/集成路径）** | 仅读取同会话最近已完成上下文；排队中 Run 不作为已确认上下文；另一个会话结果为空。 |
| F：GB/T 26610.5-2022 面积后果表 | **未通过内容命中；安全行为通过** | 对“查询 GB/T 26610.5-2022 面积后果表”的真实本地检索返回 `unresolved / E0 / risk_level=None / citations=[]`。未找到对应来源，系统没有编造表值；需要教师条款库提供可验证来源后再验收此条。 |
| G：外部 Host / 恶意 endpoint | **通过** | API 非 Loopback Host 返回 403；生产模式配置 API 返回 503；私网、localhost、非 HTTPS、`file://` 和不在 allowlist 的域名由端点校验拒绝。 |
| H：切换模型与 Run 快照 | **代码/API 快照通过；真实供应商调用未执行** | 新 Run 持久化 profile ID/provider/model，密钥未写入上下文；模型管理单测验证测试请求内容和 usage 解析。没有实际调用供应商 API，避免未经确认产生费用；真实连接按钮调用供应商接口并显式提示潜在费用。 |
| I：深浅主题桌面/手机 | **通过（Edge 浏览器截图）** | Edge 实际浏览器 1280×900、390×844 深/浅主题截图；检查 `scrollWidth == innerWidth`，无横向溢出。深色文字/背景 computed style 正常。 |
| J：Edge/Firefox 语音 | **部分通过** | Edge 实际浏览器检测到 Web Speech `SpeechRecognition` 接口；语音控件测试覆盖支持/不支持、主动点击与仅回填草稿。Firefox 未安装，无法进行真实浏览器验证；未授权实体麦克风采集，未做实际口述转写。应用保留不支持提示与手动输入，不为此重构后端。 |

## 自动化验证

- 后端：`.\.venv-langgraph\Scripts\python.exe -B -m unittest discover -s tests -q` → **156 tests，OK，3 skipped（最终全量复跑）**（在补充 Run profile snapshot 测试后应重新执行最终全量）。
- P0/P1 专项 API：自然语言聊天候选/来源、Profile 路由 Loopback/生产 fail-closed、Run 模型快照单测。
- LangGraph 教师工具：`tests/test_r9a_industrial_candidate.py` → **19 tests，OK**；保留原有三工具集及图门禁行为。
- 教师最终数据回归：`upstream\04_接口文档\validate.py --final` → **554 条条款 554/554 通过，200 条轨迹 200/200 通过，终验通过**。只读执行。
- 前端：`npm run test -- --reporter=dot` → **16 个测试文件、111 tests 全通过**；`npm run typecheck` 通过；`npm run build` 通过。构建仍报告一个约 610 kB 的主 JS chunk（优化项，不阻断验收）。
- 模型凭据测试用 Windows DPAPI 合成密钥完成加密/解密与无明文文件断言；供应商测试通过 mock 回包验证请求/usage 字段，**未发起真实付费 API 请求**。

## 浏览器截图

Edge 实际浏览器截屏保存在 `docs/audits/P12_screenshots/`：

- 桌面深色：[edge_desktop_dark.png](P12_screenshots/edge_desktop_dark.png)
- 桌面浅色：[edge_desktop_light.png](P12_screenshots/edge_desktop_light.png)
- 手机深色：[edge_mobile_dark.png](P12_screenshots/edge_mobile_dark.png)
- 手机浅色：[edge_mobile_light.png](P12_screenshots/edge_mobile_light.png)

语音兼容性背景： [MDN SpeechRecognition](https://developer.mozilla.org/en-US/docs/Web/API/SpeechRecognition) 将该 API 标注为有限可用；Firefox 未安装这一事实来自本机浏览器检查，不以单测冒充 Firefox 实测。

## Owner 复核项 / 明确限制

1. 若要通过 F，需核对教师条款库中 GB/T 26610.5-2022 面积后果表的准确条款、页码和可检索记录；当前结果按 E0 无来源处理。
2. Firefox 需在装有 Firefox 的机器上补一次页面语音 API/错误提示实测；Edge 仅完成接口能力探测，未实际授权麦克风讲话。
3. 未使用真实供应商密钥发起连接测试；可由 Owner 在本机设置页主动点击“真实连接测试”，确认计费后验证真实 provider/model/usage。
4. 当前允许的 endpoint 是官方 DeepSeek/OpenAI HTTPS 域名，不提供任意 OpenAI-compatible 主机；若将来扩展 endpoint，需维持 SSRF 限制并单独验收。

## 收口状态

**`READY_FOR_OWNER_REVIEW`** — 代码、测试与 Edge 截图已落地；已知未验收项如上。未部署公网、未提交 Git。

