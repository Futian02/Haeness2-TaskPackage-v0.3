# P16-C 定向续修验收记录

日期：2026-10-29  
状态：`PREVIEW_ONLY` / `READY_FOR_OWNER_REVIEW`（真人审签与 Owner 放行仍 BLOCKED）

## 范围与边界

先读取并遵照：

- `docs/data_quality/OWNER_P16_LIVE_HANDOFF_AUDIT_20261029.md`
- `docs/CODEX_P16_FINAL_BOUNDED_CORRECTIONS_20261029.md`

本轮只改 P16-C 文件：`scripts/p16_c_machine_gate.py`、`scripts/p16_c_prepare_human50.py`、`tests/test_p16_c_human50_gate.py`、`work/data_staging/p16/C_GATE/**` 和本报告。未改 A/B 产物、教师三个工具、上游 Excel/PDF、正式 JSONL、真实审签记录。没有生成、补写或冒用任何真人签名。

## 修正内容

### 1. Gate 状态优先级

- 新增 `machine_status(checks)`：任何机器完整性 `FAIL` 优先于 `BLOCKED`。
- 报告字段拆分为 `machine_integrity_status` 和 `human_release_status`，另保留汇总 `status`。汇总 FAIL 优先；机器/人工条件未满足则 `BLOCKED_PENDING_HUMAN_REVIEW`。
- 真人门禁不再读取 manifest 中的 `human_signed` 常量作为通过依据，也不把签名字符串非空视为真人。要求双人独立签署、Owner 公钥指纹通过进程外固定、Owner 签名的 reviewer identity registry、事件签名、抽样冻结哈希、PDF/渲染证据哈希、签名审阅事件哈希及 Owner release approval。所需可信材料目前不存在，因此真实状态为 BLOCKED。
- 统计字段来自被验证的事件：随机审查 `0/50`，A 修改对象审查 `0/42`，verified reviewer `0`，Owner approval `false`。阈值 `>=48/50` 和 `42/42` 已编码为独立规则；达到数字仍不能绕过身份与 Owner 审批。
- PDF 检查现在验证真实 PDF 页数、`0 <= page_index < page_count`、PDF SHA、渲染图片 SHA，并将机器页图存在与原文视觉正确性分开。
- A窗口42条的源PDF页索引与多页图像清单也逐项校验：42/42条目、页码边界、PDF哈希、每页PNG哈希均匹配冻结快照；不把A清单里的PDF哈希误当PNG哈希。
- RBI 原始 XLSX 与官方 JSONL 加入记录基线 SHA guard，异常会作为机器 FAIL，而不写死 `official_files_modified=false`。

### 2. 固定随机50条与源绑定

- 新的不可变快照：`work/data_staging/p16/C_GATE/P16_C_SAMPLE_FREEZE_V4.json`（V1–V3作为本轮演进历史保留；正式门禁仅读取V4）。
- 对照 P15-C `P15_C_HUMAN_REVIEW50.csv` 的 50 个 `clause_id` **逐条、逐序**比较；另核 seed、唯一性、源CSV SHA、导出索引 SHA、顺序ID SHA、P15候选 JSONL SHA、官方 JSONL SHA及 locator 清单 SHA。
- 50个 ID 与 seed=20261029、源CSV哈希绑定。独立反例保持 50 行和 seed 不变，仅替换第18条 ID，门禁明确 FAIL，首个错位定位为第18条。
- 原有人工表 `P16_C_HUMAN50.csv` 和 `P16_C_HUMAN_REVIEW90.csv` 没有被重写；机器数据另存为 `P16_C_MACHINE_SAMPLE_INDEX.csv`、`P16_C_MACHINE_REVIEW_SCOPE90.csv`、`P16_C_MACHINE_PAGE_LOCATORS.csv`。

### 3. 防覆盖及真实审签

