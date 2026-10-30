"""Loopback-only model profiles with user-scoped Windows DPAPI credentials."""
from __future__ import annotations

import base64
import ctypes
import ipaddress
import json
import os
import re
import socket
import time
from ctypes import wintypes
from pathlib import Path
from threading import RLock
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from backend.deepseek import settings as env_settings

_lock = RLock()
_APP = "Aetheris.ModelProfiles.v1"


def _root() -> Path:
    root = Path(os.getenv("AETHERIS_MODEL_STORE", str(Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData/Local")) / "Aetheris" / "ModelProfiles")))
    root.mkdir(parents=True, exist_ok=True)
    return root


def _blob(data: bytes):
    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]
    buffer = (ctypes.c_byte * len(data)).from_buffer_copy(data)
    return DATA_BLOB(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte))), buffer


def _protect(data: bytes, decrypt: bool = False) -> bytes:
    if os.name != "nt":
        raise RuntimeError("dpapi_unavailable")
    crypt32, kernel32 = ctypes.windll.crypt32, ctypes.windll.kernel32
    source, source_buffer = _blob(data)
    entropy, entropy_buffer = _blob(_APP.encode())
    output = type(source)()
    flags = 0x1  # CRYPTPROTECT_UI_FORBIDDEN
    if decrypt:
        ok = crypt32.CryptUnprotectData(ctypes.byref(source), None, ctypes.byref(entropy), None, None, flags, ctypes.byref(output))
    else:
        ok = crypt32.CryptProtectData(ctypes.byref(source), _APP, ctypes.byref(entropy), None, None, flags, ctypes.byref(output))
    if not ok:
        raise RuntimeError("dpapi_operation_failed")
    try:
        return ctypes.string_at(output.pbData, output.cbData)
    finally:
        kernel32.LocalFree(output.pbData)


def _read_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return fallback
    except (OSError, json.JSONDecodeError):
        raise RuntimeError("model_store_unreadable") from None


def _write_json(path: Path, payload: Any) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, path)


def _metadata() -> dict[str, Any]:
    return _read_json(_root() / "profiles.json", {"active_profile_id": None, "profiles": []})


def _credentials() -> dict[str, str]:
    path = _root() / "credentials.dpapi"
    if not path.exists():
        return {}
    encrypted = base64.b64decode(path.read_bytes())
    return json.loads(_protect(encrypted, decrypt=True).decode("utf-8"))


def _save_credentials(value: dict[str, str]) -> None:
    encrypted = _protect(json.dumps(value, ensure_ascii=False).encode("utf-8"))
    path = _root() / "credentials.dpapi"
    temp = path.with_suffix(".tmp")
    temp.write_bytes(base64.b64encode(encrypted))
    os.replace(temp, path)


def validate_endpoint(provider: str, endpoint: str) -> str:
    allowed = {"deepseek": {"api.deepseek.com"}, "openai-compatible": {"api.openai.com"}}
    value = endpoint.strip().rstrip("/")
    parsed = urlparse(value)
    if parsed.scheme != "https" or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ValueError("endpoint_not_allowed")
    host = (parsed.hostname or "").lower().rstrip(".")
    if host not in allowed.get(provider, set()) or parsed.path not in ("", "/", "/v1"):
        raise ValueError("endpoint_not_allowed")
    try:
        addresses = {ipaddress.ip_address(row[4][0]) for row in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)}
    except OSError:
        addresses = set()
    if any(not address.is_global for address in addresses):
        raise ValueError("endpoint_not_public")
    if not addresses:
        raise ValueError("endpoint_dns_unavailable")
    return value


def list_profiles() -> dict[str, Any]:
    with _lock:
        data = _metadata()
        profiles = [{**p, "key_configured": p.get("credential_id") in _credentials(),
                     "api_key_masked": "••••••••" if p.get("credential_id") in _credentials() else ""}
                    for p in data["profiles"]]
        return {"profiles": profiles, "active_profile_id": data.get("active_profile_id"),
                "credential_store": "Windows DPAPI (CurrentUser)" if os.name == "nt" else "unavailable"}


def save_profile(*, profile_id: str | None, provider: str, model: str, endpoint: str, api_key: str | None) -> dict[str, Any]:
    if provider not in {"deepseek", "openai-compatible"} or not re.fullmatch(r"[A-Za-z0-9._-]{1,80}", model.strip()):
        raise ValueError("invalid_provider_or_model")
    endpoint = validate_endpoint(provider, endpoint)
    if api_key is not None and not (8 <= len(api_key) <= 512 and "\n" not in api_key):
        raise ValueError("invalid_api_key")
    with _lock:
        data = _metadata(); creds = _credentials()
        pid = profile_id or os.urandom(12).hex()
        existing = next((p for p in data["profiles"] if p["id"] == pid), None)
        credential_id = existing.get("credential_id") if existing else os.urandom(16).hex()
        if api_key:
            if os.name != "nt":
                raise RuntimeError("dpapi_unavailable")
            creds[credential_id] = api_key
            _save_credentials(creds)
        elif not existing or credential_id not in creds:
            raise ValueError("api_key_required")
        profile = {"id": pid, "provider": provider, "model": model.strip(), "endpoint": endpoint,
                   "credential_id": credential_id, "enabled": True}
        data["profiles"] = [p for p in data["profiles"] if p["id"] != pid] + [profile]
        _write_json(_root() / "profiles.json", data)
        return {k: v for k, v in profile.items() if k != "credential_id"} | {"key_configured": True, "api_key_masked": "••••••••"}


