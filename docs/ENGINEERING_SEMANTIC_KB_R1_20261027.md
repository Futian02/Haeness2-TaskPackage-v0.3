# 工程语义知识库：机理卡（Mechanism Card）R1设计

## 源与知识的边界
原始 PDF / 原始两份 XLSX / 554 clauses.jsonl **不可被模型重写**。新建扩展知识层`knowledge/semantics/`，每个机理卡包含从标准抽取/专家审过的概念别名、现场观察、区分性检测建议、硬适用条件、反证条件与来源。其中模型推导内容标为`hypothesis`，人类未核前不得写成标准原文或者覆盖现有条款。

## 语义机制卡（概念Schema）
```json
{
  "card_id": "mechanism:GBT30579-2022-5.1",
  "canonical_name": "盐酸腐蚀",
  "aliases": ["HCl腐蚀"],
  "applicability": {"materials": ["碳钢"], "media": ["氯化氢"], "temperature_c": [null, null]},
  "observations": [
    {"feature": "ph", "relation": "decreased", "observed": "unknown", "provenance": {"clause_id": "GBT30579-2022-5.1", "page": 0}, "status": "draft"}
  ],
  "necessary_information": ["material", "medium", "temperature_c", "water_phase_presence"],
  "discrimination_questions": [
    {"question": "测厚是否发现减薄?", "feature": "wall_thinning", "status": "draft"},
    {"question": "是否已检测HCl浓度与结盐条件?", "feature": "hcl_concentration", "status": "draft"}
  ],
  "candidate_causes": [],
  "supporting_evidence": [],
  "contradicting_evidence": [],
  "standard_sources": [{"clause_id": "GBT30579-2022-5.1"}],
  "editorial_status": "draft",
  "verification_status": "unverified"
}
```
示例JSON只作**结构示意**，尤其示意`page:0`不能被当作有效标准页码；正式输出必须按真实条款的page并和PDF核对。

## 事实的三值逻辑
`wall_thinning = unknown`：未执行或缺少测厚证据；
`wall_thinning = false`：执行了可信测厚且未见减薄；
`wall_thinning = true`：发现减薄。
同理 crack_found。跨类型量值 `ph`、`cl_ppm`、`fe_ppm` 要区分`value`、`unit`、`measurement_time`、`method`、`quality`；数值无记录时None，不填0。
规则引擎将候选按三类分类：`supported`、`possible_but_unresolved`、`excluded_by_evidence`。这比“LLM给一个自信百分比”可追责。

## 检索与机理研判严格分工
1. 解析用户自然叙述，提取物理语义与否定词：例如“尚未测厚”不是“未发现减薄”。
2. 设备条件硬筛：材质、介质、温压、设备类型与标准适用边界；未知条件不能视作假。
3. Hybrid召回：标题/术语精确（BM25/FTS5）与现象自然描述（embedding），至少20~50金标评测后才启用语义增强。
4. 差别诊断：相关机理 vs 矛盾证据；必要时二次检索原条款与 PDF，主动列出要确认的问题。
5. Reviewer：每条可操作研判要E0/E1来源且适用性E2/E3未冲突，未核源时只能标示待专家审核。
6. 最终不给装置级不具备的RBI风险值；可返回符合依据的判定路径和所需现场因素。

## 冷静评估开源套路
- Contextual Retrieval：将每条条款的“标准名/章号/机理卡标题/适用条件”前缀加入索引文本以防短切片失上下文；**原content_raw不变**。
- Knowledge graph / GraphRAG：54? 82条机理的related_damages和设备-材质-介质关系已经提供结构边，适合小型图拓扑+邻域扩展，但GraphRAG大模型社区摘要未必对本题有收益，先做简洁邻接字典对照。
- Reranker（cross-encoder）：只在候选10~30条上精排，报告召回/准确率/延迟，而不是无条件增加网络延迟。
- 跨文档冲突：记录`standard_code`、条款版本、条件、影响/被影响关系；不能通过“相似”直接认定冲突。

## 推荐样例与评测
锁定10种标准明确的损伤机理（以真实`clause_id`为准），每种生成3个题：准确术语、现场模糊现象、误导/反证；另外加入缺数据、温度不支持、介质不在枚举表。30+案例人工标注候选/未解决/应拒答/必须补证据，区分错误硬答和适当拒绝率。
实施结果以`card_id+source+verified_by`保存在专用表中，不回写教师正式JSONL。
