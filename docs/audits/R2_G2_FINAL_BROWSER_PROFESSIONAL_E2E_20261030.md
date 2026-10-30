# R2-G2 最终浏览器专业旅程审计（2026-10-30）

## 裁决

**STOP_FIX_REQUIRED / NO_GO_PRODUCTION。** 桌面和移动 Edge 的主要 RULE_DEMO 专业旅程、输入隔离、SSE重放、来源审查弹窗及普通聊天均取得真实浏览器证据；但 Gate B 要求的浏览器内 `WORKER_CAPACITY 429` queued 恢复与模型/工具不可用的类型化失败、保留草稿/idempotency 后重试尚未完成。本轮的 DeepSeek 未配置，且未调用真实或收费模型；因此不能据此证明DeepSeek能力，也不满足整份G2 Gate 的完整GO条件。

本裁决不是生产放行。**8000/8001、正式数据库、老师upstream、真人审核数据均未写入/重启/修改。** 隔离UI本轮用例通过只表明 RULE_DEMO 在临时环境的有限页面行为。

## 本轮变更

1. `frontend/src/App.tsx`：设备/工况输入改为按 conversation ID 保存/读取 `aether:context:<cid>`；切换/新建会话时恢复该会话自己的工况，未命名新会话默认为空。对原R9与执行/模型路径无修改。
2. `scripts/r2_browser_e2e.ps1`：修复Node/CDP结果汇总中的`consoleErrors`未定义、保留Node堆栈及Runtime.evaluate异常详情；增加 bounded CDP等待、SSE断线后`Last-Event-ID`重连、真实专业旅程、证据详情交互及独立截图；Run ID由API实际返回/持久记录核验。保留浏览器/服务端/磁盘指纹fail-closed。
3. 依赖：在`requirements-langgraph.lock.txt`锁入`PyMuPDF==1.27.2.2`；项目`.venv-langgraph`内装入锁定PyMuPDF和测试锁文件中的`pytest==9.0.2`，没有全局安装。

## 实际Edge旅程证据

使用真实Microsoft Edge CDP页面、真实前端交互和独立FastAPI服务，后端使用每轮新建的临时SQLite与清空provider credential的隔离shadow。无Mock API协议替代浏览器请求。`RULE_DEMO`是环境真实默认路径；这不构成DeepSeek验证。

