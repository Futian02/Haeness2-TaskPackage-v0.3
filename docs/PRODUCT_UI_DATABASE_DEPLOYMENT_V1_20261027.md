# Doubao式多智能体研判台｜本地Web、数据库、部署方案

## 1. 功能层次
主入口不是一屏JSON，而是完整Web应用：
- 左栏 260px：新建会话/最近会话/历史查询/收藏的设备案例；换浏览器标签或刷新仍有会话。
- 中心：气泡聊天、流式答复、Markdown/引用卡、附件只读预览（初期仅原本允许分享的标准出处，不允许任意上传收费PDF）；底部多行输入、模型/模式选择、停止生成。
- 右栏 340px：**任务执行时间线**；Supervisor/Evidence/Diagnosis/Verifier/Reporter 节点的start/end/状态/耗时、工具入参与合法返回、引用条款可展开、谁反对了哪个机理、缺什么现场测量。
- 展开“证据抽屉”：每个clause引用原文`content_raw`（版权注意只给必要短摘录）、标准号、条款号、印刷页、材料/介质/温压边界、reviewed状态。 PDF页高亮定位只在本地及使用权限允许时支持。
- 页面切换：Chat / CaseLibrary / KnowledgeLab / Evaluation / Settings。先只落地Chat + History + Trace，其他页后置。
- UI主题：专业工业控制台的安静视觉，奶白+深蓝灰、局部柑橘橙提示未决证据；优先响应式，长trace用抽屉避免干扰聊天。
- 显示的是**公开的决策摘要与工具轨迹**，不能泄露模型隐藏推理。被护栏拦截也应展示事件和原因。

## 2. 开源UI决策
默认 React/TypeScript + [assistant-ui](https://github.com/assistant-ui/assistant-ui)做消息、线程、流式、工具卡；Tailwind/shadcn/ui统一设计Tokens。Agent多角色事件来自FastAPI SSE/WebSocket；UI不会直接持有模型key。
以后如果需要双向agent-UI标准状态同步/审批/动态组件，再研究[CopilotKit](https://docs.copilotkit.ai/langgraph-python)的AG-UI；不在V1同时重装两套客户端runtime。

## 3. 数据库：SQLite优先，MySQL可迁移
不要求朋友安装MySQL。**SQLite（WAL）**简单、跨平台、易备份，几个人本机demo充分；SQLAlchemy/SQLModel的URL隔离存储实现，生产需要多实例后可切MySQL/PostgreSQL。
基础表：
`users`（如公开部署仅测试账号则需认证或访客隔离）
`sessions(id,owner_id,title,created_at,updated_at)`
`messages(id,session_id,role,content,created_at)`
`runs(id,session_id,status,mode,started_at,ended_at,total_ms,model_calls,token_in,token_out)`
`events(id,run_id,seq,type,agent,payload_json,created_at)`
`evidence_refs(id,run_id,clause_id,standard_code,clause_no,page,review_level)`
`knowledge_versions(id,source_file_sha,extractor_rev,card_rev,reviewed)`
Agent图checkpoint应通过LangGraph SQLite checkpointer独立存，业务表负责查询/会话重放，两个写操作需要设计幂等run_id防止重复。
敏感信息不公开、定期备份+清除，不存Chain of Thought或原始密钥。

## 4. 端到端事件与用户体验
SSE消息格式`{schema_version:1,event_id,run_id,session_id,ts,type,agent,payload}`；
`run_started → agent_started → decision_summary → tool_called → tool_result → source_attached → verification → text_delta → run_completed`，异常`error`须带可公开的错误码和可恢复指引。
要求可取消、客户端断线提示“仍在运行/已停止”、重连后根据数据库seq回放历史，不能重复触发同一run；P0只需最小正确实现。
执行进度显示状态而不是百分比虚假预测，不把规则demo标成真实LLM协作。

## 5. 免费部署选择（核实限制后再发布）
**路径A：本机 localhost 完整验收**：FastAPI(8000) + Next(3000) + SQLite，本地浏览器UI先跑通。仅本机访问，不开放设备控制功能。
**路径B：自有域名/低成本演示**：[Cloudflare Tunnel](https://developers.cloudflare.com/tunnel/get-started/)可通过`cloudflared`将本机或朋友能长期运行的主机服务安全映射到自有域名，不需公网IP/入站端口。它是**网络入口，不是免费计算服务器**：本机/服务器必须在线。公开前必须有身份认证/限速/密钥隔离；不要直接给匿名公网公开内部PDF与历史会话。
**路径C：老师的ModelScope创空间**：保留原Gradio页面满足指定验收；与完整React网站可作为两个独立交付入口。创空间免费/资源配额与数据持久性需在使用时按官方当期规则核验，不能假定免费持久盘。
**路径D：免费应用实例/免费数据库**：比如 Render Free实例可运行Python，但其免费Web服务无持久磁盘、可能休眠/重启，免费Postgres默认有有效期，不适合不加外置DB就直接保存重要会话；具体限制见https://render.com/docs/free。其他Oracle云/外部赠送免费资源因可用性、银行卡/验证和配额不稳，暂不宣称可部署。
**最终域名/DNS选择要经用户确认后再动**；此轮没有操作域名、认证、在线服务。

## 6. 安全和性能
API密钥只在服务器env，Web不接触；服务端身份认证/用户会话隔离、速率限制、SSE断连容错、日志脱敏、输入长度与附件大小限额，审查标准版权；默认无工具可以执行系统操作、联网私有资源或修改设备。
性能记录：TTFT、全响应P50/P95，Graph各节点模型Token与耗时、检索与OCR负载；通过提前构建缓存、并行只读检索、选择性审查、限制LLM迭代来优化。5节点不等于5次模型调用，更不等于每个问题要5步。
