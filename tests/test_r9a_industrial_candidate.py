from __future__ import annotations

import unittest
from threading import Barrier

from orchestration.p6_parallel_audit import AuditFinding, SkepticFinding
from orchestration.r9_industrial_candidate import (
    IndustrialCandidate, MAX_INVESTIGATIONS, TEACHER_TOOLS,
)


CLAUSE = {"clause_id": "C-1", "standard_code": "GB/T-DEMO", "clause_no": "4.1", "page": 10}
CONTEXT = {
    "material": "碳钢", "medium": ["湿硫化氢"], "equipment_type": "管道",
    "evidence": {"wall_thinning": False, "h2s_ppm": 2.0},
}


def envelope(*, source=None, result=None, status="ok"):
    rows = source if source is not None else [CLAUSE]
    return {"status": status, "in_domain": True, "result": result or {}, "source": rows, "message": ""}


class FakeTools:
    def __init__(self, *, source=None, damage=None, clause=None, rbi=None):
        self.counts = {name: 0 for name in TEACHER_TOOLS}
        self.source = source
        self.damage = damage
        self.clause = clause
        self.rbi = rbi

    def registry(self):
        return {"damage_mechanism_query": self.damage_tool,
                "rbi_lookup": self.rbi_tool,
                "standard_clause_search": self.clause_tool}

    def damage_tool(self, **kwargs):
        self.counts["damage_mechanism_query"] += 1
        return self.damage(**kwargs) if callable(self.damage) else self.damage or envelope(source=self.source, result={"mechanisms": [{"name": "湿硫化氢破坏", "clause_id": "C-1"}]})

    def clause_tool(self, **kwargs):
        self.counts["standard_clause_search"] += 1
        return self.clause(**kwargs) if callable(self.clause) else self.clause or envelope(source=self.source, result={"hits": [{"clause_id": "C-1"}]})

    def rbi_tool(self, **kwargs):
        self.counts["rbi_lookup"] += 1
        return self.rbi(**kwargs) if callable(self.rbi) else self.rbi or envelope(source=self.source, result={"risk_level_unified": "L5"})


