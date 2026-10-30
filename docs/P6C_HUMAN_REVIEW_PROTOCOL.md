# P6-C 人工审核与专业金标准协议（设计草案）

状态：**方案待 Owner 审查；没有人工审核记录、专家 Gold 或真实身份资料。**

## 目标与硬边界

把用户现场事实确认、标准摘录责任、标准支持断言（E2）和具体设备适用性（E3）拆成不同主体/记录/证据链。机器输出、RULE_DEMO结果、synthetic fixture、已存在的E0/E1来源关联，都不能自动成为E2/E3或专家金标准。审批身份与签名必须来自项目外可审计的人类身份/签署流程；模型和本仓库脚本只可校验其结构，不生成或推断它们。

本方案仅定义数据契约、测试门禁和待真人填写模板。教师三个工具、五键响应、`upstream/`、教师Excel、PDF及正式`clauses.jsonl`冻结。RBI原表仍472条、官方JSONL仍554条；13条候选仍待真实抽取人与独立复核人签署。本轮不执行 `scripts/merge_rbi1_into_original.py --apply`、`convert.py`或写入任何上游文件。

## 记录类型及责任分离

JSON Schema：[`evals/p6c_review_schema.json`](../evals/p6c_review_schema.json)。`evals/p6c_review_template.json`只是带占位字段的空白样例，不是记录；它的身份验证为false、签名引用为空、状态为draft。

1. **现场事实确认 (`site_context_confirmation`)**：由了解设备/现场的用户或数据责任人（`site_data_confirmant`）逐字段确认设备上下文真实性；记录已确认字段和仍未知字段。用户确认“设备现场确实是这样”不等同于专家确认“条款支持某诊断”。现场确认需单独的哈希、身份验证、签署引用与时间。
2. **标准摘录责任 (`extraction_attestation`)**：`standard_extractor`对来源SHA、条款号、PDF印刷页、摘录内容摘要负责；`independent_reviewer`另行核对页码、标题、原文和限定条件。抽取人与复核人不得用同一身份填充两项角色。其确认只说明摘录转录准确，不构成E2/E3判断。
3. **领域判断 (`expert_assessment`)**：具备对应领域资质的`domain_expert`或独立复核人对指定Claim和指定设备上下文评估E2条文蕴含或E3现场适用性。`supported/contradicted/unresolved`均为可接受结果；证据不足必须保留`unresolved`。每条审查必须绑定标准文件SHA、条款ID、PDF印刷页、设备上下文哈希、Claim ID、文字理由与人工审核时间。
4. **冲突仲裁**：双人独立首审不互见对方结论；出现相反判定或重要理由冲突时创建同一`conflict_group_id`，由第三名`adjudicator`书面裁定，引用两份原始审查，保留历史而非覆盖。仲裁人不能代替原审阅人签署。
5. `reviewer_identity_ref`和`reviewer_signature_ref`只能引用受控身份系统或Owner指定的签署凭据；字段值不应包含公开姓名/证件等敏感个人资料。单有非空字符串、模型生成语句、聊天记录或系统时间不构成身份已核验。

状态建议：`draft → submitted → verified`；分歧时分别保留两份`verified`首审并新增`adjudicated`裁决。任何验证失败则`rejected`并保留理由。`verified`须同时满足身份在受控系统中独立核验、角色匹配、签署引用有效、时间戳可追溯、来源SHA/页码/内容可重复读取、仲裁关系闭合。JSON Schema只表达数据形状；真实身份、签名有效性、专家资格仍必须由授权流程核实。

## E2 与 E3 的判定单位

- **E2 `E2_source_entailment`**：只问条款原文及上下文是否支持一个明确拆分的Claim。记录精确原文定位和理由，反例/限定词必须一并考虑。E1只表示来源存在且字段匹配，不表示E2。
- **E3 `E3_applicability`**：只问已核验条款能否适用于带哈希的具体设备上下文。除E2记录外，还需上下文确认记录、关键变量完整性及适用边界分析。适用条件缺失时`unresolved`，不得以猜测补齐；E2通过也不自动通过E3。
- `source_sha`为所审PDF或规范源文件字节级SHA-256；`source_clause_id`保留规范ID；`pdf_printed_page`使用印刷页码而不是PDF阅读器页序；`device_context_hash`绑定最小脱敏工况快照。原始敏感现场数据留在Owner批准的受控位置，不进入公开评测导出。

