# Codex S3-B｜三值逻辑机理适用性引擎与独立离线评测
本机工作目录：`D:\作业\竞赛\计算机设计智能体\机械智能体`，直接使用本机文件与终端；没有本机D盘权限则报告LOCAL_EXECUTION_ENV_MISMATCH，停止，不自动启用远程连接器。

先完整阅读`AGENTS.md`、`docs/PROJECT_STATUS_CURRENT.md`、`docs/S3_DM82_APPLICABILITY_RESEARCH_AND_ENGINEERING_SPEC_20261029.md`、`docs/data_quality/DM_APPLICABILITY_ROOT_CAUSE_AND_REFORM_20261029.md`、`orchestration/agentic_v2.py`及教师3工具合同。S3-A候选源可能尚未完成：**以Schema固定和纯合成fixture单元测试先行**，不修改A的候选文件；等A完成再独立输入读取，不能猜哪些条款已获人审。

**独占可写**：`knowledge/applicability/schema_v1.py`、`orchestration/applicability_v1.py`、`tests/test_s3_applicability_v1.py`、`docs/audits/S3_B_*.md`；不得编辑`backend/execution_ledger.py`、`orchestration/agentic_v2.py`、`backend/api.py`或其他S2.5可靠性窗口文件；不修改`upstream`与教师任何正式数据、签名、真实SQLite及模型密钥。

任务:
1. 用Pydantic定义可版本化Predicate/SourceRef/DeviceFact/ApplicabilityResult，精确区分壁温/介质温、气体分压/总压、材料易感性/耐蚀描述、运行阶段、环境作用侧与子机理适用范围；禁止模糊`temp`和`pressure`不带对象。unit类型与关系符严格校验；未知值使用null+unknown，而不是默认0。
2. 实现Kleene三值比较与复杂AND/OR**必要条件**，只在真实confirmed fact与明确硬必要条件矛盾时对同一子型输出EXCLUDED_WITH_CONFIRMED_CONTRADICTION；来源无PDF审定、仅候选自动提取时不得硬排除整条机理。保护性role不能当必要负条件。
3. 输出`SUPPORTED_WITH_CONDITIONS`,`POSSIBLE_NEEDS_EVIDENCE`,`EXCLUDED_WITH_CONFIRMED_CONTRADICTION`,`NOT_ASSESSED`，每条附支持、反证、未知、source_ids/clauses和需补测优先级；风险等级永远不由此模块生成；与老师RBI等级/检验周期分离。
4. 支持shadow-only诊断API（本地Python函数，不新增第四教师工具），对既有工具结果**增加**可解释注释，不在没有人审/Owner批准前删除官方工具候选；模型/用户输入中的`ignore policy`都只能作为普通文本。
5. 使用≥35条合成正/反/未知/prompt-injection/角色混淆fixtures验证True/False/Unknown、不误硬排除、来源缺失、冲突子型、单位互换、材料防护、未确认工况、缺PoF/CoF不生成风险数值；另加property-based或确定性边界测试有益。
6. 不宣称synthetic通过=专业正确率。给评测后续owner合并使用的数据适配器与性能指标：Critical Hazard Recall@K、False Exclusion、Unknown Calibration、Unsupported Assertion、p50/p95耗时；gold未独立人审时标BLOCKED。
7. 运行专项、既有Aetheris regression、teacher validate554/200/17原合同只读，记录真实PASS/FAIL；出`docs/audits/S3_B_CONDITION_ENGINE_REVIEW_20261029.md`与S3-A字段冲突清单，不自动接默认图。

注意：S2.5正在修可靠性，必须严格遵守共享文件所有权。若发现根本性的语义假设问题，先写报告与独立失败fixture，不能为了跑绿改教师数据或替换历史人审。
