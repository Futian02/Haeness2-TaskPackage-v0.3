# Codex Luna High｜P2 有界任务：RBI1 标准表补录、质量签核、LangGraph路线验证
日期2026-10-28。**仅在当前 Codex R1任务结案后开启本任务**，不要并发写同一老师XLSX。完整权威参考：本机 `AGENTS.md`、`docs/audits/RBI_OWNER_SOURCE_AUDIT_20261028.md`、`scripts/audit_rbi1_quote_candidates.py`、老师`convert.py`与PDF。

## 目标1：源表补录（不能伪审核）
- 原表路径`upstream/01_RBI标准/条款摘录表_RBI.xlsx`。现有472条已填，绝不从空白格式行判断“还缺130条”。重点补源PDF`GB/T 26610.1-2022`先前0条的13条候选。
- 本机脚本`python -B -m scripts.audit_rbi1_quote_candidates`机器文本匹配13/13；必须人工核原PDF印刷页与源码`content_raw`逐字、标题、条件，未核字段标needs_review。
- 在独立工作副本/分支做 **非破坏性**追加：23列模板标题/列顺序不变，`clause_no`文本，引用ID`GBT26610.1-2022-...`，不填想当然risk、period、material、temp。若真实“抽取人”或独立“复核人”身份未知，**不能假定并填造姓名**；留空并保留草稿，不接入官方JSONL。
- 不要让AI的机器文本匹配冒充50条人工PDF审核。页码是原标准印刷页非PDF阅读器索引。
- 通过真人核对后，隔离输出跑`convert.py --inputs [原RBI1新增+原RBI+原DM校准的工作副本] --output [非生产文件]`，确认13条新增无重复且原554无无关改动，最终再由Owner审核并入正式源表/JSONL。不能将未核草稿直接提交。

## 目标2： LangGraph环境预检与迁移基线
- 现有`orchestration/graph.py`是可插拔的确定性六节点调度器，但主体是Python的for循环和route判断，尚不等同于官方LangGraph `StateGraph`运行时。老师的Harness保持原状。
- 现系统已安装`langgraph==1.1.2`, `langchain-core==1.2.19`, **旧版`tenacity==5.1.5`**，Python 3.11.9；新示例`python -B -m scripts.langgraph_state_routing_demo`触发`asyncio.coroutine`已删除造成导入异常。请在**隔离虚拟环境**解决依赖，不要更改全局Python或monkey patch，锁定依赖、提供pip check/最小例子运行结果，并保留原项目可回退。
- 使用官方`StateGraph`对现有 six-node graph 做逐节点移植，不允许把每个节点变成无输入输出的装饰。路由采用`add_conditional_edges`，missing context/OOD必须**跳过**工具节点；真正风险条件不足应到补证据/报告，不调用RBI判级；保留`RunState`字段和SSE的既有事件协议。
- 保留SQLite业务事件日志，另隔离LangGraph checkpoint存储，区分两者职责。模型缺key时只标 RULE_DEMO，不宣称真实multiLLM。
- 别写两个同时生效的static+dynamic边；审查环需要最大循环次数和终止条件；并行Agent更新同一State字段需显式reducer。
- 验收：2种用户输入（材质/介质缺失 vs 完整）的不同路由，PDF核实13条草稿，完整单元测试、真实SSE/持久化回放、官方validate --final、工具合同干净；性能基准保持可对照。
- 交付`docs/audits/P2_RBI1_LANGGRAPH_EVIDENCE.md`：文件变更清单、命令、通过项、blocker与人工待核清单；停在READY_FOR_OWNER_REVIEW。

禁止删除/重排教师原PDF、XLSX、备份、reference_code；不对父级仓库git clean/reset；不改工具三签名、标准原文、风险映射、输出五键。
