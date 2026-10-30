# R2-E FastAPI / SSE / Runtime 交付审计

日期：2026-10-29。状态：`E_IMPLEMENTED / ISOLATED_PREFLIGHT_PASS / OWNER_BROWSER_E2E_PENDING`。本报告只记录E范围的API与隔离启动验证；不代替G最终集成验收。

## 范围与边界

修改：`backend/api.py`、`scripts/r2_service_shadow_run.py`、`tests/test_r2_api_contract.py`、本报告。未修改`upstream/`、真实SQLite、人审记录、生产密钥配置或8000/8001服务；未发起收费模型调用。API以默认`RULE_DEMO`启动隔离环境，专业模型候选/V2均关闭。

## 协议合同

- `contract_version = aetheris-r2.0.0`。
- `/api/health`返回`capabilities`：`runs_create`, `runs_sse_stream`, `runs_replay`, `run_input_snapshot`, `model_profiles`, `professional_guidance`, `file_upload`, `explicit_web_consent`, `conversation_history`, `conversation_memory`, `sensitive_web_consent_gate`, `run_idempotency_key`, `teacher_tool_count`。运行开关独立放在`flags`；教师工具仍为三项。
- `build_fingerprint`采用进程import时计算且缓存的`sha256:<64hex>`，不是每次health重新读当前磁盘。`build.source_files`提供固定排序源列表，`build.source_manifest`提供每个相对路径的SHA256，`build.python_version`记录运行解释器。算法：对按路径排序后的每项依次hash `relative_path UTF-8 + NUL + content_length(8-byte big-endian) + file_bytes`。源集不含前端bundle；前端独立指纹由F交付。
- 每个HTTP响应带`X-Aetheris-Contract-Version`及`X-Aetheris-Build-Fingerprint`。
- `RunIn`兼容`problem→question`、`device→equipment`、`device_type→equipment_type`、`operating_conditions→operating_condition`，冲突值明确422；原字段保留。
- Run创建支持`Idempotency-Key` header。以同一会话/key原子写入receipt、user message、queued run及附件关系；同请求重试回原`run_id`和`idempotency_replayed=true`，不同请求复用key返回409，同key跨CID不串。双SSE仍由SQLite lease/CAS只认领一次。
- `GET /api/runs/{rid}/events?after_sequence=`保留事件回放；SSE亦读取`Last-Event-ID`，并发送SSE `id: sequence`，`data:`仍为既有单对象安全投影。工具容量满时SSE返回429与`Retry-After: 2`，run仍留在queued，不以空Assistant消息伪报完成。

## 旧服务只读取证

命令：

```powershell
.\.venv-langgraph\Scripts\python.exe -B scripts/r2_service_shadow_run.py --probe-legacy
```

只GET 8000/8001 `/api/health`、`/openapi.json`、`/`及index所引用静态asset；通过Windows只读CIM/监听PID查询进程，不POST、不停止、不重启。

实测：

| 端口 | PID | Python/命令 | health | OpenAPI/静态前端 |
|---|---:|---|---|---|
| 8000 | 59120 | `D:\computer learning\Python learning\python\python.exe -m uvicorn backend.api:app --host 127.0.0.1 --port 8000` | HTTP200；无`contract_version`、无`capabilities` | `/api/model-profiles`不存在；无R2 idempotency Header；served JS `index-D6-mJH8m.js` SHA256 `877e2b63f36bd0cbbe28cfb908fbf2da3d86dc36b61ceee9b98868ec8b633ac1`，616154 bytes |
| 8001 | 65000 | 同一Python解释器、uvicorn `--port 8001` | HTTP200；无`contract_version`、无`capabilities` | model profiles存在但无R2 idempotency Header；served JS/CSS hash与8000相同 |

未导出模型API key；health只有provider/model metadata。进程与服务原样保留。

## Shadow启动和隔离

命令：

```powershell
.\.venv-langgraph\Scripts\python.exe -B scripts/r2_service_shadow_run.py --shadow --port 8878 --startup-timeout 45
```

实测Uvicorn PID `50916`，端口`127.0.0.1:8878`。TEMP隔离根：`C:\Users\37813\AppData\Local\Temp\aetheris-r2-shadow-9bust9jn`；SQLite为`shadow.sqlite3`，模型Profile与uploads均位于该临时根下。子进程的DeepSeek/OpenAI/Anthropic/Azure key环境项显式置空，避免仓库`.env.local`自动加载路径恢复密钥；候选DeepSeek与V2 flags关闭。健康合同为`aetheris-r2.0.0`，`flags.default_mode=RULE_DEMO`。

磁盘预期与真实Uvicorn health指纹均为：
`sha256:90554cef98e21b67cc0876480929d03c32d21355a9cfb84a7737186e747baa87`。

`--check-only`在握手通过后terminate的只是脚本启动的PID 50916，临时证据目录保留；未触碰8000/8001。`--hold`用于QA/Edge实际联调，Ctrl-C只停止本脚本的隔离子进程。

## 自动化测试

命令：

```powershell
.\.venv-langgraph\Scripts\python.exe -B -m unittest `
  tests.test_r2_api_contract `
  tests.test_v2_s25_sse_concurrency `
  tests.test_p13_local_load `
  tests.test_p4a_api_safety `
  tests.test_api_vertical_slice -q
```

实测`Ran 27 tests in 49.571s; OK`。P13本机mock负载：1/4/8并发各100 runs，`errors=0`；p50分别约131/204/399ms，p95约170/563/865ms。另有单独`tests.test_r2_api_contract` 5/5通过及shadow实际Uvicorn启动握手通过。无真实模型调用。

## 源码指纹

| 文件 | SHA-256 |
|---|---|
| `backend/api.py` | `86B1CAD97AA5A2154A63889591E9302EE76C53A7FD9D4D5ADEA04F5ACA5AECF7` |
| `scripts/r2_service_shadow_run.py` | `F2999178FBCF73C38970F1166DAA7DD1EA5D269C60B79DBFBCCF8DB2C66540EE` |
| `tests/test_r2_api_contract.py` | `D0356C699080E65088A1538DF420A46144745F47C7F84BCFACA102323A20F5B0` |

## 失败、未验证及交接

- QA先前在旧shadow PID `70520`上检测到health源码manifest与后续磁盘`backend/api.py`不匹配，按门禁拒绝浏览器。该版本未发送Run/写DB。随后E冻结源码；新check-only握手通过，fingerprint已更新为上述值。QA需停止自己启动的旧child并重新shadow启动，才能做真实Edge；5174前端进程归QA管理，E未操作。
- E自身尚无真实Edge截图/完整专业Run HTTP/SSE/UI闭环证据；不得据此标`GO_ISOLATED_OWNER_UI_TEST`。等待QA在同一冻结源码上完成浏览器E2E与其证据报告。
- 老测试`tests/test_p0_expert_guidance.py`有精确断言旧`aetheris-2026-10-29-p0.1`。切R2统一版本后这些断言预期需在最终集成层按新合同更新；E遵守文件所有权未修改该旧测试。
- 人工来源适用性、专业Gold、真实模型预算验证仍未完成；E交付不改变生产NO-GO。
