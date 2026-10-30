from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from backend.conversation_memory import ConversationMemoryService
from backend.store import Store


class ConversationMemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="v2c-memory-")
        self.db = Path(self.temp.name) / "isolated.sqlite3"
        self.store = Store(self.db)
        self.a = self.store.create_conversation("A")['id']
        self.b = self.store.create_conversation("B")['id']
        self.memory = ConversationMemoryService(self.store, retain_recent_turns=1,
                                                max_context_chars=600, summary_threshold_chars=1)

    def tearDown(self):
        self.temp.cleanup()

    def user(self, cid, text):
        return self.store.add_message(cid, "user", text)

    def assistant(self, cid, text):
        return self.store.add_message(cid, "assistant", text)

    def add_turns(self, cid, count, prefix="turn"):
        rows = []
        for index in range(count):
            rows.append(self.user(cid, f"{prefix} question {index}"))
            rows.append(self.assistant(cid, f"{prefix} answer {index}"))
        return rows

    def test_single_wal_database_and_additive_schema_migration_preserve_messages(self):
        row = self.user(self.a, "keep exact message")
        self.assertEqual(self.store.conversation_memory_schema_version, 1)
        with self.store.session() as con:
            self.assertEqual(con.execute("PRAGMA journal_mode").fetchone()[0].lower(), "wal")
            # Simulate a pre-S1-C schema while preserving the original conversation/message data.
            con.execute("DROP TRIGGER IF EXISTS trg_memory_source_same_conversation")
            con.execute("DROP TRIGGER IF EXISTS trg_fact_source_same_conversation")
            con.execute("DROP TRIGGER IF EXISTS trg_fact_confirmed_from_user")
            con.execute("DROP TABLE conversation_fact_assertions")
            con.execute("DROP TABLE conversation_memories")
            con.execute("DROP TABLE conversation_memory_schema")
        self.store = Store(self.db)
        self.assertEqual(self.store.messages(self.a)[0]["content"], "keep exact message")
        self.assertEqual(self.store.messages(self.a)[0]["id"], row["id"])
        self.assertEqual(self.store.conversation_memory_schema_version, 1)
        self.assertEqual(self.db.name, "isolated.sqlite3")
        self.assertFalse((Path(self.temp.name) / f"{self.a}.sqlite3").exists())

    def test_conversation_history_facts_and_summaries_are_isolated(self):
        a_msg = self.user(self.a, "A has H2S")
        self.user(self.b, "B has steam")
        self.memory.record_user_confirmed_fact(self.a, field="medium", value="H2S", unit=None,
                                               object_scope="vessel-A", source_message_id=a_msg["id"])
        self.assertEqual([x["value"] for x in self.memory.get_confirmed_facts(self.a)], ["H2S"])
        self.assertEqual(self.memory.get_confirmed_facts(self.b), [])
        self.assertEqual([x["content"] for x in self.memory.get_recent_visible_history(self.b)], ["B has steam"])
        self.add_turns(self.a, 8, "A")
        self.add_turns(self.b, 8, "B")
        disabled = self.memory.propose_summary_if_needed(self.a)
        self.assertEqual(disabled["status"], "model_summary_disabled")
        self.assertIsNone(disabled["summary"])

    def test_explicit_correction_supersedes_prior_value_but_keeps_audit_history(self):
        first = self.user(self.a, "温度为180℃")
        second = self.user(self.a, "更正：温度为160℃")
        old = self.memory.record_user_confirmed_fact(self.a, field="temperature", value=180, unit="℃",
                                                     object_scope="heater-1", source_message_id=first["id"])
        new = self.memory.record_user_confirmed_fact(self.a, field="temperature", value=160, unit="℃",
                                                     object_scope="heater-1", source_message_id=second["id"])
        all_facts = self.store.fact_assertions(self.a)
        self.assertEqual(len(all_facts), 2)
        self.assertEqual(all_facts[0]["confirmation_state"], "superseded")
        self.assertEqual(all_facts[0]["superseded_by"], new["assertion_id"])
        self.assertEqual(all_facts[1]["value"], 160)
        self.assertEqual([fact["assertion_id"] for fact in self.memory.get_confirmed_facts(self.a)], [new["assertion_id"]])
        self.assertNotEqual(old["assertion_id"], new["assertion_id"])
        # Asking about a condition does not write facts; only explicit calls do.
        self.user(self.a, "160℃会怎样？")
        self.assertEqual(len(self.memory.get_confirmed_facts(self.a)), 1)

    def test_candidate_never_enters_confirmed_context_and_requires_same_conversation_source(self):
        source = self.assistant(self.a, "候选：介质可能是酸性水")
        candidate = self.memory.record_candidate_fact(self.a, field="medium", value="酸性水", unit=None,
                                                       object_scope="vessel-A", source_message_id=source["id"])
        self.assertEqual(candidate["confirmation_state"], "candidate")
        self.assertEqual(self.memory.get_confirmed_facts(self.a), [])
        b_source = self.user(self.b, "不可跨会话")
        with self.assertRaises(ValueError):
            self.memory.record_user_confirmed_fact(self.a, field="medium", value="bad", unit=None,
                                                    object_scope="vessel-A", source_message_id=b_source["id"])
        with self.assertRaises(ValueError):
            self.store.add_conversation_memory(self.a, summary="bad", covered_until_message_id=b_source["id"],
                                               source_message_ids=[b_source["id"]], source_hash="x",
                                               parent_memory_version=None, model_id="x", generation_kind="mock_model", status="ready")

    def test_history_is_bounded_by_turn_count_and_character_budget(self):
        self.add_turns(self.a, 8)
        history = self.memory.get_recent_visible_history(self.a, max_turns=2, max_chars=35)
        self.assertLessEqual(len(history), 4)
        self.assertLessEqual(sum(len(row["content"]) for row in history), 35)
        self.assertTrue(all(row["role"] in {"user", "assistant"} for row in history))

    def test_optional_mock_summary_is_incremental_versioned_and_hash_verified(self):
        rows = self.add_turns(self.a, 8)
        calls = []
        def summarizer(payload):
            calls.append(payload)
            return {"summary": f"仅作上下文提示 v{len(calls)}"}
        before = self.store.messages(self.a)
        first = self.memory.propose_summary_if_needed(self.a, summarizer=summarizer, allow_model=True, model_id="mock-v1")
        self.assertEqual(first["status"], "created")
        self.assertEqual(first["summary"]["authority"], "untrusted_context_hint")
        self.assertEqual(first["summary"]["memory_version"], 1)
        self.assertEqual(first["summary"]["source_message_ids"], [row["id"] for row in rows[:14]])
        self.assertIsNone(first["summary"]["parent_memory_version"])
        self.add_turns(self.a, 2, "later")
        self.add_turns(self.a, 2, "later2")
        second = self.memory.propose_summary_if_needed(self.a, summarizer=summarizer, allow_model=True, model_id="mock-v1")
        self.assertEqual(second["summary"]["memory_version"], 2)
        self.assertEqual(second["summary"]["parent_memory_version"], 1)
        self.assertEqual(len(second["summary"]["source_message_ids"]), 8)
        self.assertEqual(len(self.store.messages(self.a)), len(before) + 8)
        with self.store.session() as con:
            con.execute("UPDATE messages SET content='tampered' WHERE id=?", (second["summary"]["source_message_ids"][0],))
        # The tampered newest delta is rejected; the last independently intact
        # version remains usable rather than being discarded with it.
        self.assertEqual(self.memory.get_compacted_summary(self.a)["memory_version"], 1)
        with self.store.session() as con:
            con.execute("UPDATE messages SET content='tampered-parent' WHERE id=?", (rows[0]["id"],))
        self.assertIsNone(self.memory.get_compacted_summary(self.a))

    def test_summary_default_disabled_sensitive_gate_and_failures_fall_back_without_mutation(self):
        original = self.add_turns(self.a, 8)
        source = self.store.messages(self.a)
        calls = []
        disabled = self.memory.propose_summary_if_needed(self.a, summarizer=lambda payload: calls.append(payload) or "x")
        self.assertEqual(disabled["status"], "model_summary_disabled")
        self.assertEqual(calls, [])
        sensitive = self.memory.propose_summary_if_needed(self.a, summarizer=lambda payload: "x", allow_model=True, sensitive=True)
        self.assertEqual(sensitive["status"], "sensitive_content_not_authorized")
        for provider, expected in [
            (lambda payload: (_ for _ in ()).throw(TimeoutError()), "summary_timeout"),
            (lambda payload: {"summary": "x", "confirmed_fact": True}, "summary_invalid_or_failed"),
            (lambda payload: "x" * 9000, "summary_invalid_or_failed"),
        ]:
            failed = self.memory.propose_summary_if_needed(self.a, summarizer=provider, allow_model=True)
            self.assertEqual(failed["status"], "fallback")
            self.assertEqual(failed["error_code"], expected)
            self.assertEqual(len(failed["history"]), 2)
            self.assertEqual([m["id"] for m in self.store.messages(self.a)], [m["id"] for m in source])
        self.assertEqual(len(original), 16)

    def test_history_and_summary_replay_after_store_reopen(self):
        rows = self.add_turns(self.a, 8, "replay")
        created = self.memory.propose_summary_if_needed(
            self.a, summarizer=lambda payload: "replay context hint", allow_model=True, model_id="mock-replay")
        self.assertEqual(created["status"], "created")
        replay_store = Store(self.db)
        replay_memory = ConversationMemoryService(replay_store, retain_recent_turns=1,
                                                  max_context_chars=600, summary_threshold_chars=1)
        replayed = replay_memory.get_compacted_summary(self.a)
        self.assertEqual(replayed["summary"], "replay context hint")
        self.assertEqual(replayed["source_message_ids"], [row["id"] for row in rows[:14]])
        self.assertEqual(replay_memory.get_recent_visible_history(self.a), self.memory.get_recent_visible_history(self.a))

    def test_attachment_visibility_remains_conversation_scoped(self):
        message = self.user(self.a, "attached")
        now = self.store.messages(self.a)[0]["created_at"]
        with self.store.session() as con:
            con.execute("INSERT INTO conversation_files VALUES(?,?,?,?,?,?,?,?,?,?)",
                        ("file-a", self.a, "sha", "a.txt", "storage-a", "text/plain", 3, now, "ready", "user_upload"))
            con.execute("INSERT INTO message_attachments VALUES(?,?,?)", (message["id"], "file-a", 0))
        self.assertEqual(len(self.store.messages(self.a)[0]["attachments"]), 1)
        self.assertEqual(self.store.messages(self.b), [])
        self.assertEqual(self.store.files(self.b), [])


if __name__ == "__main__":
    unittest.main()
