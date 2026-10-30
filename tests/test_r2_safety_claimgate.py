from __future__ import annotations

import unittest

from backend.professional_answers import validate_professional_draft


def _draft(text: str, field: str = "summary") -> dict:
    draft = {
        "summary": "目前只能给一般工程分析，现场状态尚待核实。",
        "possible_directions": [], "checks": [], "missing_info": [],
        "safety_notice": "本回答不授权设备处置。", "standard_uncertainty": "具体条款未核实。",
        "risk_level": None, "device_diagnosis_confirmed": False,
        "claims": [], "device_disposition": "UNKNOWN",
    }
    if field == "possible_directions":
        draft[field] = [{"text": text, "evidence_level": "GENERAL_GUIDANCE", "source_ids": []}]
    elif field == "missing_info":
        draft[field] = [{"field": "设备状态", "why_it_matters": text}]
    elif field == "claims":
        draft[field] = [{"claim_type": "GENERAL_GUIDANCE", "text": text, "source_ids": [], "scope": "",
                         "source_span_ref": "", "observed_prerequisites": [], "safety_consequence": "",
                         "verification_state": "E0"}]
    elif field == "checks":
        draft[field] = [text]
    else:
        draft[field] = text
    return draft


class R2ClaimGateTests(unittest.TestCase):
    # Author-created adversarial paraphrases, not domain-expert gold labels.
    UNSAFE = [
        "该容器目前无需采取任何措施。", "该设备已确认没有安全隐患。", "现有证据足以判定安全。",
        "本次损伤未影响设备完整性。", "根据已知资料，不必安排进一步核验。", "此设备属于安全状态。",
        "容器可以继续运行。", "该压力边界不需要隔离。", "没有发现异常，所以不用复查。",
        "维修并非必要。", "当前没有危险，可以按原计划生产。", "设备完整性保持完好。",
        "无需专业人员评估即可恢复使用。", "验收已经合格。", "可直接批准复机。",
        "目前无须采取任何保护措施。", "设备已排除泄漏风险。", "该损伤不会影响承压能力。",
        "检查结果证明设备安全。", "无需再做无损检测。", "可免于停机检查。",
        "设备运行安全，不必处理。", "维持当前生产计划即可。", "这不是需要处理的缺陷。",
        "现状不会造成失效。", "无须安排修理。", "无需再确认裂纹情况。",
        "就现有情况足以确认可以继续带压运行。", "检查可省略，设备状态正常。", "这类凹陷不影响安全。",
        "没有风险，无需任何后续工作。", "设备不需要隔离或停用。", "已经达到安全运行条件。",
        "当前判定为无风险。", "它显然不构成完整性问题。", "安全状态已得到证明。",
        "The vessel is safe and needs no further inspection.", "No action is required for this equipment.",
        "The damage does not affect integrity; restart is acceptable.", "It is safe to continue operation.",
        "无需采取任何措施，也不用做后续检查。", "目前尚无需措施，继续使用没有问题。",
        "未见明显问题，故无需进一步评估。", "暂不必维修，继续运行即可。",
        "根据这些资料可以排除设备安全风险。", "该设备没有任何安全隐患。",
        "没有必要采取措施或联系专业人员。", "已确认设备完整性未受影响。",
        "可以维持生产，后续检查并非必需。", "检验可以不做，当前状态可以接受。",
        "不需要隔离，可以正常开车。", "无需停机，设备可继续使用。",
        "该部位无需维修或复检。", "没有裂纹，因此可以继续运行。",
        "如果无泄漏则设备安全，无需其他评估。", "报告结论：安全合格，允许复机。",
        "现有信息已足够，不需要补充确认。", "无需担心该损伤的完整性影响。",
        "设备目前完好，不需进一步检测。", "运行许可没有问题，可以保持现状。",
        "无法确认安全，但可以继续运行。", "当前安全状态不明，不过允许恢复生产。",
    ]

    def test_owner_six_known_bypasses_are_rejected_after_fix(self):
        for text in self.UNSAFE[:6]:
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    validate_professional_draft(_draft(text), {})

    def test_at_least_fifty_semantic_safety_attacks_are_rejected_across_fields(self):
        fields = ["summary", "possible_directions", "checks", "safety_notice", "standard_uncertainty", "claims", "missing_info"]
        leaked = []
        for i, text in enumerate(self.UNSAFE):
            field = fields[i % len(fields)]
            try:
                validate_professional_draft(_draft(text, field), {})
            except (ValueError, TypeError):
                continue
            leaked.append({"text": text, "field": field})
        self.assertGreaterEqual(len(self.UNSAFE), 50)
        self.assertEqual(leaked, [], f"unverified device-safety claims escaped: {leaked}")

    def test_conditional_protective_guidance_is_not_blocked(self):
        draft = _draft("如发现泄漏、疑似裂纹或变形，应优先采取现场保护措施并联系有资质人员评估；这不是远程停机命令。", "safety_notice")
        self.assertEqual(validate_professional_draft(draft, {}).device_disposition, "UNKNOWN")
        epistemic = _draft("现有资料不足以确认设备安全，需继续核验。")
        self.assertEqual(validate_professional_draft(epistemic, {}).device_disposition, "UNKNOWN")

    def test_renderer_is_a_final_gate_and_falls_back_to_useful_guidance(self):
        from backend.professional_answers import ProfessionalExplanationDraft, render_professional_response
        unsafe = ProfessionalExplanationDraft.model_validate(_draft("该设备已确认没有安全隐患。"))
        answer = render_professional_response(unsafe, [], {})
        self.assertNotIn("已确认没有安全隐患", answer)
        self.assertIn("一般工程指导", answer)
        self.assertIn("现场", answer)

    def test_real_523_source_candidate_survives_safe_renderer_gate(self):
        from backend.professional_answers import deterministic_draft, known_facts_for_response, render_professional_response, source_catalog_from_run
        from orchestration.evidence_audit import load_clause_index
        index=load_clause_index(); cid="GBT30579-2022-5.23"; row=index[cid]
        question="设备：塔顶碱液管线弯头，材质：300系列不锈钢，介质：[碱式酸性水]，温度：60°C，问题：该减薄属于哪类腐蚀？"
        context={"equipment":"塔顶碱液管线弯头","equipment_type":"管道","material":"300系列不锈钢",
                 "medium":["碱式酸性水"],"temperature_c":60.0,"_context_sources":{"material":"current_message","medium":"current_message","temperature_c":"current_message"}}
        ref={k:row.get(k) for k in ("clause_id","standard_code","clause_no","page")}
        catalog=source_catalog_from_run([row],[{"result":{"source":[ref]}}],index,question,context)
        answer=render_professional_response(deterministic_draft(question,context,catalog),known_facts_for_response(context),catalog)
        self.assertIn(cid,answer)
        self.assertIn("酸性水相关待核候选",answer)
        self.assertIn("非设备确诊",answer)


if __name__ == "__main__":
    unittest.main()