| 场景 | Edge桌面 1440×900 | Edge移动 390×844 | 核查点 |
|---|---|---|---|
| 未配置模型直接API调用失败 + UI普通聊天恢复 | Run `9ea292ad-63c2-4ae8-a45d-3c52512c68cf`；HTTP 503未创建Run，随后UI hello成功 | Run `346753f7-46ef-4f89-8232-935c1e6e9036` | 503来自真实隔离服务；恢复路径通过UI RULE_DEMO。**并非模型失败UI显示验证** |
| SCC概念解释 | `9f9338bc-69de-4938-ac40-45df203c1fef` | `e7d9209c-381a-40bf-b48c-7fd205447da2` | 可见答案涵盖敏感材料、腐蚀环境、拉应力和裂纹，不要求缺失工况 |
| 专业A：弯头减薄，300系列不锈钢、碱式酸性水、60°C | `7df9af05-e369-4f1b-853c-0cf5ff8f05eb` | `e47e337f-4f78-41d2-a9a8-d5f323b3eef4` | Run快照保留字段；调用`damage_mechanism_query`与`standard_clause_search`；不作设备风险/停复机结论 |
| A温度修正至80°C | `2daca0a4-8c23-430e-b9dc-ee82f82041d4` | `3d48677a-43b4-4786-ac01-31d6690560fe` | 保留同设备上下文；不把5.23局部49–66°C误作排除整种机理的全局阈值 |
| A来源审查 | `f57c3162-3dc8-4196-b09a-96775050e1b3` | `5b29e2aa-c15f-4328-93a1-d07fc2aaa26c` | UI打开A2来源事件原始详情；`GBT30579-2022-5.23`、`GBT30579-2022-5.6`标为`E0`、`applicability=UNKNOWN`、`may_support_claim=false`、待人工适用性复核；不会因候选存在就宣称条款通过 |
| 专业B：壳体磕碰/维修验收 | `9f6773ae-c453-4b35-a66b-93bbfefa7aad` | `8836fab2-6fef-47d3-a70e-ca983bba639d` | 无来源时仍给危险征象、隔离/检查建议；不批准继续运行/复机。候选`TSG21-2016-8.5.8`的UI原始详情是E0，不作为无条件凹坑阈值 |
| 同CID工况更正 | 原始 `3e128502-2f36-423a-ab30-122561a36537` → 更正 `6f777aa8-af40-4236-b2a8-06d4e0820a46` | `fa021a76-d56f-4e69-8735-7d4083bc9f37` → `aebe5f43-ab72-49d2-95ce-5a817ff42933` | 用户明确更正材质碳钢→316L，快照规范值为奥氏体不锈钢，冲突审计保留`explicit_correction_supersedes_prior` |
| 同CID另一个匿名设备/后续追问 | `16592b38-d665-442d-a1f4-d9d21084806c` / `e7ac96af-9a4f-4048-99ec-b2086bec6d46` | `aa6a619b-4a9d-4360-8d34-df9db3031333` / `38314db0-6346-4889-989a-df8ccf5ccd6f` | 工况表清空后，不沿用也不从对话回灌设备甲/316L/H2S事实 |
| 新CID隔离 | `2fda86e8-6996-4af1-a35a-32c36b3f1bd9` | `9bf61f66-9f5f-4b35-be9a-f73191031db3` | 不串入前一CID的材质/设备 |

每个正常run均保存了SQLite终态`completed`、回答DOM可见状态、连续事件序列及SSE断流后重连序列；没有重复序列/重复assistant消息。桌面全旅程`consoleErrors=0`、非取消网络失败0；移动同样为0。移动视口`width=390, scrollWidth=390, composer bottom=844`，桌面`width=1440, scrollWidth=1440, composer bottom=900`。

截图、逐Run完整脱敏JSON、PowerShell/Node日志及异常记录均位于：
`docs/audits/evidence/r2_g2_20261030/`

主截图：
- Desktop A：`Edge_desktop_professional_A_60C_1793350091328.png`
- Desktop B：`Edge_desktop_professional_B_shell_impact_1793350094881.png`
- Desktop A源详情：`Edge_desktop_source_review_source_audit_1793350093773.png`
- Desktop B源详情：`Edge_desktop_professional_B_shell_impact_source_audit_1793350094988.png`
- Mobile A：`Edge_mobile_professional_A_60C_1793349986574.png`
- Mobile B：`Edge_mobile_professional_B_shell_impact_1793349996550.png`；来源详情：`Edge_mobile_professional_B_shell_impact_source_audit_1793349996913.png`

## 修复与失败记录

