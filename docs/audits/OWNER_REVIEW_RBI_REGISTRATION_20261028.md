# Owner 复核：RBI 节点注册与 SSE 持久化（2026-10-28）

## 目标/边界

- 目标：验证 `AgentGraph` 执行表中的 `rbi_specialist` 确实注册，缺失时在建图阶段暴露；验证 SSE 首跑和事件重放路径。
- 合同：教师上游三工具、参数、返回壳、标准数据均不变。本轮只编辑产品 `orchestration/graph.py`、`tests/test_store_and_graph.py` 与状态/审计文档。
- 清理：依 `docs/OWNER_REVIEW_LAYOUT_AND_CONVERT_20261027.md` 的并发与审计要求，本轮不移动/删除/清理 `upstream/` 或其他目录。
- 回滚：只撤销上述产品代码/test/审计增量；不触及教师上游工作树与 Git 历史。

## 审查发现与修复

Owner报告中的快照认为 `AgentGraph.run` 排程含 `rbi_specialist` 而默认节点缺失。当前工作树初始复核时，默认构造列表已包括 `RbiSpecialistAgent()`；但缺少“路由 schedule 与节点注册必须一致”的显式不变量。此次新增 `ROUTED_NODE_NAMES` 和 `validate_routes()`：建图及运行前同时检查必需节点、order遗漏和dangling名称；缺项时 `ValueError` fail-fast，避免执行中 `KeyError` 并连带丢失 assistant 消息。新增 `test_graph_fails_fast_when_registered_nodes_do_not_cover_routes`。

节点实际分工仍为现有六个产品内部节点；没有注册第四个教师工具。API SSE链路复用现有持久化实现，不更改教师Harness。

## 实测命令/结果

1. 读取并核对：`AGENTS.md`、`docs/PROJECT_STATE.md`、`docs/OWNER_REVIEW_LAYOUT_AND_CONVERT_20261027.md`、`orchestration/graph.py`。
2. `python -B -m unittest discover -s tests -q` → **Ran 44 tests / OK**。
3. `python -B -m unittest tests.test_api_vertical_slice -v` → **3/3 PASS**：health tool set、创建对话/运行、SSE事件持久化与replay、assistant message、重连不重复执行、run内sequence、`schema_version/session_id/ts` 字段。
4. `git -C upstream diff --exit-code HEAD -- README.md 04_接口文档/工具接口规范.md 04_接口文档/技术指标验证方法.md 04_接口文档/enums.json 04_接口文档/risk_level_mapping.xlsx 05_提交区` → exit 0。
5. `git -C upstream status --short --branch` → `## master...origin/master`，干净。

## 文件变更

- 修改：`orchestration/graph.py` — 路由/注册一致性检查。
- 修改：`tests/test_store_and_graph.py` — 缺失路由节点时构造 fail-fast 回归。
- 修改：`docs/PROJECT_STATE.md` — 本轮实际状态与当前 suite 数。
- 新增：本报告。

Owner指出38项，但当前 `tests/` 磁盘实际收集到44项（含后来增加的语义、路由和SSE回归）；以实跑总数为准，未伪报38项。所有44项通过。

## 清理处理

未执行文件删除、搬移、`git rm`、`git clean`、`git reset` 或上游提交。上游原件、标准、样例、reference源码、渲染缓存和备份继续保留；任何整理等待当前开发阶段结束，并先生成路径/SHA/引用关系清单和可回滚归档包。
