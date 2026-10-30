# R8-B OSS 来源与许可证清单

审查日期：2026-10-28。仅将以下第一项依赖直接用于应用；其余仓库作为交互/架构参考，没有复制源文件、图标、品牌或组件代码。

| 项目 | 锁定版本 / 源 commit | License | 本项目使用方式 | 来源 |
|---|---|---|---|---|
| `@assistant-ui/react` | npm lock 实际解析版本 `0.15.32`; upstream `main` 快照 `b6b10672ef896e2deaf1603e7414ef0142943e9e` | MIT | 已有 Thread/Message primitives；R8-B 将会话列表接入 `useExternalStoreRuntime` + `ThreadListPrimitive` | [npm package](https://www.npmjs.com/package/@assistant-ui/react), [LICENSE](https://github.com/assistant-ui/assistant-ui/blob/main/LICENSE), [docs](https://www.assistant-ui.com/docs/api-reference/primitives/thread-list) |
| `langchain-ai/agent-chat-ui` | `main` 快照 `7a503412aeeb4534a24b04bd97b618ee3871821e` | MIT | 仅参考 LangGraph 流事件/聊天工位布局；未拷贝代码或组件 | [repository](https://github.com/langchain-ai/agent-chat-ui), [LICENSE](https://github.com/langchain-ai/agent-chat-ui/blob/main/LICENSE) |
| `vercel/chatbot` | `main` 快照 `c2f8235e1f3ea903ad8b7f61447c4f74164b5c58` | MIT（该快照 LICENSE 文件） | 仅参考会话列表、输入区和消息导航体验；未复制 Next.js、Postgres、身份或模型代码 | [repository](https://github.com/vercel/chatbot), [LICENSE](https://github.com/vercel/chatbot/blob/main/LICENSE) |
| `open-webui/open-webui` | 未固定/未引入 | 版本相关；官方说明 `v0.6.6+` 为 Open WebUI 自定义许可 | 只研究附件交互，不复制代码；不作为依赖 | [official license note](https://docs.openwebui.com/license/) |

## 代码来源声明

- 直接 OSS 运行时依赖仅是当前 package lock 中已存在的 assistant-ui；本轮未新增生产依赖、未迁移 Next.js/PostgreSQL。
- `ConversationThreadList.tsx` 使用该 MIT 库公开的 React primitives API，不复制仓库源码。
- 上传、SQLite schema、文件安全路径、Run 快照、对话工作台视觉与交互为本项目实现。
- MIT 许可证文本来自各项目 GitHub LICENSE 文件；第三方参考仓库只引用链接/commit，不含其源代码副本。开源许可证不等同于本项目的部署许可或产品审核。
