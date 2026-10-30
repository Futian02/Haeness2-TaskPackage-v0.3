"""Durable V2 read-only tool execution ledger.

The ledger is deliberately restricted to a temporary SQLite database. Each
successful action result and its state transition commit in one transaction.
A crash between external execution and persistence is surfaced as UNCERTAIN;
the only automatic retry policy is for the three frozen read-only teacher
queries, so the system never claims physical exactly-once execution.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
from uuid import uuid4
from pathlib import Path
from typing import Any, Callable

TEACHER_TOOLS = frozenset({
    "damage_mechanism_query", "rbi_lookup", "standard_clause_search",
})
TERMINAL_STATES = frozenset({"SUCCEEDED"})


class _ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc, traceback):
        try:
            return super().__exit__(exc_type, exc, traceback)
        finally:
            self.close()


class LedgerConflict(RuntimeError):
    """Stable action identity was reused with different input."""


class LedgerUnavailable(RuntimeError):
    """A ledger action cannot be safely resumed within the configured budget."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _process_alive(pid: int | None) -> bool:
    """Conservatively check whether a claimed action's owning process is alive.

    Unknown access/process state is treated as alive (fail closed). An exited
    owner may be reclaimed; a live owner may never be preempted by a duplicate
    stream, even if its tool invocation is taking longer than anticipated.
    """
    if not pid or int(pid) <= 0:
        return True  # Legacy rows without owner identity need explicit recovery.
    pid = int(pid)
    if pid == os.getpid():
        return True
    if os.name == "nt":
        import ctypes
        kernel = ctypes.windll.kernel32
        kernel.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
        kernel.OpenProcess.restype = ctypes.c_void_p
        handle = kernel.OpenProcess(0x00100000, 0, pid)  # SYNCHRONIZE
        if not handle:
            # ERROR_INVALID_PARAMETER (87) means no process with this PID.
            # ACCESS_DENIED remains an unknown/alive state (fail closed).
            kernel.GetLastError.restype = ctypes.c_ulong
            return kernel.GetLastError() != 87
        try:
            kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
            kernel.WaitForSingleObject.restype = ctypes.c_ulong
            return kernel.WaitForSingleObject(handle, 0) != 0  # 0: signaled/exited
        finally:
            kernel.CloseHandle.argtypes = [ctypes.c_void_p]
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except (PermissionError, OSError):
        return True


