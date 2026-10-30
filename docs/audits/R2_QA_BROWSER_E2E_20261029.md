# R2 QA｜协议Mock与真实浏览器 E2E 准备记录

状态：`READY_FOR_OWNER_REVIEW / STOP_FIX_REQUIRED / EDGE_SMOKE_NOT_RUN / NO_PRODUCTION_TOUCH`。本文件属于 QA 专属范围。

## 1. 共享接口合同

- `contract_version`: `aetheris-r2.0.0`
- `build_fingerprint`: 64位小写SHA-256，来自后端源码manifest；前端需独立给出frontend fingerprint。
- `capabilities`: `runs_create`, `runs_sse_stream`, `runs_replay`, `run_input_snapshot`, `model_profiles`, `professional_guidance`, `file_upload`, `explicit_web_consent`, `conversation_history`, `conversation_memory`, `sensitive_web_consent_gate`均为bool；`teacher_tool_count`必须为3。
- Run 输入保留`question/equipment/equipment_type/material/medium/operating_condition/field_evidence/mode/web_mode/web_search_enabled/allow_sensitive_web_search/model_profile_id`。
- 幂等：相同幂等键与相同请求返回同一Run；相同键但不同请求必须冲突，不得第二次执行工具。
- Replay：事件身份为`run_id+sequence`，`after_sequence`为exclusive；重放去重不依赖payload文本。
- 对外trace不包含密钥、系统提示、隐藏推理、内部环境变量或原始SSE正文。
- HTTP错误区分422合同错误、429可重试背压、5xx服务/Provider失败，断线可先Replay再续SSE。

## 2. 已准备的QA文件

- `tests/test_r2_browser_e2e.py`：冻结协议fixture的正向/负向校验，覆盖缺合同版本、缺能力、错误指纹、教师工具数漂移、Run输入字段、幂等冲突与复用、SSE断线后的exclusive序号恢复、事件重放身份、敏感字段泄漏与HTTP错误分类。此阶段只验证QA断言/fixture，不把mock测试当应用通过。
- `docs/audits/evidence/r2_qa/protocol_mock_contract.json`：共享合同测试fixture。
- `scripts/r2_browser_e2e.ps1`：仅在显式`-OwnerApproved`后运行；限制目标为loopback且排除8000/8001，先GET健康接口核对版本/能力/指纹，并依据E冻结的`source_files + source_manifest`和长度前缀算法独立重算磁盘后端SHA-256；按F冻结算法本地重算前端src/build输入，再在真实DOM核对meta。浏览器内再fetch相对`/api/health`，要求Vite代理返回的版本/fingerprint与直连E健康接口一致；`-HelloSmoke`通过真实CDP键盘输入和按钮点击发送“你好”，核验SQLite持久消息、terminal SSE replay、DOM答复与composer viewport，再保存欢迎/答复截图。实际脚本已在Edge启动前多次fail-closed，未到浏览器步骤。

QA源码/协议fixture SHA-256（本轮实测）：

| 文件 | SHA-256 |
|---|---|
| `scripts/r2_browser_e2e.ps1` | `001B2EADEE935A4F79D60AF0B1930F89EE690C5D34A1AAF2203EE124C6932251` |
| `tests/test_r2_browser_e2e.py` | `1A877ED9414AB9360E1A1AA23FE874BF43DADBF34AA6A59DDA5C49211B48F62F` |
| `docs/audits/evidence/r2_qa/protocol_mock_contract.json` | `FEBB51718F8CF28D519641A3F3132B60E9AF8DE9DACE101F26736CC24E99C1CA` |

## 3. 环境实查

| 项 | 事实 |
|---|---|
| Edge | `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`, 142.0.3595.53 |
| Chrome | `C:\Program Files\Google\Chrome\Application\chrome.exe`, 146.0.7680.178 |
| Node | v24.11.1，原生WebSocket可用 |
| Python venv | 无Playwright/Selenium；`httpx`与`fastapi`可导入 |
| frontend依赖 | 未安装`playwright`/`playwright-core`/Puppeteer；已有历史真实Edge脚本直接CDP连接9222 |
| 当前CDP | 9222未监听；无浏览器自动化连接 |
| 生产服务 | 8000/8001仍在监听，QA未向其发请求/写数据、未停止/重启 |

## 4. 当前可确认的测试/阻塞

