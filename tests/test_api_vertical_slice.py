import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import json

from fastapi.testclient import TestClient


class ApiVerticalSliceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        db = Path(cls.temp.name) / "api.db"
        with patch.dict(os.environ, {"DATABASE_URL": "sqlite:///" + str(db).replace("\\", "/")}):
            cls.api = importlib.import_module("backend.api")
        cls.client = TestClient(cls.api.app)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_health_exposes_only_frozen_teacher_tools(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.json()["teacher_tools"]), {"damage_mechanism_query", "rbi_lookup", "standard_clause_search"})

    def test_create_run_stream_and_replay_are_persisted(self):
        conversation = self.client.post("/api/conversations", json={"title": "SSE test"}).json()
        created = self.client.post(f"/api/conversations/{conversation['id']}/runs", json={
            "question": "塔顶水样pH 5.8，铁离子 4.1 mg/L，尚未测厚，可能的损伤机理？",
            "field_evidence": "塔顶水样pH 5.8，铁离子 4.1 mg/L，尚未测厚",
            "material": "碳钢", "medium": ["氯化氢"], "equipment_type": "换热器",
        }).json()
        response = self.client.get(created["events_url"])
        self.assertEqual(response.status_code, 200)
        self.assertIn("event: ", response.text) if "event: " in response.text else self.assertIn("data: ", response.text)
        replay = self.client.get(f"/api/runs/{created['run_id']}/events").json()["events"]
        self.assertGreater(len(replay), 10)
        self.assertEqual([e["sequence"] for e in replay], sorted(e["sequence"] for e in replay))
        self.assertTrue(all(e["schema_version"] == 1 and e["session_id"] == conversation["id"] and e["ts"] for e in replay))
        conv = self.client.get(f"/api/conversations/{conversation['id']}").json()
        self.assertEqual([m["role"] for m in conv["messages"]], ["user", "assistant"])
        self.assertEqual([m["run_id"] for m in conv["messages"]], [created["run_id"], created["run_id"]])
        self.assertEqual(replay[-1]["type"], "run_completed")
        self.assertEqual(replay[-1]["payload"]["risk_level"], None)

    def test_p12_chat_only_context_routes_to_tools_and_renders_sourced_candidate(self):
        conversation = self.client.post("/api/conversations", json={"title": "P12 无表单诊断"}).json()
        question = "设备：塔顶碱液管线弯头，材质：300系列不锈钢，介质：碱式酸性水，温度：60°C，该减薄属于哪类腐蚀？"
        created = self.client.post(f"/api/conversations/{conversation['id']}/runs", json={"question": question}).json()
        self.client.get(created["events_url"])
        events = self.client.get(f"/api/runs/{created['run_id']}/events").json()["events"]
        resolved = next(row["payload"] for row in events if row["type"] == "context_resolved")
        self.assertEqual(resolved["fields"]["material"], "已记录（具体值未公开）")
        self.assertEqual(resolved["fields"]["medium"], "已记录（具体值未公开）")
        self.assertNotIn("300系列不锈钢", str(events))
        self.assertNotIn("碱式酸性水", str(events))
        self.assertTrue(any(row["type"] == "tool_called" for row in events))
        reply = self.client.get(f"/api/conversations/{conversation['id']}").json()["messages"][-1]["content"]
        self.assertIn("酸性水腐蚀(碱式酸性水)", reply)
        self.assertIn("GB/T 30579-2022 5.23", reply)
        self.assertIn("待核", reply)
        self.assertNotIn("draft_for_review", reply)
        self.assertNotIn("RULE_DEMO", reply)
        self.assertNotIn("风险等级：", reply)

    def test_p12_selected_profile_is_snapshotted_on_new_run(self):
        conversation = self.client.post("/api/conversations", json={"title": "model snapshot"}).json()
        selected = {"profile_id":"profile-test", "provider":"deepseek", "model":"p12-mock-model",
                    "endpoint":"https://api.deepseek.com/v1/chat/completions", "api_key":"synthetic-not-real", "timeout":1}
        with patch("backend.model_profiles.safe_profile", return_value=selected):
            created = self.client.post(f"/api/conversations/{conversation['id']}/runs", json={
                "question":"你好", "model_profile_id":"profile-test"}).json()
        run = self.api.store.run(created["run_id"])
        self.assertEqual(run["mode"], "DEEPSEEK")
        self.assertEqual(run["context"]["_model_profile_snapshot"], {
            "profile_id":"profile-test", "provider":"deepseek", "model":"p12-mock-model"})
        self.assertNotIn("api_key", json.dumps(run["context"]))

    def test_model_profile_api_is_loopback_only_and_never_returns_secret(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {"AETHERIS_MODEL_STORE": temp}, clear=False), \
                patch("backend.model_profiles.socket.getaddrinfo", return_value=[(2, 1, 6, "", ("8.8.8.8", 443))]):
            response = self.client.post("/api/model-profiles", json={"provider":"deepseek", "model":"deepseek-chat",
                "endpoint":"https://api.deepseek.com/v1", "api_key":"synthetic-p12-secret-123"})
            if os.name == "nt":
                self.assertEqual(response.status_code, 200)
                profile = response.json()
                self.assertNotIn("api_key", profile)
                self.assertNotIn("synthetic-p12-secret-123", response.text)
                listing = self.client.get("/api/model-profiles").json()
                self.assertEqual(listing["profiles"][0]["api_key_masked"], "••••••••")
                self.assertNotIn("synthetic-p12-secret-123", json.dumps(listing))
            else:
                self.assertEqual(response.status_code, 503)
            external_host = self.client.get("/api/model-profiles", headers={"host":"config.example"})
            self.assertEqual(external_host.status_code, 403)
            with patch.dict(os.environ, {"APP_ENV":"production"}):
                self.assertEqual(self.client.get("/api/model-profiles").status_code, 503)

    def test_root_serves_built_chat_when_dist_exists(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        if (self.api.FRONTEND_DIST / "index.html").is_file():
            self.assertIn('id="root"', response.text)

    def test_event_replay_is_idempotent(self):
        conversation = self.client.post("/api/conversations", json={}).json()
        run = self.client.post(f"/api/conversations/{conversation['id']}/runs", json={"question": "查条款"}).json()
        self.client.get(run["events_url"])
        all_events = self.client.get(f"/api/runs/{run['run_id']}/events").json()["events"]
        last = all_events[-1]["sequence"]
        self.assertEqual(self.client.get(f"/api/runs/{run['run_id']}/events?after_sequence={last-1}").json()["events"][0]["sequence"], last)
        # Reconnecting the stream replays events; it does not execute the graph twice.
        self.client.get(run["events_url"])
        again = self.client.get(f"/api/runs/{run['run_id']}/events").json()["events"]
        self.assertEqual(len(again), len(all_events))


if __name__ == "__main__":
    unittest.main()
