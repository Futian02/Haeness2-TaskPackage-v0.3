import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from backend.store import Store
from orchestration.graph import AgentGraph, RunState


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name) / "case.db")
        self.conversation = self.store.create_conversation("replay test")

    def tearDown(self): self.temp.cleanup()

    def test_wal_enabled(self):
        with self.store.session() as c:
            self.assertEqual(c.execute("PRAGMA journal_mode").fetchone()[0].lower(), "wal")

    def test_conversation_and_messages_persist(self):
        self.store.add_message(self.conversation["id"], "user", "pH下降")
        self.assertEqual(self.store.messages(self.conversation["id"])[0]["content"], "pH下降")

    def test_run_event_sequence_is_monotonic(self):
        run = self.store.create_run(self.conversation["id"], "q", {}, "RULE_DEMO")
        a = self.store.append_event(run["id"], "run_started", "supervisor", {})
        b = self.store.append_event(run["id"], "run_completed", "supervisor", {})
        self.assertEqual((a["sequence"], b["sequence"]), (1, 2))
        self.assertEqual(a["schema_version"], 1)
        self.assertEqual(a["session_id"], self.conversation["id"])
        self.assertTrue(a["ts"])

    def test_event_replay_after_sequence(self):
        run = self.store.create_run(self.conversation["id"], "q", {}, "RULE_DEMO")
        for n in range(3): self.store.append_event(run["id"], "decision_summary", "supervisor", {"n": n})
        self.assertEqual([e["sequence"] for e in self.store.events(run["id"], 1)], [2, 3])

    def test_tool_calls_and_evidence_are_separate_records(self):
        run = self.store.create_run(self.conversation["id"], "q", {}, "RULE_DEMO")
        self.store.append_event(run["id"], "tool_called", "evidence_agent", {"tool": "standard_clause_search", "args": {"keyword": "pH"}})
        self.store.append_event(run["id"], "tool_result", "evidence_agent", {"tool": "standard_clause_search", "result": {"status": "ok"}})
        self.store.append_event(run["id"], "reference_added", "evidence_agent", {"clause_id": "c1", "standard_code": "GB/X", "clause_no": "1.2", "page": 3})
        with self.store.session() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM tool_calls").fetchone()[0], 1)
            self.assertEqual(c.execute("SELECT COUNT(*) FROM evidence_refs").fetchone()[0], 1)

    def test_mysql_url_fails_loudly(self):
        with self.assertRaises(ValueError): Store("mysql://user:pass@localhost/db")

    def test_knowledge_document_is_draft_by_default(self):
        self.store.add_knowledge_document({"clause_id": "c", "quote_span": "short quote"})
        with self.store.session() as c:
            self.assertEqual(c.execute("SELECT review_status FROM knowledge_documents").fetchone()[0], "draft_needs_review")