class SQLiteExecutionLedger:
    """SQLite-backed idempotency and recovery ledger for bounded read-only tools."""

    def __init__(self, database_path: str | Path):
        self.path = Path(database_path).resolve()
        temp_root = Path(tempfile.gettempdir()).resolve()
        if not self.path.is_relative_to(temp_root):
            raise ValueError("V2 execution ledger requires temporary SQLite")
        if not self.path.is_file():
            raise ValueError("V2 execution ledger requires an existing Store database")
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(str(self.path), timeout=10.0, isolation_level=None, factory=_ClosingConnection)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        con.execute("PRAGMA busy_timeout=10000")
        return con

    def _initialize(self) -> None:
        with self._connect() as con:
            if not con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='runs'").fetchone():
                raise ValueError("execution ledger requires the project's runs table")
            con.executescript("""
                CREATE TABLE IF NOT EXISTS v2_execution_actions(
                    action_id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
                    subtask_id TEXT NOT NULL,
                    step_id TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    args_digest TEXT NOT NULL,
                    args_json TEXT NOT NULL,
                    state TEXT NOT NULL CHECK(state IN
                      ('INTENT_RECORDED','STARTED','SUCCEEDED','FAILED','UNCERTAIN','CANCEL_REQUESTED')),
                    attempt_count INTEGER NOT NULL DEFAULT 0 CHECK(attempt_count >= 0),
                    result_json TEXT,
                    result_digest TEXT,
                    source_digest TEXT,
                    last_error TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(run_id,subtask_id,step_id)
                );
                CREATE INDEX IF NOT EXISTS ix_v2_actions_run ON v2_execution_actions(run_id,subtask_id,step_id);
                CREATE TABLE IF NOT EXISTS v2_execution_transitions(
                    transition_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action_id TEXT NOT NULL REFERENCES v2_execution_actions(action_id) ON DELETE CASCADE,
                    state TEXT NOT NULL,
                    attempt_count INTEGER NOT NULL,
                    detail_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS ix_v2_transitions_action ON v2_execution_transitions(action_id,transition_id);
                CREATE TABLE IF NOT EXISTS v2_subtasks(
                    run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
                    subtask_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    goal_digest TEXT NOT NULL,
                    dependencies_json TEXT NOT NULL,
                    state TEXT NOT NULL CHECK(state IN
                      ('PENDING','RUNNING','SUCCEEDED','FAILED','UNCERTAIN','SKIPPED','DEFERRED')),
                    attempt_count INTEGER NOT NULL DEFAULT 0 CHECK(attempt_count >= 0),
                    result_json TEXT,
                    result_digest TEXT,
                    source_ids_json TEXT NOT NULL DEFAULT '[]',
                    error TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(run_id,subtask_id)
                );
                CREATE TABLE IF NOT EXISTS v2_subtask_events(
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    subtask_id TEXT NOT NULL,
                    state TEXT NOT NULL,
                    attempt_count INTEGER NOT NULL,
                    detail_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(run_id,subtask_id) REFERENCES v2_subtasks(run_id,subtask_id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS ix_v2_subtask_events_run ON v2_subtask_events(run_id,event_id);
            """)
            # Forward-compatible migration for S2.5 action ownership fencing.
            for table, column, sql_type in (
                ("v2_execution_actions", "owner_pid", "INTEGER"),
                ("v2_execution_actions", "owner_claim", "TEXT"),
                ("v2_subtasks", "owner_pid", "INTEGER"),
            ):
                cols = {row[1] for row in con.execute(f"PRAGMA table_info({table})")}
                if column not in cols:
                    con.execute(f"ALTER TABLE {table} ADD COLUMN {column} {sql_type}")

    @staticmethod
    def _action_id(run_id: str, subtask_id: str, step_id: str) -> str:
        return digest({"run_id": run_id, "subtask_id": subtask_id, "step_id": step_id})

    @staticmethod
    def _transition(con: sqlite3.Connection, action_id: str, state: str,
                    attempt_count: int, detail: dict[str, Any] | None = None) -> None:
        con.execute(
            "INSERT INTO v2_execution_transitions(action_id,state,attempt_count,detail_json) VALUES(?,?,?,?)",
            (action_id, state, attempt_count, canonical_json(detail or {})),
        )

    def execute_tool(self, *, conversation_id: str, run_id: str, subtask_id: str,
                     step_id: str, tool_name: str, args: dict[str, Any],
                     action: Callable[[], dict[str, Any]], max_attempts: int = 2,
                     crash_hook: Callable[[dict[str, Any]], None] | None = None
                     ) -> tuple[dict[str, Any], bool, int]:
        if tool_name not in TEACHER_TOOLS:
            raise ValueError(f"tool is outside the frozen allowlist: {tool_name}")
        if not all((conversation_id, run_id, subtask_id, step_id)):
            raise ValueError("conversation/run/subtask/step identity is required")
        if max_attempts < 1 or max_attempts > 3:
            raise ValueError("read-only retry budget must be 1..3")
        # Keep a structural manifest for diagnostics; never persist raw query,
        # material, medium, or operating-condition values in the public ledger.
        args_json = canonical_json({str(key): {"present": True, "type": type(value).__name__}
                                    for key, value in args.items()})
        args_digest = digest(args)
        action_id = self._action_id(run_id, subtask_id, step_id)
        claim = uuid4().hex
        owner_pid = os.getpid()

        with self._connect() as con:
            con.execute("BEGIN IMMEDIATE")
            existing = con.execute("SELECT * FROM v2_execution_actions WHERE action_id=?", (action_id,)).fetchone()
            if existing is None:
                con.execute("""INSERT INTO v2_execution_actions
                    (action_id,conversation_id,run_id,subtask_id,step_id,tool_name,args_digest,args_json,state)
                    VALUES(?,?,?,?,?,?,?,?, 'INTENT_RECORDED')""",
                    (action_id, conversation_id, run_id, subtask_id, step_id, tool_name, args_digest, args_json))
                self._transition(con, action_id, "INTENT_RECORDED", 0, {"tool_name": tool_name})
                existing = con.execute("SELECT * FROM v2_execution_actions WHERE action_id=?", (action_id,)).fetchone()
            elif (existing["conversation_id"] != conversation_id or existing["tool_name"] != tool_name
                  or existing["args_digest"] != args_digest):
                raise LedgerConflict("stable action identity was reused with a different conversation/tool/args digest")
            if existing["state"] == "SUCCEEDED":
                result = json.loads(existing["result_json"] or "{}")
                con.commit()
                result["_ledger_replayed"] = True
                return result, True, 0
            if existing["state"] == "STARTED":
                if _process_alive(existing["owner_pid"]):
                    raise LedgerUnavailable("action already executing in a live worker; refuse duplicate read-only call")
                con.execute("""UPDATE v2_execution_actions SET state='UNCERTAIN',updated_at=CURRENT_TIMESTAMP,
                    last_error='worker_lost_after_start_before_result_commit' WHERE action_id=?""", (action_id,))
                self._transition(con, action_id, "UNCERTAIN", int(existing["attempt_count"]),
                                 {"reason": "worker_lost_after_start_before_result_commit",
                                  "retry_policy": "bounded_read_only_query"})
                existing = con.execute("SELECT * FROM v2_execution_actions WHERE action_id=?", (action_id,)).fetchone()
            attempts = int(existing["attempt_count"])
            prior_state = str(existing["state"])
            con.commit()

        actual_delta = 0
        last_result: dict[str, Any] = {}
        while attempts < max_attempts:
            with self._connect() as con:
                con.execute("BEGIN IMMEDIATE")
                current = con.execute("SELECT * FROM v2_execution_actions WHERE action_id=?", (action_id,)).fetchone()
                if current is None:
                    raise LedgerUnavailable("execution intent disappeared")
                if current["state"] == "SUCCEEDED":
                    result = json.loads(current["result_json"] or "{}")
                    con.commit()
                    result["_ledger_replayed"] = True
                    return result, True, actual_delta
                if current["state"] == "STARTED":
                    if current["owner_claim"] != claim and _process_alive(current["owner_pid"]):
                        raise LedgerUnavailable("concurrent owner holds the execution action")
                attempts = int(current["attempt_count"]) + 1
                con.execute("""UPDATE v2_execution_actions SET state='STARTED',attempt_count=?,updated_at=CURRENT_TIMESTAMP,
                    last_error=NULL,owner_pid=?,owner_claim=? WHERE action_id=?""",
                    (attempts, owner_pid, claim, action_id))
                self._transition(con, action_id, "STARTED", attempts,
                                 {"recovered_from": prior_state, "attempt": attempts,
                                  "retryable_read_only": True})
                con.commit()
            actual_delta += 1
            try:
                result = action()
                if not isinstance(result, dict):
                    raise TypeError("tool adapter result must be an object")
                last_result = dict(result)
                if crash_hook is not None:
                    crash_hook(last_result)
                encoded = canonical_json(last_result)
                result_digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
                envelope = last_result.get("envelope")
                sources = envelope.get("source", []) if isinstance(envelope, dict) else []
                source_digest = digest(sources)
                succeeded = last_result.get("status") != "error"
                state = "SUCCEEDED" if succeeded else "FAILED"
                with self._connect() as con:
                    con.execute("BEGIN IMMEDIATE")
                    con.execute("""UPDATE v2_execution_actions SET state=?,result_json=?,result_digest=?,source_digest=?,
                        last_error=?,updated_at=CURRENT_TIMESTAMP WHERE action_id=? AND state='STARTED'
                        AND owner_pid=? AND owner_claim=?""", 
                        (state, encoded, result_digest, source_digest,
                         str(last_result.get("error") or "")[:300] or None, action_id, owner_pid, claim))
                    if con.execute("SELECT changes()").fetchone()[0] != 1:
                        raise LedgerUnavailable("tool result lost its owner claim")
                    self._transition(con, action_id, state, attempts,
                                     {"result_digest": result_digest, "source_digest": source_digest})
                    con.commit()
                if succeeded:
                    last_result["_ledger_replayed"] = False
                    return last_result, False, actual_delta
                prior_state = "FAILED"
            except (LedgerUnavailable, LedgerConflict):
                raise
            except Exception as exc:
                last_result = {"status": "error", "envelope": None, "attempts": 1,
                               "error": f"{type(exc).__name__}: {exc}"[:300]}
                encoded = canonical_json(last_result)
                result_digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
                with self._connect() as con:
                    con.execute("BEGIN IMMEDIATE")
                    con.execute("""UPDATE v2_execution_actions SET state='FAILED',result_json=?,result_digest=?,
                        last_error=?,updated_at=CURRENT_TIMESTAMP WHERE action_id=? AND state='STARTED'
                        AND owner_pid=? AND owner_claim=?""",
                        (encoded, result_digest, last_result["error"], action_id, owner_pid, claim))
                    if con.execute("SELECT changes()").fetchone()[0] != 1:
                        raise LedgerUnavailable("failed tool attempt lost its owner claim")
                    self._transition(con, action_id, "FAILED", attempts, {"error": last_result["error"]})
                    con.commit()
                prior_state = "FAILED"
            if attempts < max_attempts:
                continue
        last_result.setdefault("status", "error")
        last_result["_ledger_replayed"] = False
        last_result["_ledger_attempts_delta"] = actual_delta
        return last_result, False, actual_delta

    def begin_subtask(self, *, run_id: str, subtask_id: str, kind: str, goal: str,
                      dependencies: list[str], max_attempts: int = 2) -> dict[str, Any]:
        if not (1 <= len(subtask_id) <= 24) or not (1 <= len(kind) <= 64):
            raise ValueError("invalid subtask identity")
        if not 1 <= max_attempts <= 3:
            raise ValueError("subtask retry budget must be 1..3")
        goal_digest = digest({"goal": goal})
        deps_json = canonical_json(dependencies)
        with self._connect() as con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute("SELECT * FROM v2_subtasks WHERE run_id=? AND subtask_id=?",
                              (run_id, subtask_id)).fetchone()
            if row is None:
                con.execute("""INSERT INTO v2_subtasks(run_id,subtask_id,kind,goal_digest,dependencies_json,
                    state,attempt_count,owner_pid) VALUES(?,?,?,?,?,'RUNNING',1,?)""",
                    (run_id, subtask_id, kind, goal_digest, deps_json, os.getpid()))
                con.execute("""INSERT INTO v2_subtask_events(run_id,subtask_id,state,attempt_count,detail_json)
                    VALUES(?,?, 'RUNNING',1,?)""", (run_id, subtask_id, canonical_json({"kind": kind})))
                con.commit()
                return {"state": "RUNNING", "attempt_count": 1, "replayed": False}
            if row["kind"] != kind or row["goal_digest"] != goal_digest or row["dependencies_json"] != deps_json:
                raise LedgerConflict("subtask identity was reused with different goal/dependencies")
            if row["state"] in {"SUCCEEDED", "SKIPPED", "DEFERRED"} or (
                    row["state"] == "FAILED" and int(row["attempt_count"]) >= max_attempts):
                result = json.loads(row["result_json"] or "{}")
                con.commit()
                return {"state": row["state"], "attempt_count": row["attempt_count"],
                        "replayed": True, "result": result}
            if row["state"] == "RUNNING":
                if _process_alive(row["owner_pid"]):
                    raise LedgerUnavailable("subtask already running in a live worker")
                con.execute("""UPDATE v2_subtasks SET state='UNCERTAIN',updated_at=CURRENT_TIMESTAMP,
                    error='worker_lost_during_subtask' WHERE run_id=? AND subtask_id=?""",
                    (run_id, subtask_id))
                con.execute("""INSERT INTO v2_subtask_events(run_id,subtask_id,state,attempt_count,detail_json)
                    VALUES(?,?, 'UNCERTAIN',?,?)""",
                    (run_id, subtask_id, row["attempt_count"], canonical_json({"reason":"worker_lost_during_subtask"})))
                row = con.execute("SELECT * FROM v2_subtasks WHERE run_id=? AND subtask_id=?",
                                  (run_id, subtask_id)).fetchone()
            attempts = int(row["attempt_count"]) + 1
            if attempts > max_attempts:
                result = {"status": "retry_budget_exhausted", "previous_state": row["state"]}
                con.execute("""UPDATE v2_subtasks SET state='FAILED',result_json=?,error=?,
                    updated_at=CURRENT_TIMESTAMP WHERE run_id=? AND subtask_id=?""",
                    (canonical_json(result), "subtask_retry_budget_exhausted", run_id, subtask_id))
                con.execute("""INSERT INTO v2_subtask_events(run_id,subtask_id,state,attempt_count,detail_json)
                    VALUES(?,?, 'FAILED',?,?)""",
                    (run_id, subtask_id, row["attempt_count"],
                     canonical_json({"reason":"subtask_retry_budget_exhausted"})))
                con.commit()
                return {"state":"FAILED","attempt_count":int(row["attempt_count"]),
                        "replayed":True,"result":result}
            con.execute("""UPDATE v2_subtasks SET state='RUNNING',attempt_count=?,error=NULL,
                owner_pid=?,updated_at=CURRENT_TIMESTAMP WHERE run_id=? AND subtask_id=?""",
                (attempts, os.getpid(), run_id, subtask_id))
            con.execute("""INSERT INTO v2_subtask_events(run_id,subtask_id,state,attempt_count,detail_json)
                VALUES(?,?, 'RUNNING',?,?)""",
                (run_id, subtask_id, attempts, canonical_json({"recovered_from": row["state"]})))
            con.commit()
            return {"state": "RUNNING", "attempt_count": attempts, "replayed": False}

    def finish_subtask(self, *, run_id: str, subtask_id: str, state: str,
                       result: dict[str, Any] | None = None, source_ids: list[str] | None = None,
                       error: str | None = None) -> None:
        if state not in {"SUCCEEDED", "FAILED", "SKIPPED", "DEFERRED"}:
            raise ValueError("invalid terminal subtask state")
        encoded = canonical_json(result or {})
        result_hash = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        source_values = sorted(set(str(value) for value in (source_ids or []) if value))
        with self._connect() as con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute("SELECT attempt_count,state FROM v2_subtasks WHERE run_id=? AND subtask_id=?",
                              (run_id, subtask_id)).fetchone()
            if row is None:
                raise KeyError("subtask was not started")
            if row["state"] in {"SUCCEEDED", "SKIPPED", "DEFERRED"}:
                existing = con.execute("SELECT result_digest FROM v2_subtasks WHERE run_id=? AND subtask_id=?",
                                       (run_id, subtask_id)).fetchone()[0]
                if existing != result_hash:
                    raise LedgerConflict("terminal subtask result is immutable")
                con.commit()
                return
            con.execute("""UPDATE v2_subtasks SET state=?,result_json=?,result_digest=?,source_ids_json=?,
                error=?,updated_at=CURRENT_TIMESTAMP WHERE run_id=? AND subtask_id=?""",
                (state, encoded, result_hash, canonical_json(source_values), (error or "")[:300] or None,
                 run_id, subtask_id))
            con.execute("""INSERT INTO v2_subtask_events(run_id,subtask_id,state,attempt_count,detail_json)
                VALUES(?,?,?,?,?)""",
                (run_id, subtask_id, state, row["attempt_count"],
                 canonical_json({"result_digest": result_hash, "source_ids": source_values, "error": error})))
            con.commit()

    def get_subtasks(self, run_id: str) -> list[dict[str, Any]]:
        with self._connect() as con:
            rows = con.execute("SELECT * FROM v2_subtasks WHERE run_id=? ORDER BY created_at,subtask_id",
                               (run_id,)).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["dependencies"] = json.loads(item.pop("dependencies_json"))
            item["source_ids"] = json.loads(item.pop("source_ids_json"))
            if item.get("result_json"):
                item["result"] = json.loads(item["result_json"])
            result.append(item)
        return result

    def get_action(self, *, run_id: str, subtask_id: str, step_id: str) -> dict[str, Any] | None:
        action_id = self._action_id(run_id, subtask_id, step_id)
        with self._connect() as con:
            row = con.execute("SELECT * FROM v2_execution_actions WHERE action_id=?", (action_id,)).fetchone()
            if row is None:
                return None
            transitions = con.execute("""SELECT state,attempt_count,detail_json,created_at
                FROM v2_execution_transitions WHERE action_id=? ORDER BY transition_id""", (action_id,)).fetchall()
        result = dict(row)
        result["transitions"] = [dict(state=x["state"], attempt_count=x["attempt_count"],
                                     detail=json.loads(x["detail_json"]), created_at=x["created_at"])
                                 for x in transitions]
        if result.get("result_json"):
            result["result"] = json.loads(result["result_json"])
        return result