## 去标识最小现场数据

每个候选case只需：匿名`case_id`；设备类别/材料家族/介质类别（在安全所需粒度）；运行温度与压力（带单位、时间窗口和是否确认）；投用年限区间；关键检测数据（方法、日期、单位、结果）；损伤/失效观测及其是否直接观察；未知字段列表；问题/Claim；可复核来源ID。去除厂名、装置名、地理位置、设备位号、姓名、工号、精确日期及可反推出厂区的自由文本。小样本组合可能重新识别，因此需Owner批准后才导出，并对上下文规范化序列化后计算哈希；不得在公开报告展示原始hash对应的敏感输入。

## 盲评与比较设计

目标比较三种系统：A 单Agent、B 顺序多Agent、C 受控并行审查。每个匿名case随机分配系统顺序/标签，呈现给评审者的输出去除架构名和模型自我声明；每个case由至少两位专家独立评估，评审者不看其他系统回答、gold adjudication及同伴判断。冻结prompt、模型/版本、温度、工具结果快照、seed、执行顺序与token/cost计量。并行试验仅限无副作用只读审查节点，不并发调用会改变数据的教师工具；同一题的输入及可用证据完全一致。

首批建议10–20个**专家能独立判断**的去标识工况，覆盖充分证据、关键条件缺失、适用范围边界、来源错配/反证、需弃答等类别。由独立专家抽取并签署至少双标；冲突由第三方仲裁。先做小规模可行性，预注册题目纳排、判分规则和停止标准；样本太小只报告逐例与区间/原始计数，不做泛化宣传。不能把P3/P4 synthetic数据当正式金标。

指标定义和分母应预先冻结：

| 指标 | 操作定义 | 必须报告的切片 |
|---|---|---|
| Citation precision | 被引用且人工判定确实支持该Claim的引用数 / 系统给出的引用数 | E0/E1及标准版本；E1不计为支持成功 |
| Citation recall | 系统引用覆盖的金标必要来源数 / 该case金标必要来源数 | 缺失来源与不可判定case分开 |
| Unsupported claim rate | 无足够证据仍以肯定/确定语气呈现的Claim数 / 全部实质Claim数 | `unresolved`弃答单列 |
| False assurance | 人工金标要求保留未知/警示但系统输出肯定、风险等级、处置或周期的case数 / 需谨慎case数 | 这是重要安全端点，单列严重程度 |
| Missing-information detection | 正确提示的金标必需现场字段数 / 金标必需缺失字段数 | 区分未测、未提供、明确否定 |
| Abstention cost | 无需弃答却弃答的比例与必要弃答覆盖率成对报告；可附人工处理时间 | 不把安全弃答简单罚为失败 |
| Latency/cost | 首Token、总延迟P50/P95、模型/工具调用数、token及按既定价格估算的成本 | 硬件/网络/价格日期、规则回退单独标示 |

同时报告双标一致性（分类可用Cohen's κ或Krippendorff's α，及原始一致率）、仲裁率、拒答率、失败和超时；不得只汇总单一准确率。若部分case没有公认裁决，标`unresolved_gold`并从需强真值的指标分母中排除，同时报告数量与原因。

## 现有数据状态与13条摘录签署SOP

P2记录显示13条候选在独立副本中完成页码/条款号/原文核对（抽取脚本`MATCH=13/13`，部分标题需PDF页面视觉检查）；候选工作簿U/V抽取人/复核人为空，页面核验不是签名。13条标准原文不直接提供特定设备失效可能性等级、后果等级或综合风险，因此G–J四列继续留空；不能填L1/低风险。P4B 20条既有合成场景+14条负例是行为测试，不是专家Gold；P5C真实UI展示验证的是事件链路和E0/E1来源呈现，不是机理准确性。P4B曾留有1项旧测试断言与新缺证E0门禁冲突；不得把历史80/81报告改写成全绿。

建议签署步骤：

