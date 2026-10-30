import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient


class R8BUploadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        with patch.dict(os.environ, {"DATABASE_URL": "sqlite:///" + str(root / "r8b.sqlite3")}):
            from backend import api
            cls.api = api
        cls.api.store = cls.api.Store(root / "r8b.sqlite3")
        cls.api.UPLOAD_ROOT = root / "uploads"
        cls.client = TestClient(cls.api.app)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def conversation(self, title="R8B"):
        return self.client.post("/api/conversations", json={"title": title}).json()["id"]

    def test_upload_persists_file_and_preview_metadata(self):
        cid = self.conversation()
        data = "塔顶温度 84 C，尚未测厚。".encode()
        response = self.client.post(f"/api/conversations/{cid}/files", files={"files": ("现场记录.txt", data, "text/plain")})
        self.assertEqual(response.status_code, 200, response.text)
        record = response.json()["files"][0]
        self.assertEqual(record["file_sha256"], hashlib.sha256(data).hexdigest())
        self.assertIn("塔顶温度", record["preview"]["text"])
        path = self.api.UPLOAD_ROOT / self.api.store.file(cid, record["id"])["storage_key"]
        self.assertEqual(path.read_bytes(), data)
        listed = self.client.get(f"/api/conversations/{cid}/files").json()["files"]
        self.assertEqual(listed[0]["id"], record["id"])
        other = self.conversation("isolated")
        duplicate_bytes = self.client.post(f"/api/conversations/{other}/files", files={"files": ("copy.txt", data, "text/plain")})
        self.assertEqual(duplicate_bytes.status_code, 200, duplicate_bytes.text)
        other_record = duplicate_bytes.json()["files"][0]
        self.assertNotEqual(self.api.store.file(cid, record["id"])["storage_key"], self.api.store.file(other, other_record["id"])["storage_key"])

    def test_pdf_preview_extracts_simple_content_stream_without_external_upload(self):
        cid = self.conversation()
        pdf = b"%PDF-1.4\n1 0 obj << /Length 41 >> stream\nBT (Local PDF preview) Tj ET\nendstream\nendobj\n%%EOF"
        result = self.client.post(f"/api/conversations/{cid}/files", files={"files": ("local.pdf", pdf, "application/pdf")})
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()["files"][0]["preview"]["status"], "pdf_preview")
        self.assertIn("Local PDF preview", result.json()["files"][0]["preview"]["text"])

    def test_upload_rejects_unsupported_extension_and_mime_mismatch(self):
        cid = self.conversation()
        self.assertEqual(self.client.post(f"/api/conversations/{cid}/files", files={"files": ("evil.exe", b"MZ", "text/plain")}).status_code, 415)
        self.assertEqual(self.client.post(f"/api/conversations/{cid}/files", files={"files": ("fake.pdf", b"not a pdf", "application/pdf")}).status_code, 415)
        self.assertEqual(list((self.api.UPLOAD_ROOT).rglob(".upload-*")), [])

    def test_upload_stream_limit_and_six_file_batch_are_rejected(self):
        cid = self.conversation()
        oversized = self.client.post(f"/api/conversations/{cid}/files", files={"files": ("large.txt", b"x" * (self.api.MAX_UPLOAD_BYTES + 1), "text/plain")})
        self.assertEqual(oversized.status_code, 413)
        batch = [("files", (f"{i}.txt", str(i).encode(), "text/plain")) for i in range(6)]
        too_many = self.client.post(f"/api/conversations/{cid}/files", files=batch)
        self.assertEqual(too_many.status_code, 422)
        self.assertEqual(self.api.store.files(cid), [])
        self.assertEqual(list(self.api.UPLOAD_ROOT.rglob(".upload-*")), [])

    def test_upload_isolated_by_conversation_and_run_snapshot_binds_files(self):
        a, b = self.conversation("A"), self.conversation("B")
        upload = self.client.post(f"/api/conversations/{a}/files", files={"files": ("evidence.md", b"observed", "text/markdown")}).json()["files"][0]
        self.assertEqual(self.client.get(f"/api/conversations/{b}/files/{upload['id']}/preview").status_code, 404)
        run = self.client.post(f"/api/conversations/{a}/runs", json={"question": "check", "material": "CS", "file_ids": [upload["id"]]}).json()
        snapshot = self.client.get(f"/api/runs/{run['run_id']}/input").json()
        self.assertEqual(snapshot["question"], "check")
        self.assertEqual(snapshot["attachments"][0]["id"], upload["id"])
        self.assertIn("RULE_DEMO", snapshot["mode_disclaimer"])
        self.assertEqual(self.client.get(f"/api/conversations/{a}").json()["messages"][0]["attachments"][0]["id"], upload["id"])

    def test_run_rejects_cross_conversation_attachment_and_patch_rename(self):
        a, b = self.conversation("A"), self.conversation("B")
        upload = self.client.post(f"/api/conversations/{a}/files", files={"files": ("x.txt", b"x", "text/plain")}).json()["files"][0]
        response = self.client.post(f"/api/conversations/{b}/runs", json={"question": "x", "file_ids": [upload["id"]]})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.client.patch(f"/api/conversations/{a}", json={"title": "Renamed"}).json()["title"], "Renamed")

    def test_run_snapshot_reports_prior_history_without_claiming_it_was_included(self):
        cid = self.conversation("history")
        first = self.client.post(f"/api/conversations/{cid}/runs", json={"question": "first"}).json()
        self.client.get(first["events_url"])
        second = self.client.post(f"/api/conversations/{cid}/runs", json={"question": "second"}).json()
        snapshot = self.client.get(f"/api/runs/{second['run_id']}/input").json()
        self.assertGreaterEqual(snapshot["history_message_count"], 2)
        self.assertEqual(len(snapshot["history_message_ids"]), snapshot["history_message_count"])
        self.assertFalse(snapshot["history_scope"]["selected_for_this_run"])
        self.assertIn("不代表LLM记忆", snapshot["mode_disclaimer"])


if __name__ == "__main__":
    unittest.main()
