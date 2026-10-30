# P16-C 最终发布门禁与人工核验包（2026-10-29）

**交付状态：`READY_FOR_OWNER_REVIEW`（仅审阅证据包）**  
**发布状态：`BLOCKED_PENDING_HUMAN_REVIEW` / `PREVIEW_ONLY`。**  
本轮没有覆盖正式Excel/JSONL，没有生成可发布标记。

## 1. 阅读、输入及边界

完整读取：

- `AGENTS.md`
- `docs/data_quality/P16_CLOSEOUT_MASTERPLAN_20261029.md`
- `docs/CODEX_P16_C_HUMAN50_GATE_20261029.md`
- `docs/data_quality/OWNER_P15_ABC_INDEPENDENT_REVIEW_20261029.md`
- 教师填写指南及原版 `upstream/04_接口文档/convert.py`、`validate.py`。

只读P15固定随机抽样/差分/Excel候选/P15候选JSONL、P14页面索引，以及P16-A/B隔离产物。C新增代码只在 `scripts/p16_c_*.py`、`tests/test_p16_c_*.py`；所有本轮渲染、预览、日志只写 `work/data_staging/p16/C_GATE/`、`work/data_staging/p16/merged/` 与本C报告。未写上游PDF、原始Excel、官方JSONL、教师工具、P13应用、正式数据库；未提交、未部署、未删除文件。

## 2. 固定随机50条PDF原图卡与90项登记

从 `work/data_staging/p15/C_QA/P15_C_HUMAN_REVIEW50.csv` 原样保留seed `20261029`、50行与原50个clause_id，未重新抽样。已生成：

- `work/data_staging/p16/C_GATE/index.html`、`cards/`：50张本地HTML卡。每卡呈现条款号/标题、印刷页、0-based物理页、候选F/content_raw、applicable_conditions、来源PDF SHA-256、原始PDF整页图、真人填写栏。
- `pdf_pages/`：50个随机对象渲染为34张不同原始PDF页PNG；重复页复用。
- `P16_C_HUMAN50.csv`、`P16_C_HUMAN50_PAGE_LOCATORS.csv`：原ID、seed、定位方式、物理页、源哈希和卡路径。
- `P16_C_HUMAN_REVIEW90.csv`：合并50随机抽样与A的42条定向审核，引用A的42张卡，不重制A卡。

页定位使用原PDF上条款号、印刷页脚、唯一已核页号锚点；GB/T 30579页码常数由P14既有多页配对支持。50/50页图均存在且源PDF哈希匹配，机器页定位都只是待人核导航，**不是人已确认页码或原文准确率**。

交集2条：`GBT26610.3-2014-7-p`、`GBT26610.5-2022-表3-d`。去重结果 `50+42−2=90`。50条分母仍单独计；要求随机至少48条真实通过，42个变更对象全部得到明确的人审结论，不能互相替代。

## 3. A/B独立QA及当前可见风险

P16-A包：42条记录、73个Excel cell change，42张卡、19张唯一源图；机器状态为28 `MATCH`、13 `AMBIGUOUS`、1 `CONTRADICTS`。关键项包括26610.5表2/表3的10条数值/单位/边界机器视觉核读一致（教师表格转写格式仍待裁决）、26610.3图1矩阵25格一致、TSG条款和30579第5.6/5.23/6.7语义边界待审。A识别到TSG 21 §8.3.12台账定位矛盾：台账印刷页79/PDF index78与图页不符，条款标题应在印刷页79/PDF index83；该修正仍是提案，没有回写候选。§5.6 F范围也需裁定。

P16-B包：211条高风险表格剩余队列；82个模式的G–N及O–V合计1312字段待来源核读；56章补充标准待目录/范围复核；共11条隔离建议（6条来源/字段复核、5条应用检索建议）。20条OCR/页面采集只用于导航；不作原文转录或真值。46个合成检索查询中，基线37/42相关ID、Recall@20 0.881、MRR@20 0.816；隔离候选42/42、Recall@20 1.000、MRR@20 0.952。后者使用查询扩展且只对合成gold测试，不是专家准确率，不改P13/官方工具/gold/正式数据。