- 项目venv首次运行P16时报`No module named pytest`；验证锁中已有`pytest==9.0.2`，只向项目venv安装该锁定版本及依赖，再以相同venv重跑5/5。未改使用系统Python拆分验证。`PyMuPDF==1.27.2.2`也锁入主venv并在该venv核验导入。
- Node/CDP初次报`Error: Uncaught`：定位到评估表达式异常对象被丢弃及报告汇总引用不存在变量。现记录`exceptionDetails.text/description/stackTrace.callFrames`、短表达式哈希、target URL/ID、Node/browser PID和退出码；修复汇总变量。一次中间桌面重跑在SCC点击时`send disabled`，加入有界`send ready`等待后完整桌面11个真实UI run成功。失败原始JSON仍保留，没有删去。
- 首次在修改前端后Vite进程的编译期fingerprint未刷新（页面`8267…`与磁盘`6693…`不匹配），遵守指纹门禁，仅重启本轮自建的5174 Vite，不操作8000/8001；随后前端/磁盘指纹一致。
- 更正断言最初把整个快照的审计`prior_value=碳钢`视作当前值冲突，是测试误判。改为断言当前结构化材质字段为316L映射值，并另验冲突审计标记；产品数据未改动。
- 一轮中途GET runs出现HTTP 503且未获得Run ID；没有保留响应体，根因不确定。新隔离shadow完整复跑时未重现。该失败的JSON保留在证据目录，不能把本轮当作429验收。
- Node runner完整桌面/移动证据分别选取`Edge_desktop_20261030_164807.json`、`Edge_mobile_20261030_164617.json`；最新桌面CDP无Uncaught。还有更早失败JSON供审计对比。
- 真实DeepSeek未配置（health`llm.configured=false`），没有真实模型调用或收费请求。UI默认RULE_DEMO成功不能等同DeepSeek能力通过。

## 回归结果

1. `.venv-langgraph\Scripts\python.exe -B -m unittest discover -s tests -v`：**451 tests，0 failure，0 error，3 skipped**，最终`OK (skipped=3)`。3项为可选telemetry/Phoenix/OpenInference依赖未安装；不影响主流程，但相应可观测性集成未验证。
2. 同一`.venv-langgraph`：`.venv-langgraph\Scripts\python.exe -B -m pytest tests\test_p16_a_evidence42.py -q`：**5 passed**。合计本轮Python执行覆盖456项（451 unittest + 5 P16）；不是把P16移出或改写unittest结果。
3. `frontend`目录：`npm test -- --run` **128/128**；`npm run typecheck`通过；`npm run build`通过。保留Vite chunk >500 KB提示。
4. 教师只读终验：`upstream/04_接口文档/validate.py --final` **554/554 clauses、200/200 trajectories通过**；`upstream/05_提交区/_selftest_tools.py` **17/17**。源JSONL SHA-256仍为`A8151797BA15A6A7452DD83AAEC9FAB4C0A815724CA45062EB1E2BAC7B4D49EF`。
5. 项目venv：PyMuPDF `1.27.2.2`、pytest `9.0.2`；`fitz`从项目venv导入。
6. Edge runs报告后端指纹：`sha256:51dcdca504fc13eb4ae4e884ee3b35ec2018cec81d25a9b95c51ded60968b7be`；前端源码指纹：`66936b984ce1dc363f2ecb5a00dc812eba18ace1ccae4c026d318f840ba49168`。运行指纹等于对应磁盘源码计算值。

## 未通过 / 下一步Owner决策

1. **阻塞G2 GO**：补真实Edge UI中的worker-slot `WORKER_CAPACITY` HTTP429（检查保留queued状态、retry-after、浏览器重新订阅/恢复，Run不重复）及模型配置不可用/工具超时在UI的类型化错误、草稿与幂等键保留、重试不重复Run。单元/API测试对部分语义有覆盖，但不能替代该真实浏览器门。
2. **DeepSeek独立Gate**：需要Owner核准预算、模型配置和单次受控验证窗口；隔离shadow当前明确无credential，本轮没有对外调用，不能由RULE_DEMO/本地假Provider代替。
3. 证据源现有E0、未知适用性/语义，且真人审核仍未签核。不要使用它们批准设备运行、维修验收或RBI等级；老师原文和正式数据库保持冻结。

建议Owner：允许下一轮仅在独立临时SQLite/Edge中为WorkerCapacity做可控故障注入（不加载DeepSeek）；模型UI错误做未配置profile fail-closed验证。之后单独审批一笔有上限的真实DeepSeek连接/输出验证，再决定是否开`GO_ISOLATED_OWNER_RULE_DEMO_UI_TEST`或专业模型评审。现阶段总状态保持`STOP_FIX_REQUIRED`，生产`NO-GO`。