- 实测命令：`.venv-langgraph\Scripts\python.exe -B -m unittest tests.test_r2_browser_e2e -v` → **9/9 PASS**；PowerShell AST parser对`r2_browser_e2e.ps1` → **PASS**。这些仅为测试器/fixture契约oracle，不能证明应用通过。
- 已有本机Edge/Chrome与Node原生CDP能力，无需装包即可执行CDP截图与DOM/网络检查。
- 主控批准后，第1次实际启动E隔离shadow `127.0.0.1:8877`（包装PID 70520、uvicorn子PID 75300）及Vite `127.0.0.1:5174`（`VITE_API_TARGET=http://127.0.0.1:8877`）。QA runner直GET health后独立对比`health.build.source_manifest`与当前磁盘，发现`backend/api.py` hash已漂移，**在启动Edge前fail-closed**。当时磁盘`backend/api.py` SHA-256为`86B1CAD97AA5A2154A63889591E9302EE76C53A7FD9D4D5ADEA04F5ACA5AECF7`；运行服务fingerprint为`sha256:78fc8d1994a5f50f95efaafef26c232d60da463ac80b117d44ccbf7617ff7ca2`。没有Edge、截图、创建Run、POST或shadow SQLite写入。
- E告知API冻结后重启，QA第2次在8877启动shadow（wrapper PID 58980、uvicorn child PID 39048，临时根`C:\Users\37813\AppData\Local\Temp\aetheris-r2-shadow-nlfc2r6w`），启动时source/disk hash一致=`sha256:90554cef98e21b67cc0876480929d03c32d21355a9cfb84a7737186e747baa87`。Edge门禁再发现另一处跨窗口源码漂移：`orchestration/r9_industrial_candidate.py` manifest=`ef040e2c0c0da4316e2f89591f7c2e46786c8a0980da97765602fe368e65d7f7d`，而当前磁盘=`98792d08d255732a9c9fa8cbad47737fce74164952381d9b4e9c0d4722816c28`。第二次仍在Edge启动前fail-closed；没有浏览器、截图、Run、POST或DB写入。
- 两次仅停止QA自己创建的shadow/Vite进程。结束后端口复核只剩旧服务8000 PID 59120、8001 PID 65000；QA未停止、重启或POST旧服务。隔离临时证据目录`C:\Users\37813\AppData\Local\Temp\aetheris-r2-shadow-bx8pmd4c`与`...\aetheris-r2-shadow-nlfc2r6w`保留runtime-manifest、空SQLite/目录和uvicorn日志，provider凭据为空。
- 另一次5174无可用前端时的URL预检返回HTTP 502，Edge没有启动；此为前置不可达，不是页面交互证据。清理后F只读GET已停止的8877返回502，与服务不在相符。最终端口检查仅8000/8001仍监听；8877、5174、CDP 9222无监听。
- F报告限定握手/欢迎页smoke的build/typecheck/Vitest已就绪，且页面meta可被本地重新计算验证；因E/C源码指纹门禁连续两次检测到运行版本与磁盘漂移，QA未启动Edge、尚未实测普通hello收发。A/B、跨会话、断线重放、来源卡及移动端全路径未做；A报告也未交付。
- 初步协议测试为契约oracle，不是生产代码或真实浏览器HTTP/交互证据；真实结果必须另行记录截图、health、fingerprint、run id、脱敏HTTP/SSE和错误分母。

## 5. 下一步

待A/C共享输入稳定并交付报告，E/C相关源文件停止修改；经主控批准后重启QA隔离shadow并再次确认source manifest一致，再做Edge限定smoke：

```powershell
python -B -m unittest tests.test_r2_browser_e2e -v
& .\scripts\r2_browser_e2e.ps1 -Browser Edge -ApiBaseUrl http://127.0.0.1:<E_PORT> -FrontendUrl http://127.0.0.1:<F_PORT> -Viewport desktop -OwnerApproved
& .\scripts\r2_browser_e2e.ps1 -Browser Edge -ApiBaseUrl http://127.0.0.1:<E_PORT> -FrontendUrl http://127.0.0.1:<F_PORT> -Viewport mobile -OwnerApproved
```

随后人工浏览器交互脚本增加普通聊天、专业A/B、同CID更正/异CID隔离、双SSE/重放、断线失败和来源抽屉断言。没有服务真实接入就不得把此阶段标记`GO_ISOLATED_OWNER_UI_TEST`。