P16-A/B签核字段都仍为空；两边输出是待审材料，不代表签核完成。

## 4. P16隔离预览整合、老师原版转换及差分

A/B输入齐备后，C独自在 `work/data_staging/p16/merged/` 生成：

- `P16_RELEASE_CANDIDATE_PREVIEW_RBI.xlsx`
- `P16_RELEASE_CANDIDATE_PREVIEW_DM.xlsx`
- `P16_CLAUSES_PREVIEW_ONLY.jsonl`
- `P16_C_PREVIEW_JSONL_DIFF.csv`

两份Excel从P15转换合格候选副本复制而来。P16-A的1条定位纠正、其余待裁决项，以及P16-B六条来源建议未在无真人批准时写入表格；5条检索建议不属于教师标准数据。预览继承P15已经候选化的42条记录修订。候选相对官方正式JSONL：554条；新增0、删除0、修改42个clause_id、44个JSON字段差异。13条未签草稿不在合格预览中，仍与可转换数据隔离。

实际执行教师原版：

```powershell
.venv-langgraph/Scripts/python.exe -B scripts/p16_c_integrate_preview.py
```

其中原版 `convert.py` 在隔离副本上输出：`554条（损伤机理82、RBI472），错误0、提示0`；JSONL SHA-256 `7efebc07786fd6232da05d21c43323486f3b15d1ff4edd731075755fe419d196`。原版 `validate.py --final`：候选条款554/554、轨迹200/200通过；multi_step 144、exclusion/insufficient_info/out_of_domain各15；终验PASS。完整stdout在 `work/data_staging/p16/merged/P16_C_CONVERT_PREVIEW.log` 与 `P16_C_VALIDATE_FINAL_PREVIEW.log`。

教师原版三个工具从上游复制到 `merged/candidate_tool_probe/` 后以预览JSONL运行 `_selftest_tools.py`：**17/17 PASS、0失败**，日志 `P16_C_TEACHER_TOOL_SELFTEST.log`。此结果是接口/自测通过，不是行业结论准确率。

官方工具/数据SHA只读前后快照一致：RBI Excel `e43f7b0d3381a38fa648c2505e27d1c87893af5aea89aa119097dbfc49c6b7bf`；DM Excel `8bb05d1d0dacbe542a1713a317a769f064a9c6c7ad34053417f0dbba01a0d62e`；正式JSONL `a8151797ba15a6a7452dd83aaec9fab4c0a815724ca45062eb1e2bac7b4d49ef`。状态明确为 `PREVIEW_ONLY_NOT_RELEASE`，未产出“convertible/release”标记。

## 5. 门禁、测试及失败说明

`work/data_staging/p16/C_GATE/P16_C_MACHINE_GATE.csv/.json` 当前机器检查：固定seed样本、90去重对象、42条/73格链接、50张原页图/来源哈希、无伪签、A/B预览集成及A/B结构数量均PASS。阻断项：一项未裁决来源页码冲突（TSG §8.3.12）、随机50真人签核0/50、42定向审核0/42。

专项：

- P16-C：`python -B -m unittest tests.test_p16_c_human50_gate -v` → 5/5 PASS。
- P16-B：`python -B -m unittest tests.test_p16_b_fidelity_retrieval -v` → 最终稳定产物5/5 PASS。
- P16-A：`python -m pytest -q tests/test_p16_a_evidence42.py`（系统Python，含PyMuPDF）→ 5 passed。
- 项目测试：隔离Python中排除因缺`fitz`无法导入的P16-A pytest模块，其他31个测试模块运行**229 tests、PASS、3可选SKIP、0失败**。随后P16-A模块独立用pytest通过，故所有现有模块都分别执行通过；但不能声称单一隔离解释器下的unittest discovery全绿。

完整unittest discovery命令：

```powershell
.venv-langgraph/Scripts/python.exe -B -m unittest discover -s tests -q
```