def delete_profile(profile_id: str) -> bool:
    with _lock:
        data = _metadata(); matches = [p for p in data["profiles"] if p["id"] == profile_id]
        if not matches:
            return False
        creds = _credentials()
        for profile in matches:
            creds.pop(profile.get("credential_id", ""), None)
        data["profiles"] = [p for p in data["profiles"] if p["id"] != profile_id]
        if data.get("active_profile_id") == profile_id:
            data["active_profile_id"] = None
        _write_json(_root() / "profiles.json", data)
        _save_credentials(creds)
        return True


def activate_profile(profile_id: str | None) -> dict[str, Any] | None:
    with _lock:
        data = _metadata()
        selected = next((p for p in data["profiles"] if p["id"] == profile_id), None) if profile_id else None
        if profile_id and not selected:
            raise KeyError("profile_not_found")
        data["active_profile_id"] = profile_id
        _write_json(_root() / "profiles.json", data)
        return {k: v for k, v in selected.items() if k != "credential_id"} if selected else None


def resolve_profile(profile_id: str | None = None) -> dict[str, Any] | None:
    with _lock:
        data = _metadata()
        pid = profile_id or data.get("active_profile_id")
        profile = next((p for p in data["profiles"] if p["id"] == pid), None)
        if not profile:
            return None
        secret = _credentials().get(profile.get("credential_id", ""))
        if not secret:
            raise RuntimeError("credential_unavailable")
        return {"provider": profile["provider"], "model": profile["model"], "base_url": profile["endpoint"],
                "endpoint": profile["endpoint"].rstrip("/") + ("" if profile["endpoint"].endswith("/chat/completions") else "/chat/completions"),
                "api_key": secret, "timeout": 45.0, "profile_id": profile["id"]}


def environment_profile() -> dict[str, Any] | None:
    config = env_settings()
    return ({**config, "provider": "deepseek", "profile_id": None} if config["api_key"] and config["base_url"].startswith("https://") else None)


def safe_profile(profile_id: str | None = None) -> dict[str, Any] | None:
    return resolve_profile(profile_id) if profile_id else (resolve_profile() or environment_profile())


def resolve_snapshot(profile_id: str | None) -> dict[str, Any] | None:
    # None means the environment-backed compatibility profile was snapshotted;
    # do not silently follow a later active-profile change.
    return resolve_profile(profile_id) if profile_id else environment_profile()


def active_metadata() -> dict[str, Any] | None:
    data = _metadata()
    profile = next((p for p in data["profiles"] if p["id"] == data.get("active_profile_id")), None)
    if profile:
        try:
            configured = bool(_credentials().get(profile.get("credential_id", "")))
        except RuntimeError:
            configured = False
        return {k: v for k, v in profile.items() if k != "credential_id"} | {"configured": configured}
    env = environment_profile()
    return ({"id": None, "provider": env["provider"], "model": env["model"], "configured": True} if env else None)


def test_connection(profile_id: str) -> dict[str, Any]:
    profile = resolve_profile(profile_id)
    if not profile:
        raise KeyError("profile_not_found")
    validate_endpoint(profile["provider"], profile["base_url"])
    payload = {"model": profile["model"], "messages": [{"role": "user", "content": "Reply with OK."}],
               "temperature": 0, "max_tokens": 2, "stream": False}
    request = Request(profile["endpoint"], data=json.dumps(payload).encode(),
                      headers={"Authorization": f"Bearer {profile['api_key']}", "Content-Type": "application/json"}, method="POST")
    started = time.perf_counter()
    try:
        with urlopen(request, timeout=20) as response:
            body = json.loads(response.read(1_000_000).decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(f"provider_http_{exc.code}") from None
    except (URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        raise RuntimeError(f"provider_{type(exc).__name__.lower()}") from None
    choices = body.get("choices") or []
    if not choices or not isinstance((choices[0].get("message") or {}).get("content"), str):
        raise RuntimeError("provider_invalid_response")
    usage = body.get("usage") if isinstance(body.get("usage"), dict) else {}
    return {"ok": True, "provider": profile["provider"], "model": profile["model"],
            "latency_ms": round((time.perf_counter() - started) * 1000),
            "usage": {k: usage.get(k) for k in ("prompt_tokens", "completion_tokens", "total_tokens") if usage.get(k) is not None},
            "cost_warning": "供应商可能按请求计费；测试仅发送固定的 OK 提示，不含设备数据。"}
