from __future__ import annotations

import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from backend.store import Store


class LeaseEventIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="p5a-lease-")
        self.store = Store(Path(self.tmp.name) / "business.sqlite")
        self.conversation = self.store.create_conversation("P5A lease integrity")

    def tearDown(self):
        self.tmp.cleanup()

    def new_claimed_run(self, token="worker-a"):
        run = self.store.create_run(self.conversation["id"], "question", {}, "RULE_DEMO")
        self.assertTrue(self.store.claim_run(run["id"], token))
        return run["id"], token

    def make_stale(self, rid):
        with self.store.session() as conn:
            conn.execute("UPDATE runs SET worker_heartbeat_at=? WHERE id=?",
                         ("2000-01-01T00:00:00+00:00", rid))

    def test_explicit_token_required_and_wrong_token_rejected(self):
        rid, token = self.new_claimed_run()
        with self.assertRaises(PermissionError):
            self.store.append_event(rid, "claim_added", "old", {"claim_id": "c"}, worker_token="forged")
        event = self.store.append_event(rid, "agent_started", "worker", {}, worker_token=token)
        self.assertEqual(event["sequence"], 1)

    def test_failed_and_completed_run_reject_old_worker(self):
        for terminal in ("failed", "completed"):
            with self.subTest(terminal=terminal):
                rid, token = self.new_claimed_run("token-" + terminal)
                self.store.append_event(rid, "agent_started", "worker", {}, worker_token=token)
                self.assertTrue(self.store.finish_run(rid, token, terminal, "test" if terminal == "failed" else None))
                with self.assertRaises(PermissionError):
                    self.store.append_event(rid, "claim_added", "stale", {"claim_id": "late"}, worker_token=token)
                events = self.store.events(rid)
                self.assertEqual([e["sequence"] for e in events], [1, 2] if terminal == "failed" else [1])
                if terminal == "failed":
                    self.assertEqual(events[-1]["type"], "run_failed")

    def test_expired_worker_cannot_append_but_recovery_system_event_persists(self):
        rid, token = self.new_claimed_run()
        self.store.append_event(rid, "agent_started", "worker", {}, worker_token=token)
        self.make_stale(rid)
        self.assertTrue(self.store.recover_stale_run(rid, stale_after_seconds=0))
        with self.assertRaises(PermissionError):
            self.store.append_event(rid, "claim_added", "old-worker", {"claim_id": "late"}, worker_token=token)
        events = self.store.events(rid)
        self.assertEqual([(e["sequence"], e["type"], e["payload"].get("code")) for e in events],
                         [(1, "agent_started", None), (2, "error", "worker_lost")])
        self.assertEqual(self.store.run(rid)["status"], "failed")

    def test_completed_terminal_event_and_assistant_reply_commit_atomically(self):
        rid, token = self.new_claimed_run("terminal-worker")
        self.store.append_event(rid, "agent_completed", "reporting_agent", {}, worker_token=token)
        self.assertTrue(self.store.finish_run_with_message(rid, token, "review required", {"summary": "complete"}))
        events = self.store.events(rid)
        self.assertEqual([(e["sequence"], e["type"]) for e in events],
                         [(1, "agent_completed"), (2, "run_completed")])
        self.assertEqual(events[-1]["payload"], {"summary": "complete"})
        self.assertEqual(self.store.run(rid)["status"], "completed")
        self.assertEqual([m["content"] for m in self.store.messages(self.conversation["id"]) if m["role"] == "assistant"],
                         ["review required"])
        with self.assertRaises(PermissionError):
            self.store.append_event(rid, "claim_added", "stale", {"claim_id": "late"}, worker_token=token)

    def test_ten_concurrent_writers_and_recovery_have_atomic_order(self):
        rid, token = self.new_claimed_run("race-worker")
        self.make_stale(rid)
        barrier = threading.Barrier(11)

        def writer(i):
            barrier.wait()
            try:
                event = self.store.append_event(rid, "decision_summary", "race-worker", {"n": i}, worker_token=token)
                return ("accepted", event["sequence"])
            except PermissionError:
                return ("rejected", i)

        def recover():
            barrier.wait()
            return self.store.recover_stale_run(rid, stale_after_seconds=0)

        with ThreadPoolExecutor(max_workers=11) as pool:
            futures = [pool.submit(writer, i) for i in range(10)]
            recovery = pool.submit(recover)
            results = [f.result(timeout=10) for f in futures]
            self.assertTrue(recovery.result(timeout=10))

        # Depending on SQLite lock order, a writer may commit before recovery;
        # every event after worker_lost must be rejected and sequence numbers contiguous.
        events = self.store.events(rid)
        self.assertEqual(events[-1]["type"], "error")
        self.assertEqual(events[-1]["payload"]["code"], "worker_lost")
        self.assertEqual([e["sequence"] for e in events], list(range(1, len(events) + 1)))
        self.assertLessEqual(sum(status == "accepted" for status, _ in results), 10)
        with self.assertRaises(PermissionError):
            self.store.append_event(rid, "run_completed", "race-worker", {}, worker_token=token)

    def test_legacy_trusted_emitters_cannot_bypass_terminal_state(self):
        rid = self.store.create_run(self.conversation["id"], "q", {}, "RULE_DEMO")["id"]
        first = self.store.append_event(rid, "run_started", "supervisor", {})
        self.assertEqual(first["sequence"], 1)
        token = self.store.run(rid)["worker_token"]
        self.assertTrue(self.store.finish_run(rid, token, "failed", "fixture"))
        with self.assertRaises(PermissionError):
            self.store.append_event(rid, "run_completed", "supervisor", {})


if __name__ == "__main__":
    unittest.main()