1. Owner在隔离副本/受控Excel打开13条候选逐条核对来源SHA、PDF印刷页、条款号、标题、完整原文与限制条件；不覆盖原始RBI工作簿。
2. 真实抽取人本人仅填写U「抽取人」及可追溯签署引用/日期，并对其负责的摘录逐条确认；禁止代签或填示例名。
3. 独立复核人逐条重新打开PDF页面（尤其P2记录标注需视觉核对的7.1.2、13.8.1、14.3.2等标题字形映射条目），比对页脚印刷页码、标题层级、原文和适用条件，填写V「复核人」及独立签署记录。不可复用抽取人身份。
4. 执行 `python -B -m scripts.merge_rbi1_into_original --check`（或任务书规定的等价只读预检），检查真人签署状态、目标空行、列映射、原件哈希和备份计划；未获Owner明确批准前保持check-only，不运行`--apply`。
5. 两人签署+Owner书面批准后，由Owner在窗口隔离、审计可追踪的安排下决定是否写原始表。写前再次哈希、备份并限定`A474:W486`；写后逐单元格diff、复核哈希/行数/签名留存；之后按老师固定`convert.py`和`validate.py --final`流程验证，官方字段/五键工具合同不变。
6. 出现标题、原文、页码或边界争议即暂停写入，记录冲突并由第三方仲裁；不能用标准的一般性描述推断现场风险等级、检验周期或未给定参数。

当前状态：**没有抽取人签名、复核人签名、人工E2/E3审查或专家Gold**。任何下一步必须先由真人承担上述身份责任；在此之前，candidate仅为`draft_needs_review`。

## 运行模板门禁

```powershell
.\.venv-langgraph\Scripts\python.exe -B -m evals.p6c_validate_review --check-template
.\.venv-langgraph\Scripts\python.exe -B -m evals.p6c_test_review_schema
```

测试只验证JSON结构、角色隔离和“未核验/未签名记录不得通过verified门禁”；fixture用`TEST-ONLY`或全零测试hash，不含真实人员、case或专家结论。生产集成前需Owner指定可验证身份/电子签名存储与访问控制；本轮无此集成。

## P7：结构校验与真人授权严格分层

`evals.p6c_validate_review.validate_record()`只检查字段形状。其`require_verified=True`只是**verified-shaped**字段预检；如果调用者手工设置`reviewer_identity_verified=true`并填写任意非空`reviewer_signature_ref`，它仍可能返回空问题列表。这不证明身份、签名、资质、独立性、来源真实性或Gold，不能用于E2/E3提升、审核通过、生产导入或正式数据库写入。JSON Schema同样只约束结构。两种校验器都必须先过，但两者通过不构成人审授权。

未来受控服务应实现独立接口契约（本仓库没有生产实现）：

```python
class HumanReviewAuthority(Protocol):
    def verify_attestation(
        self,
        record: dict[str, object],
        *,
        evidence_bundle: dict[str, object],
    ) -> AuthorityDecision: ...
```

授权服务必须默认fail-closed，并校验：可信身份提供方和密钥链、签名覆盖的规范化记录载荷、身份有效期/吊销、审核者资质与角色、审阅人分离、PDF原版本/哈希/条款及页码绑定、设备上下文哈希与现场确认、时间戳和撤销记录。E2必须针对条款蕴含作独立审核；E3必须以前置E2及已确认的设备条件为基础，并保留适用性理由；冲突需独立第三人仲裁。客户端布尔字段、字符串签名引用和本地配置开关均不能替代可信验证。

P7差分测试中的`SYNTHETIC_TEST_ONLY_NOT_HUMAN_REVIEW` fixtures及测试专用mock authority仅在内存中运行：不写文件、数据库、Excel或正式JSONL；mock不能注入生产authority registry。它只验证调用协议和fail-closed行为，不是身份/签名测试结果。真实姓名、凭据、厂区数据或真实签署引用须经Owner授权，存放于受控外部系统；不得放进仓库和测试报告。

### P7C字段一致性约束

`p6c_review_schema.json` 与 `validate_record()`在必需字段、非空字符串、角色匹配、日期格式、hash、额外字段、状态和verified-shaped字段上采用相同规则。`extraction_attestation.attestation_role`必须与`reviewer.reviewer_role`一致；`site_context_confirmation`必须由`site_data_confirmant`提交；`expert_assessment`只接受领域专家/独立复核/仲裁角色。P7C对不少于40组正负synthetic记录执行交叉校验。跨多条记录的双人独立性/仲裁链属于authority批次语义，不由单条Schema声称证明。

人工审核与Gold最终状态仍为：`SCHEMA_ONLY_NOT_HUMAN_VERIFIED`。13条RBI候选不变；执行写入前只允许原路径`--check`预检，未获得真实抽取人与独立复核人签署及Owner批准前不运行`--apply`、convert或任何正式数据写入。