class GraphTests(unittest.TestCase):
    def test_graph_has_swappable_nodes_and_required_roles(self):
        graph = AgentGraph()
        self.assertTrue({"supervisor", "evidence_agent", "diagnosis_agent", "rbi_specialist", "evidence_auditor", "reporting_agent"}.issubset(graph.nodes))
        self.assertNotIn("platform", graph.nodes)

    def test_graph_accepts_an_independent_inserted_node(self):
        class TriageNode:
            name = "triage_extension"
            def run(self, state): state.route = "triaged:" + state.route
        graph = AgentGraph()
        graph.add_node(TriageNode(), after="supervisor")
        self.assertEqual(graph.order[1], "triage_extension")
        state = RunState("r", "c", "查条款", {"material": "碳钢", "medium": ["氯化氢"]})
        events = []
        graph.run(state, lambda *args: events.append(args))
        self.assertIn("triage_extension", {event[1] for event in events})

    def test_agent_graph_is_a_real_state_graph_and_checkpoints_are_separate(self):
        from langgraph.graph import StateGraph
        with tempfile.TemporaryDirectory() as tmp:
            checkpoint = Path(tmp) / "graph-checkpoints.sqlite"
            graph = AgentGraph(checkpoint_path=checkpoint)
            self.assertIsInstance(graph.state_graph, StateGraph)
            self.assertTrue({"supervisor", "evidence_agent", "diagnosis_agent", "rbi_specialist", "evidence_auditor", "reporting_agent"}.issubset(graph.state_graph.nodes))
            state = RunState("checkpoint-run", "c", "讲个笑话", {"material": "碳钢", "medium": ["氯化氢"]})
            graph.run(state, lambda *_args: None)
            self.assertEqual(state.route, "out_of_domain")
            self.assertTrue(checkpoint.exists())
            db = sqlite3.connect(checkpoint)
            try:
                tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            finally:
                db.close()
            self.assertIn("checkpoints", tables)
            self.assertNotEqual(checkpoint.resolve(), (Path(tmp) / "business-events.sqlite").resolve())

    def test_graph_fails_fast_when_registered_nodes_do_not_cover_routes(self):
        from orchestration.graph import SupervisorAgent
        with self.assertRaisesRegex(ValueError, "route/registry mismatch"):
            AgentGraph(nodes=[SupervisorAgent()])

    def test_graph_emits_agent_events_and_preserves_unknown(self):
        state = RunState("r", "c", "塔顶水样pH 5.8，尚未测厚", {"material": "碳钢", "medium": ["氯化氢"], "field_evidence": "塔顶水样pH 5.8，尚未测厚", "equipment_type": "换热器"})
        events = []
        AgentGraph().run(state, lambda *x: events.append(x))
        self.assertEqual(state.mode, "RULE_DEMO")
        self.assertEqual(next(x for x in state.observations if x["field"] == "wall_thinning")["observation_state"], "unknown")
        self.assertIn("evidence_agent", {x[1] for x in events})
        self.assertIn("rbi_specialist", {x[1] for x in events})
        self.assertEqual(events[-1][0], "run_completed")
        self.assertFalse(state.rbi_results, "缺温压/投用年限/候选不足时不调用RBI工具")
        self.assertIn("RULE_DEMO", state.answer)

    def test_missing_material_causes_supervisor_to_request_context(self):
        state = RunState("r", "c", "诊断", {"material": "", "medium": []})
        events = []
        # Supervisor routing is independently runnable without touching the teacher tools.
        from orchestration.graph import SupervisorAgent
        SupervisorAgent().run(state)
        self.assertEqual(state.route, "ask_for_context")

    def test_supervisor_skips_tools_when_context_is_missing(self):
        state = RunState("r", "c", "帮我分析这个问题", {"material": "", "medium": []})
        AgentGraph().run(state, lambda *args: None)
        self.assertEqual(state.route, "ask_for_context")
        self.assertEqual(state.tool_results, [])
        self.assertIn("补充材质与介质", state.answer)

    def test_standard_question_routes_only_to_clause_search(self):
        state = RunState("r", "c", "查询盐酸腐蚀标准条款", {"material": "碳钢", "medium": ["氯化氢"]})
        AgentGraph().run(state, lambda *args: None)
        self.assertEqual(state.route, "standard_lookup")
        self.assertEqual([x["tool"] for x in state.tool_results], ["standard_clause_search"])

    def test_out_of_domain_routes_without_teacher_tools(self):
        state = RunState("r", "c", "讲一个笑话", {"material": "碳钢", "medium": ["氯化氢"]})
        AgentGraph().run(state, lambda *args: None)
        self.assertEqual(state.route, "out_of_domain")
        self.assertEqual(state.tool_results, [])
        self.assertIn("不在设备风险研判范围", state.answer)

    def test_rbi_tool_runs_only_when_operating_factors_and_candidate_exist(self):
        state = RunState("r", "c", "主要损伤机理是什么？", {
            "material": "碳钢", "medium": ["氯化氢"], "equipment_type": "换热器",
            "operating_condition": "操作温度110℃，压力0.1MPa，已投用8年", "field_evidence": "pH 5.8",
        })
        AgentGraph().run(state, lambda *args: None)
        tool_names = [x["tool"] for x in state.tool_results]
        self.assertEqual(tool_names.count("rbi_lookup"), 1)
        self.assertEqual(len(state.rbi_results), 1)


if __name__ == "__main__": unittest.main()