实际 `Ran 230 tests`、`FAILED (errors=1, skipped=3)`：唯一ERROR是 `tests/test_p16_a_evidence42.py` 导入 `fitz` 失败（`.venv-langgraph` 未安装PyMuPDF）。该文件为A窗口所有，本C未改。系统Python单独跑A的pytest 5项通过；若用系统Python跑全项目，则遇到旧Tenacity对新asyncio的兼容错误（历史日志 `P16_C_FULL_PROJECT_TESTS_SYSTEM_PYTHON.log`），不作为正确的全套运行环境。

期间观察到A/B写入尚在变化时的短暂测试结果，已保留 `P16_C_FULL_PROJECT_TESTS_DURING_B_WRITE.log` 与 `P16_C_P16B_TESTS_DURING_B_WRITE.log`；A/B产物稳定后重跑：B专项5/5通过，当前完整发现只剩上述PyMuPDF导入ERROR。现行稳定测试日志和门禁stdout均保存在 `work/data_staging/p16/C_GATE/`。

## 6. 未完成与放行阻断

1. 随机50真人审签0/50，故50条通过数为“待审”，不是0%通过率；42个定向变更审核0/42。身份、签名、时间、页码确认、结论及第二人交叉核验/分歧裁决都未填写。达到随机≥48条真人通过与变更42/42结论前不得发布。
2. TSG §8.3.12来源定位矛盾需要Owner/真人确认，并确定是否更正P15源台账；机器预览没有自行替换。
3. 211条表格风险项、82×8字段来源/条件、56章补充PDF范围、5个合成检索错失问题仍未达到人工内容审定。Recall改善不等于专家检索准确率。
4. 26610.5表格转写格式、25格颜色判断、温压/分压语义、材料/介质枚举、F≤300字与跨单元格引用、OCR与原图、provenance标准归属等内容正确性仍待人工/领域审查。本轮convert/validate/selftest只说明结构和工具接口门禁通过。
5. P16-B应用检索建议未并入P13；6条来源/字段建议未获人审，未写进预览工作簿。
6. Owner书面放行未取得；正式Excel/JSONL保持冻结。教师100组真实LLM解析、五轮调用和ModelScope公开展示不由本轮结果代替。

## 7. 变更清单及复现命令

新增：

- `scripts/p16_c_prepare_human50.py`：固定seed抽样卡、原页图、90条登记及A卡引用。
- `scripts/p16_c_machine_gate.py`：样本、单元格、原PDF哈希/页图、A/B输入、真实签核、冲突和release门禁。
- `scripts/p16_c_integrate_preview.py`：P16隔离预览复制、原版convert/validate、差分、教师工具独立副本和自测。
- `tests/test_p16_c_human50_gate.py`：5项C专项不变量。
- `work/data_staging/p16/C_GATE/`：50卡、90对象CSV、页图、门禁、测试和真实日志。
- `work/data_staging/p16/merged/`：两份预览Excel、候选JSONL、差分、教师工具隔离副本与日志。
- 本报告。

```powershell
.venv-langgraph/Scripts/python.exe -B scripts/p16_c_prepare_human50.py
.venv-langgraph/Scripts/python.exe -B scripts/p16_c_integrate_preview.py  # 退出码2=人工门阻断；converter/validator/tool可已通过
.venv-langgraph/Scripts/python.exe -B scripts/p16_c_machine_gate.py     # 退出码2=当前release阻断
.venv-langgraph/Scripts/python.exe -B -m unittest tests.test_p16_c_human50_gate -v
.venv-langgraph/Scripts/python.exe -B -m unittest tests.test_p16_b_fidelity_retrieval -v
python -m pytest -q tests/test_p16_a_evidence42.py
.venv-langgraph/Scripts/python.exe -B -m unittest discover -s tests -q
```

最终状态：**P16-C证据包 `READY_FOR_OWNER_REVIEW`；数据状态仍 `BLOCKED_PENDING_HUMAN_REVIEW`。** 不部署、不提交、不覆盖上游。下一步由真实审核人完成50随机核验及42条定向审签，再由Owner确认来源页码冲突与B建议，届时C可在隔离目录重跑全套Gate。