class R9AIndustrialCandidateTests(unittest.TestCase):
    def build(self, fake, **kwargs):
        return IndustrialCandidate(tool_registry=fake.registry(), clause_index={"C-1": CLAUSE}, **kwargs)

    def test_exactly_three_teacher_tools_and_standard_query_without_material(self):
        fake = FakeTools()
        graph = self.build(fake)
        result = graph.run("GB/T-DEMO 标准第4.1条是什么？", {})
        self.assertEqual(set(graph.tool_registry), set(TEACHER_TOOLS))
        self.assertEqual(fake.counts["standard_clause_search"], 1)
        self.assertEqual(fake.counts["damage_mechanism_query"], 0)
        self.assertEqual(result["output"]["status"], "draft_for_review")

    def test_missing_context_mechanism_question_only_explores_traceable_sources(self):
        fake = FakeTools()
        result = self.build(fake).run("设备腐蚀原因是什么？", {"material": "碳钢"})
        self.assertEqual(result["output"]["status"], "exploratory_directions")
        self.assertEqual(fake.counts["damage_mechanism_query"], 0)
        self.assertEqual(fake.counts["standard_clause_search"], 1)
        self.assertIsNone(result["output"]["risk_level"])

    def test_low_quality_retrieval_rewrites_and_retries_with_traceable_source(self):
        n = {"calls": 0}
        def clause(**kwargs):
            n["calls"] += 1
            if n["calls"] == 1:
                return envelope(source=[], result={"hits": []}, status="not_found")
            return envelope(source=[CLAUSE], result={"hits": [{"clause_id": "C-1"}]})
        fake = FakeTools(damage=envelope(source=[], result={"mechanisms": []}, status="not_found"), clause=clause)
        result = self.build(fake).run("请问帮我设备情况可能是什么", CONTEXT)
        self.assertGreaterEqual(n["calls"], 2)
        self.assertGreaterEqual(result["investigate_iteration"], 2)
        self.assertTrue(result["citations"])
        self.assertNotEqual(result["query_variants"][0], result["query_variants"][1])

    def test_identical_query_zero_information_gain_stops_loop(self):
        fake = FakeTools(source=[])
        result = self.build(fake).run("设备腐蚀", CONTEXT)
        self.assertLessEqual(result["investigate_iteration"], MAX_INVESTIGATIONS)
        self.assertIn("zero_information_gain", result["gate_decisions"][-1]["reason_codes"])
        self.assertLessEqual(result["tool_budget"], 8)

    def test_generic_mechanism_candidate_does_not_require_wall_thickness(self):
        fake = FakeTools()
        context = {k: v for k, v in CONTEXT.items() if k != "evidence"}
        result = self.build(fake).run("设备腐蚀机理", context)
        self.assertEqual(result["output"]["status"], "draft_for_review")
        self.assertTrue(result["auditor_findings"])
        self.assertTrue(result["skeptic_findings"])
        self.assertIsNone(result["output"]["risk_level"])

    def test_explicit_thickness_confirmation_requires_wall_measurement(self):
        fake = FakeTools()
        context = {k: v for k, v in CONTEXT.items() if k != "evidence"}
        result = self.build(fake).run("请确认是否存在壁厚减薄", context)
        self.assertEqual(result["output"]["status"], "insufficient_evidence")
        self.assertEqual(result["review_rows"], [])
        self.assertIsNone(result["output"]["risk_level"])

    def test_stream_callback_observes_tool_and_actual_parallel_branches(self):
        observed = []
        result = self.build(FakeTools()).run("设备腐蚀机理", CONTEXT, on_event=observed.append)
        self.assertEqual(result["output"]["status"], "draft_for_review")
        names = [row["event"] for row in observed]
        self.assertIn("tool_called", names)
        self.assertIn("review_started", names)
        self.assertEqual(names.count("agent_completed"), 2)

    def test_standard_lookup_rejects_requested_standard_mismatch(self):
        fake = FakeTools(source=[{**CLAUSE, "standard_code": "GB/T 1234-2022"}])
        index = {"C-1": {**CLAUSE, "standard_code": "GB/T 9999-2022", "title": "设备条款", "content_raw": "设备工况"}}
        result = IndustrialCandidate(tool_registry=fake.registry(), clause_index=index).run("查询 GB/T 1234 设备工况标准", {})
        self.assertEqual(result["citations"], [])
        self.assertEqual(result["output"]["status"], "unresolved")
        self.assertEqual(result["tool_calls"][0]["rejected_sources"][0]["reason"], "requested_standard_mismatch")

    def test_satisfied_evidence_dispatches_two_parallel_reviews(self):
        fake = FakeTools()
        result = self.build(fake).run("设备腐蚀机理", CONTEXT)
        self.assertEqual(result["review_round"], 1)
        self.assertTrue(result["auditor_findings"])
        self.assertTrue(result["skeptic_findings"])
        self.assertTrue(any(e["event"] == "review_started" for e in result["events"]))

    def test_auditor_and_skeptic_execute_in_parallel_fanout(self):
        barrier = Barrier(2, timeout=2)
        fake = FakeTools()
        def auditor(state):
            barrier.wait()
            return [AuditFinding(state["run_id"], "claim", "C-1", "evidence_auditor", "review-1", {"grade": "E0"})]
        def skeptic(state):
            barrier.wait()
            return [SkepticFinding(state["run_id"], "claim", "C-1", "skeptic", "review-1", {"verdict": "unresolved"})]
        result = self.build(fake, auditor=auditor, skeptic=skeptic).run("设备腐蚀机理", CONTEXT)
        self.assertTrue(result["auditor_findings"])
        self.assertTrue(result["skeptic_findings"])

    def test_parallel_review_conflict_is_preserved_and_clamped_to_e0(self):
        fake = FakeTools()
        def auditor(state):
            return [
                AuditFinding(state["run_id"], "claim", "C-1", "evidence_auditor", "review-1", {"grade": "E1", "finding": "matched"}),
                AuditFinding(state["run_id"], "claim", "C-1", "evidence_auditor", "review-1", {"grade": "E0", "finding": "mismatch"}),
            ]
        def skeptic(state):
            return [SkepticFinding(state["run_id"], "claim", "C-1", "skeptic", "review-1", {"verdict": "unresolved"})]
        result = self.build(fake, auditor=auditor, skeptic=skeptic).run("设备腐蚀机理", CONTEXT)
        conflict = next(row for row in result["review_rows"] if row["origin_agent"] == "evidence_auditor")
        self.assertTrue(conflict["conflict_requires_review"])
        self.assertEqual(conflict["verification_level"], "E0")
        self.assertEqual(len(conflict["conflicting_payloads"]), 2)
        self.assertEqual(result["output"]["status"], "review_conflict")

    def test_wrong_page_is_not_verified(self):
        wrong_page = {**CLAUSE, "page": 999}
        fake = FakeTools(source=[wrong_page])
        result = self.build(fake).run("设备腐蚀机理", CONTEXT)
        audit = next(row for row in result["review_rows"] if row["origin_agent"] == "evidence_auditor")
        self.assertEqual(audit["verification_level"], "E0")
        self.assertFalse(audit["result"]["checks"]["page"])
        self.assertEqual(result["output"]["verification_level"], "E0")

    def test_untrusted_e3_or_risk_grade_cannot_become_device_risk(self):
        fake = FakeTools()
        def auditor(state):
            return [AuditFinding(state["run_id"], "claim", "C-1", "evidence_auditor", "review-1", {"grade": "E3", "risk_level": "L5"})]
        result = self.build(fake, auditor=auditor).run("设备腐蚀机理", CONTEXT)
        self.assertEqual(result["review_rows"][0]["verification_level"], "E0")
        self.assertIsNone(result["output"]["risk_level"])
        self.assertFalse(result["output"]["human_signed"])

    def test_teacher_rbi_risk_label_is_not_promoted_to_final_device_risk(self):
        fake = FakeTools(rbi=envelope(source=[CLAUSE], result={"risk_level_unified": "L5", "risk_level": "极高风险"}))
        context = {**CONTEXT, "pressure_mpa": 1.2, "service_years": 12}
        result = self.build(fake).run("设备腐蚀机理", context)
        self.assertEqual(fake.counts["rbi_lookup"], 1)
        self.assertIsNone(result["output"]["risk_level"])
        self.assertFalse(result["output"]["human_signed"])

    def test_review_requested_recheck_is_bounded_by_two_retries(self):
        lookup = {"n": 1}
        def clause(**kwargs):
            lookup["n"] += 1
            row = {**CLAUSE, "clause_id": f"C-{lookup['n']}", "page": 10 + lookup["n"]}
            return envelope(source=[row], result={"hits": [{"clause_id": row["clause_id"]}]})
        fake = FakeTools(clause=clause)
        def auditor(state):
            return [AuditFinding(state["run_id"], "claim", "C-1", "evidence_auditor", f"review-{state['review_round']}",
                                 {"grade": "E0", "retry_reason": f"核对印刷页码第{state['review_round']}轮"})]
        index = {f"C-{i}": {**CLAUSE, "clause_id": f"C-{i}", "page": 10 + i} for i in range(1, 5)}
        result = IndustrialCandidate(tool_registry=fake.registry(), clause_index=index, auditor=auditor).run("设备腐蚀机理", CONTEXT)
        self.assertEqual(result["review_retry_count"], 2)
        self.assertEqual(result["review_round"], 3)
        self.assertLessEqual(result["investigate_iteration"], MAX_INVESTIGATIONS)
        self.assertLessEqual(len(result["tool_calls"]), 8)
        self.assertEqual(result["gate_decisions"][-1]["next_action"], "report")

    def test_transient_tool_failure_retries_and_records_attempt_count(self):
        n = {"calls": 0}
        def clause(**kwargs):
            n["calls"] += 1
            if n["calls"] == 1:
                raise TimeoutError("transient")
            return envelope(source=[CLAUSE], result={"hits": []})
        fake = FakeTools(clause=clause)
        result = self.build(fake).run("GB/T-DEMO 标准第4.1条", {})
        call = next(row for row in result["tool_calls"] if row["tool"] == "standard_clause_search")
        self.assertEqual(n["calls"], 2)
        self.assertEqual(call["attempts"], 2)
        self.assertEqual(call["status"], "ok")

    def test_permanent_tool_exception_ends_as_unresolved_not_crash(self):
        def clause(**kwargs):
            raise RuntimeError("fixture failure")
        fake = FakeTools(clause=clause)
        result = self.build(fake).run("GB/T-DEMO 标准条款", {})
        self.assertEqual(result["output"]["status"], "unresolved")
        self.assertEqual(result["tool_calls"][0]["status"], "error")
        self.assertIn("fixture failure", result["tool_calls"][0]["error"])

    def test_tool_budget_is_bounded_and_configurable_only_downward(self):
        fake = FakeTools()
        result = self.build(fake).run("设备腐蚀机理", CONTEXT, tool_budget=1)
        self.assertEqual(result["tool_budget"], 0)
        self.assertLessEqual(len(result["tool_calls"]), 1)
        self.assertIn("tool_budget_exhausted", result["gate_decisions"][-1]["reason_codes"])
        with self.assertRaises(ValueError):
            self.build(FakeTools()).run("q", CONTEXT, tool_budget=9)

    def test_repeat_run_is_idempotent_by_run_key_and_does_not_sign(self):
        graph = self.build(FakeTools())
        first = graph.run("設備腐蚀机理".replace("蚀", "蝕"), CONTEXT, run_id="same-run")
        second = graph.run("設備腐蚀机理".replace("蚀", "蝕"), CONTEXT, run_id="same-run")
        self.assertEqual(first["tool_call_keys"], second["tool_call_keys"])
        self.assertFalse(first["output"]["human_signed"])
        self.assertFalse(second["output"]["human_signed"])


if __name__ == "__main__":
    unittest.main()