- 准备脚本不再向人工 CSV 写入。重跑可更新机器侧定位/索引，但对已存在冻结清单仅允许相同的源/ID/候选/官方/locator 哈希；不一致则拒绝覆盖。
- 已存在的证据卡若与新生成内容不同（可能含人工批注），准备脚本拒绝覆盖；只在目标不存在时以独占创建方式写入。
- 签审流程设计为独立事件 JSONL + Owner 可信身份注册表 + 进程外 pin 的 Owner 公钥指纹 + 单独 Owner 放行签名；审签事件需签入 clause/scope/结论/时间/冻结哈希/PDF哈希/渲染哈希。每个对象至少两位独立审核者，结论冲突阻断。纠正后以 `CORRECTED_AND_REVIEWED` 明确记录，不以“已改”自动算复核。
- 所有模拟审签只在 `TemporaryDirectory` 内的单测 fixture 中运行，fixture 验证器被 mock；没有写进 C_GATE 人工表或正式数据。

### 4. 统计与源文件核验

- P15-C随机样本：50个唯一条款；精确顺序匹配。V4绑定P15原始样本、机器索引、P15候选/官方JSONL、随机样本页图定位和A的42条多页证据哈希。
- A修改核验对象：42个唯一 clause_id、73个单元格；与随机样本重合2项；合并为90个唯一核验对象。
- 人工进度：随机 `0/50`；修改对象 `0/42`；签名及身份验证 `0`；Owner release approval `0`。历史表中目前没有人工字段值。
- 官方源快照：RBI XLSX SHA-256 `e43f7b0d3381a38fa648c2505e27d1c87893af5aea89aa119097dbfc49c6b7bf`；`clauses.jsonl` SHA-256 `a8151797ba15a6a7452dd83aaec9fab4c0a815724ca45062eb1e2bac7b4d49ef`。与本轮记录的基线一致。
- 机器完整性 gate：样本顺序、样本/源绑定、官方源hash、90对象与73格统计、50条页范围与图像哈希、A 42条页索引与多页图像哈希、A/B交接结构均 PASS。TSG21 §8.3.12 页定位矛盾仍为 BLOCKED。故 `machine_integrity_status=BLOCKED`、`human_release_status=BLOCKED`、汇总 `BLOCKED_PENDING_HUMAN_REVIEW`。这是有意阻断，不是内容 PASS。

## 测试与真实命令

### PyMuPDF隔离环境

主 `.venv-langgraph` 原先缺 `fitz`，导致 P16-A PDF专项测试 import error。仅在 C_GATE 下建立 test-only 包目录，未改应用依赖或项目锁文件：

```powershell
python -m pip install --disable-pip-version-check --no-warn-script-location --target work/data_staging/p16/C_GATE/test_deps PyMuPDF==1.27.2.2
$env:PYTHONPATH=(Resolve-Path work/data_staging/p16/C_GATE/test_deps).Path
.venv-langgraph/Scripts/python.exe -c "import sys; sys.path.insert(0, r'work/data_staging/p16/C_GATE/test_deps'); import fitz; print(fitz.VersionBind)"
```

实际版本：`1.27.2.2`。依赖锁仅在 `work/data_staging/p16/C_GATE/test_deps/requirements.txt`。

### P16专项、门禁和语法

```powershell
$env:PYTHONPATH=(Resolve-Path work/data_staging/p16/C_GATE/test_deps).Path
.venv-langgraph/Scripts/python.exe -B -m unittest tests.test_p16_a_evidence42 tests.test_p16_b_fidelity_retrieval tests.test_p16_c_human50_gate -q
.venv-langgraph/Scripts/python.exe -B -m py_compile scripts/p16_c_machine_gate.py scripts/p16_c_prepare_human50.py tests/test_p16_c_human50_gate.py
.venv-langgraph/Scripts/python.exe -B -m unittest tests.test_p16_c_human50_gate -v
```

