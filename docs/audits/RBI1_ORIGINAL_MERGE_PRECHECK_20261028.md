# RBI1 原表直接合并脚本：Owner准备和安全预检（2026-10-28）

## 用户最终授权与操作范围
Excel已经关闭；用户授权将P2核验的13条GBT26610.1-2022候选直接合并到
`upstream/01_RBI标准/条款摘录表_RBI.xlsx` 原文件的`摘录表`，不得修改别的3张工作表、表头、既有472行及样式。老师`convert.py`→`validate.py --final`必须最后审查；固定3个老师工具。
与Codex的LangGraph/前端代码应分区并行，**不允许多个执行器同时改同一个工作簿**。

## 本轮本机只读事实
- 原Excel SHA-256：`38cf71bf9f9868cfa531729cda70dea2e2857b3a788ec1a67f56d27ef01512f9`，原表仍未被修改。
- P2独立候选SHA-256 `d292a20f1487b3cedcc67d6b36ea192df15f79e3e360905f946252970e818853`；候选14行（含表头）、13新增。
- 原RBI 472条，`A2:W473`已填，空白格式行`A474:W602`。新数据范围为`A474:W486`。
- G/H/I/J已覆盖全部具备联合概率+后果输入的25格矩阵；其余不能将独立G或H硬配成风险等级。
- 新增13条来自GBT26610.1的**方法学**条款，无文内统一概率等级/后果等级/风险等级/检验周期；G/H/I/J/K全部真实留空。
- P2逐页人工视觉检查与机器逐句匹配证据见`docs/audits/P2_RBI1_LANGGRAPH_EVIDENCE.md`。不因这一审核就冒称真实学生署名/独立人工核签。

## 已创建的可重放无损增量工具
`scripts/merge_rbi1_into_original.py`
- 仅读两份现有XLSX的OOXML，把`xl/worksheets/sheet2.xml`第474-486行预格式化空行的已允许单元格按原模板样式填入。
- 在原表SHA、候选SHA、唯一ID、表头、PDF候选quote/title/页码全部通过时继续；任一基础变动就fail-closed。
- 只写入`A/B/C/D/E/F/U/W`必要列；F沿用上一条款原文换行样式；`G/H`保留模板空白样式；其余不编造数值。
- 保留ZIP内**所有其他part字节级相同**；同一工作表A1:W473及row487以后原始XML字节相同。保存前建原Excel原样备份，ZIP CRC和重新解码校验，temp→atomic rename。
- 明确`--check`预检与`--apply --extractor 学号_姓名`正式签名合并两种方式；如真抽取人仍未知，只有显式`--apply --unsigned-draft`才允许把待签稿写进原Excel，此时老师convert按规定拒绝，原始JSONL不被改动。V复核人需另一真实审核者后续填写。

## 本轮实测
`python -B -m scripts.merge_rbi1_into_original --check`：
`READY_TO_APPEND 13 A474:W486`，`EXTRACTOR_SIGNED False`，无文件修改。
在内存中实际执行`modify_xml(original_sheet_bytes, 13)`，验证所得工作表XML成功解析、修改前区域（row474之前）与修改后区域（row487之后）**字节完全一致**。
独立 LangGraph venv 实测`45 tests ... OK`（另旧环境Tenacity仍有冲突）。
**未执行远程二进制XLSX写盘**：本会话DevSpace`write/edit`仅允许纯文本文件；DevSpace`bash`禁止用来创建/修改本地文件；Remote Desktop Commander设备离线；`dorqinspace.codex_bind_workspace`两次内部错误，不能声称Codex已被本窗口启动。执行应由用户已开启的原生本机Codex完成，或待有受支持本机Excel编辑连接后完成。

## 直接执行的安全指令（给当前本机Codex）
```powershell
cd "D:\作业\竞赛\计算机设计智能体\机械智能体"
python -B -m scripts.merge_rbi1_into_original --check
# 在确认真实抽取人学号_姓名后：
python -B -m scripts.merge_rbi1_into_original --apply --extractor "2024xxxx_真实姓名"
# 如果真实人身份暂不可得，只能由Owner显式选draft；
# 此时convert应拒绝，不允许用随意占位姓名欺骗门禁：
# python -B -m scripts.merge_rbi1_into_original --apply --unsigned-draft
```
之后先`convert.py --output 临时JSONL`检查（真实extractor才会通过），再正式`convert.py`更新老师`05_提交区/clauses.jsonl`，再`validate.py --final`及45项单测。若13条均合并，则预期有效条数变为 RBI485+DM82=567；未合并时仍为554。
严禁手改`clauses.jsonl`、伪造U/V学号姓名或对TSG21有条件周期编无条件K值。
