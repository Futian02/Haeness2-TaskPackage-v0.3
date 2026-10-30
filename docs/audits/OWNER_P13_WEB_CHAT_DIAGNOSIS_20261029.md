# P13 Owner 独立故障复盘：联网、机理候选、空回答与多轮对话（2026-10-29）
状态：ROOT_CAUSES_IDENTIFIED / REPAIRS_NOT_APPLIED。**本轮仅新增诊断脚本和文档。未改应用核心代码、教师三工具/PDF/Excel、真实SQLite或模型密钥；不发付费API请求，不重启当前服务。**

## 验证依据与复现
1. **真实运行环境版本漂移（确定）**：`127.0.0.1:8000`监听进程 PID 59120，启动于2026-10-28 21:54:56；浏览器正在连它。实时`GET /api/health`=200，但`GET /api/model-profiles`=404；最新版磁盘`backend/api.py`包含该路由，离线FastAPI route枚举23条含此路径。实时health里llm字段仅`configured/model/provider`，新源码还应有`profile_id`。**必须先在不破坏用户DB/正在运行任务的条件下正常停止并重启FastAPI，然后重新核对路由/端到端。** 不能认为重启就解决全部问题，后面缺陷是源码仍存在。
2. **真实SQLite只读审核**：`data/haeness2.db`共65 run，60 completed、3 failed、2 queued。3个fail都是HTML/SVG骑车动画相关，`error`事件`RuntimeError: DeepSeek 返回空内容`，助手消息0条。截图相关DEEPSEEK run`0747fe77` question含`介质:[碱式酸性水]`但实际保存material=''、medium=[]、缺`context_resolved`；P12新代码的同类RULE_DEMO run保存正确material+medium，候选`酸性水腐蚀(碱式酸性水)`。版本漂移是这张图的首要原因之一。
3. **后端空内容错误与前端吞失败（确定）**：`backend/deepseek.py::generate_chat()`只读取`choices[0].message.content`，遇`None/''`一律报`DeepSeek 返回空内容`；既不记录`finish_reason`，也不记响应`usage`，无法判别token预算、content_filter、空thinking输出。普通聊天固定`max_tokens=900`且不传`thinking`，按DeepSeek现行API thinking默认启用，较复杂代码请求易存在token budget不足可能，**尚未从真实供应商响应证实具体finish_reason**。离线mock`finish_reason=length/content=null`成功复现同一RuntimeError。
  `frontend/src/api.ts::readSse/consumeRun`将`error`视为terminal正常返回，不throw；`App.tsx`仅在网络异常的catch里setError，未渲染失败run的inline error卡。离线FastAPI→SSE→SQLite模拟证据：status failed、SSE HTTP200、事件`context_resolved/phase_started/llm_started/error`、assistant_messages=0，复现“模型像没回复”。
4. **普通对话失去多轮上下文（确定）**：`generate_chat(question)`每次只发送1条system和当前1条user，不带同会话最近轮次和失败事件摘要；离线mock`怎么回事`请求messages用户列表确实只有“怎么回事”，没有前一轮HTML/SVG任务。应从同会话SQLite获取最近8–12轮经授权、按token有界的普通聊天历史与上一失败run的可见状态；跨会话严格隔离，敏感工程详情不无意转发。
5. **历史工程工况污染意图（确定）**：`orchestration/intent.py::classify_intent`中`if c.material and c.medium -> engineering`位置过早。13组诊断确认，在旧材质/介质上下文下`今天的天气如何`、`创建HTML动画`、`什么是图灵机`均错误归类工程；需先以当前utterance判断是否为独立general_chat，再利用历史工程槽位补全明确的工程追问。优先顺序：当前明确任务意图>历史工程上下文；“那怎么检测”这样有指代的才可沿用。
6. **partial context机械拒答（设计缺口）**：`orchestration/r9_industrial_candidate.py::route_task`有missing material/medium直接报告，工具调用0、假设0，只有needs_user_input。适合不得确定性RBI风险L级，但不适合“列出可能腐蚀类型并说明典型条件”。建议增加`hypothesis_exploration`模式，以官方`standard_clause_search`在部分/无条件下检索知识库已有候选，再按**可核条件与来源覆盖程度**排序，标“可能方向/适用条件未核/缺什么现场证据”。不得用1–100%这种未经校准概率冒充真实置信度。风险等级仍严格门禁。
7. **括号符号污染检索（确定）**：`backend/context_slots.py::_value`的`介质：[碱式酸性水]`解析为`['[碱式酸性水]']`，传到`damage_mechanism_query`无法与枚举匹配。13组诊断：精确写法→2工具/1候选/1出处；带方括号→2工具/0候选/1泛标准出处。应strip合法包装符号、逐项匹配`enums.json`，未经确认非枚举不得冒充已有机理；JSON array形式也要处理。
8. **现有模型无联网工具（确定）**：`backend/deepseek.py` payload无`tools`、`web_search`或自有搜索调用，当前`DEEPSEEK`=普通聊天+结果整理，不是内置自动搜索或自主工具使用。DeepSeek官方2026文档`https://api-docs.deepseek.com/guides/search/`支持独立`/v1/tools/search`与`/v1/tools/fetch`；`https://api-docs.deepseek.com/api/create-response/`描述内置`web_search`仅支持`deepseek-v4-pro`，并非当前`deepseek-flash`的聊天请求自动具备。内部建立`WebSearchService`，作为应用外部资料工具，不要改老师冻结的3个正式工具及统一5键返回。时间/天气城市未指定要询问地点，不推断当前位置。
9. **另一条后端业务空耗**：`backend/api.py`当前工程模式调用`generate_report`，但模型改写的`llm_answer`仅进`llm_completed.summary`折叠活动，不代替正文；可导致花token只生成调试摘要。建议让模型在结构化候选/条件/引用门禁下生成经验证的简洁专业答复，失败时安全保留本地已核结果而不把整Run判失败；普通聊天失败则给显式错误卡+重试，不虚构回答。

## 已运行测试
- `./.venv-langgraph/Scripts/python.exe -B -m scripts.audit_p13_dialogue_diagnostic` 13组场景（天气、代码、概念、历史工程污染、工况缺失、显式工况、介质方括号、自然语言、标准、风险、追问）；附两次模型离线mock及一次FastAPI/SSE/SQLite隔离临时库E2E。
- 当前`./.venv-langgraph/Scripts/python.exe -B -m unittest discover -s tests -q`：156 tests, OK (3 skips)，**旧测试全绿并不能覆盖这次的缺口**。
- 不打印真实密钥、敏感聊天全文；不对已存在的历史Run回写。

## 修改优先级与收工线
**P0（一天/单轮修完即可）**：重启并验证最新版backend路由；LLM终态分层`finish_reason/token_usage`与超限错误；frontend`error`转可见失败卡（每个失败run）+重试；`generate_chat`多轮历史；高优先通用意图防旧工况污染；`介质:[...]`标准化。专项用19个真实失败/反例测试。
**P1**：`hypothesis_exploration`条件性候选+证据排名，独立网络搜索工具（用户主动允许、带URL来源、时间与能耗），网页搜索来源不能成为老师标准条款/工程安全断言的权威依据。
**P2**：实际供应商小成本真实20题（需Owner明确授权收费）验证finish_reason、1000+字HTML代码返回、普通天气指定城市、连续追问、工况排序；生产合格需明确真实调用数、token、成本、延迟P50/P95。外站必须先做用户身份、权限与密钥隔离。
**不能因本轮离线复现就声称已经修复实际客户端故障或上线联网。**
