"""Local-first FastAPI chat API with durable, idempotent SSE replay.

Production mode is deliberately fail-closed until a real identity/tenant adapter
is implemented. This demo does not claim public-deployment safety.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import mimetypes
import os
import re
import tempfile
import time
import zlib
import sys
from collections import defaultdict, deque
from pathlib import Path
from threading import BoundedSemaphore, Event, Lock, Thread
from typing import Annotated, Any, Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, Header
from starlette.datastructures import UploadFile as StarletteUploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.store import Store, utcnow
from backend import deepseek
from backend.web_search import CallBudget, DeepSeekWebSearch, SearchError
from backend.context_slots import extract_explicit_context
from backend import model_profiles
from orchestration.r9_industrial_candidate import IndustrialCandidate
from orchestration.intent import classify_intent, rule_chat_reply
from backend.intent_router_v2 import LLMStructuredIntentRouter, MainRoute, LocalIntentPolicy, RouteDecision, IntentSubtask, TaskKind, dispatch_route, router_from_environment
from orchestration.semantics import extract_observations
from backend.conversation_memory import ConversationMemoryService

# Candidate cutover is explicit and remains disabled unless the local Owner opts in.
AETHER_V2_AGENTIC_ENABLED = os.getenv("AETHER_V2_AGENTIC_ENABLED", "0").strip() == "1"
# P0 expert explanation remains an isolated candidate. It is never enabled by default.
AETHER_EXPERT_GUIDANCE_CANDIDATE = os.getenv("AETHER_EXPERT_GUIDANCE_CANDIDATE", "0").strip() == "1"
API_CONTRACT_VERSION = "aetheris-r2.0.0"
_BUILD_SOURCE_FILES = (
    "backend/api.py",
    "backend/store.py",
    "backend/deepseek.py",
    "backend/model_profiles.py",
    "backend/context_slots.py",
    "backend/conversation_memory.py",
    "backend/professional_answers.py",
    "backend/intent_router_v2.py",
    "orchestration/intent.py",
    "orchestration/graph.py",
    "orchestration/r9_industrial_candidate.py",
)


def _compute_backend_build_identity() -> tuple[str, dict[str, str]]:
    """Fingerprint loaded service inputs once at import; never read live disk in health()."""
    digest = hashlib.sha256()
    manifest: dict[str, str] = {}
    source_root = Path(__file__).resolve().parents[1]
    for relative in sorted(_BUILD_SOURCE_FILES):
        path = source_root / relative
        digest.update(relative.replace("\\", "/").encode("utf-8"))
        digest.update(b"\0")
        try:
            content = path.read_bytes()
        except OSError:
            content = b"<missing>"
        manifest[relative.replace("\\", "/")] = hashlib.sha256(content).hexdigest()
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return "sha256:" + digest.hexdigest(), manifest


# Computed once after imports. This identifies the source set observed when this
# process loaded; health must not hash mutable files on each request.
BACKEND_BUILD_FINGERPRINT, BACKEND_BUILD_MANIFEST = _compute_backend_build_identity()
BACKEND_BUILD_SOURCE_FILES = tuple(sorted(_BUILD_SOURCE_FILES))
_agentic_v2_candidate = None
_agentic_v2_checkpointer_context = None
_agentic_v2_store_path = None

def _get_agentic_v2_candidate():
    global _agentic_v2_candidate, _agentic_v2_checkpointer_context, _agentic_v2_store_path
    if not AETHER_V2_AGENTIC_ENABLED:
        raise RuntimeError("v2_feature_disabled")
    current = store.path.resolve()
    temp_root = Path(tempfile.gettempdir()).resolve()
    if not current.is_relative_to(temp_root):
        raise RuntimeError("v2_requires_temporary_sqlite")
    current_path = str(current)
    if _agentic_v2_candidate is not None and _agentic_v2_store_path != current_path:
        if _agentic_v2_checkpointer_context is not None:
            _agentic_v2_checkpointer_context.__exit__(None, None, None)
        _agentic_v2_candidate = None
        _agentic_v2_checkpointer_context = None
    if _agentic_v2_candidate is None:
        from orchestration.agentic_v2 import AgenticV2Candidate
        from backend.agentic_provider import ScriptedFakePlanner
        from backend.execution_ledger import SQLiteExecutionLedger
        from langgraph.checkpoint.sqlite import SqliteSaver
        # Both checkpoint and execution ledger are scoped to the opt-in temporary
        # Store. The API feature gate rejects all non-temp SQLite paths.
        _agentic_v2_checkpointer_context = SqliteSaver.from_conn_string(current_path)
        saver = _agentic_v2_checkpointer_context.__enter__()
        _agentic_v2_store_path = current_path
        ledger = SQLiteExecutionLedger(current_path)
        _agentic_v2_candidate = AgenticV2Candidate(
            planner=ScriptedFakePlanner(), checkpointer=saver, replay_ledger=ledger
        )
    return _agentic_v2_candidate

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web" / "index.html"
FRONTEND_DIST = ROOT / "frontend" / "dist"
store = Store(os.getenv("DATABASE_URL", "sqlite:///./data/haeness2.db"))
graph = IndustrialCandidate()
# No provider/client is created by default. A structured model route is injectable for tests;
# live billing remains disabled unless a separately authorized provider is installed.
intent_router = router_from_environment()
app = FastAPI(title="Haeness2 Multi-Agent Demo", version="0.1.0")
_worker_slots = BoundedSemaphore(4)
_rate_lock = Lock()
_rates: dict[str, deque[float]] = defaultdict(deque)
_MAX_BODY_BYTES = 128 * 1024
_RATE_BUDGET = 300
MAX_UPLOAD_BYTES = 15 * 1024 * 1024
MAX_UPLOAD_FILES = 5
UPLOAD_ROOT = Path(os.getenv("UPLOAD_ROOT", str(ROOT / "data" / "uploads"))).resolve()

if (FRONTEND_DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="frontend-assets")


class ConversationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(default="新对话", min_length=1, max_length=120)


class RunIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=4000)
    # Empty/missing means unknown. Never populate engineering facts from a demo.
    equipment: str | None = Field(default=None, max_length=120)
    equipment_type: str | None = Field(default=None, max_length=120)
    material: str | None = Field(default=None, max_length=120)
    medium: list[Annotated[str, Field(max_length=120)]] = Field(default_factory=list, max_length=20)
    operating_condition: str = Field(default="", max_length=2000)
    field_evidence: str = Field(default="", max_length=4000)
    mode: str = Field(default="RULE_DEMO", max_length=32)
    web_mode: Literal["off", "auto", "on"] = "auto"
    # Backward-compatible input; new clients use web_mode.
    web_search_enabled: bool = False
    allow_sensitive_web_search: bool = False
    file_ids: list[str] = Field(default_factory=list, max_length=5)
    model_profile_id: str | None = Field(default=None, max_length=64)

    @model_validator(mode="before")
    @classmethod
    def accept_legacy_client_names(cls, value):
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        aliases = {
            "problem": "question",
            "device": "equipment",
            "device_type": "equipment_type",
            "operating_conditions": "operating_condition",
        }
        for old, canonical in aliases.items():
            if old not in normalized:
                continue
            if canonical in normalized and normalized[canonical] != normalized[old]:
                raise ValueError(f"conflicting fields: {old} and {canonical}")
            normalized.setdefault(canonical, normalized[old])
            normalized.pop(old)
        return normalized


class ModelProfileIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: str = Field(min_length=1, max_length=40)
    model: str = Field(min_length=1, max_length=80)
    endpoint: str = Field(min_length=1, max_length=300)
    api_key: str | None = Field(default=None, min_length=8, max_length=512)


class ModelProfilePatch(ModelProfileIn):
    api_key: str | None = Field(default=None, min_length=8, max_length=512)


class ProfileActivationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile_id: str | None = Field(default=None, max_length=64)


class ConversationPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(default=None, min_length=1, max_length=120)
    archived: bool | None = None


@app.middleware("http")
async def local_and_resource_guard(request: Request, call_next):
    def stamp(response):
        response.headers["X-Aetheris-Contract-Version"] = API_CONTRACT_VERSION
        response.headers["X-Aetheris-Build-Fingerprint"] = BACKEND_BUILD_FINGERPRINT
        return response
    # No authentication/tenant isolation exists; refuse production mode closed.
    if os.getenv("APP_ENV", "development").lower() == "production":
        return stamp(JSONResponse(status_code=503, content={"detail": "auth_required", "code": "AUTH_REQUIRED"}))
    client_host = request.client.host if request.client else ""
    if client_host not in {"testclient", "localhost"}:
        import ipaddress
        try:
            if not ipaddress.ip_address(client_host).is_loopback:
                return stamp(JSONResponse(status_code=403, content={"detail": "loopback_only", "code": "LOOPBACK_ONLY"}))
        except ValueError:
            return stamp(JSONResponse(status_code=403, content={"detail": "loopback_only", "code": "LOOPBACK_ONLY"}))
    length = request.headers.get("content-length")
    if length:
        try:
            allowance = (MAX_UPLOAD_BYTES * MAX_UPLOAD_FILES + 1024 * 1024) if request.url.path.endswith("/files") and request.method == "POST" else _MAX_BODY_BYTES
            if int(length) > allowance:
                return stamp(JSONResponse(status_code=413, content={"detail": "request_too_large", "code": "REQUEST_TOO_LARGE"}))
        except ValueError:
            return stamp(JSONResponse(status_code=400, content={"detail": "invalid_content_length", "code": "INVALID_CONTENT_LENGTH"}))
    key = f"{client_host}:{request.url.path.split('/')[2] if len(request.url.path.split('/')) > 2 else 'root'}"
    now = time.monotonic()
    with _rate_lock:
        bucket = _rates[key]
        while bucket and bucket[0] <= now - 60:
            bucket.popleft()
        if len(bucket) >= _RATE_BUDGET:
            return stamp(JSONResponse(status_code=429, content={"detail": "rate_limited", "code": "RATE_LIMITED"}, headers={"Retry-After": "60"}))
        bucket.append(now)
    return stamp(await call_next(request))


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(FRONTEND_DIST / "index.html" if (FRONTEND_DIST / "index.html").is_file() else WEB)


@app.get("/api/health")
def health():
    active = model_profiles.active_metadata()
    llm_ready = bool(active and active.get("configured"))
    return {"status": "ok",
            "mode": "DEEPSEEK" if llm_ready else "RULE_DEMO",
            "default_mode": "DEEPSEEK" if llm_ready else "RULE_DEMO",
            "llm": {"configured": llm_ready, "provider": active.get("provider") if llm_ready else None,
                    "model": active.get("model") if llm_ready else None, "profile_id": active.get("id") if llm_ready else None},
            "security": "loopback_only_auth_required_for_production",
            "contract_version": API_CONTRACT_VERSION,
            "capabilities": {"runs_create": True,
                             "runs_sse_stream": True,
                             "runs_replay": True,
                             "run_input_snapshot": True,
                             "model_profiles": True,
                             "professional_guidance": True,
                             "file_upload": True,
                             "explicit_web_consent": True,
                             "conversation_history": True,
                             "conversation_memory": True,
                             "sensitive_web_consent_gate": True,
                             "run_idempotency_key": True,
                             "teacher_tool_count": 3},
            "build_fingerprint": BACKEND_BUILD_FINGERPRINT,
            "build": {"source_files": list(BACKEND_BUILD_SOURCE_FILES),
                      "source_manifest": dict(BACKEND_BUILD_MANIFEST),
                      "python_version": sys.version.split()[0]},
            "flags": {"expert_guidance_candidate": os.getenv("AETHER_EXPERT_GUIDANCE_CANDIDATE", "0").strip() == "1",
                      "professional_guidance_deterministic": os.getenv("AETHER_PROFESSIONAL_GUIDANCE_ENABLED", "1").strip() == "1",
                      "v2_agentic": AETHER_V2_AGENTIC_ENABLED,
                      "default_mode": "DEEPSEEK" if llm_ready else "RULE_DEMO"},
            "professional_guidance_candidate": os.getenv("AETHER_EXPERT_GUIDANCE_CANDIDATE", "0").strip() == "1",
            "teacher_tools": ["damage_mechanism_query", "rbi_lookup", "standard_clause_search"]}


def _assert_local_admin(request: Request) -> None:
    if os.getenv("APP_ENV", "development").lower() == "production":
        raise HTTPException(503, "AUTH_REQUIRED")
    client = request.client.host if request.client else ""
    if client not in {"testclient", "localhost"}:
        import ipaddress
        try:
            if not ipaddress.ip_address(client).is_loopback:
                raise HTTPException(403, "LOOPBACK_ONLY")
        except ValueError:
            raise HTTPException(403, "LOOPBACK_ONLY") from None
    host = (request.headers.get("host", "").split(":", 1)[0]).lower()
    if host not in {"localhost", "127.0.0.1", "[::1]", "testserver"}:
        raise HTTPException(403, "LOCAL_HOST_ONLY")


@app.get("/api/model-profiles")
def get_model_profiles(request: Request):
    _assert_local_admin(request)
    return model_profiles.list_profiles()


@app.post("/api/model-profiles")
def post_model_profile(body: ModelProfileIn, request: Request):
    _assert_local_admin(request)
    try:
        return model_profiles.save_profile(profile_id=None, **body.model_dump())
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from None


@app.patch("/api/model-profiles/{profile_id}")
def patch_model_profile(profile_id: str, body: ModelProfilePatch, request: Request):
    _assert_local_admin(request)
    try:
        return model_profiles.save_profile(profile_id=profile_id, **body.model_dump())
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from None


@app.delete("/api/model-profiles/{profile_id}")
def remove_model_profile(profile_id: str, request: Request):
    _assert_local_admin(request)
    if not model_profiles.delete_profile(profile_id):
        raise HTTPException(404, "profile_not_found")
    return {"deleted": True}


@app.post("/api/model-profiles/active")
def select_model_profile(body: ProfileActivationIn, request: Request):
    _assert_local_admin(request)
    try:
        profile = model_profiles.activate_profile(body.profile_id)
    except KeyError:
        raise HTTPException(404, "profile_not_found") from None
    return {"active_profile_id": body.profile_id, "profile": profile}


@app.post("/api/model-profiles/{profile_id}/test")
def test_model_profile(profile_id: str, request: Request):
    _assert_local_admin(request)
    try:
        return model_profiles.test_connection(profile_id)
    except KeyError:
        raise HTTPException(404, "profile_not_found") from None
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(502, str(exc)) from None


@app.post("/api/conversations")
def create_conversation(body: ConversationIn):
    return store.create_conversation(body.title)


@app.get("/api/conversations")
def list_conversations(include_archived: bool = False):
    rows = store.conversations()
    return rows if include_archived else [row for row in rows if not row.get("archived_at")]


@app.patch("/api/conversations/{cid}")
def patch_conversation(cid: str, body: ConversationPatch):
    if not store.conversation(cid):
        raise HTTPException(404, "conversation not found")
    changes = body.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(422, "no conversation fields supplied")
    result = store.update_conversation(cid, **changes)
    return result


@app.get("/api/conversations/{cid}")
def get_conversation(cid: str):
    conversation = store.conversation(cid)
    if not conversation:
        raise HTTPException(404, "conversation not found")
    return {**conversation, "messages": store.messages(cid)}


@app.get("/api/conversations/{cid}/runs")
def list_conversation_runs(cid: str, limit: int = 20, offset: int = 0):
    if not store.conversation(cid):
        raise HTTPException(404, "conversation not found")
    if not 1 <= limit <= 100 or not 0 <= offset <= 100000:
        raise HTTPException(422, "limit must be 1..100 and offset 0..100000")
    runs, total = store.list_runs_by_conversation(cid, limit=limit, offset=offset)
    return {"conversation_id": cid, "runs": runs, "limit": limit, "offset": offset, "total": total}


def _create_idempotent_run(cid: str, body: RunIn, context: dict[str, Any], mode: str,
                           idempotency_key: str | None) -> tuple[dict[str, Any], bool]:
    """Atomically persist the idempotency receipt, user message and queued run."""
    if not idempotency_key:
        return store.create_run_with_message(cid, body.question, context, mode, body.file_ids), False
    key = idempotency_key.strip()
    if not 8 <= len(key) <= 128 or any(ord(char) < 0x21 or ord(char) > 0x7e for char in key):
        raise ValueError("invalid Idempotency-Key")
    request_material = {
        "conversation_id": cid,
        "question": body.question,
        "mode": mode,
        "request": body.model_dump(mode="json", exclude={"question", "mode"}),
    }
    request_hash = hashlib.sha256(json.dumps(request_material, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()
    # Store is replaceable by isolated tests, so create this API-owned additive
    # table lazily on the active database. No Store/source migration is required.
    with store.session() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS api_run_idempotency(
            conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
            idempotency_key TEXT NOT NULL,
            request_hash TEXT NOT NULL,
            run_id TEXT NOT NULL UNIQUE REFERENCES runs(id) ON DELETE CASCADE,
            created_at TEXT NOT NULL,
            PRIMARY KEY(conversation_id,idempotency_key))""")
    with store.session() as con:
        con.execute("BEGIN IMMEDIATE")
        existing = con.execute("""SELECT i.request_hash,i.run_id,r.status,r.mode,r.question,r.context_json,
                                      r.conversation_id,r.started_at,r.ended_at,r.error_code,r.input_message_id
            FROM api_run_idempotency i JOIN runs r ON r.id=i.run_id
            WHERE i.conversation_id=? AND i.idempotency_key=?""", (cid, key)).fetchone()
        if existing:
            if existing["request_hash"] != request_hash:
                raise HTTPException(409, detail={"code": "IDEMPOTENCY_KEY_REUSED", "detail": "Idempotency-Key was already used with a different request"})
            return ({"id": existing["run_id"], "conversation_id": cid, "status": existing["status"],
                     "mode": existing["mode"], "question": existing["question"],
                     "context": json.loads(existing["context_json"]), "message_id": existing["input_message_id"]}, True)
        if not con.execute("SELECT 1 FROM conversations WHERE id=?", (cid,)).fetchone():
            raise KeyError("conversation not found")
        file_ids = body.file_ids
        owned = {row[0] for row in con.execute("SELECT id FROM conversation_files WHERE conversation_id=?", (cid,))}
        if len(file_ids) > 5 or len(set(file_ids)) != len(file_ids) or any(file_id not in owned for file_id in file_ids):
            raise ValueError("invalid or cross-conversation file_ids")
        now, run_id, message_id = utcnow(), str(uuid4()), str(uuid4())
        encoded_context = json.dumps(context, ensure_ascii=False)
        con.execute("""INSERT INTO messages(id,conversation_id,role,content,created_at,run_id)
            VALUES(?,?,?,?,?,?)""", (message_id, cid, "user", body.question, now, run_id))
        con.execute("""INSERT INTO runs(id,conversation_id,status,mode,question,context_json,started_at,
            ended_at,error_code,worker_token,worker_heartbeat_at,input_message_id)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (run_id,cid,"queued",mode,body.question,encoded_context,now,None,None,None,None,message_id))
        for position, file_id in enumerate(file_ids):
            con.execute("INSERT INTO message_attachments VALUES(?,?,?)", (message_id,file_id,position))
            con.execute("INSERT INTO run_attachments VALUES(?,?,?)", (run_id,file_id,position))
        con.execute("UPDATE conversations SET updated_at=? WHERE id=?", (now,cid))
        con.execute("INSERT INTO api_run_idempotency VALUES(?,?,?,?,?)", (cid,key,request_hash,run_id,now))
        return ({"id":run_id,"conversation_id":cid,"status":"queued","mode":mode,
                 "question":body.question,"context":context,"message_id":message_id}, False)


@app.post("/api/conversations/{cid}/runs")
def create_run(cid: str, body: RunIn, idempotency_header: str | None = Header(default=None, alias="Idempotency-Key")):
    if not store.conversation(cid):
        raise HTTPException(404, "conversation not found")
    if body.mode not in {"RULE_DEMO", "DEEPSEEK", "V2_AGENTIC"}:
        raise HTTPException(422, "mode 只允许 RULE_DEMO、DEEPSEEK 或显式启用的 V2_AGENTIC")
    if body.mode == "V2_AGENTIC" and not AETHER_V2_AGENTIC_ENABLED:
        raise HTTPException(503, "v2_feature_disabled")
    if body.mode == "V2_AGENTIC" and not store.path.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve()):
        raise HTTPException(503, "v2_requires_temporary_sqlite")
    try:
        # Never resolve or inherit the local API key for the offline V2 candidate.
        selected_profile = None if body.mode == "V2_AGENTIC" else (model_profiles.safe_profile(body.model_profile_id) if body.model_profile_id else model_profiles.safe_profile())
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from None
    if (body.model_profile_id or body.mode == "DEEPSEEK") and not selected_profile:
        raise HTTPException(503, "DeepSeek 未配置；请设置 DEEPSEEK_API_KEY")
    selected_web_mode = "on" if body.web_search_enabled and body.web_mode == "auto" else body.web_mode
    structured = body.model_dump(exclude={"question", "mode", "file_ids", "model_profile_id", "web_search_enabled"})
    structured["web_mode"] = selected_web_mode
    # Load only confirmed same-conversation facts for routing compatibility. They are
    # not sent to general chat; only an engineering route receives them below.
    # A lexical switch to another/new object is a hard context boundary. Detect
    # it before consulting either snapshots or the assertion ledger.
    turn_scope = extract_explicit_context(body.question, structured)
    new_object_scope = bool(turn_scope.get("new_object_scope"))
    retained: dict[str, Any] = {} if new_object_scope else store.latest_confirmed_context(cid)
    memory = ConversationMemoryService(store)
    active_scope = str(retained.get("_object_scope") or "conversation_object")
    for fact in (() if new_object_scope else memory.get_confirmed_facts(cid)):
        field = str(fact.get("field") or "")
        if (str(fact.get("object_scope") or "") == active_scope
                and field in {"equipment", "equipment_type", "material", "medium", "temperature_c", "pressure_mpa", "service_years"}
                and retained.get(field) in (None, "", [])):
            retained[field] = fact.get("value")
    route_decision = intent_router.route(body.question)
    # Preserve Owner's R9 short follow-up patch: a terse current-turn professional
    # follow-up may inherit confirmed context, while explicit writing/general intent may not.
    contextual = {**retained, **{k: v for k, v in structured.items() if v not in (None, "", [])}}
    legacy_route = classify_intent(body.question, contextual)
    if dispatch_route(route_decision) == MainRoute.GENERAL and legacy_route != "general_chat":
        kind = TaskKind.RBI_ASSESSMENT if legacy_route == "deterministic_rbi_grade" else TaskKind.DEVICE_DIAGNOSIS if legacy_route == "device_diagnosis" else TaskKind.MECHANISM_EXPLORATION
        route_decision = RouteDecision(primary_route=MainRoute.ENGINEERING, safety_relevance=True,
            confidence=0.55, reasons_public=["保留Owner R9同会话短追问兼容；显式普通/写作任务不继承设备上下文"],
            subtasks=[IntentSubtask(id="contextual_engineering", kind=kind,
                user_goal="沿用同会话已确认工况进行有界专业追问", task_risk="SAFETY_RELEVANT")])
    route_snapshot = route_decision.snapshot()
    current_route = route_snapshot["dispatch_route"]
    # Current-turn routing wins. Ordinary chat and standard lookup never inherit facts.
    prior: dict[str, Any] = dict(retained) if current_route == MainRoute.ENGINEERING.value else {}
    # Same-conversation only, and only explicitly stated user messages. Never
    # reinterpret assistant-generated text as confirmed context.
    for message in (reversed(store.messages(cid)) if prior else ()):
        if message.get("role") != "user":
            continue
        message_values = extract_explicit_context(message.get("content", ""))["values"]
        if message_values:
            prior.update(message_values)
        # Only the latest user turn can establish carry-forward context. Do
        # not skip an empty/new-object turn and resurrect an older object's facts.
        break
    resolved = extract_explicit_context(body.question, structured, prior)
    effective_structured = dict(structured)
    for field_name in resolved.get("unknown_enum_values", {}):
        if field_name not in resolved["values"]:
            effective_structured.pop(field_name, None)
    context = {**effective_structured, **resolved["values"],
               "_object_scope": resolved["object_scope"],
               "_v2_route_decision": route_snapshot,
               "_v2_route_execution": ("V2_AGENTIC_FAKE_CANDIDATE" if body.mode == "V2_AGENTIC" and route_decision.primary_route != MainRoute.MIXED else
                                        "MIXED_DAG_EXECUTED_OFFLINE" if body.mode == "V2_AGENTIC" and route_decision.primary_route == MainRoute.MIXED else
                                        "TRANSITIONAL_R9" if route_decision.primary_route == MainRoute.STANDARD_LOOKUP else
                                        "MIXED_ENGINEERING_FIRST_R9" if route_decision.primary_route == MainRoute.MIXED else
                                        "DIRECT_CHAT" if current_route == MainRoute.GENERAL.value else "R9_ENGINEERING"),
               "_context_sources": resolved["sources"],
               "_context_conflicts": resolved["conflicts"],
               "_context_raw_values": resolved.get("raw_values", {}),
               "_context_unknown_enums": resolved.get("unknown_enum_values", {}),
               "_context_field_details": resolved.get("field_details", {}),
               "raw_medium": resolved.get("raw_values", {}).get("medium"),
               "_context_extraction_method": resolved["extraction_method"]}
    if selected_profile:
        context["_model_profile_snapshot"] = {"profile_id": selected_profile.get("profile_id"),
                                                "provider": selected_profile.get("provider"),
                                                "model": selected_profile.get("model")}
    try:
        effective_mode = "DEEPSEEK" if selected_profile and (body.model_profile_id or body.mode == "DEEPSEEK") else body.mode
        run, idempotency_replayed = _create_idempotent_run(cid, body, context, effective_mode, idempotency_header)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    # Persist explicit same-turn facts with the user message as provenance.
    # Summary generation stays disabled; candidates and assistant text never enter this path.
    explicit_fields = {"equipment", "equipment_type", "material", "medium", "temperature_c", "pressure_mpa", "service_years"}
    for field, value in resolved["values"].items():
        if current_route != MainRoute.ENGINEERING.value or field not in explicit_fields or resolved["sources"].get(field) not in {"structured_form", "current_message"}:
            continue
        try:
            ConversationMemoryService(store).record_user_confirmed_fact(
                cid, field=field, value=value, unit="C" if field == "temperature_c" else "MPa" if field == "pressure_mpa" else None,
                object_scope=str(resolved["object_scope"]),
                source_message_id=run["message_id"], structured_confirmation=resolved["sources"].get(field) == "structured_form")
        except (ValueError, KeyError):
            # Memory is auxiliary: a failed append does not block the primary run.
            pass
    return {"run_id": run["id"], "status": run["status"], "mode": run["mode"],
            "web_mode": selected_web_mode, "idempotency_replayed": idempotency_replayed,
            "events_url": f"/api/runs/{run['id']}/stream"}


@app.get("/api/runs/{rid}/input")
def get_run_input(rid: str):
    snapshot = store.run_input(rid)
    if not snapshot:
        raise HTTPException(404, "run not found")
    return snapshot


_ALLOWED_EXTENSIONS = {".txt": "text/plain", ".md": "text/markdown", ".csv": "text/csv", ".pdf": "application/pdf", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}


def _safe_upload_name(name: str) -> str:
    leaf = name.replace("\\", "/").split("/")[-1]
    leaf = re.sub(r"[^\w.()\-\u4e00-\u9fff ]", "_", leaf, flags=re.UNICODE).strip(" .")[:180]
    return leaf or "upload"


def _verify_file_signature(path: Path, suffix: str) -> None:
    head = path.read_bytes()[:16]
    valid = {".pdf": head.startswith(b"%PDF-"), ".png": head.startswith(b"\x89PNG\r\n\x1a\n"), ".jpg": head.startswith(b"\xff\xd8\xff"), ".jpeg": head.startswith(b"\xff\xd8\xff"), ".webp": len(head) >= 12 and head[:4] == b"RIFF" and head[8:12] == b"WEBP", ".docx": head.startswith(b"PK\x03\x04"), ".xlsx": head.startswith(b"PK\x03\x04")}
    if suffix in valid and not valid[suffix]:
        raise ValueError("文件扩展名与文件签名不匹配")
    if suffix in {".txt", ".md", ".csv"}:
        path.read_text(encoding="utf-8")


def _file_preview(path: Path, record: dict[str, Any]) -> dict[str, Any]:
    if Path(record["original_name"]).suffix.lower() in {".txt", ".md", ".csv"}:
        return {"status": "text_preview", "text": path.read_text(encoding="utf-8")[:20000]}
    if Path(record["original_name"]).suffix.lower() == ".pdf":
        try:
            import fitz
            with fitz.open(path) as pdf:
                preview_text = "\n\n".join(page.get_text() for page in pdf[:3])[:12000]
                if not preview_text.strip():
                    # Empty extraction is not a successful preview: allow the
                    # bounded stdlib content-stream fallback below to run.
                    raise ValueError("empty PDF text extraction")
                return {"status": "pdf_preview", "page_count": len(pdf), "text": preview_text}
        except Exception:
            raw = path.read_bytes()
            extracted: list[str] = []
            for stream in re.findall(rb"stream\r?\n(.*?)\r?\nendstream", raw, re.S):
                data = stream
                # Best-effort support for ordinary Flate-compressed content streams.
                if len(data) > 2 and data[0] == 0x78:
                    try: data = zlib.decompress(data)
                    except zlib.error: pass
                for block in re.findall(rb"BT(.*?)ET", data, re.S):
                    for literal in re.findall(rb"\(((?:\\.|[^\\)])*)\)\s*Tj", block, re.S):
                        value = re.sub(rb"\\([()\\])", rb"\1", literal)
                        value = re.sub(rb"\\([0-7]{1,3})", lambda m: bytes([int(m.group(1), 8)]), value)
                        extracted.append(value.decode("latin-1", errors="replace"))
                    for hx in re.findall(rb"<([0-9A-Fa-f\s]+)>\s*Tj", block):
                        try: extracted.append(bytes.fromhex(hx.decode()).decode("utf-16-be" if len(bytes.fromhex(hx.decode())) % 2 == 0 else "latin-1", errors="replace"))
                        except (ValueError, UnicodeDecodeError): pass
            text = " ".join(x for x in extracted if x.strip())[:12000]
            if text:
                return {"status": "pdf_preview", "page_count": None, "text": text, "parser": "stdlib_pdf_text_fallback"}
            return {"status": "stored_not_parsed", "message": "PDF 已安全保存；本机无法抽取文本，可能为扫描件或复杂编码"}
    return {"status": "stored_not_parsed", "message": "文件已安全保存，当前仅支持文本/PDF预览"}


@app.post("/api/conversations/{cid}/files")
async def upload_conversation_files(cid: str, request: Request):
    if not store.conversation(cid):
        raise HTTPException(404, "conversation not found")
    if not request.headers.get("content-length"):
        raise HTTPException(411, "multipart upload requires Content-Length for bounded storage")
    form = await request.form()
    uploads = [value for _, value in form.multi_items() if isinstance(value, StarletteUploadFile)]
    if not uploads or len(uploads) > MAX_UPLOAD_FILES:
        for upload in uploads:
            await upload.close()
        raise HTTPException(422, "每次上传 1 至 5 个文件")
    saved: list[dict[str, Any]] = []
    temporaries: list[Path] = []
    try:
        UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
        for upload in uploads:
            name = _safe_upload_name(upload.filename or "upload")
            suffix = Path(name).suffix.lower()
            if suffix not in _ALLOWED_EXTENSIONS:
                raise HTTPException(415, f"不支持的文件类型：{suffix or '无扩展名'}")
            digest = hashlib.sha256()
            size = 0
            fd, temp_name = tempfile.mkstemp(prefix=".upload-", dir=UPLOAD_ROOT)
            temp_path = Path(temp_name); temporaries.append(temp_path)
            with os.fdopen(fd, "wb") as out:
                while chunk := await upload.read(64 * 1024):
                    size += len(chunk)
                    if size > MAX_UPLOAD_BYTES:
                        raise HTTPException(413, f"单文件上限为 {MAX_UPLOAD_BYTES} 字节")
                    digest.update(chunk); out.write(chunk)
            _verify_file_signature(temp_path, suffix)
            content_type = _ALLOWED_EXTENSIONS[suffix]
            tenant_dir = hashlib.sha256(cid.encode("utf-8")).hexdigest()[:20]
            key = f"{tenant_dir}/{digest.hexdigest()}.blob"
            target = (UPLOAD_ROOT / key).resolve()
            if UPLOAD_ROOT not in target.parents:
                raise HTTPException(400, "invalid storage path")
            target.parent.mkdir(parents=True, exist_ok=True)
            existing = store.file_by_hash(cid, digest.hexdigest())
            if existing:
                existing_path = UPLOAD_ROOT / existing["storage_key"]
                if not existing_path.exists():
                    existing_path.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(temp_path, existing_path)
                else:
                    temp_path.unlink(missing_ok=True)
                temporaries.remove(temp_path)
                record = existing
            else:
                if not target.exists(): os.replace(temp_path, target)
                else: temp_path.unlink(missing_ok=True)
                temporaries.remove(temp_path)
                metadata = {"id": str(uuid4()), "file_sha256": digest.hexdigest(), "original_name": name, "storage_key": key,
                            "content_type": content_type, "size_bytes": size, "uploaded_at": store_module_now(),
                            "extraction_status": "pending"}
                try:
                    record, _ = store.insert_file(cid, metadata)
                except Exception:
                    if not store.file_by_hash(cid, digest.hexdigest()): target.unlink(missing_ok=True)
                    raise
            preview = _file_preview(UPLOAD_ROOT / record["storage_key"], record)
            if preview["status"] != "stored_not_parsed":
                with store.session() as con:
                    con.execute("UPDATE conversation_files SET extraction_status=? WHERE id=?", (preview["status"], record["id"]))
                record["extraction_status"] = preview["status"]
            public = {k: record[k] for k in ("id", "conversation_id", "file_sha256", "original_name", "content_type", "size_bytes", "uploaded_at", "extraction_status") if k in record}
            saved.append({**public, "preview": preview})
        return {"files": saved}
    except HTTPException:
        raise
    except (UnicodeDecodeError, ValueError) as exc:
        raise HTTPException(415, str(exc)) from exc
    finally:
        for path in temporaries: path.unlink(missing_ok=True)
        for upload in uploads: await upload.close()


def store_module_now() -> str:
    from backend.store import utcnow
    return utcnow()


def _ordinary_history(cid: str, current_run_id: str, limit_turns: int = 12) -> tuple[list[dict[str, str]], str | None]:
    """Return bounded, same-conversation general-only turns; professional context stays isolated."""
    history, failed_summary = store.chat_history(cid, current_run_id, limit_turns=limit_turns)
    messages = store.messages(cid)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    loose: list[dict[str, Any]] = []
    for message in messages:
        rid = message.get("run_id")
        if rid and rid != current_run_id:
            grouped[str(rid)].append(message)
        elif not rid:
            loose.append(message)
    allowed_contents: list[tuple[str, str]] = []
    for rid, rows in grouped.items():
        snapshot = store.run_input(rid) or {}
        route = (snapshot.get("context") or {}).get("_v2_route_decision") or {}
        if route.get("dispatch_route") == MainRoute.GENERAL.value and not snapshot.get("attachments"):
            allowed_contents.extend((str(m.get("role")), str(m.get("content") or "")) for m in rows)
    for message in loose:
        if message.get("role") in {"user", "assistant"} and classify_intent(str(message.get("content") or ""), {}) == "general_chat":
            allowed_contents.append((str(message.get("role")), str(message.get("content") or "")))
    # Preserve chronological order and duplicate messages by consuming occurrence counts.
    remaining: dict[tuple[str, str], int] = defaultdict(int)
    for pair in allowed_contents: remaining[pair] += 1
    filtered=[]
    for item in history:
        key=(str(item.get("role")),str(item.get("content") or ""))
        if remaining[key]: filtered.append(item); remaining[key]-=1
    # Failed-run summaries can include engineering facts; keep only a generic failure code.
    if failed_summary:
        latest_failed = [m for m in grouped.values() if m]
        failed_summary = None
    return filtered[-max(1,min(limit_turns,12))*2:], failed_summary


@app.get("/api/conversations/{cid}/files")
def list_conversation_files(cid: str):
    if not store.conversation(cid): raise HTTPException(404, "conversation not found")
    return {"files": store.files(cid)}


@app.get("/api/conversations/{cid}/files/{file_id}/preview")
def preview_conversation_file(cid: str, file_id: str):
    record = store.file(cid, file_id)
    if not record: raise HTTPException(404, "file not found")
    return _file_preview(UPLOAD_ROOT / record["storage_key"], record)


@app.get("/api/conversations/{cid}/files/{file_id}/download")
def download_conversation_file(cid: str, file_id: str):
    record = store.file(cid, file_id)
    if not record: raise HTTPException(404, "file not found")
    return FileResponse(UPLOAD_ROOT / record["storage_key"], filename=record["original_name"], media_type=record["content_type"])


@app.get("/api/runs/{rid}")
def get_run(rid: str):
    run = store.run(rid)
    if not run:
        raise HTTPException(404, "run not found")
    return {k: run[k] for k in ("id", "conversation_id", "status", "mode", "started_at", "ended_at", "error_code")}


def _public_event_projection(event: dict[str, Any]) -> dict[str, Any]:
    """Server-side allowlist projection; the frontend mask is not an access boundary."""
    payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
    safe: dict[str, Any] = {}
    for key in ("phase", "status", "route", "primary_route", "dispatch_route",
                "route_execution", "verification_level", "public_rationale",
                "tool", "tool_name", "tool_call_id", "step_id", "parent_step_id",
                "actual_attempts", "model_request_count", "intent_model_request_count",
                "subtask_count", "candidate_count", "evidence_count", "claim_count",
                "gap_count", "iteration", "duration_ms", "risk_level", "review_status",
                "verdict", "grade", "conflict_requires_review", "kind", "state",
                "failure_class", "failure_site", "code",
                "subtask_id", "dependencies", "blocked_by", "source_ids"):
        if key in payload and (payload[key] is None or isinstance(payload[key], (str, int, float, bool, list))):
            value = payload[key]
            if isinstance(value, str):
                safe[key] = value[:240]
            elif isinstance(value, list) and key in {"dependencies", "blocked_by", "source_ids"}:
                safe[key] = [str(item)[:80] for item in value[:8] if isinstance(item, (str, int))]
            else:
                safe[key] = value
    source_fields = ("clause_id", "standard_code", "clause_no", "page", "verification_level")
    sources = payload.get("sources")
    if not isinstance(sources, list) and isinstance(payload.get("result"), dict):
        sources = payload["result"].get("sources")
    if not isinstance(sources, list) and isinstance(payload.get("result"), dict):
        sources = payload["result"].get("source")
    if not isinstance(sources, list):
        sources = payload.get("source") if isinstance(payload.get("source"), list) else []
    projected_sources = [{key: row[key] for key in source_fields if key in row}
                         for row in sources[:8] if isinstance(row, dict)] if sources else []
    if projected_sources:
        safe["sources"] = projected_sources
    if isinstance(payload.get("result"), dict):
        raw_result = payload["result"]
        safe["result"] = {"status": raw_result.get("status")} if isinstance(raw_result.get("status"), str) else {}
        if projected_sources:
            safe["result"]["sources"] = projected_sources
    if isinstance(payload.get("fields"), dict):
        safe["fields"] = {str(key): "已记录（具体值未公开）"
                          for key, value in payload["fields"].items()
                          if key in {"material", "medium", "temperature_c", "pressure_mpa", "equipment_type"}
                          and value not in (None, "", [])}
    if event.get("type") == "a2_candidate_retrieval":
        safe["authority"] = "pointer_only_not_citation_or_applicability"
        safe["index_version"] = str(payload.get("index_version") or "")[:64]
        safe["query_sha256"] = str(payload.get("query_sha256") or "")[:64]
        safe["candidate_count"] = min(max(int(payload.get("candidate_count") or 0), 0), 5)
        safe["a2_candidates"] = []
        for row in payload.get("candidates", [])[:5] if isinstance(payload.get("candidates"), list) else []:
            if not isinstance(row, dict):
                continue
            safe["a2_candidates"].append({key: row[key] for key in (
                "clause_id", "standard_code", "clause_no", "printed_page", "excerpt_ref",
                "source_hash", "applicability", "semantic_relevance", "evidence_level",
                "may_support_claim", "review_state") if key in row})
    if isinstance(payload.get("args"), dict):
        args = payload["args"]
        safe_args: dict[str, Any] = {}
        for key, value in args.items():
            if key in {"keyword", "material", "medium", "temperature_c", "pressure_mpa", "equipment_type"}:
                safe_args[key] = "已记录（值由服务端保留，不公开）"
            elif key in {"top_k", "knowledge_type"} and isinstance(value, (int, str)):
                safe_args[key] = value if key == "top_k" else str(value)[:48]
        safe["args"] = safe_args
        safe["argument_presence"] = sorted(str(key) for key in args if isinstance(key, str))[:16]
    # Arbitrary payload fields, raw exception strings, prompts, paths, source excerpts
    # and assistant prose are intentionally omitted from the public trace.
    projected = {"run_id": event.get("run_id"), "sequence": event.get("sequence"),
                 "type": event.get("type"), "agent": event.get("agent"),
                 "ts": event.get("ts"), "payload": safe}
    for key in ("schema_version", "session_id"):
        if key in event:
            projected[key] = event[key]
    return projected


@app.get("/api/runs/{rid}/events")
def replay_events(rid: str, after_sequence: int = 0):
    if after_sequence < 0:
        raise HTTPException(422, "after_sequence must be non-negative")
    if not store.run(rid):
        raise HTTPException(404, "run not found")
    events = store.events(rid, after_sequence)
    return {"run_id": rid, "events": [_public_event_projection(event) for event in events]}


@app.get("/api/runs/{rid}/claims")
def list_claims(rid: str):
    if not store.run(rid):
        raise HTTPException(404, "run not found")
    return {"run_id": rid, "claims": store.claims(rid)}


@app.get("/api/runs/{rid}/disagreements")
def list_disagreements(rid: str):
    if not store.run(rid):
        raise HTTPException(404, "run not found")
    return {"run_id": rid, "disagreements": store.disagreements(rid)}


def _start_worker(rid: str, worker_token: str) -> None:
    run = store.run(rid)
    if not run:
        store.finish_run(rid, worker_token, "failed", "run_missing")
        _worker_slots.release()
        return

    def worker():
        stop_heartbeat = Event()
        terminal_payload: dict[str, Any] = {}
        generation_model_request_count = 0
        def heartbeat():
            while not stop_heartbeat.wait(5):
                if not store.heartbeat_run(rid, worker_token):
                    return
        Thread(target=heartbeat, name=f"lease-{rid[:8]}", daemon=True).start()
        try:
            def emit(kind: str, agent: str, payload: dict[str, Any]):
                # The graph announces completion before the API commits the
                # assistant message. Defer this event so status/message/final
                # sequence become visible together in one transaction.
                if kind == "run_completed":
                    terminal_payload.update(payload)
                else:
                    store.append_event(rid, kind, agent, payload, worker_token=worker_token)
                if not store.heartbeat_run(rid, worker_token):
                    raise RuntimeError("worker lease lost; graph event emission stopped")
            base = dict(run["context"])
            profile_snapshot = base.get("_model_profile_snapshot") or {}
            model_config = model_profiles.resolve_snapshot(profile_snapshot.get("profile_id")) if run.get("mode") == "DEEPSEEK" else None
            if run.get("mode") == "DEEPSEEK" and not model_config:
                raise RuntimeError("model_profile_unavailable")
            emit("context_resolved", "supervisor", {
                "original_question": str(run["question"])[:4000],
                "fields": {key: value for key, value in base.items() if key in {"equipment", "equipment_type", "material", "medium", "temperature_c", "pressure_mpa", "service_years"}},
                "sources": base.get("_context_sources", {}),
                "raw_values": base.get("_context_raw_values", {}),
                "unknown_enum_values": base.get("_context_unknown_enums", {}),
                "field_details": base.get("_context_field_details", {}),
                "conflicts": base.get("_context_conflicts", []),
                "extraction_method": base.get("_context_extraction_method", "structured_form_only"),
                "web_mode": base.get("web_mode", "auto"),
            })
            observed = extract_observations(" ".join((str(base.get("field_evidence") or ""), str(base.get("operating_condition") or ""))))
            evidence: dict[str, Any] = {}
            evidence_fields = {"ph": "ph", "iron_ion": "fe_ppm", "chloride": "cl_ppm", "h2s": "h2s_ppm", "wall_thinning": "wall_thinning", "crack_found": "crack_found"}
            for item in observed:
                key = evidence_fields.get(item.field)
                if key and item.observation_state.value != "unknown" and item.normalized_value is not None:
                    evidence[key] = item.normalized_value
                if item.field == "temperature" and isinstance(item.normalized_value, (int, float)):
                    base["temperature_c"] = item.normalized_value
                elif item.field == "pressure" and isinstance(item.normalized_value, (int, float)):
                    base["pressure_mpa"] = item.normalized_value
                elif item.field == "service_years" and isinstance(item.normalized_value, (int, float)):
                    base["service_years"] = item.normalized_value
            base["evidence"] = evidence
            def persist_candidate_event(event: dict[str, Any]):
                kind = str(event.get("event") or "graph_event")
                phase = str(event.get("phase") or "legacy")
                tool = str(event.get("tool") or "")
                agent = ("supervisor" if phase in {"route", "review_dispatch", "review_gate"} else
                         "evidence_auditor" if phase in {"review_merge", "auditor"} else
                         "skeptic" if phase == "skeptic" else
                         "rbi_specialist" if tool == "rbi_lookup" else
                         "diagnosis_agent" if tool == "damage_mechanism_query" or phase == "investigate" else
                         "evidence_agent" if tool == "standard_clause_search" else "reporting_agent" if phase == "report" else "supervisor")
                payload = {key: value for key, value in event.items() if key != "event"}
                payload.setdefault("phase", phase)
                if kind == "review_started":
                    emit(kind, agent, payload)
                    for reviewer in ("evidence_auditor", "skeptic"):
                        emit("agent_started", reviewer, {"phase": reviewer, "public_rationale": "并行独立审查已启动"})
                elif kind == "agent_completed" and agent in {"auditor", "skeptic"}:
                    emit("agent_completed", "evidence_auditor" if agent == "auditor" else "skeptic", payload)
                elif kind != "final":
                    emit(kind, agent, payload)

            route_snapshot = base.get("_v2_route_decision") or {}
            route = route_snapshot.get("dispatch_route", "ENGINEERING")
            direct_general = route == MainRoute.GENERAL.value
            store.append_event(rid, "intent_routed", "supervisor", {
                "primary_route": route_snapshot.get("primary_route", "CLARIFICATION"),
                "dispatch_route": route,
                "model_request_count": (route_snapshot.get("model_usage") or {}).get("request_count", 0),
                "intent_model_request_count": (route_snapshot.get("model_usage") or {}).get("request_count", 0),
                "fallback_reason": (route_snapshot.get("model_usage") or {}).get("fallback_reason"),
                "subtask_count": len(route_snapshot.get("subtasks") or []),
                "execution_mode": base.get("_v2_route_execution", "TRANSITIONAL_R9"),
            }, worker_token=worker_token)
            if direct_general:
                # Ordinary chat is a FastAPI worker branch: it never invokes LangGraph or teacher tools.
                result = {"output": {"status": "general_chat", "conclusion": "", "citations": [],
                                     "hypotheses": [], "unknowns": [], "tool_calls": 0,
                                     "verification_level": "E0"}, "review_round": None}
            elif run.get("mode") == "V2_AGENTIC":
                # V2 is an opt-in offline candidate. Ordinary chat remains direct;
                # the candidate can only reach the frozen three read-only tools.
                store.append_event(rid, "phase_started", "supervisor", {
                    "phase": "v2_agentic_candidate", "public_rationale": "显式V2候选路径；Fake Provider，不触达收费模型。",
                    "primary_route": route_snapshot.get("primary_route"),
                }, worker_token=worker_token)
                candidate = _get_agentic_v2_candidate()
                mixed = route_snapshot.get("primary_route") == MainRoute.MIXED.value
                mixed_output = None
                if mixed:
                    # Snapshot contains a derived dispatch_route not accepted by the frozen
                    # RouteDecision schema; reconstruct only the canonical decision fields.
                    decision_data = {key: value for key, value in route_snapshot.items()
                                     if key != "dispatch_route"}
                    decision = RouteDecision.model_validate_json(
                        json.dumps(decision_data, ensure_ascii=False))
                    from orchestration.mixed_dag import MixedDAGExecutor
                    dag = MixedDAGExecutor(candidate=candidate, ledger=candidate.replay,
                        standard_tool=candidate.tools["standard_clause_search"])
                    def persist_mixed_event(event):
                        kind = str(event.get("type") or "mixed_subtask_event")
                        safe = {key: event.get(key) for key in
                                ("subtask_id", "kind", "status", "dependencies", "blocked_by", "source_ids",
                                 "tool", "tool_name", "args", "result", "actual_attempts")
                                if key in event}
                        store.append_event(rid, kind, "mixed_dag", safe,
                                           worker_token=worker_token)
                    mixed_output = dag.execute(decision, question=run["question"], context=base,
                        run_id=rid, conversation_id=run["conversation_id"], on_event=persist_mixed_event)
                    candidate_output = {"candidates": [], "citations": [], "unknowns": [],
                        "tool_calls": [], "events": [], "review": None}
                    execution_note = mixed_output["route_execution"]
                else:
                    raw_result = candidate.run(run["question"], base, run_id=rid,
                                               thread_id=run["conversation_id"])
                    candidate_output = raw_result["output"]
                    execution_note = "V2_AGENTIC_FAKE_CANDIDATE"
                hypotheses = [{"claim_id": hashlib.sha256((rid + str(i) + str(row.get("label"))).encode()).hexdigest()[:24],
                               "text": str(row.get("label") or "来源支持的待核候选")[:300],
                               "source_clause_ids": list(row.get("source_ids") or []),
                               "kind": "engineering_hypothesis"}
                              for i, row in enumerate(candidate_output.get("candidates") or [])]
                for evt in candidate_output.get("events") or []:
                    store.append_event(rid, "phase_started", "supervisor", {
                        "phase": str(evt.get("node") or "agentic_v2")[:80],
                        "public_rationale": str(evt.get("public_rationale") or "V2候选执行阶段")[:240],
                        "candidate_event": str(evt.get("kind") or "")[:64],
                    }, worker_token=worker_token)
                for call in candidate_output.get("tool_calls") or []:
                    env = call.get("result") if isinstance(call.get("result"), dict) else {}
                    refs = env.get("source") if isinstance(env.get("source"), list) else []
                    tool_name = str(call.get("tool") or "teacher_tool")[:80]
                    public_refs = [{k: src.get(k) for k in ("clause_id", "standard_code", "clause_no", "page", "verification_level") if k in src}
                                   for src in refs[:8] if isinstance(src, dict)]
                    public_args = call.get("arguments") if isinstance(call.get("arguments"), dict) else {}
                    store.append_event(rid, "tool_called", tool_name, {
                        "tool": tool_name, "tool_name": tool_name, "args": public_args,
                        "status": "running", "actual_attempts": int(call.get("attempts") or 0),
                        "public_rationale": "经固定教师工具白名单和参数Schema校验后执行。",
                    }, worker_token=worker_token)
                    call_status = str(call.get("status") or "unknown")
                    store.append_event(rid, "tool_result", tool_name, {
                        "tool": tool_name, "tool_name": tool_name,
                        "result": {"status": "completed" if call_status == "returned" else "failed", "sources": public_refs},
                        "actual_attempts": int(call.get("attempts") or 0),
                        "public_rationale": "仅显示脱敏的实际执行状态与核验来源标识。",
                    }, worker_token=worker_token)
                output = {
                    "status": (mixed_output.get("status") if mixed_output else
                              "insufficient_evidence" if not hypotheses else "exploratory"),
                    "conclusion": (mixed_output.get("final_text") if mixed_output else
                                   "V2离线候选形成了来源可追溯的初步调查方向；不构成工程确认或人工审核。"),
                    "citations": candidate_output.get("citations") or [], "hypotheses": hypotheses,
                    "unknowns": candidate_output.get("unknowns") or [],
                    "tool_calls": (mixed_output.get("tool_calls", 0) if mixed_output else
                                   len(candidate_output.get("tool_calls") or [])),
                    "verification_level": "E0", "agentic_candidate": candidate_output,
                    "mixed_dag": mixed_output, "route_execution": execution_note,
                }
                result = {"output": output, "review_round": candidate_output.get("review")}
            else:
                # Preserve the legacy route event consumed by existing clients while exposing
                # the richer intent_routed snapshot above. This is metadata, not a second route.
                legacy_route = classify_intent(run["question"], base)
                store.append_event(rid, "phase_started", "supervisor", {
                    "phase": "route", "public_rationale": f"route={legacy_route}",
                    "primary_route": route_snapshot.get("primary_route"),
                }, worker_token=worker_token)
                professional_plan = None
                candidate_enabled = os.getenv("AETHER_EXPERT_GUIDANCE_CANDIDATE", "0").strip() == "1"
                if candidate_enabled and run.get("mode") == "DEEPSEEK" and model_config:
                    from backend.professional_answers import classify_professional_intent, validate_professional_plan
                    planning_intents=classify_professional_intent(run["question"])
                    if any(name in planning_intents for name in ("MaintenanceSafety","RBIGrade","StandardsLookup","MechanismExploration","DeviceInvestigation")):
                        try:
                            emit("llm_started", "professional_planner", {"provider":model_config.get("provider"),"model":model_config.get("model"),
                                "purpose":"提出有界只读检索计划；由程序白名单校验后执行","max_requests":1,"max_tokens":600,"attachments_sent":False})
                            generation_model_request_count += 1
                            plan_result=deepseek.plan_professional_investigation(run["question"],base,model_config)
                            professional_plan=validate_professional_plan(plan_result.content)
                            emit("professional_plan_validated","professional_planner",{"provider":model_config.get("provider"),
                                "model":getattr(plan_result,"model",None),"duration_ms":getattr(plan_result,"duration_ms",None),
                                "finish_reason":getattr(plan_result,"finish_reason",None),"usage":getattr(plan_result,"usage",None),
                                "steps":len(professional_plan),"tools":sorted({t for step in professional_plan for t in step["tools"]})})
                        except Exception as exc:
                            # A planner failure never blocks professional F1 or the deterministic R9 plan.
                            professional_plan=None
                            emit("professional_plan_rejected","professional_planner",{"error_code":str(getattr(exc,"code",type(exc).__name__))[:64],
                                "status":"deterministic_plan_fallback","public_message":"专业检索规划未通过校验，已回退到受限本地检索计划。"})
                result = graph.run(run["question"], base, run_id=rid, on_event=persist_candidate_event,
                                   professional_mode=candidate_enabled, professional_plan=professional_plan)
            output = result["output"]
            professional_response = None
            if run.get("mode") != "V2_AGENTIC":
                from backend.professional_answers import (classify_professional_intent, deterministic_draft,
                    known_facts_for_response, render_professional_response, source_catalog_from_run, validate_professional_draft)
                from orchestration.evidence_audit import load_clause_index
                intent_names = classify_professional_intent(run["question"])
                candidate_enabled = os.getenv("AETHER_EXPERT_GUIDANCE_CANDIDATE", "0").strip() == "1"
                domain_concept = bool(re.search(r"腐蚀|裂纹|开裂|损伤|检验|RBI|压力容器|焊缝|失效", run["question"], re.I))
                professional_request = any(name in intent_names for name in ("MaintenanceSafety", "RBIGrade", "StandardsLookup", "MechanismExploration", "DeviceInvestigation")) or ("Concept" in intent_names and domain_concept)
                professional_guidance_enabled = os.getenv("AETHER_PROFESSIONAL_GUIDANCE_ENABLED", "1").strip() == "1"
                if professional_request and professional_guidance_enabled:
                    source_catalog = source_catalog_from_run(output.get("citations") or [], result.get("tool_calls") or [], load_clause_index(),
                                                           question=run["question"], context=base)
                    draft = deterministic_draft(run["question"], base, source_catalog)
                    # Candidate model planning/generation is opt-in and request-bounded. Default 0 means no added model cost.
                    if candidate_enabled and run.get("mode") == "DEEPSEEK" and model_config:
                        try:
                            emit("llm_started", "professional_explanation", {"provider": model_config.get("provider"), "model": model_config.get("model"),
                                "purpose": "受限结构化专业规划与主回答生成（不作设备确诊/RBI定级）", "attachments_sent": False,
                                "max_requests": 1, "max_tokens": 1800})
                            generation_model_request_count += 1
                            generated = deepseek.generate_professional_explanation(run["question"], base, source_catalog, model_config)
                            draft = validate_professional_draft(generated.content, source_catalog)
                            emit("professional_explanation_completed", "professional_explanation", {"provider": model_config.get("provider"),
                                "model": getattr(generated, "model", None), "duration_ms": getattr(generated, "duration_ms", None),
                                "finish_reason": getattr(generated, "finish_reason", None), "usage": getattr(generated, "usage", None),
                                "source_ids": sorted(source_catalog), "status": "completed_validated"})
                        except Exception as exc:
                            # Fail closed for model content; retain deterministic F1/F4 response.
                            emit("professional_explanation_rejected", "professional_explanation", {"error_code": str(getattr(exc, "code", type(exc).__name__))[:64],
                                "status": "deterministic_fallback", "public_message": "结构化回答未通过来源/风险门禁，已使用有界本地回答。"})
                    professional_response = {"intent": intent_names, "evidence_level": "GENERAL_GUIDANCE_WITH_SOURCE_CANDIDATES" if source_catalog else "GENERAL_GUIDANCE_WITHOUT_VERIFIED_STANDARD",
                        "known_facts": known_facts_for_response(base),
                        "source_catalog": list(source_catalog.values()), "human_source_verified": False, "risk_level": None,
                        "draft": draft.model_dump(mode="json")}
                    output["professional_response"] = professional_response
                    output["conclusion"] = render_professional_response(draft, professional_response["known_facts"], source_catalog)
                    output["status"] = "professional_guidance_candidate"
            # Project the candidate's actual hypotheses/review findings into the
            # existing SQLite claim ledger. This is an adapter over graph output,
            # not another reviewer or generated conclusion.
            hypothesis_by_id = {
                str(item.get("claim_id")): item
                for item in output.get("hypotheses") or []
                if item.get("claim_id")
            }
            for hypothesis in hypothesis_by_id.values():
                claim_id = str(hypothesis.get("claim_id") or "")
                if not claim_id:
                    continue
                emit("claim_added", "diagnosis_agent", {
                    **hypothesis, "claim": hypothesis.get("text"), "grade": "E0",
                    "verdict": "unresolved", "review_status": "requires_human_review",
                })
            for row in output.get("review_rows") or []:
                result_row = row.get("result") or {}
                origin = str(row.get("origin_agent") or "evidence_auditor")
                reviewer = "skeptic" if origin == "skeptic" else "evidence_auditor"
                hypothesis = hypothesis_by_id.get(str(row.get("claim_id")), {})
                finding = {
                    "claim_id": row.get("claim_id"),
                    "claim": hypothesis.get("text"),
                    "statement": hypothesis.get("text"),
                    "kind": hypothesis.get("kind", "engineering_hypothesis"),
                    "source_clause_id": row.get("source_clause_id"),
                    "source_clause_ids": [row.get("source_clause_id")] if row.get("source_clause_id") else [],
                    "grade": result_row.get("grade") or row.get("verification_level") or "E0",
                    "verdict": result_row.get("verdict") or "unresolved",
                    "review_status": "requires_human_review",
                    "verification_level": row.get("verification_level") or "E0",
                    "checks": result_row.get("checks") or {},
                    "payload_sha256": row.get("payload_sha256"),
                    "conflict_requires_review": bool(row.get("conflict_requires_review")),
                }
                emit("claim_checked", reviewer, finding)
                if finding["conflict_requires_review"]:
                    emit("contradiction_found", reviewer, {
                        **finding,
                        "disagreement_id": f"{finding.get('claim_id')}:{finding.get('source_clause_id')}:{row.get('attempt_id')}",
                        "kind": "independent_review_conflict",
                        "verdict": "conflict",
                        "grade": "E0",
                    })
            status = output.get("status", "unresolved")
            answer = [str(output.get("conclusion") or "未形成结论。")]
            hypotheses = output.get("hypotheses") or []
            if hypotheses and not output.get("professional_response"):
                materials = base.get("material")
                media = base.get("medium")
                material_text = ", ".join(materials) if isinstance(materials, list) else str(materials or "")
                medium_text = ", ".join(media) if isinstance(media, list) else str(media or "")
                conditions = "、".join(x for x in (material_text, medium_text) if x)
                answer[0] = (f"根据本轮提供的{conditions}，以下机理是值得核查的候选，不是确定结论。" if conditions
                             else "以下为来源支持的待核机理候选，不是确定结论。")
                rendered = []
                for row in hypotheses[:8]:
                    text = str(row.get("text") or "待核候选")
                    ids = row.get("source_clause_ids") or ([row.get("source_clause_id")] if row.get("source_clause_id") else [])
                    refs = [ref for ref in (output.get("citations") or []) if ref.get("clause_id") in ids]
                    provenance = "；".join(f"{ref.get('standard_code') or ''} {ref.get('clause_no') or ref.get('clause_id')}，p.{ref.get('page') or '未知'}".strip() for ref in refs)
                    rendered.append(f"- {text}" + (f"（来源：{provenance}；E0，待核）" if provenance else "（E0，待核；尚无直接出处）"))
                answer.append("**待核机理候选（不是结论）：**\n" + "\n".join(rendered))
                if any("酸性水腐蚀" in str(row.get("text")) for row in hypotheses):
                    answer.append("下一步请核对是否有实测减薄及其分布，并补充现场 pH、盐组分等工况证据；当前不能据此判定腐蚀已发生或给出风险等级。")
            citations = output.get("citations") or []
            if citations and not output.get("professional_response"):
                answer.append("**本轮检索出处：**" + "；".join(f"{row.get('standard_code') or ''} {row.get('clause_no') or row.get('clause_id')} p.{row.get('page') or '未知'}（仅证明来源可追溯，适用性待核）" for row in citations[:8]))
            explicit_sensitive_web_block = (
                run.get("mode") == "DEEPSEEK" and base.get("web_mode") == "on"
                and bool(re.search(r"设备|管线|容器|换热器|材质|介质|腐蚀|损伤|风险|RBI|检验|压力|温度|企业|装置|工况|测厚|标准",
                                   run["question"], re.IGNORECASE))
                and not bool(base.get("allow_sensitive_web_search"))
            )
            if status != "general_chat" and explicit_sensitive_web_block:
                emit("web_search_skipped", "web_search", {
                    "web_mode": "on", "error_code": "sensitive_data_blocked",
                    "message": "检测到工程敏感上下文；未向外部搜索服务发送问题或工况。",
                    "source_notice": "敏感联网需本轮单独明确允许；本次没有发出外部请求。",
                })
            if status == "general_chat" and run.get("mode") == "DEEPSEEK":
                emit("llm_started", "reporting_agent", {
                    "provider": model_config["provider"], "model": model_config["model"],
                    "purpose": "普通对话，不调用工程工具", "attachments_sent": False,
                })
                history, failed_summary = _ordinary_history(run["conversation_id"], rid, limit_turns=12)
                chat_profile = dict(model_config)
                search_sources: list[dict[str, Any]] = []
                search_mode = str(base.get("web_mode") or ("on" if base.get("web_search_enabled") else "off"))
                sensitive = bool(re.search(
                        r"设备|管线|容器|换热器|材质|介质|腐蚀|损伤|风险|RBI|检验|压力|温度|企业|装置|工况|测厚|标准",
                        run["question"], re.IGNORECASE)) or any(
                        base.get(field) not in (None, "", []) for field in
                        ("equipment", "equipment_type", "material", "medium", "operating_condition", "field_evidence"))
                allow_sensitive = bool(base.get("allow_sensitive_web_search"))
                from backend.web_search import should_search
                search_requested = should_search(search_mode, run["question"], sensitive=sensitive)
                search_blocked_sensitive = search_mode == "auto" and sensitive and bool(re.search(
                    r"最新|最近|当前|現在|今天|明天|本周|本月|今年|实时|新闻|天气|价格|报价|汇率|政策|公告|发布|版本|官网|文档|更新|查一下|搜索一下|联网查|latest|current|today|news|weather|price|version|release",
                    run["question"], re.IGNORECASE))
                search_error_message: str | None = None
                if search_blocked_sensitive:
                    emit("web_search_skipped", "web_search", {
                        "web_mode": search_mode, "error_code": "sensitive_data_blocked",
                        "message": "检测到工程敏感上下文，本轮自动跳过外部联网检索。",
                        "source_notice": "没有向外部搜索服务发送本轮问题或工况。",
                    })
                elif search_requested:
                    emit("web_search_started", "web_search", {
                        "enabled": True, "web_mode": search_mode, "sensitive_query": sensitive,
                        "sensitive_outbound_allowed": allow_sensitive,
                        "query_length": min(len(run["question"]), 128), "provider": "deepseek_search_fetch",
                    })
                    try:
                        search = DeepSeekWebSearch(api_key=model_config.get("api_key")).search(
                            run["question"][:128], enabled=True, sensitive=sensitive,
                            allow_sensitive_outbound=allow_sensitive, count=5,
                            budget=CallBudget(max_calls=1, timeout_seconds=8.0),
                        )
                        search_sources = [
                            {"title": src.title, "url": src.url, "retrieved_at": src.retrieved_at,
                             "snippet": src.snippet, "summary": src.summary,
                             "source_scope": src.source_scope}
                            for src in search.sources[:5]
                        ]
                        emit("web_search_completed", "web_search", {
                            "provider": search.provider, "elapsed_ms": search.elapsed_ms,
                            "source_notice": search.source_notice,
                            "sources": [{k: src[k] for k in ("title", "url", "retrieved_at", "source_scope")} for src in search_sources],
                        })
                        chat_profile["_web_sources"] = search_sources
                    except SearchError as exc:
                        search_error_message = str(exc)[:240]
                        emit("web_search_skipped" if exc.code in {"sensitive_data_blocked", "location_required", "opt_in_required"}
                             else "web_search_failed", "web_search", {
                                 "error_code": exc.code, "web_mode": search_mode,
                                 "message": search_error_message,
                                 "source_notice": "外部网络资料不是老师标准条文权威依据。",
                             })
                if history:
                    chat_profile["_history"] = history
                if failed_summary:
                    chat_profile["_failed_run_summary"] = failed_summary
                if model_config.get("profile_id") or history or failed_summary:
                    generation_model_request_count += 1
                    generation = deepseek.generate_chat(run["question"], chat_profile)
                else:
                    # Preserve the old first-turn adapter call shape.
                    generation_model_request_count += 1
                    generation = deepseek.generate_chat(run["question"])
                chat_answer, chat_ms = generation
                answer = [chat_answer]
                if search_error_message:
                    answer.append(f"**联网检索状态：**{search_error_message}；本回答未获得可引用的实时网页来源。")
                if search_sources:
                    refs = [f"- [{src['title'] or src['url']}]({src['url']})（检索于 {src['retrieved_at']}）"
                            for src in search_sources]
                    answer.append("**外部网络参考（非老师标准条文权威依据）：**\n" + "\n".join(refs))
                emit("llm_completed", "reporting_agent", {
                    "provider": model_config["provider"], "model": model_config["model"],
                    "duration_ms": chat_ms, "status": "completed", "attachments_sent": False,
                    "finish_reason": getattr(generation, "finish_reason", None),
                    "usage": getattr(generation, "usage", None),
                    "returned_model": getattr(generation, "model", None),
                })
            elif run.get("mode") == "DEEPSEEK" and not output.get("professional_response"):
                emit("llm_started", "reporting_agent", {
                    "provider": model_config["provider"], "model": model_config["model"],
                    "purpose": "仅改写有界确定性结果，不参与诊断、检索或审核",
                    "attachments_sent": False,
                })
                # Keep the normal chat reply short and authoritative. The
                # optional model-written wording lives in a collapsed process
                # disclosure, not inline as if it were private chain-of-thought.
                missing = [str(value) for value in (output.get("unknowns") or [])[:8]]
                if missing:
                    answer.append("待补充信息：" + "、".join(missing))
                answer.append("风险等级未给出；候选机理需结合现场证据和适用条款由人工复核。")
                try:
                    generation_model_request_count += 1
                    generation = (deepseek.generate_report(run["question"], output, base, model_config)
                                  if model_config.get("profile_id") else deepseek.generate_report(run["question"], output, base))
                    llm_answer, llm_duration_ms = generation
                    emit("llm_completed", "reporting_agent", {
                        "provider": model_config["provider"], "model": model_config["model"],
                        "duration_ms": llm_duration_ms, "status": "completed",
                        "attachments_sent": False,
                        "finish_reason": getattr(generation, "finish_reason", None),
                        "usage": getattr(generation, "usage", None),
                        "returned_model": getattr(generation, "model", None),
                        "summary_label": "DeepSeek 表达整理（非思维链）",
                        "summary": llm_answer,
                    })
                except Exception as exc:
                    # Local graph output remains the authoritative report when
                    # optional wording fails. Never surface provider bodies.
                    code = getattr(exc, "code", "provider_error")
                    emit("llm_failed", "reporting_agent", {
                        "provider": model_config.get("provider"), "model": model_config.get("model"),
                        "error_code": str(code)[:64], "status": "failed",
                        "public_message": "表达整理暂不可用；以上本地证据与待核候选仍有效。",
                    })
            else:
                if status == "general_chat":
                    answer = [rule_chat_reply(run["question"], model_name=(model_config or {}).get("model"))]
                elif status in {"needs_user_input", "insufficient_evidence", "review_conflict"}:
                    answer.append("风险等级未给出；请补齐现场数据并由工程人员复核。")
            route_snapshot = base.get("_v2_route_decision") or {}
            terminal_payload.update({"status": status, "mode": run.get("mode", "RULE_DEMO"), "web_mode": base.get("web_mode", "off"), "verification_level": output.get("verification_level", "E0"), "tool_calls": output.get("tool_calls", 0), "parallel_review": bool(result.get("review_round")), "risk_level": None,
                                     "primary_route": route_snapshot.get("primary_route"), "dispatch_route": route_snapshot.get("dispatch_route"),
                                     "intent_model_request_count": (route_snapshot.get("model_usage") or {}).get("request_count", 0),
                                     "generation_model_request_count": generation_model_request_count,
                                     "model_request_count": (route_snapshot.get("model_usage") or {}).get("request_count", 0) + generation_model_request_count,
                                     "route_execution": base.get("_v2_route_execution"),
                                     "provider": model_config.get("provider") if model_config else None,
                                     "model": model_config.get("model") if model_config else None,
                                     "profile_id": model_config.get("profile_id") if model_config else None})
            # CAS + assistant reply commit together; a lost lease cannot publish a reply.
            store.finish_run_with_message(rid, worker_token, "\n\n".join(answer), terminal_payload)
        except Exception as exc:
            failure_tb = exc.__traceback__
            while failure_tb is not None and failure_tb.tb_next is not None:
                failure_tb = failure_tb.tb_next
            failure_site = (f"{Path(failure_tb.tb_frame.f_code.co_filename).name}:"
                            f"{failure_tb.tb_lineno}") if failure_tb is not None else "unknown"
            # A recovered/expired lease must not emit a second error after the
            # system's worker_lost event; the CAS rejects stale tokens atomically.
            try:
                error_code = getattr(exc, "code", None)
                if not isinstance(error_code, str) or not re.fullmatch(r"[a-z0-9_]{1,64}", error_code):
                    error_code = "run_failed"
                public_messages = {
                    "output_truncated": "模型输出达到长度上限；请重试或缩短问题。",
                    "content_filtered": "模型未返回可显示内容；请调整请求后重试。",
                    "empty_response": "模型未返回可显示内容；请重试。",
                    "provider_rate_limited": "模型服务暂时繁忙，请稍后重试。",
                    "provider_timeout": "模型请求超时，请重试。",
                    "provider_network_error": "模型连接中断，请检查网络后重试。",
                    "provider_auth_error": "模型服务认证失败，请检查本地配置。",
                    "provider_request_error": "模型服务拒绝了本次请求。",
                    "provider_payment_required": "模型服务要求检查账户额度或付款方式；本轮未完成。",
                    "provider_unavailable": "模型服务暂时不可用，请重试。",
                    "provider_invalid_response": "模型服务返回格式异常，请重试。",
                    "provider_error": "模型生成失败，请重试。",
                    "run_failed": "本轮未完成，请重试。",
                }
                store.append_event(rid, "error", "supervisor",
                                   {"code": error_code, "failure_class": type(exc).__name__,
                                    "failure_site": failure_site,
                                    "message": public_messages.get(error_code, "本轮未完成，请重试。"),
                                    "finish_reason": getattr(exc, "finish_reason", None),
                                    "usage": getattr(exc, "usage", None),
                                    "returned_model": getattr(exc, "model", None)},
                                   worker_token=worker_token)
            except PermissionError:
                pass
            store.finish_run(rid, worker_token, "failed", error_code if 'error_code' in locals() else "run_failed")
        finally:
            stop_heartbeat.set()
            _worker_slots.release()
    Thread(target=worker, name=f"run-{rid[:8]}", daemon=True).start()


@app.get("/api/runs/{rid}/stream")
def stream_run(rid: str, after_sequence: int = 0,
               last_event_id: str | None = Header(default=None, alias="Last-Event-ID")):
    if last_event_id is not None:
        try:
            header_sequence = int(last_event_id.strip())
        except (TypeError, ValueError):
            raise HTTPException(422, "Last-Event-ID must be a non-negative event sequence") from None
        if header_sequence < 0:
            raise HTTPException(422, "Last-Event-ID must be a non-negative event sequence")
        after_sequence = max(after_sequence, header_sequence)
    if after_sequence < 0:
        raise HTTPException(422, "after_sequence must be non-negative")
    run = store.run(rid)
    if not run:
        raise HTTPException(404, "run not found")
    if run["status"] == "running":
        if run.get("mode") == "V2_AGENTIC":
            store.recover_stale_v2_run(rid)
        else:
            store.recover_stale_run(rid)
        run = store.run(rid)
    if run["status"] == "queued":
        if not _worker_slots.acquire(blocking=False):
            raise HTTPException(429, detail={"code": "WORKER_CAPACITY", "detail": "worker capacity reached; queued run is retained"},
                                headers={"Retry-After": "2"})
        token = str(uuid4())
        if store.claim_run(rid, token):
            _start_worker(rid, token)
        else:
            _worker_slots.release()

    async def generate():
        cursor = after_sequence
        while True:
            events = store.events(rid, cursor)
            for event in events:
                cursor = event["sequence"]
                # Keep the established one-object `data:` SSE wire format, but
                # enforce the same server-side public projection as replay.
                yield f"id: {cursor}\n" + "data: " + json.dumps(_public_event_projection(event), ensure_ascii=False) + "\n\n"
            current = store.run(rid)
            if current is not None and current["status"] == "running":
                if current.get("mode") == "V2_AGENTIC":
                    store.recover_stale_v2_run(rid)
                else:
                    store.recover_stale_run(rid)
                current = store.run(rid)
            if current is None or current["status"] in {"completed", "failed"}:
                # Read once more after terminal state to close append/status race.
                tail = store.events(rid, cursor)
                for event in tail:
                    cursor = event["sequence"]
                    yield f"id: {cursor}\n" + "data: " + json.dumps(_public_event_projection(event), ensure_ascii=False) + "\n\n"
                break
            await asyncio.sleep(0.05)

    return StreamingResponse(generate(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
