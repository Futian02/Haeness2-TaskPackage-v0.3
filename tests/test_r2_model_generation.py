from __future__ import annotations

import json
import unittest
from unittest.mock import patch


class R2ProfessionalModelGenerationTests(unittest.TestCase):
    def _response(self, content: str, *, finish_reason: str = "stop"):
        body={"choices":[{"message":{"content":content},"finish_reason":finish_reason}],
              "usage":{"prompt_tokens":120,"completion_tokens":90,"total_tokens":210},"model":"mock-r2"}
        class Response:
            def __enter__(self): return self
            def __exit__(self,*args): return False
            def read(self,n): return json.dumps(body,ensure_ascii=False).encode()
        return Response()

    def _draft(self, *, summary="SCC通常需要拉应力、敏感材料和特定腐蚀环境共同作用。", directions=None):
        return json.dumps({
            "summary":summary,
            "possible_directions":directions or [{"text":"概念层面可从材料敏感性、环境化学和拉应力三方面解释裂纹萌生。",
                "evidence_level":"GENERAL_GUIDANCE","source_ids":[],"scope":"通用机理解释，不对应具体设备诊断。",
                "source_span_ref":"","observed_prerequisites":[],"verification_state":"E0"}],
            "claims":[{"claim_type":"GENERAL_GUIDANCE","text":"概念解释不等同于现场设备诊断。","source_ids":[],
                "scope":"一般概念","source_span_ref":"","observed_prerequisites":[],"safety_consequence":"","verification_state":"E0"}],
            "checks":["若用于具体设备评估，再核对材料、环境与拉应力来源。"],
            "missing_info":[],"safety_notice":"","standard_uncertainty":"未引用标准条款。",
            "risk_level":None,"device_diagnosis_confirmed":False,"device_disposition":"UNKNOWN"},ensure_ascii=False)

    def test_scc_concept_uses_direct_explanation_without_device_parameters(self):
        from backend.deepseek import generate_professional_explanation
        from backend.professional_answers import validate_professional_draft
        content=self._draft()
        cfg={"api_key":"mock","endpoint":"https://example.invalid/chat/completions","timeout":8,"model":"mock-r2","provider":"deepseek"}
        with patch("backend.deepseek.urlopen",return_value=self._response(content)) as mocked:
            result=generate_professional_explanation("什么是应力腐蚀开裂？",{}, {},cfg)
        payload=json.loads(mocked.call_args.args[0].data.decode())
        user=json.loads(payload["messages"][1]["content"])
        self.assertEqual(user["answer_mode"],"concept_explanation")
        self.assertEqual(user["explicit_user_facts"],{})
        system=payload["messages"][0]["content"]
        self.assertIn("拉应力",system)
        self.assertIn("竞争解释",system)
        self.assertEqual(payload["max_tokens"],1800)
        draft=validate_professional_draft(result.content,{})
        self.assertIn("材料敏感性",draft.possible_directions[0].text)
        self.assertFalse(draft.device_diagnosis_confirmed)

    def test_hypothesis_generation_receives_only_bounded_current_sources(self):
        from backend.deepseek import generate_professional_explanation
        content=self._draft()
        source={"C1":{"source_id":"C1","standard_code":"GB/T 123-2020","clause_no":"5.1",
            "page":7,"title":"测试条款","verification":"E0","content_excerpt":"A"*20000,
            "scope_note":"适用边界","relevance_label":"候选"}}
        cfg={"api_key":"mock","endpoint":"https://example.invalid/chat/completions","timeout":8,"model":"mock-r2","provider":"deepseek"}
        with patch("backend.deepseek.urlopen",return_value=self._response(content)) as mocked:
            generate_professional_explanation("弯头减薄要排查什么？",{"equipment":"弯头","material":"未知材质",
                "private_note":"do-not-send"},source,cfg)
        payload=json.loads(mocked.call_args.args[0].data.decode())
        user=json.loads(payload["messages"][1]["content"])
        self.assertNotIn("private_note",user["explicit_user_facts"])
        sent_source=user["verified_current_run_source_catalog"][0]
        self.assertEqual(len(sent_source["content_excerpt"]),400)
        self.assertEqual(sent_source["source_id"],"C1")
        self.assertEqual(payload["max_tokens"],1800)
        self.assertLessEqual(payload["messages"][1]["content"].__len__(),6000)

    def test_truncated_model_response_is_typed_failure(self):
        from backend.deepseek import ModelGenerationError, generate_professional_explanation
        cfg={"api_key":"mock","endpoint":"https://example.invalid/chat/completions","timeout":8,"model":"mock-r2","provider":"deepseek"}
        with patch("backend.deepseek.urlopen",return_value=self._response("{",finish_reason="length")):
            with self.assertRaises(ModelGenerationError) as raised:
                generate_professional_explanation("什么是SCC？",{}, {},cfg)
        self.assertEqual(raised.exception.code,"output_truncated")

    def test_fake_standard_claim_and_device_permission_fail_claim_gate(self):
        from backend.professional_answers import validate_professional_draft
        def candidate(text, *, claim_type="SOURCE_SUMMARY", source_ids=("FAKE",)):
            return {"summary":"候选分析。","possible_directions":[],"claims":[{"claim_type":claim_type,"text":text,
                "source_ids":list(source_ids),"scope":"全设备","source_span_ref":"","observed_prerequisites":[],
                "safety_consequence":"","verification_state":"E0"}],"checks":[],"missing_info":[],
                "safety_notice":"","standard_uncertainty":"","risk_level":None,
                "device_diagnosis_confirmed":False,"device_disposition":"UNKNOWN"}
        with self.assertRaises(Exception):
            validate_professional_draft(candidate("GB/T 99999-2099规定凹坑小于3mm。"),{})
        with self.assertRaises(Exception):
            validate_professional_draft(candidate("设备目前无需采取任何措施。",claim_type="GENERAL_GUIDANCE",source_ids=()),{})

    def test_invalid_json_cannot_become_a_valid_professional_draft(self):
        from backend.professional_answers import validate_professional_draft
        with self.assertRaises((ValueError, json.JSONDecodeError)):
            validate_professional_draft('{"summary":"unfinished',{})


if __name__ == "__main__":
    unittest.main()
