from __future__ import annotations

import json
import importlib
import os
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from types import SimpleNamespace

from backend.store import Store
from fastapi.testclient import TestClient
from orchestration.evidence_audit import audit_claim, skeptic_findings
from orchestration.graph import AgentGraph, RunState, public_tool_result
from orchestration.semantics import Claim


class P3BClaimAuditTests(unittest.TestCase):
    def make_state(self, *, context=None, observations=None, sources=None):
        return RunState(
            run_id="audit-run", conversation_id="conv", question="candidate?",
            context=context or {}, observations=observations or [],
            tool_results=[{"tool": "standard_clause_search", "result": {"status": "ok", "source": sources or []}}],
        )

    def make_claim(self, cid="R-1"):
        return Claim(claim_id="claim-1", kind="mechanism_candidate", text="candidate pending review",
                     source_clause_ids=[cid], observation_ids=["obs-ph"]).model_dump(mode="json")

    def test_missing_official_or_same_run_source_stays_e0_unresolved(self):
        canonical = {"R-1": {"clause_id": "R-1", "standard_code": "GB/T X", "clause_no": "1", "page": 1,
                             "applicable_conditions": {}}}
        state = self.make_state(sources=[])
        result = audit_claim(self.make_claim(), state, canonical)
        self.assertEqual((result.grade, result.verdict, result.review_status), ("E0", "unresolved", "requires_human_review"))
        self.assertIn("current_run_source", {x["check"] for x in result.checks})

    def test_source_membership_and_same_run_provenance_cap_at_e1(self):
        canonical = {"R-1": {"clause_id": "R-1", "standard_code": "GB/T X", "clause_no": "1", "page": 1,
                             "content_raw": "some standard sentence", "applicable_conditions": {}}}
        source = {"clause_id": "R-1", "standard_code": "GB/T X", "clause_no": "1", "page": 1, "content_raw": "some standard sentence"}
        result = audit_claim(self.make_claim(), self.make_state(sources=[source]), canonical)
        self.assertEqual(result.grade, "E1")
        self.assertEqual(result.verdict, "unresolved", "E1 is provenance, not semantic entailment")
        self.assertEqual(result.review_status, "requires_human_review")
        self.assertIsNone(result.independent_validation)

    def test_explicit_condition_mismatch_is_not_applicable(self):
        canonical = {"R-1": {"clause_id": "R-1", "standard_code": "GB/T X", "clause_no": "1", "page": 1,
                             "content_raw": "该规则只适用于指定材质和介质条件。",
                             "applicable_conditions": {"material": ["碳钢"], "medium": ["氯化氢"]}}}
        source = {"clause_id": "R-1", "standard_code": "GB/T X", "clause_no": "1", "page": 1}
        state = self.make_state(context={"material": "奥氏体不锈钢", "medium": ["水"]}, sources=[source])
        result = audit_claim(self.make_claim(), state, canonical)
        self.assertEqual(result.grade, "E1")
        self.assertEqual(result.verdict, "unresolved", "condition mismatch is surfaced for human review, not finalized as semantic contradiction")
        self.assertTrue(any(x["status"] == "mismatch" for x in result.checks))

    def test_unknown_observations_never_turn_into_negative_evidence(self):
        state = self.make_state(observations=[{"field": "wall_thinning", "observation_state": "unknown", "normalized_value": None}])
        state.claims = [self.make_claim()]
        findings = skeptic_findings(state)
        self.assertEqual(findings[0]["verdict"], "unresolved")
        self.assertIn("unknown不能作为无减薄或有减薄", findings[0]["finding"])

    def test_rbi_unreviewed_risk_fields_are_masked_in_sse_copy_only(self):
        original = {"status": "ok", "result": {"risk_level": "低风险", "risk_level_unified": "L1",
                    "nested": {"likelihood": "1", "consequence": "A", "inspection_interval_year": 5}, "other": "kept"}}
        public = public_tool_result("rbi_lookup", original)
        self.assertEqual(original["result"]["risk_level_unified"], "L1", "audit still sees untouched teacher payload")
        self.assertNotIn("risk_level", public["result"])
        self.assertNotIn("risk_level_unified", public["result"])
        self.assertEqual(public["result"]["nested"], {})
        self.assertEqual(public["result"]["other"], "kept")

    def test_rbi_tool_evidence_does_not_become_unreviewed_risk_claim_or_sse_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = RunState("rbi-gate", "c", "主要损伤机理是什么？", {
                "material": "碳钢", "medium": ["氯化氢"], "equipment_type": "换热器",
                "operating_condition": "操作温度110℃，压力0.1MPa，已投用8年",
                "field_evidence": "pH 5.8，铁离子 4.1 mg/L",
            })
            events = []
            AgentGraph(checkpoint_path=Path(tmp) / "checkpoints.sqlite").run(state, lambda *event: events.append(event))
            self.assertTrue(state.rbi_results, "keep the frozen tool call for trace compatibility")
            self.assertTrue(any(gap["field"] == "rbi_level_evidence" for gap in state.gaps))
            self.assertFalse(any(claim["kind"] == "risk_level" for claim in state.claims))
            self.assertFalse(any(token in state.answer for token in ("L1", "L2", "L3", "L4", "低风险", "高风险")))
            tool_results = [event[2]["result"] for event in events if event[0] == "tool_result" and event[2].get("tool") == "rbi_lookup"]
            self.assertTrue(tool_results)
            encoded = json.dumps(tool_results, ensure_ascii=False)
            for field in ("risk_level", "risk_level_unified", "likelihood", "consequence", "inspection_interval_year"):
                self.assertNotIn(field, encoded)

    def test_full_graph_persists_claim_audit_and_skeptic_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "business.sqlite"
            checkpoint = Path(tmp) / "checkpoint.sqlite"
            store = Store(db_path)
            conversation = store.create_conversation("P3B integration")
            run = store.create_run(conversation["id"], "塔顶水样pH 5.8，铁离子 4.1 mg/L，尚未测厚，可能的损伤机理？", {
                "material": "碳钢", "medium": ["氯化氢"], "equipment_type": "换热器",
                "field_evidence": "塔顶水样pH 5.8，铁离子 4.1 mg/L，尚未测厚",
            }, "RULE_DEMO")
            state = RunState(run["id"], conversation["id"], run["question"], run["context"])
            AgentGraph(checkpoint_path=checkpoint).run(state, lambda kind, agent, payload: store.append_event(run["id"], kind, agent, payload))
            replay = store.events(run["id"])
            kinds = {event["type"] for event in replay}
            self.assertIn("claim_added", kinds)
            self.assertIn("claim_checked", kinds)
            self.assertIn("requires_human_review", kinds)
            self.assertEqual([e["sequence"] for e in replay], list(range(1, len(replay) + 1)))
            self.assertTrue(state.claims)
            self.assertTrue(all(c["grade"] in {"E0", "E1"} and c["verdict"] == "unresolved" for c in state.claims))
            self.assertTrue(all(c["review_status"] == "requires_human_review" for c in state.claims))
            self.assertTrue(state.disagreements)
            self.assertTrue(all("RBI工具返回" not in state.answer and label not in state.answer for label in ("L1", "低风险", "高风险")))
            reopened = Store(db_path)
            persisted_claims = reopened.claims(run["id"])
            persisted_disagreements = reopened.disagreements(run["id"])
            self.assertEqual(len(persisted_claims), len(state.claims))
            self.assertEqual(len(persisted_disagreements), len(state.disagreements))
            self.assertEqual([e["sequence"] for e in reopened.events(run["id"])], list(range(1, len(replay) + 1)))

    def test_event_log_redacts_secrets_and_preserves_protocol_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / "events.sqlite")
            conv = store.create_conversation("secret scrub")
            run = store.create_run(conv["id"], "test", {}, "RULE_DEMO")
            event = store.append_event(run["id"], "tool_called", "evidence_agent", {
                "tool": "standard_clause_search", "args": {"keyword": "api_key=abc123", "access_token": "tok-secret"}}
            )
            self.assertEqual(event["sequence"], 1)
            self.assertEqual(event["type"], "tool_called")
            replayed = store.events(run["id"])[0]
            self.assertIn("[REDACTED]", replayed["payload"]["args"]["keyword"])
            self.assertEqual(replayed["payload"]["args"]["access_token"], "[REDACTED]")
            self.assertNotIn("abc123", json.dumps(replayed["payload"]))
            self.assertNotIn("tok-secret", json.dumps(replayed["payload"]))

    def test_current_graph_projects_actual_claim_reviews_without_inventing_disagreements(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "api.sqlite"
            with patch.dict(os.environ, {"DATABASE_URL": "sqlite:///" + str(db).replace("\\", "/")}):
                api_module = importlib.reload(importlib.import_module("backend.api"))
            client = TestClient(api_module.app)
            conversation = client.post("/api/conversations", json={"title": "P3B views"}).json()
            run = client.post(f"/api/conversations/{conversation['id']}/runs", json={
                "question": "塔顶水样pH 5.8，铁离子升高，尚未测厚，可能的损伤机理？",
                "material": "碳钢", "medium": ["氯化氢"],
                "field_evidence": "塔顶水样pH 5.8，铁离子升高，尚未测厚",
            }).json()
            response = client.get(run["events_url"])
            self.assertEqual(response.status_code, 200)
            claims = client.get(f"/api/runs/{run['run_id']}/claims").json()["claims"]
            disagreements = client.get(f"/api/runs/{run['run_id']}/disagreements").json()["disagreements"]
            # Graph hypotheses and actual reviewer rows are projected into the
            # existing SQLite ledger; no conflict is fabricated when none exists.
            self.assertTrue(claims)
            self.assertTrue(all(c["review_status"] == "requires_human_review" for c in claims))
            self.assertEqual(disagreements, [])
            events = client.get(f"/api/runs/{run['run_id']}/events").json()["events"]
            self.assertTrue(any(event["type"] == "review_result" for event in events))
            self.assertTrue(any(event["type"] == "claim_checked" for event in events))
            self.assertTrue(any(event["type"] == "agent_completed" and event["agent"] == "evidence_auditor" for event in events))
            self.assertTrue(any(event["type"] == "agent_completed" and event["agent"] == "skeptic" for event in events))
            terminal = next(event for event in events if event["type"] == "run_completed")
            self.assertIsNone(terminal["payload"]["risk_level"])
            self.assertTrue(all({"type", "agent", "payload", "sequence"}.issubset(event) for event in events))


if __name__ == "__main__":
    unittest.main()
