# R9-B 开源许可与来源清单

更新：2026-10-28。本清单对应本轮隔离组件与 Phoenix 本机验证环境；不是对后续整产品发行包的最终法律审查。

## 直接复用 / 新增的核心项

| 组件 | 版本/来源 | 许可 | 处理 |
|---|---|---|---|
| `@assistant-ui/react` | 0.15.32（项目已有） | MIT | 复用 `MessagePrimitive.GroupedParts` / `groupPartByType` / runtime primitives；本轮没有改 package manifest 或 lockfile。 |
| assistant-ui shadcn registry UI | 官方 `elements-reasoning`、`elements-tool-group`、`elements-tool-fallback`、`elements-collapsible` 源码；上游 `assistant-ui/assistant-ui` HEAD `b6b10672ef896e2deaf1603e7414ef0142943e9e` | MIT | 直接复制并局部桥接为 `frontend/src/components/trace/` 下的 React 组件；完整 MIT 文本放在 `ASSISTANT_UI_LICENSE.txt`。 |
| `arize-phoenix` | 20.26.1 | Elastic License 2.0（ELv2；不是 OSI 开源许可） | 仅隔离 venv 与 localhost 开发者验证；不把 Phoenix Web UI/服务代码嵌入聊天 UI、不随产品分发。发布或托管 Phoenix 前需单独审核 ELv2 条款。 |
| `arize-phoenix-otel` | 0.17.2 | Apache-2.0 | 用于官方 Phoenix OpenTelemetry exporter/register。 |
| `openinference-instrumentation-langchain` | 0.1.80 | Apache-2.0 | 隔离 harness 使用官方 OpenInference LangChain Instrumentor，并配置 hide input/output。 |
| `openinference-instrumentation` | 0.1.72 | Apache-2.0 | `TraceConfig` 输入/输出脱敏。 |
| `opentelemetry-api`, `opentelemetry-sdk` | 1.45.1 | Apache-2.0 | span 构建、上下文、导出与测试 exporter。 |
| `langchain-core` | 1.2.19（仅 observability 隔离 venv） | MIT | 为 OpenInference LangChain smoke harness 提供 Runnable；不加到产品依赖。 |

运行时组件源码使用的 `lucide-react`、Radix primitives、`class-variance-authority`、`clsx`/tailwind merge 来自现有前端依赖；本轮未新增任何 npm 依赖。完整隔离 Python 锁文件：[`observability/requirements.lock.txt`](../../observability/requirements.lock.txt)。生成时隔离环境共 157 个 Python distributions，完整 metadata 清单和版本见 [`python-license-inventory.json`](R9B_RUNTIME_EVIDENCE/python-license-inventory.json)；该清单按安装 metadata 的 License/License-Expression/Classifier 提取，仍需在产品发行前用正式 SBOM 与版权文本复核。

## 明确排除

- Langfuse：未安装、未配置、未启用。
- Phoenix UI 源码：未复制、未嵌入产品。
- assistant-ui 的 legacy `ChainOfThoughtPrimitive`：未用；使用官方 `MessagePrimitive.GroupedParts` 和 typed reasoning/tool parts。

## 许可依据

- [assistant-ui 官方文档：Chain of Thought](https://www.assistant-ui.com/docs/guides/chain-of-thought)
- [assistant-ui 官方文档：Part Grouping](https://www.assistant-ui.com/docs/guides/part-grouping)
- [assistant-ui 官方 Reasoning](https://www.assistant-ui.com/elements/reasoning)、[Tool Group](https://www.assistant-ui.com/elements/tool-group)、[Tool Fallback](https://www.assistant-ui.com/elements/tool-fallback)
- [assistant-ui 上游仓库](https://github.com/assistant-ui/assistant-ui)
- [Arize Phoenix 仓库许可](https://github.com/Arize-ai/phoenix/blob/main/LICENSE)
- [Phoenix OpenTelemetry SDK](https://github.com/Arize-ai/phoenix/tree/main/packages/phoenix-otel)
- [OpenInference Instrumentation](https://github.com/Arize-ai/openinference)
- [OpenTelemetry Python](https://github.com/open-telemetry/opentelemetry-python)