实际结果：P16 A/B/C 合计 **19 tests OK**；C专项 **14 tests OK**；`py_compile` exit 0。覆盖状态优先级、47/50、48/50、42缺1、错误总数、身份与Owner阻断、替换ID同seed反例、固定顺序与hash绑定、90/73/2统计、PDF页边界、审签不可信、双人独立性、临时fixture模拟48/50+42/42、准备脚本重跑不改人工CSV，以及真实机器gate当前状态。

### 全项目回归

```powershell
$env:PYTHONPATH=(Resolve-Path work/data_staging/p16/C_GATE/test_deps).Path
.venv-langgraph/Scripts/python.exe -B -m unittest discover -s tests -q
```

实际结果：**238 tests，1 FAIL，3 skipped**，35.896秒。唯一失败为既有 `tests/test_r8b_upload.py::test_pdf_preview_extracts_simple_content_stream_without_external_upload`：PyMuPDF 1.27.2.2 对其极简且缺少完整 xref 的 PDF 输入成功打开但返回空文本，测试期望文本 fallback。试用隔离 PyMuPDF 1.24.14也出现相同结果，故判定为 R8-B 上传预览实现/测试兼容缺陷；不属于 C 写入边界，本轮未改 backend 或该测试。其余237项通过，3项 skip；不能宣称全项目全绿。

### 教师官方终验及工具自测（只读执行）

```powershell
python -B upstream/04_接口文档/validate.py --final
python -B upstream/04_接口文档/validate.py --final --clauses work/data_staging/p16/merged/P16_CLAUSES_PREVIEW_ONLY.jsonl --trajectories upstream/05_提交区/trajectories.jsonl
python -B upstream/05_提交区/_selftest_tools.py
```

实际结果：官方数据 554/554 clauses、200/200 trajectories 通过；隔离 PREVIEW 候选同样554/554 + 200/200通过；教师三个工具自测 **17/17 PASS**。这些结果只证明 schema/工具兼容，不代表条款专业内容完成真人审核或正式可发布。

## 本轮差分

- `scripts/p16_c_machine_gate.py`：重构状态汇总；增加 ordered-ID/source/hash/PDF范围/PNG hash/官方源 hash 检查；新增签名事件验证、Owner key pin、双审与阈值门禁；输出机器与人工两套状态。
- `scripts/p16_c_prepare_human50.py`：人工CSV不再作为输出目标；生成独立机器索引与 V2 freeze；保护已存在证据卡和既有冻结。
- `tests/test_p16_c_human50_gate.py`：从5项扩展到14项，覆盖上述正反例。
- `work/data_staging/p16/C_GATE/P16_C_SAMPLE_FREEZE_V2.json` 与机器索引/页定位清单/机器gate JSON/CSV、测试依赖目录为本轮C隔离产物。
- 既有 `P16_C_HUMAN50.csv` SHA-256仍为 `dc28384d339f92020fc4820ec2fbc50f4eae731d3170aee0bd6329a2cafd0d8c`；既有 `P16_C_HUMAN_REVIEW90.csv` SHA-256仍为 `cd4a14c7224d62217232444a2835ae938b6ab448277d712d2f273edd64eaafa6`。没有实际人工签名可保留或统计。

## 阻断和下一步

1. 当前真实人审仍 `0/50`、`0/42`；Owner须提供独立可信公钥指纹、已核实审核人注册表签署和完整审核事件。不得用本报告中的测试fixture替代。
2. 需要Owner/审核人处理 TSG21 §8.3.12 PDF index 78/83 页定位矛盾，并完成其余来源原文视觉核验。
3. 全套测试中的 R8-B PDF 极简预览用例仍失败；需由对应前端/后端负责人审查实现或固定测试fixture，C窗口不越界修改。
4. 因专业审查、身份验证及Owner放行未完成，状态固定为 **PREVIEW_ONLY**；未覆盖正式Excel/JSONL，无部署/提交。
