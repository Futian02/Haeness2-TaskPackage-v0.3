"""Owner regression checks for S1 route safety/legacy R9 bridge.
No network, no DB, no upstream modification.
"""
import unittest
from pydantic import ValidationError
from orchestration.intent import classify_intent
from backend.intent_router_v2 import LLMStructuredIntentRouter, MainRoute, RouteDecision


class OwnerV2RoutingRegressions(unittest.TestCase):
    CONTEXT = {"material": "碳钢", "medium": ["湿硫化氢"], "equipment_type": "管道"}

    def test_terse_device_followups_keep_legacy_engineering(self):
        for question in ("设备腐蚀", "请问帮我设备情况可能是什么", "这台设备的裂纹怎么检查"):
            with self.subTest(question=question):
                self.assertIn(classify_intent(question, self.CONTEXT),
                              {"device_diagnosis", "deterministic_rbi_grade", "hypothesis_exploration"})

    def test_numbered_standard_reference_is_lookup_without_verb(self):
        for q in ("GB/T-DEMO 标准第4.1条", "GB/T 30579-2022 第5.23条"):
            with self.subTest(q=q):
                self.assertEqual(classify_intent(q, {}), "standard_lookup")

    def test_context_does_not_hijack_general_requests(self):
        for q in ("你好", "把这段腐蚀报告翻译成英文", "帮我写一篇关于腐蚀机理的科普文章"):
            with self.subTest(q=q):
                self.assertEqual(classify_intent(q, self.CONTEXT), "general_chat")

    def test_model_cannot_embed_high_risk_task_in_general_route(self):
        payload = {
            "version": "v2a.1", "primary_route": "GENERAL", "safety_relevance": False, "confidence": 0.9,
            "subtasks": [{
                "id": "engineering", "kind": "DEVICE_DIAGNOSIS",
                "user_goal": "judge device risk", "task_risk": "HIGH_CONSEQUENCE",
                "depends_on": [], "requires": []
            }],
        }
        with self.assertRaises(ValidationError):
            RouteDecision.model_validate(payload)
        router = LLMStructuredIntentRouter(provider=lambda _: payload, enabled=True)
        result = router.route("你好")
        self.assertEqual(result.primary_route, MainRoute.GENERAL)
        self.assertEqual(result.model_usage.get("source"), "fallback")
        self.assertEqual(result.subtasks[0].kind.value, "GENERAL_EXPLANATION")


if __name__ == "__main__":
    unittest.main()
