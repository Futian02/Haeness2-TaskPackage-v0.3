# P13 Web Search service 接口备忘

状态：`READY_FOR_OWNER_REVIEW`（搜索 API/SSE/前端已接线，Edge真实浏览器模式选择与Run快照回放已验证；20个mock transport场景通过，真实公网 Search/Fetch 未验证）。

## 用途和边界

- `backend/web_search.py` 提供应用内部 `DeepSeekWebSearch.search()` / `fetch()`，不是 LangGraph 老师工具；不修改 `damage_mechanism_query`、`rbi_lookup`、`standard_clause_search` 或五键协议。
- `enabled=False` 是默认值。每次调用都要调用方显式传 `enabled=True`；敏感工程内容另需 `sensitive=True, allow_sensitive_outbound=True` 双重显式授权，否则在网络前拒绝。
- 搜索/抓取结果是外网资料，不等于老师标准条文或经审核的工程证据；统一带 `source_scope=external_web_not_teacher_standard_authority`、来源URL、标题、取回时间、片段/摘要及原始发布时间（如有）。不得将其包装成 `standard_clause_search` 的返回。
- 天气/气温查询没有用户明确给出的地点时以 `location_required` 失败返回；服务不访问 IP、浏览器定位或任何本机位置。
- 单次操作默认最多1次外部请求、最长8秒；服务硬上限单操作2次/20秒、搜索最多5条/每条最多2000字符；错误做分类并去除供应商响应体和异常字符串。
- 仅固定官方 HTTPS host `api.deepseek.com` 接收 `DEEPSEEK_API_KEY`，避免 bearer secret 被误发到可配置任意地址。自定义离线 transport 只为测试注入。

## 调用形状

```python
from backend.web_search import CallBudget, DeepSeekWebSearch, SearchError

service = DeepSeekWebSearch()  # reads DEEPSEEK_API_KEY; performs no request here
try:
    result = service.search(
        "公开主题", enabled=user_enabled,
        sensitive=False, count=5, budget=CallBudget(max_calls=1, timeout_seconds=8),
    )
except SearchError as exc:
    # expose only exc.code / safe message; never provider body
    ...
```

如涉及设备台账、真实运行参数、事故信息、用户/企业名称或其他敏感字段，调用者必须将 `sensitive=True`。该默认防护是应用层防护，不代替前端开关与后端鉴权；在请求中使用安全的通用查询词，不要原样上传工单/设备全文。

## 官方协议核对（2026-10-29）

已查看 [DeepSeek Search & Fetch 官方 API 文档](https://api-docs.deepseek.com/guides/search/)：Search 为 `POST https://api.deepseek.com/v1/tools/search`，请求字段 `query`/`count`/`need_content`；Fetch 为 `POST https://api.deepseek.com/v1/tools/fetch`，body 为 `url`；使用 bearer key + JSON。文档列出 Search 与 Fetch 成功调用按次计费，费率与账户/日期条款可能变化。**当前没有真实调用，未验证本账户计费、响应变化、配额、服务可用性或真实来源质量；Owner 允许真实调用并核查费用前不要将联网按钮默认打开。**

## 验证

专项测试 `tests/test_p13_search_service.py` 使用注入的 fake transport，验证关闭默认、敏感外发双重 opt-in、地点缺失、URL 过滤、固定官方 endpoint、来源元数据、预算与错误脱敏。测试不会建立 socket，也不会消费 API key/额度。

产品接线：聊天栏提供 `off/auto/on`；`auto` 仅在明确的公开时效问题触发，`on` 执行公开查询；服务端将 web_mode 写入 Run 上下文并在 `context_resolved`、terminal事件和运行快照中保留。Search来源元数据显示在回答与事件中；真实浏览器回放证据见 `evidence/P13/P13_browser_interactions.json`。所有网络调用仅做fake-transport测试，真实Search/Fetch及计费/可用性仍待Owner明确授权后验证。
