"""SQLite WAL repository for conversations, replayable runs, and audit records."""
from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


_SECRET_PATTERN = re.compile(r"(?i)\b(api[_-]?key|access[_-]?token|authorization|password|secret)\b\s*[:=]\s*([^\s,;]+)")
_MAX_EVENT_JSON_CHARS = 30000


def _scrub(value: Any) -> Any:
    if isinstance(value, str):
        cleaned = _SECRET_PATTERN.sub(r"\1=[REDACTED]", value)
        return cleaned if len(cleaned) <= 6000 else cleaned[:6000] + "…[truncated]"
    if isinstance(value, list):
        return [_scrub(x) for x in value[:100]] + (["…[items truncated]"] if len(value) > 100 else [])
    if isinstance(value, dict):
        secret_names = {"apikey", "accesstoken", "authorization", "password", "secret", "token"}
        result = {
            str(k): ("[REDACTED]" if re.sub(r"[^a-z]", "", str(k).lower()) in secret_names else _scrub(v))
            for k, v in list(value.items())[:100]
        }
        if len(value) > 100:
            result["_truncated_keys"] = len(value) - 100
        return result
    return value


def _bounded_event_payload(payload: dict[str, Any]) -> dict[str, Any]:
    safe = _scrub(payload)
    encoded = json.dumps(safe, ensure_ascii=False)
    if len(encoded) <= _MAX_EVENT_JSON_CHARS:
        return safe
    return {"truncated": True, "preview": encoded[:_MAX_EVENT_JSON_CHARS - 32] + "…"}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class Store:
    def __init__(self, database: str | Path | None = None):
        selected = database if database is not None else os.getenv("DATABASE_URL", "sqlite:///./data/haeness2.db")
        if isinstance(selected, str) and "://" in selected and not selected.startswith("sqlite:///"):
            raise ValueError("R1 默认实现只支持 SQLite DATABASE_URL；MySQL 适配器留待后续，不静默回退")
        raw = selected.removeprefix("sqlite:///") if isinstance(selected, str) else selected
        self.path = Path(raw)
        if not self.path.is_absolute(): self.path = Path.cwd() / self.path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._compat_worker_tokens: dict[str, str] = {}
        self._compat_lock = threading.RLock()
        self._init()

    def connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.path, timeout=10)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        con.execute("PRAGMA busy_timeout=10000")
        return con

    @contextmanager
    def session(self):
        con = self.connect()
        try:
            with con:
                yield con
        finally:
            con.close()

    def _init(self) -> None:
        with self.session() as c:
            c.execute("PRAGMA journal_mode=WAL")
            c.executescript("""
            CREATE TABLE IF NOT EXISTS conversations(id TEXT PRIMARY KEY, title TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, archived_at TEXT);
            CREATE TABLE IF NOT EXISTS messages(id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL REFERENCES conversations(id), role TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT NOT NULL, run_id TEXT);
            CREATE INDEX IF NOT EXISTS ix_messages_conversation ON messages(conversation_id, created_at);
            CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL REFERENCES conversations(id), status TEXT NOT NULL, mode TEXT NOT NULL, question TEXT NOT NULL, context_json TEXT NOT NULL, started_at TEXT NOT NULL, ended_at TEXT, error_code TEXT, worker_token TEXT, worker_heartbeat_at TEXT);
            CREATE INDEX IF NOT EXISTS ix_runs_conversation ON runs(conversation_id, started_at);
            CREATE TABLE IF NOT EXISTS agent_events(id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id), sequence INTEGER NOT NULL, type TEXT NOT NULL, agent TEXT, payload_json TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(run_id, sequence));
            CREATE TABLE IF NOT EXISTS tool_calls(id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id), sequence INTEGER NOT NULL, tool TEXT NOT NULL, args_json TEXT NOT NULL, result_json TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS evidence_refs(id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id), clause_id TEXT NOT NULL, standard_code TEXT, clause_no TEXT, page INTEGER, verification_level TEXT NOT NULL, payload_json TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS knowledge_documents(id TEXT PRIMARY KEY, source_file_sha TEXT, standard_code TEXT, clause_no TEXT, page_printed INTEGER, pdf_page INTEGER, quote_span TEXT, extraction_method TEXT NOT NULL, review_status TEXT NOT NULL, payload_json TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS claims(run_id TEXT NOT NULL REFERENCES runs(id), claim_id TEXT NOT NULL, kind TEXT NOT NULL, verdict TEXT NOT NULL, grade TEXT NOT NULL, review_status TEXT NOT NULL, payload_json TEXT NOT NULL, updated_at TEXT NOT NULL, PRIMARY KEY(run_id,claim_id));
            CREATE INDEX IF NOT EXISTS ix_claims_run ON claims(run_id,updated_at);
            CREATE TABLE IF NOT EXISTS disagreements(run_id TEXT NOT NULL REFERENCES runs(id), disagreement_id TEXT NOT NULL, claim_id TEXT NOT NULL, kind TEXT NOT NULL, verdict TEXT NOT NULL, review_status TEXT NOT NULL, payload_json TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY(run_id,disagreement_id));
            CREATE INDEX IF NOT EXISTS ix_disagreements_run ON disagreements(run_id,created_at);
            CREATE TABLE IF NOT EXISTS conversation_files(
                id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                file_sha256 TEXT NOT NULL, original_name TEXT NOT NULL, storage_key TEXT NOT NULL UNIQUE,
                content_type TEXT NOT NULL, size_bytes INTEGER NOT NULL CHECK(size_bytes >= 0),
                uploaded_at TEXT NOT NULL, extraction_status TEXT NOT NULL, source_type TEXT NOT NULL DEFAULT 'user_upload',
                UNIQUE(conversation_id,file_sha256));
            CREATE INDEX IF NOT EXISTS ix_conversation_files ON conversation_files(conversation_id,uploaded_at);
            CREATE TABLE IF NOT EXISTS message_attachments(
                message_id TEXT NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
                file_id TEXT NOT NULL REFERENCES conversation_files(id) ON DELETE CASCADE,
                position INTEGER NOT NULL, PRIMARY KEY(message_id,file_id), UNIQUE(message_id,position));
            CREATE TABLE IF NOT EXISTS run_attachments(
                run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
                file_id TEXT NOT NULL REFERENCES conversation_files(id) ON DELETE CASCADE,
                position INTEGER NOT NULL, PRIMARY KEY(run_id,file_id), UNIQUE(run_id,position));
            CREATE TABLE IF NOT EXISTS conversation_memory_schema(
                singleton INTEGER PRIMARY KEY CHECK(singleton=1), version INTEGER NOT NULL, updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS conversation_memories(
                conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                memory_version INTEGER NOT NULL CHECK(memory_version > 0), summary TEXT NOT NULL,
                covered_until_message_id TEXT REFERENCES messages(id), source_message_ids_json TEXT NOT NULL,
                source_hash TEXT NOT NULL, parent_memory_version INTEGER, model_id TEXT NOT NULL DEFAULT 'none',
                generation_kind TEXT NOT NULL CHECK(generation_kind IN ('deterministic','mock_model')),
                status TEXT NOT NULL CHECK(status IN ('ready','failed','rejected')),
                error_code TEXT, created_at TEXT NOT NULL,
                PRIMARY KEY(conversation_id,memory_version),
                FOREIGN KEY(conversation_id,parent_memory_version) REFERENCES conversation_memories(conversation_id,memory_version));
            CREATE INDEX IF NOT EXISTS ix_conversation_memories_latest ON conversation_memories(conversation_id,memory_version DESC,status);
            CREATE TABLE IF NOT EXISTS conversation_fact_assertions(
                assertion_id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                field TEXT NOT NULL CHECK(length(field) BETWEEN 1 AND 120), value_json TEXT NOT NULL,
                unit TEXT, object_scope TEXT NOT NULL CHECK(length(object_scope) BETWEEN 1 AND 160),
                provenance_type TEXT NOT NULL CHECK(provenance_type IN ('user_statement','structured_confirmation','model_candidate','assistant_suggestion')),
                source_message_id TEXT NOT NULL REFERENCES messages(id), confidence_label TEXT NOT NULL,
                confirmation_state TEXT NOT NULL CHECK(confirmation_state IN ('confirmed','candidate','retracted','superseded','conflict')),
                superseded_by TEXT REFERENCES conversation_fact_assertions(assertion_id), created_at TEXT NOT NULL,
                UNIQUE(conversation_id,assertion_id));
            CREATE INDEX IF NOT EXISTS ix_conversation_facts_active ON conversation_fact_assertions(conversation_id,field,object_scope,confirmation_state,created_at);
            """)
            conv_columns = {row[1] for row in c.execute("PRAGMA table_info(conversations)")}
            if "archived_at" not in conv_columns:
                c.execute("ALTER TABLE conversations ADD COLUMN archived_at TEXT")
            run_columns = {row[1] for row in c.execute("PRAGMA table_info(runs)")}
            if "input_message_id" not in run_columns:
                c.execute("ALTER TABLE runs ADD COLUMN input_message_id TEXT")
            # Backward-compatible migration for P3 databases created before
            # execution leases were introduced.
            columns = {row[1] for row in c.execute("PRAGMA table_info(runs)")}
            if "worker_token" not in columns:
                c.execute("ALTER TABLE runs ADD COLUMN worker_token TEXT")
            if "worker_heartbeat_at" not in columns:
                c.execute("ALTER TABLE runs ADD COLUMN worker_heartbeat_at TEXT")
            message_columns = {row[1] for row in c.execute("PRAGMA table_info(messages)")}
            if "run_id" not in message_columns:
                c.execute("ALTER TABLE messages ADD COLUMN run_id TEXT")
            c.execute("CREATE INDEX IF NOT EXISTS ix_messages_run ON messages(run_id)")
            c.execute("""UPDATE messages SET run_id=(SELECT r.id FROM runs r WHERE r.input_message_id=messages.id LIMIT 1)
                WHERE run_id IS NULL AND role='user' AND EXISTS(SELECT 1 FROM runs r WHERE r.input_message_id=messages.id)""")
            # Prior versions committed the response and run terminal timestamp in
            # the same transaction using the exact same UTC value.
            c.execute("""UPDATE messages SET run_id=(SELECT r.id FROM runs r WHERE r.conversation_id=messages.conversation_id
                AND r.status='completed' AND r.ended_at=messages.created_at LIMIT 1)
                WHERE run_id IS NULL AND role='assistant' AND EXISTS(SELECT 1 FROM runs r WHERE r.conversation_id=messages.conversation_id
                AND r.status='completed' AND r.ended_at=messages.created_at)""")
            c.execute("INSERT INTO conversation_memory_schema(singleton,version,updated_at) VALUES(1,1,?) ON CONFLICT(singleton) DO UPDATE SET version=MAX(version,excluded.version)", (utcnow(),))
            c.executescript("""
            CREATE TRIGGER IF NOT EXISTS trg_memory_source_same_conversation
            BEFORE INSERT ON conversation_memories
            WHEN EXISTS (
                SELECT 1 FROM json_each(NEW.source_message_ids_json) ids
                LEFT JOIN messages m ON m.id=ids.value
                WHERE m.id IS NULL OR m.conversation_id<>NEW.conversation_id OR m.role NOT IN ('user','assistant')
            )
            BEGIN SELECT RAISE(ABORT, 'memory source messages must be visible messages from the same conversation'); END;
            CREATE TRIGGER IF NOT EXISTS trg_fact_source_same_conversation
            BEFORE INSERT ON conversation_fact_assertions
            WHEN NOT EXISTS (SELECT 1 FROM messages m WHERE m.id=NEW.source_message_id AND m.conversation_id=NEW.conversation_id)
            BEGIN SELECT RAISE(ABORT, 'fact source message must belong to the same conversation'); END;
            CREATE TRIGGER IF NOT EXISTS trg_fact_confirmed_from_user
            BEFORE INSERT ON conversation_fact_assertions
            WHEN NEW.confirmation_state='confirmed' AND
                 (NEW.provenance_type NOT IN ('user_statement','structured_confirmation') OR
                  NOT EXISTS (SELECT 1 FROM messages m WHERE m.id=NEW.source_message_id AND m.conversation_id=NEW.conversation_id AND m.role='user'))
            BEGIN SELECT RAISE(ABORT, 'confirmed facts require explicit user-origin evidence'); END;
            """)

    def create_conversation(self, title: str) -> dict[str, Any]:
        now, cid = utcnow(), str(uuid4())
        with self.session() as c:
            c.execute("INSERT INTO conversations(id,title,created_at,updated_at,archived_at) VALUES(?,?,?,?,NULL)", (cid, title[:120] or "新对话", now, now))
        return {"id": cid, "title": title[:120] or "新对话", "created_at": now, "updated_at": now, "archived_at": None}

    def conversations(self) -> list[dict[str, Any]]:
        with self.session() as c: return [dict(r) for r in c.execute("SELECT * FROM conversations ORDER BY updated_at DESC")]

    def update_conversation(self, cid: str, *, title: str | None = None, archived: bool | None = None) -> dict[str, Any] | None:
        now = utcnow()
        with self.session() as c:
            if title is not None:
                c.execute("UPDATE conversations SET title=?,updated_at=? WHERE id=?", (title[:120] or "新对话", now, cid))
            if archived is not None:
                c.execute("UPDATE conversations SET archived_at=?,updated_at=? WHERE id=?", (now if archived else None, now, cid))
            row=c.execute("SELECT * FROM conversations WHERE id=?",(cid,)).fetchone()
        return dict(row) if row else None

    def conversation(self, cid: str) -> dict[str, Any] | None:
        with self.session() as c:
            row = c.execute("SELECT * FROM conversations WHERE id=?", (cid,)).fetchone()
            return dict(row) if row else None

    def add_message(self, cid: str, role: str, content: str) -> dict[str, Any]:
        item = {"id": str(uuid4()), "conversation_id": cid, "role": role, "content": content, "created_at": utcnow(), "run_id": None}
        with self.session() as c:
            c.execute("INSERT INTO messages(id,conversation_id,role,content,created_at,run_id) VALUES(?,?,?,?,?,?)", tuple(item.values()))
            c.execute("UPDATE conversations SET updated_at=? WHERE id=?", (item["created_at"], cid))
        return item

    def messages(self, cid: str) -> list[dict[str, Any]]:
        with self.session() as c:
            rows=[dict(r) for r in c.execute("SELECT * FROM messages WHERE conversation_id=? ORDER BY created_at,id", (cid,))]
            for row in rows:
                row["attachments"]=[dict(x) for x in c.execute("""SELECT f.id,f.original_name,f.content_type,f.size_bytes,f.file_sha256,f.extraction_status
                    FROM message_attachments ma JOIN conversation_files f ON f.id=ma.file_id
                    WHERE ma.message_id=? ORDER BY ma.position""",(row["id"],))]
            return rows

    @property
    def conversation_memory_schema_version(self) -> int:
        with self.session() as c:
            row = c.execute("SELECT version FROM conversation_memory_schema WHERE singleton=1").fetchone()
        return int(row[0]) if row else 0

    def fact_assertions(self, cid: str, *, confirmed_only: bool = False) -> list[dict[str, Any]]:
        """Read only this conversation's facts; historical superseded rows remain queryable."""
        where = " AND confirmation_state='confirmed'" if confirmed_only else ""
        with self.session() as c:
            records = c.execute(f"""SELECT assertion_id,conversation_id,field,value_json,unit,object_scope,
                provenance_type,source_message_id,confidence_label,confirmation_state,superseded_by,created_at
                FROM conversation_fact_assertions WHERE conversation_id=?{where}
                ORDER BY created_at,assertion_id""", (cid,)).fetchall()
        result = []
        for row in records:
            item = dict(row)
            try:
                item["value"] = json.loads(item.pop("value_json"))
            except json.JSONDecodeError:
                item["value"] = None
            result.append(item)
        return result

    def add_fact_assertion(self, cid: str, *, field: str, value: Any, unit: str | None,
                           object_scope: str, source_message_id: str, provenance_type: str,
                           confirmation_state: str = "candidate", confidence_label: str = "unverified",
                           user_confirmed: bool = False) -> dict[str, Any]:
        """Append a sourced assertion; only explicit user confirmation can create an active fact."""
        allowed_provenance = {"user_statement", "structured_confirmation", "model_candidate", "assistant_suggestion"}
        allowed_states = {"confirmed", "candidate", "retracted", "conflict"}
        if provenance_type not in allowed_provenance or confirmation_state not in allowed_states:
            raise ValueError("invalid fact provenance or state")
        if confirmation_state == "confirmed" and (not user_confirmed or provenance_type not in {"user_statement", "structured_confirmation"}):
            raise ValueError("confirmed facts require explicit user confirmation")
        if confirmation_state == "confirmed" and confidence_label not in {"user_confirmed", "structured_confirmed"}:
            raise ValueError("confirmed facts require a confirmation confidence label")
        if not field.strip() or not object_scope.strip():
            raise ValueError("fact field and object_scope are required")
        value_json = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        if len(value_json) > 4000:
            raise ValueError("fact value exceeds bounded storage limit")
        assertion_id, created = str(uuid4()), utcnow()
        with self.session() as c:
            source = c.execute("SELECT role FROM messages WHERE id=? AND conversation_id=?", (source_message_id, cid)).fetchone()
            if not source or source["role"] not in ({"user"} if confirmation_state == "confirmed" else {"user", "assistant"}):
                raise ValueError("confirmed facts require a user source; candidate sources must be visible same-conversation messages")
            if not c.execute("SELECT 1 FROM conversations WHERE id=?", (cid,)).fetchone():
                raise KeyError("conversation not found")
            if confirmation_state == "confirmed":
                previous = c.execute("""SELECT assertion_id FROM conversation_fact_assertions
                    WHERE conversation_id=? AND field=? AND object_scope=? AND confirmation_state='confirmed'
                    ORDER BY created_at DESC,assertion_id DESC""", (cid, field, object_scope)).fetchall()
            c.execute("""INSERT INTO conversation_fact_assertions
                (assertion_id,conversation_id,field,value_json,unit,object_scope,provenance_type,
                 source_message_id,confidence_label,confirmation_state,superseded_by,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,NULL,?)""",
                (assertion_id,cid,field[:120],value_json,unit[:80] if unit else None,object_scope[:160],provenance_type,
                 source_message_id,confidence_label,confirmation_state,created))
            if confirmation_state == "confirmed":
                for row in previous:
                    c.execute("UPDATE conversation_fact_assertions SET confirmation_state='superseded',superseded_by=? WHERE assertion_id=?", (assertion_id, row[0]))
        return {"assertion_id": assertion_id, "conversation_id": cid, "field": field[:120], "value": value,
                "unit": unit, "object_scope": object_scope[:160], "provenance_type": provenance_type,
                "source_message_id": source_message_id, "confidence_label": confidence_label,
                "confirmation_state": confirmation_state, "superseded_by": None, "created_at": created}

    def add_conversation_memory(self, cid: str, *, summary: str, covered_until_message_id: str | None,
                                source_message_ids: list[str], source_hash: str,
                                parent_memory_version: int | None, model_id: str,
                                generation_kind: str, status: str, error_code: str | None = None) -> dict[str, Any]:
        if generation_kind not in {"deterministic", "mock_model"} or status not in {"ready", "failed", "rejected"}:
            raise ValueError("invalid conversation memory metadata")
        if status == "ready" and (not summary.strip() or len(summary) > 8000):
            raise ValueError("ready summary must be nonempty and within 8000 characters")
        if len(source_message_ids) > 1000 or len(set(source_message_ids)) != len(source_message_ids):
            raise ValueError("invalid or oversized source_message_ids")
        encoded_ids = json.dumps(source_message_ids, ensure_ascii=False, separators=(",", ":"))
        with self.session() as c:
            if not c.execute("SELECT 1 FROM conversations WHERE id=?", (cid,)).fetchone():
                raise KeyError("conversation not found")
            if source_message_ids:
                placeholders = ",".join("?" for _ in source_message_ids)
                owned = {r[0] for r in c.execute(f"SELECT id FROM messages WHERE conversation_id=? AND id IN ({placeholders}) AND role IN ('user','assistant')", (cid, *source_message_ids))}
                if owned != set(source_message_ids):
                    raise ValueError("summary source IDs must be visible messages from the same conversation")
            if covered_until_message_id:
                covered = c.execute("SELECT 1 FROM messages WHERE id=? AND conversation_id=?", (covered_until_message_id,cid)).fetchone()
                if not covered:
                    raise ValueError("covered_until_message_id belongs to another conversation")
            if parent_memory_version is not None and not c.execute("SELECT 1 FROM conversation_memories WHERE conversation_id=? AND memory_version=?", (cid,parent_memory_version)).fetchone():
                raise ValueError("parent memory version does not exist in this conversation")
            version = int(c.execute("SELECT COALESCE(MAX(memory_version),0)+1 FROM conversation_memories WHERE conversation_id=?", (cid,)).fetchone()[0])
            created = utcnow()
            c.execute("""INSERT INTO conversation_memories(conversation_id,memory_version,summary,covered_until_message_id,
                source_message_ids_json,source_hash,parent_memory_version,model_id,generation_kind,status,error_code,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                (cid,version,summary[:8000],covered_until_message_id,encoded_ids,source_hash,parent_memory_version,
                 model_id[:120],generation_kind,status,error_code[:80] if error_code else None,created))
        return {"conversation_id": cid, "memory_version": version, "summary": summary[:8000],
                "covered_until_message_id": covered_until_message_id, "source_message_ids": source_message_ids,
                "source_hash": source_hash, "parent_memory_version": parent_memory_version,
                "model_id": model_id[:120], "generation_kind": generation_kind, "status": status,
                "error_code": error_code[:80] if error_code else None, "created_at": created}

    def conversation_memories(self, cid: str) -> list[dict[str, Any]]:
        with self.session() as c:
            rows = c.execute("SELECT * FROM conversation_memories WHERE conversation_id=? ORDER BY memory_version", (cid,)).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["source_message_ids"] = json.loads(item.pop("source_message_ids_json"))
            result.append(item)
        return result

    def chat_history(self, cid: str, current_run_id: str, limit_turns: int = 12) -> tuple[list[dict[str, str]], str | None]:
        """Bounded, visible same-conversation context for ordinary chat only.

        Excludes current input, attachments, events, hidden reasoning and all other
        conversations. Failed runs contribute only their user-visible question
        and finite error code.
        """
        limit_turns = max(1, min(int(limit_turns), 12))
        with self.session() as c:
            current = c.execute("""SELECT rowid,conversation_id,started_at,input_message_id FROM runs WHERE id=?""",
                                (current_run_id,)).fetchone()
            if not current or current["conversation_id"] != cid:
                return [], None
            current_message = c.execute("SELECT rowid FROM messages WHERE id=?", (current["input_message_id"],)).fetchone() if current["input_message_id"] else None
            rows = c.execute("""SELECT role,content FROM messages
                WHERE conversation_id=? AND rowid<? AND role IN ('user','assistant')
                ORDER BY rowid DESC LIMIT ?""", (cid, current_message[0] if current_message else 2**63 - 1,
                                                     limit_turns * 2)).fetchall()
            failed = c.execute("""SELECT question,error_code FROM runs
                WHERE conversation_id=? AND status='failed' AND rowid<?
                ORDER BY rowid DESC LIMIT 1""", (cid, current["rowid"])).fetchone()
        history = [{"role": row["role"], "content": str(row["content"] or "")[:4000]} for row in reversed(rows)]
        failure_summary = None
        if failed:
            failure_summary = f"用户问题：{str(failed['question'] or '')[:300]}；错误类别：{str(failed['error_code'] or 'run_failed')[:80]}。未生成可用答复。"
        return history, failure_summary

    def create_run(self, cid: str, question: str, context: dict[str, Any], mode: str) -> dict[str, Any]:
        item = {"id": str(uuid4()), "conversation_id": cid, "status": "queued", "mode": mode,
                "question": question, "context_json": json.dumps(context, ensure_ascii=False), "started_at": utcnow(), "ended_at": None, "error_code": None}
        with self.session() as c:
            c.execute("""INSERT INTO runs
                (id,conversation_id,status,mode,question,context_json,started_at,ended_at,error_code,worker_token,worker_heartbeat_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (*item.values(), None, None))
        return {**item, "context": context}

    def file_by_hash(self, cid: str, digest: str) -> dict[str, Any] | None:
        with self.session() as c:
            row=c.execute("SELECT * FROM conversation_files WHERE conversation_id=? AND file_sha256=?",(cid,digest)).fetchone()
        return dict(row) if row else None

    def insert_file(self, cid: str, file: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        """Insert upload metadata; return (existing/new record, was_duplicate)."""
        with self.session() as c:
            if not c.execute("SELECT 1 FROM conversations WHERE id=?",(cid,)).fetchone():
                raise KeyError("conversation not found")
            found=c.execute("SELECT * FROM conversation_files WHERE conversation_id=? AND file_sha256=?",(cid,file["file_sha256"])).fetchone()
            if found: return dict(found),True
            c.execute("""INSERT INTO conversation_files
                (id,conversation_id,file_sha256,original_name,storage_key,content_type,size_bytes,uploaded_at,extraction_status,source_type)
                VALUES(?,?,?,?,?,?,?,?,?,?)""",(file["id"],cid,file["file_sha256"],file["original_name"],file["storage_key"],file["content_type"],file["size_bytes"],file["uploaded_at"],file["extraction_status"],"user_upload"))
            row=c.execute("SELECT * FROM conversation_files WHERE id=?",(file["id"],)).fetchone()
        return dict(row),False

    def file(self, cid: str, file_id: str) -> dict[str, Any] | None:
        with self.session() as c:
            row=c.execute("SELECT * FROM conversation_files WHERE id=? AND conversation_id=?",(file_id,cid)).fetchone()
        return dict(row) if row else None

    def files(self, cid: str) -> list[dict[str, Any]]:
        with self.session() as c:
            return [dict(r) for r in c.execute("""SELECT id,conversation_id,file_sha256,original_name,content_type,size_bytes,uploaded_at,extraction_status,source_type
                FROM conversation_files WHERE conversation_id=? ORDER BY uploaded_at,id""",(cid,))]

    def create_run_with_message(self, cid: str, question: str, context: dict[str, Any], mode: str, file_ids: list[str]) -> dict[str, Any]:
        now, rid, mid = utcnow(),str(uuid4()),str(uuid4())
        item={"id":rid,"conversation_id":cid,"status":"queued","mode":mode,"question":question,
              "context_json":json.dumps(context,ensure_ascii=False),"started_at":now,"ended_at":None,"error_code":None}
        with self.session() as c:
            if not c.execute("SELECT 1 FROM conversations WHERE id=?",(cid,)).fetchone(): raise KeyError("conversation not found")
            owned={r[0] for r in c.execute("SELECT id FROM conversation_files WHERE conversation_id=?",(cid,))}
            if len(file_ids)>5 or len(set(file_ids))!=len(file_ids) or any(fid not in owned for fid in file_ids):
                raise ValueError("invalid or cross-conversation file_ids")
            c.execute("INSERT INTO messages(id,conversation_id,role,content,created_at,run_id) VALUES(?,?,?,?,?,?)",(mid,cid,"user",question,now,rid))
            c.execute("""INSERT INTO runs(id,conversation_id,status,mode,question,context_json,started_at,ended_at,error_code,worker_token,worker_heartbeat_at,input_message_id)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",(rid,cid,"queued",mode,question,item["context_json"],now,None,None,None,None,mid))
            for pos,fid in enumerate(file_ids):
                c.execute("INSERT INTO message_attachments VALUES(?,?,?)",(mid,fid,pos))
                c.execute("INSERT INTO run_attachments VALUES(?,?,?)",(rid,fid,pos))
            c.execute("UPDATE conversations SET updated_at=? WHERE id=?",(now,cid))
        return {**item,"context":context,"message_id":mid}

    def run_input(self, rid: str) -> dict[str, Any] | None:
        with self.session() as c:
            row=c.execute("SELECT id,conversation_id,question,context_json,mode,started_at,input_message_id FROM runs WHERE id=?",(rid,)).fetchone()
            if not row:return None
            result=dict(row);result["context"]=json.loads(result.pop("context_json"))
            result["attachments"]=[dict(x) for x in c.execute("""SELECT f.id,f.original_name,f.content_type,f.size_bytes,f.file_sha256,f.extraction_status
                FROM run_attachments ra JOIN conversation_files f ON f.id=ra.file_id WHERE ra.run_id=? ORDER BY ra.position""",(rid,))]
            current=c.execute("SELECT created_at FROM messages WHERE id=?",(result["input_message_id"],)).fetchone() if result["input_message_id"] else None
            before=current[0] if current else result["started_at"]
            history=c.execute("SELECT id FROM messages WHERE conversation_id=? AND created_at<? ORDER BY created_at,id",(result["conversation_id"],before)).fetchall()
            result["history_message_count"]=len(history)
            result["history_message_ids"]=[row[0] for row in history[:1000]]
            result["history_truncated"]=len(history)>1000
            result["history_scope"]={"available_count":len(history),"selected_for_this_run":False,"message_ids":result["history_message_ids"],"truncated":len(history)>1000}
            result["mode_disclaimer"]="RULE_DEMO；本轮仅使用明确快照字段，不会自动纳入历史消息，也不代表LLM记忆"
            return result

    def run(self, rid: str) -> dict[str, Any] | None:
        with self.session() as c: row = c.execute("SELECT * FROM runs WHERE id=?", (rid,)).fetchone()
        if not row: return None
        item = dict(row); item["context"] = json.loads(item.pop("context_json")); return item

    def latest_confirmed_context(self, cid: str) -> dict[str, Any]:
        """Return the latest completed same-conversation explicit input snapshot."""
        allowed = {"equipment", "equipment_type", "material", "medium", "temperature_c", "pressure_mpa", "service_years"}
        with self.session() as c:
            row = c.execute("SELECT context_json FROM runs WHERE conversation_id=? AND status='completed' ORDER BY started_at DESC,id DESC LIMIT 1", (cid,)).fetchone()
        if not row:
            return {}
        try:
            context = json.loads(row[0])
            result = {key: context[key] for key in allowed if context.get(key) not in (None, "", [])}
            if context.get("_object_scope"):
                result["_object_scope"] = str(context["_object_scope"])
            return result
        except (TypeError, json.JSONDecodeError):
            return {}

    def list_runs_by_conversation(self, cid: str, limit: int = 20, offset: int = 0) -> tuple[list[dict[str, Any]], int]:
        """Read-only, bounded timeline page; context and question are not returned."""
        if not 1 <= limit <= 100 or offset < 0:
            raise ValueError("invalid run pagination")
        with self.session() as c:
            total = c.execute("SELECT COUNT(*) FROM runs WHERE conversation_id=?", (cid,)).fetchone()[0]
            rows = c.execute("""SELECT id,conversation_id,status,mode,started_at,ended_at,error_code
                FROM runs WHERE conversation_id=? ORDER BY started_at DESC,id DESC LIMIT ? OFFSET ?""",
                (cid, limit, offset)).fetchall()
        return [dict(row) for row in rows], total

    def set_run_status(self, rid: str, status: str, error_code: str | None = None) -> None:
        with self.session() as c: c.execute("UPDATE runs SET status=?,ended_at=?,error_code=? WHERE id=?", (status, utcnow() if status in {"completed", "failed"} else None, error_code, rid))

    def claim_run(self, rid: str, worker_token: str) -> bool:
        """Atomically transfer QUEUED work to one worker; duplicate streams lose."""
        with self.session() as c:
            cur = c.execute("""UPDATE runs SET status='running',ended_at=NULL,error_code=NULL,
                worker_token=?,worker_heartbeat_at=? WHERE id=? AND status='queued'""",
                (worker_token, utcnow(), rid))
            claimed = cur.rowcount == 1
        if claimed:
            with self._compat_lock:
                self._compat_worker_tokens[rid] = worker_token
        return claimed

    def heartbeat_run(self, rid: str, worker_token: str) -> bool:
        with self.session() as c:
            cur = c.execute("UPDATE runs SET worker_heartbeat_at=? WHERE id=? AND status='running' AND worker_token=?",
                            (utcnow(), rid, worker_token))
            return cur.rowcount == 1

    def finish_run(self, rid: str, worker_token: str, status: str, error_code: str | None = None) -> bool:
        if status not in {"completed", "failed"}:
            raise ValueError("worker may finish only as completed or failed")
        with self.session() as c:
            cur = c.execute("""UPDATE runs SET status=?,ended_at=?,error_code=?,worker_token=NULL,
                worker_heartbeat_at=NULL WHERE id=? AND status='running' AND worker_token=?""",
                (status, utcnow(), error_code, rid, worker_token))
            finished = cur.rowcount == 1
            if finished and status == "failed":
                now = utcnow()
                sequence = c.execute("SELECT COALESCE(MAX(sequence),0)+1 FROM agent_events WHERE run_id=?", (rid,)).fetchone()[0]
                code = error_code if isinstance(error_code, str) and re.fullmatch(r"[a-z0-9_]{1,64}", error_code) else "run_failed"
                self._insert_event(c, rid, sequence, "run_failed", "supervisor",
                                   {"code": code, "status": "failed", "message": "本轮未完成；可以检查原因后重试。"}, now)
        if finished:
            with self._compat_lock:
                self._compat_worker_tokens.pop(rid, None)
        return finished

    def finish_run_with_message(self, rid: str, worker_token: str, content: str,
                                terminal_payload: dict[str, Any] | None = None) -> bool:
        """Atomically commit the sole assistant reply, final event, and terminal status."""
        now = utcnow()
        with self.session() as c:
            cur = c.execute("""UPDATE runs SET status='completed',ended_at=?,error_code=NULL,
                worker_token=NULL,worker_heartbeat_at=NULL WHERE id=? AND status='running' AND worker_token=?""",
                (now, rid, worker_token))
            if cur.rowcount != 1:
                return False
            cid = c.execute("SELECT conversation_id FROM runs WHERE id=?", (rid,)).fetchone()[0]
            c.execute("INSERT INTO messages(id,conversation_id,role,content,created_at,run_id) VALUES(?,?,?,?,?,?)", (str(uuid4()), cid, "assistant", content, now, rid))
            c.execute("UPDATE conversations SET updated_at=? WHERE id=?", (now, cid))
            sequence = c.execute("SELECT COALESCE(MAX(sequence),0)+1 FROM agent_events WHERE run_id=?", (rid,)).fetchone()[0]
            self._insert_event(c, rid, sequence, "run_completed", "supervisor",
                               terminal_payload or {"status": "completed"}, now)
        with self._compat_lock:
            self._compat_worker_tokens.pop(rid, None)
        return True

    def recover_stale_v2_run(self, rid: str, stale_after_seconds: float = 20.0) -> bool:
        """Requeue only an expired V2 lease; durable tool actions arbitrate replay."""
        import tempfile
        if not self.path.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve()):
            return False
        cutoff = (datetime.now(timezone.utc) - timedelta(seconds=stale_after_seconds)).isoformat(timespec="milliseconds")
        now = utcnow()
        with self.session() as c:
            c.execute("BEGIN IMMEDIATE")
            cur = c.execute("""UPDATE runs SET status='queued',ended_at=NULL,error_code=NULL,
                worker_token=NULL,worker_heartbeat_at=NULL WHERE id=? AND mode='V2_AGENTIC'
                AND status='running' AND (worker_heartbeat_at IS NULL OR worker_heartbeat_at < ?)""",
                (rid, cutoff))
            if cur.rowcount != 1:
                return False
            sequence = c.execute("SELECT COALESCE(MAX(sequence),0)+1 FROM agent_events WHERE run_id=?", (rid,)).fetchone()[0]
            self._insert_event(c, rid, sequence, "run_recovery_queued", "supervisor",
                               {"status": "queued", "reason": "stale_v2_worker_lease",
                                "recovery": "durable_read_only_action_ledger"}, now)
        with self._compat_lock:
            self._compat_worker_tokens.pop(rid, None)
        return True

    def recover_stale_run(self, rid: str, stale_after_seconds: float = 20.0) -> bool:
        """Fail a dead worker lease without retrying possibly side-effectful work."""
        cutoff = (datetime.now(timezone.utc) - timedelta(seconds=stale_after_seconds)).isoformat(timespec="milliseconds")
        now = utcnow()
        with self.session() as c:
            cur = c.execute("""UPDATE runs SET status='failed',ended_at=?,error_code='worker_lost',
                worker_token=NULL,worker_heartbeat_at=NULL WHERE id=? AND status='running'
                AND (worker_heartbeat_at IS NULL OR worker_heartbeat_at < ?)""", (now, rid, cutoff))
            if cur.rowcount != 1:
                return False
            sequence = c.execute("SELECT COALESCE(MAX(sequence),0)+1 FROM agent_events WHERE run_id=?", (rid,)).fetchone()[0]
            payload = {"code": "worker_lost", "message": "run worker lease expired; work was not retried"}
            self._insert_event(c, rid, sequence, "error", "supervisor", payload, now)
        with self._compat_lock:
            self._compat_worker_tokens.pop(rid, None)
        return True

    @staticmethod
    def _insert_event(c: sqlite3.Connection, rid: str, sequence: int, event_type: str,
                      agent: str | None, payload: dict[str, Any], now: str) -> dict[str, Any]:
        """Insert an already-authorized event and all projections in the caller transaction."""
        run = c.execute("SELECT conversation_id FROM runs WHERE id=?", (rid,)).fetchone()
        if run is None:
            raise KeyError(f"run not found: {rid}")
        safe_payload = _bounded_event_payload(payload)
        row = {"schema_version": 1, "event_id": str(uuid4()), "run_id": rid,
               "session_id": run[0], "sequence": sequence, "ts": now,
               "type": event_type, "agent": agent, "payload": safe_payload}
        c.execute("INSERT INTO agent_events VALUES(?,?,?,?,?,?,?)", (row["event_id"], rid, sequence,
                  event_type, agent, json.dumps(safe_payload, ensure_ascii=False), now))
        if event_type == "tool_called":
            c.execute("INSERT INTO tool_calls VALUES(?,?,?,?,?,?,?)", (str(uuid4()), rid, sequence,
                      safe_payload["tool"], json.dumps(safe_payload.get("args", {}), ensure_ascii=False), "{}", now))
        elif event_type == "tool_result":
            c.execute("UPDATE tool_calls SET result_json=? WHERE run_id=? AND tool=? AND result_json='{}'",
                      (json.dumps(safe_payload.get("result", {}), ensure_ascii=False), rid, safe_payload["tool"]))
        elif event_type == "reference_added":
            c.execute("INSERT INTO evidence_refs VALUES(?,?,?,?,?,?,?,?,?)", (str(uuid4()), rid,
                      safe_payload["clause_id"], safe_payload.get("standard_code"), safe_payload.get("clause_no"),
                      safe_payload.get("page"), safe_payload.get("verification_level", "E0"),
                      json.dumps(safe_payload, ensure_ascii=False), now))
        if event_type in {"claim_added", "claim_checked", "requires_human_review"} and safe_payload.get("claim_id") and "grade" in safe_payload:
            c.execute("""INSERT INTO claims VALUES(?,?,?,?,?,?,?,?)
                ON CONFLICT(run_id,claim_id) DO UPDATE SET kind=excluded.kind,verdict=excluded.verdict,
                grade=excluded.grade,review_status=excluded.review_status,payload_json=excluded.payload_json,updated_at=excluded.updated_at""",
                (rid, safe_payload["claim_id"], safe_payload.get("kind", "unknown"), safe_payload.get("verdict", "unresolved"),
                 safe_payload.get("grade", "E0"), safe_payload.get("review_status", "draft_needs_review"),
                 json.dumps(safe_payload, ensure_ascii=False), now))
        if safe_payload.get("disagreement_id") and event_type in {"contradiction_found", "requires_human_review"}:
            c.execute("""INSERT INTO disagreements VALUES(?,?,?,?,?,?,?,?)
                ON CONFLICT(run_id,disagreement_id) DO UPDATE SET verdict=excluded.verdict,
                review_status=excluded.review_status,payload_json=excluded.payload_json""",
                (rid, safe_payload["disagreement_id"], safe_payload.get("claim_id", ""), safe_payload.get("kind", "unknown"),
                 safe_payload.get("verdict", "unresolved"), safe_payload.get("review_status", "requires_human_review"),
                 json.dumps(safe_payload, ensure_ascii=False), now))
        return row

    def append_event(self, rid: str, event_type: str, agent: str | None, payload: dict[str, Any],
                     worker_token: str | None = None) -> dict[str, Any]:
        """Append only while the owning worker lease is active.

        Tokenless compatibility callers can acquire a queued run once, atomically;
        they cannot append once that lease is failed, completed, or recovered.
        Production API workers always supply their explicit token.
        """
        now = utcnow()
        with self._compat_lock:
            if worker_token is None:
                worker_token = self._compat_worker_tokens.get(rid)
                if worker_token is None:
                    candidate = str(uuid4())
                    with self.session() as c:
                        cur = c.execute("""UPDATE runs SET status='running',worker_token=?,worker_heartbeat_at=?
                            WHERE id=? AND status='queued'""", (candidate, now, rid))
                    if cur.rowcount != 1:
                        raise PermissionError("event append requires the active worker lease")
                    self._compat_worker_tokens[rid] = candidate
                    worker_token = candidate
            with self.session() as c:
                c.execute("BEGIN IMMEDIATE")
                active = c.execute("SELECT status,worker_token FROM runs WHERE id=?", (rid,)).fetchone()
                if active is None or active["status"] != "running" or active["worker_token"] != worker_token:
                    raise PermissionError("event append rejected: worker lease is no longer active")
                seq = c.execute("SELECT COALESCE(MAX(sequence),0)+1 FROM agent_events WHERE run_id=?", (rid,)).fetchone()[0]
                return self._insert_event(c, rid, seq, event_type, agent, payload, now)

    def events(self, rid: str, after_sequence: int = 0) -> list[dict[str, Any]]:
        with self.session() as c:
            rows = c.execute("SELECT e.*,r.conversation_id FROM agent_events e JOIN runs r ON r.id=e.run_id WHERE e.run_id=? AND e.sequence>? ORDER BY e.sequence", (rid, after_sequence)).fetchall()
        return [{"schema_version": 1, "event_id": r["id"], "run_id": r["run_id"], "session_id": r["conversation_id"],
                 "sequence": r["sequence"], "ts": r["created_at"], "type": r["type"], "agent": r["agent"],
                 "payload": json.loads(r["payload_json"])} for r in rows]

    def claims(self, rid: str) -> list[dict[str, Any]]:
        with self.session() as c:
            rows = c.execute("SELECT payload_json FROM claims WHERE run_id=? ORDER BY updated_at,claim_id", (rid,)).fetchall()
        return [json.loads(row[0]) for row in rows]

    def disagreements(self, rid: str) -> list[dict[str, Any]]:
        with self.session() as c:
            rows = c.execute("SELECT payload_json FROM disagreements WHERE run_id=? ORDER BY created_at,disagreement_id", (rid,)).fetchall()
        return [json.loads(row[0]) for row in rows]

    def add_knowledge_document(self, payload: dict[str, Any]) -> None:
        with self.session() as c:
            c.execute("INSERT INTO knowledge_documents VALUES(?,?,?,?,?,?,?,?,?,?,?)", (str(uuid4()), payload.get("doc_sha256"), payload.get("standard_code"), payload.get("clause_no"), payload.get("page_printed"), payload.get("pdf_page"), payload.get("quote_span"), payload.get("extraction_method", "unknown"), payload.get("review_status", "draft_needs_review"), json.dumps(payload, ensure_ascii=False), utcnow()))
