"""Conversation-scoped bounded memory on the shared SQLite WAL store.

Summaries are contextual hints, never confirmed plant facts. This module has no
network client and calls a summarizer only when one is injected and explicitly
enabled by the caller.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from typing import Any

from backend.store import Store

SummaryProvider = Callable[[dict[str, Any]], str | Mapping[str, Any]]


class ConversationMemoryService:
    def __init__(self, store: Store, *, retain_recent_turns: int = 12,
                 max_context_chars: int = 16000, summary_threshold_chars: int = 12000,
                 max_summary_chars: int = 8000):
        self.store = store
        self.retain_recent_turns = max(1, min(int(retain_recent_turns), 12))
        self.max_context_chars = max(500, min(int(max_context_chars), 32000))
        self.summary_threshold_chars = max(1, min(int(summary_threshold_chars), 100000))
        self.max_summary_chars = max(200, min(int(max_summary_chars), 8000))

    @staticmethod
    def _message_hash(parent_hash: str | None, messages: list[dict[str, Any]]) -> str:
        source = {
            "parent_source_hash": parent_hash,
            "messages": [{"id": row["id"], "role": row["role"], "content": row["content"]} for row in messages],
        }
        encoded = json.dumps(source, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def get_recent_visible_history(self, cid: str, *, max_turns: int | None = None,
                                   max_chars: int | None = None) -> list[dict[str, str]]:
        """Return only visible user/assistant messages from cid, bounded by turns and chars."""
        limit_turns = self.retain_recent_turns if max_turns is None else max(1, min(int(max_turns), 12))
        budget = self.max_context_chars if max_chars is None else max(1, min(int(max_chars), 32000))
        all_messages = self.store.messages(cid)
        visible = [m for m in all_messages if m.get("role") in {"user", "assistant"}]
        visible = visible[-(limit_turns * 2):]
        kept: list[dict[str, str]] = []
        used = 0
        for message in reversed(visible):
            content = str(message.get("content", ""))
            remaining = budget - used
            if remaining <= 0:
                break
            if len(content) > remaining:
                content = "…[较早内容已截断]…" + content[-max(0, remaining - 16):] if remaining > 16 else content[-remaining:]
            kept.append({"role": str(message["role"]), "content": content})
            used += len(content)
            if used >= budget:
                break
        return list(reversed(kept))

    def get_confirmed_facts(self, cid: str) -> list[dict[str, Any]]:
        """Confirmed facts only. Candidates, assistant suggestions and memory text are excluded."""
        return self.store.fact_assertions(cid, confirmed_only=True)

    def clear_memory_records(self, cid: str, *, authorized: bool = False,
                             retain_audit: bool) -> dict[str, Any]:
        """Clear derived memory with explicit authorization and retention choice.

        This is deliberately not a conversation/message deletion API.  With
        ``retain_audit=True`` the assertion rows remain as audit history but
        are retracted from active context; with ``False`` fact audit rows are
        deleted. Visible messages, runs, attachments, and execution ledgers are
        untouched and require a separate owner-approved retention workflow.
        """
        if not authorized:
            raise PermissionError("explicit memory deletion authorization is required")
        if not isinstance(retain_audit, bool):
            raise TypeError("retain_audit must be an explicit bool")
        with self.store.session() as con:
            if not con.execute("SELECT 1 FROM conversations WHERE id=?", (cid,)).fetchone():
                raise KeyError("conversation not found")
            versions = [int(row[0]) for row in con.execute(
                "SELECT memory_version FROM conversation_memories WHERE conversation_id=? ORDER BY memory_version DESC", (cid,))]
            for version in versions:
                con.execute("DELETE FROM conversation_memories WHERE conversation_id=? AND memory_version=?", (cid, version))
            if retain_audit:
                con.execute("UPDATE conversation_fact_assertions SET confirmation_state='retracted' "
                            "WHERE conversation_id=? AND confirmation_state IN ('confirmed','candidate','conflict')", (cid,))
            else:
                con.execute("UPDATE conversation_fact_assertions SET superseded_by=NULL WHERE conversation_id=?", (cid,))
                con.execute("DELETE FROM conversation_fact_assertions WHERE conversation_id=?", (cid,))
        return {"conversation_id": cid, "summaries_deleted": len(versions),
                "audit_retained": retain_audit, "visible_messages_deleted": False,
                "runs_deleted": False, "attachments_deleted": False}

    def record_user_confirmed_fact(self, cid: str, *, field: str, value: Any, unit: str | None,
                                   object_scope: str, source_message_id: str,
                                   structured_confirmation: bool = False) -> dict[str, Any]:
        """Record an explicitly confirmed user statement; supersede active same-object values, never erase them."""
        return self.store.add_fact_assertion(
            cid, field=field, value=value, unit=unit, object_scope=object_scope,
            source_message_id=source_message_id,
            provenance_type="structured_confirmation" if structured_confirmation else "user_statement",
            confirmation_state="confirmed", confidence_label="structured_confirmed" if structured_confirmation else "user_confirmed",
            user_confirmed=True,
        )

    def record_candidate_fact(self, cid: str, *, field: str, value: Any, unit: str | None,
                              object_scope: str, source_message_id: str,
                              provenance_type: str = "model_candidate") -> dict[str, Any]:
        if provenance_type not in {"model_candidate", "assistant_suggestion"}:
            raise ValueError("candidate facts must retain model/assistant provenance")
        return self.store.add_fact_assertion(
            cid, field=field, value=value, unit=unit, object_scope=object_scope,
            source_message_id=source_message_id, provenance_type=provenance_type,
            confirmation_state="candidate", confidence_label="unverified", user_confirmed=False,
        )

    def get_compacted_summary(self, cid: str) -> dict[str, Any] | None:
        """Get the newest intact same-conversation summary; invalid source hash is ignored."""
        memories = self.store.conversation_memories(cid)
        by_version = {int(row["memory_version"]): row for row in memories}

        def intact(memory: dict[str, Any], visiting: set[int] | None = None) -> bool:
            if memory["status"] != "ready":
                return False
            version = int(memory["memory_version"])
            visiting = set() if visiting is None else visiting
            if version in visiting:
                return False
            visiting.add(version)
            parent = by_version.get(memory["parent_memory_version"]) if memory["parent_memory_version"] else None
            if memory["parent_memory_version"] and (parent is None or not intact(parent, visiting)):
                return False
            source_rows = self._source_rows(cid, memory["source_message_ids"])
            if source_rows is None:
                return False
            expected = self._message_hash(parent["source_hash"] if parent else None, source_rows)
            return expected == memory["source_hash"]

        for memory in reversed(memories):
            if not intact(memory):
                continue
            return {"summary": memory["summary"], "conversation_id": cid,
                    "memory_version": memory["memory_version"],
                    "covered_until_message_id": memory["covered_until_message_id"],
                    "source_message_ids": list(memory["source_message_ids"]),
                    "source_hash": memory["source_hash"],
                    "parent_memory_version": memory["parent_memory_version"],
                    "generation_kind": memory["generation_kind"], "model_id": memory["model_id"],
                    "status": memory["status"], "authority": "untrusted_context_hint"}
        return None

    def _source_rows(self, cid: str, ids: list[str]) -> list[dict[str, Any]] | None:
        if not ids:
            return []
        all_by_id = {row["id"]: row for row in self.store.messages(cid)}
        if any(mid not in all_by_id for mid in ids):
            return None
        return [{"id": mid, "role": all_by_id[mid]["role"], "content": all_by_id[mid]["content"]} for mid in ids]

    def propose_summary_if_needed(self, cid: str, *, summarizer: SummaryProvider | None = None,
                                  allow_model: bool = False, model_id: str = "mock-summary",
                                  sensitive: bool = False, allow_sensitive_content: bool = False) -> dict[str, Any]:
        """Optionally append a versioned incremental summary; no provider/network is built in.

        Summary failures are audited as failed versions and fall back to original bounded history.
        Existing messages and previous summaries are never overwritten.
        """
        all_messages = [m for m in self.store.messages(cid) if m.get("role") in {"user", "assistant"}]
        cutoff = max(0, len(all_messages) - self.retain_recent_turns * 2)
        eligible = all_messages[:cutoff]
        if not eligible:
            return {"status": "not_needed", "summary": None, "history": self.get_recent_visible_history(cid)}
        memories = self.store.conversation_memories(cid)
        intact_latest = self.get_compacted_summary(cid)
        previous = next((m for m in reversed(memories) if intact_latest
                         and m["memory_version"] == intact_latest["memory_version"]), None)
        parent_version = int(previous["memory_version"]) if previous else None
        parent_hash = str(previous["source_hash"]) if previous else None
        previous_covered = str(previous["covered_until_message_id"]) if previous and previous["covered_until_message_id"] else None
        start_index = next((i + 1 for i, m in enumerate(eligible) if m["id"] == previous_covered), 0) if previous_covered else 0
        delta = eligible[start_index:]
        if not delta:
            return {"status": "already_compacted", "summary": self.get_compacted_summary(cid), "history": self.get_recent_visible_history(cid)}
        delta_chars = sum(len(str(row.get("content", ""))) for row in delta)
        if delta_chars < self.summary_threshold_chars:
            return {"status": "below_threshold", "summary": self.get_compacted_summary(cid), "history": self.get_recent_visible_history(cid)}
        has_attachments = any(bool(row.get("attachments")) for row in delta)
        if (sensitive or has_attachments) and not allow_sensitive_content:
            return {"status": "sensitive_content_not_authorized", "summary": self.get_compacted_summary(cid), "history": self.get_recent_visible_history(cid)}
        if not allow_model or summarizer is None:
            return {"status": "model_summary_disabled", "summary": self.get_compacted_summary(cid), "history": self.get_recent_visible_history(cid)}
        source_rows = [{"id": row["id"], "role": row["role"], "content": str(row.get("content", ""))} for row in delta]
        source_hash = self._message_hash(parent_hash, source_rows)
        payload = {
            "task": "incremental_context_summary",
            "previous_summary": previous["summary"] if previous else None,
            "messages": [{"role": row["role"], "content": row["content"]} for row in source_rows],
            "authority": "untrusted_context_hint_not_confirmed_facts",
            "do_not_infer_observations": True,
        }
        failure: str | None = None
        summary = ""
        try:
            output = summarizer(payload)
            if isinstance(output, Mapping):
                if set(output) - {"summary"}:
                    raise ValueError("summary output has unsupported fields")
                output = output.get("summary")
            if not isinstance(output, str) or not output.strip():
                raise ValueError("summary output is empty or not text")
            summary = output.strip()
            if len(summary) > self.max_summary_chars:
                raise ValueError("summary output exceeds configured bound")
        except TimeoutError:
            failure = "summary_timeout"
        except Exception as exc:
            failure = "summary_invalid_or_failed" if isinstance(exc, (ValueError, TypeError, json.JSONDecodeError)) else "summary_provider_error"
        stored = self.store.add_conversation_memory(
            cid, summary=summary, covered_until_message_id=delta[-1]["id"],
            source_message_ids=[row["id"] for row in source_rows], source_hash=source_hash,
            parent_memory_version=parent_version, model_id=model_id if not failure else "none",
            generation_kind="mock_model", status="failed" if failure else "ready", error_code=failure,
        )
        if failure:
            return {"status": "fallback", "error_code": failure, "summary": self.get_compacted_summary(cid),
                    "history": self.get_recent_visible_history(cid), "memory_version": stored["memory_version"]}
        return {"status": "created", "summary": self.get_compacted_summary(cid),
                "history": self.get_recent_visible_history(cid), "memory_version": stored["memory_version"]}
