#!/usr/bin/env python3
"""Start/probe an isolated R2 FastAPI service without touching live ports or data.

Examples:
  python scripts/r2_service_shadow_run.py --probe-legacy
  python scripts/r2_service_shadow_run.py --shadow --port 8877 --hold
  python scripts/r2_service_shadow_run.py --shadow --port 8877 --check-only

The shadow profile always uses temporary SQLite/uploads/model-profile paths and
strips provider credentials from the child environment. Ctrl-C stops only the
child process created by this script.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = "aetheris-r2.0.0"
SOURCE_FILES = tuple(sorted((
    "backend/api.py", "backend/store.py", "backend/deepseek.py",
    "backend/model_profiles.py", "backend/context_slots.py",
    "backend/conversation_memory.py", "backend/professional_answers.py",
    "backend/intent_router_v2.py", "orchestration/intent.py",
    "orchestration/graph.py", "orchestration/r9_industrial_candidate.py",
)))


def fingerprint() -> str:
    digest = hashlib.sha256()
    for relative in SOURCE_FILES:
        data = (ROOT / relative).read_bytes()
        digest.update(relative.encode("utf-8")); digest.update(b"\0")
        digest.update(len(data).to_bytes(8, "big")); digest.update(data)
    return "sha256:" + digest.hexdigest()


def get_json(url: str, timeout: float = 2.0):
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read(1024 * 1024)
        content_type = response.headers.get("content-type", "")
        if "json" not in content_type:
            return response.status, {"_content_type": content_type, "_body_prefix": raw[:256].decode("utf-8", "replace")}
        return response.status, json.loads(raw.decode("utf-8"))


def port_is_free(host: str, port: int) -> bool:
    with socket.socket() as sock:
        try:
            sock.bind((host, port))
            return True
        except OSError:
            return False


def redact(value: str) -> str:
    value = re.sub(r"(?i)(api[_-]?key|token|password|secret)(\s*[=:]\s*)[^\s;]+", r"\1\2[REDACTED]", value)
    return value[:2000]


def process_facts(pid: int) -> dict:
    script = f"""
$p = Get-CimInstance Win32_Process -Filter "ProcessId={int(pid)}" -ErrorAction SilentlyContinue
if (-not $p) {{ '{{"exists":false}}'; exit 0 }}
$proc = Get-Process -Id {int(pid)} -ErrorAction SilentlyContinue
[pscustomobject]@{{exists=$true;pid={int(pid)};name=$p.Name;executable=$p.ExecutablePath;creation_date=$p.CreationDate;command_line=$p.CommandLine;process_path=if($proc){{$proc.Path}}else{{$null}}}} | ConvertTo-Json -Compress
"""
    result = subprocess.run(["powershell", "-NoProfile", "-Command", script],
                           capture_output=True, text=True, timeout=10)
    if result.returncode or not result.stdout.strip():
        return {"exists": False, "probe_error": redact(result.stderr.strip() or result.stdout.strip())}
    try:
        info = json.loads(result.stdout.strip())
        if isinstance(info.get("command_line"), str):
            info["command_line"] = redact(info["command_line"])
        return info
    except json.JSONDecodeError:
        return {"exists": False, "probe_error": redact(result.stdout.strip())}


def probe_legacy() -> dict:
    probes = []
    for port in (8000, 8001):
        entry = {"port": port}
        try:
            status, health = get_json(f"http://127.0.0.1:{port}/api/health")
            entry["health_http_status"] = status
            entry["health"] = health
            openapi_status, spec = get_json(f"http://127.0.0.1:{port}/openapi.json")
            entry["openapi_http_status"] = openapi_status
            paths = spec.get("paths", {}) if isinstance(spec, dict) else {}
            entry["has_model_profiles"] = "/api/model-profiles" in paths
            entry["has_idempotency_header"] = "Idempotency-Key" in json.dumps(paths.get("/api/conversations/{cid}/runs", {}))
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=3) as response:
                html_bytes = response.read(1024 * 1024)
                entry["root_http_status"] = response.status
                entry["root_content_type"] = response.headers.get("content-type")
            html = html_bytes.decode("utf-8", "replace")
            asset_paths = sorted(set(re.findall(r"(?:src|href)=['\"]([^'\"]*/assets/[^'\"]+)['\"]", html)))
            assets = []
            for asset_path in asset_paths[:12]:
                asset_url = asset_path if asset_path.startswith("http") else f"http://127.0.0.1:{port}{asset_path}"
                try:
                    with urllib.request.urlopen(asset_url, timeout=3) as response:
                        data = response.read(16 * 1024 * 1024)
                        assets.append({"path": asset_path, "http_status": response.status,
                                       "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)})
                except Exception as exc:
                    assets.append({"path": asset_path, "error": type(exc).__name__})
            entry["served_frontend_assets"] = assets
        except Exception as exc:
            entry["probe_error"] = type(exc).__name__ + ": " + redact(str(exc))
        pid = None
        try:
            for row in subprocess.check_output(["powershell", "-NoProfile", "-Command",
                f"(Get-NetTCPConnection -State Listen -LocalPort {port} -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty OwningProcess)"],
                text=True, timeout=10).splitlines():
                row = row.strip()
                if row.isdigit():
                    pid = int(row); break
        except Exception as exc:
            entry["pid_probe_error"] = type(exc).__name__
        entry["pid"] = pid
        entry["process"] = process_facts(pid) if pid else None
        probes.append(entry)
    result = {"operation": "GET-only legacy probe", "ports_touched": [8000, 8001], "writes": False,
              "process_actions": "none", "probes": probes}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def start_shadow(port: int, hold: bool, startup_timeout: float) -> int:
    if not port_is_free("127.0.0.1", port):
        raise SystemExit(f"shadow port {port} is already occupied; choose another port")
    temp_root = Path(tempfile.mkdtemp(prefix="aetheris-r2-shadow-"))
    (temp_root / "model-profiles").mkdir()
    (temp_root / "uploads").mkdir()
    log_path = temp_root / "uvicorn.log"
    env = os.environ.copy()
    for name in ("DEEPSEEK_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "AZURE_OPENAI_API_KEY"):
        # deepseek.py reads the repository's ignored .env.local only when the
        # key is absent from process env; set empty explicitly to prevent that.
        env[name] = ""
    env.update({
        "APP_ENV": "development",
        "DATABASE_URL": "sqlite:///" + str(temp_root / "shadow.sqlite3"),
        "UPLOAD_ROOT": str(temp_root / "uploads"),
        "AETHERIS_MODEL_STORE": str(temp_root / "model-profiles"),
        "AETHER_EXPERT_GUIDANCE_CANDIDATE": "0",
        "AETHER_PROFESSIONAL_GUIDANCE_ENABLED": "1",
        "AETHER_V2_AGENTIC_ENABLED": "0",
    })
    with log_path.open("wb") as log:
        child = subprocess.Popen([sys.executable, "-m", "uvicorn", "backend.api:app",
                                  "--host", "127.0.0.1", "--port", str(port), "--no-access-log"],
                                 cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
        base = f"http://127.0.0.1:{port}"
        deadline = time.monotonic() + startup_timeout
        health = None
        while time.monotonic() < deadline and child.poll() is None:
            try:
                _, health = get_json(base + "/api/health")
                break
            except Exception:
                time.sleep(0.25)
        if health is None:
            child.terminate()
            try: child.wait(timeout=5)
            except subprocess.TimeoutExpired: child.kill(); child.wait(timeout=5)
            log.flush()
            raise SystemExit(f"shadow backend failed readiness; see {log_path}")
        expected = fingerprint()
        observed = health.get("build_fingerprint")
        ok = health.get("contract_version") == CONTRACT and observed == expected
        manifest = {"base_url": base, "pid": child.pid, "database": str(temp_root / "shadow.sqlite3"),
                    "temporary_root": str(temp_root), "model_profile_dir": str(temp_root / "model-profiles"),
                    "upload_root": str(temp_root / "uploads"), "contract_version": health.get("contract_version"),
                    "expected_source_fingerprint": expected, "observed_build_fingerprint": observed,
                    "health_capabilities": health.get("capabilities"), "flags": health.get("flags"),
                    "isolated": ok, "provider_credentials_removed": True, "log_path": str(log_path)}
        manifest_path = temp_root / "runtime-manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(manifest, ensure_ascii=False, indent=2), flush=True)
        if not ok:
            child.terminate(); child.wait(timeout=5)
            raise SystemExit("contract/fingerprint mismatch: shadow service is not accepted")
        if not hold:
            child.terminate()
            child.wait(timeout=10)
            print("SHADOW_CHECK_PASS server stopped; temp root retained for evidence.", flush=True)
            return 0
        print("Shadow backend is running. Ctrl-C stops only this isolated child.", flush=True)
        try:
            while child.poll() is None:
                time.sleep(0.5)
        except KeyboardInterrupt:
            print("Stopping isolated shadow child only.", flush=True)
            child.terminate()
            try: child.wait(timeout=10)
            except subprocess.TimeoutExpired: child.kill(); child.wait(timeout=5)
        return child.returncode or 0


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--probe-legacy", action="store_true", help="GET-only inspect 8000/8001 process/API")
    group.add_argument("--shadow", action="store_true", help="start isolated temporary backend")
    parser.add_argument("--port", type=int, default=8877)
    parser.add_argument("--hold", action="store_true", help="keep isolated backend running until Ctrl-C")
    parser.add_argument("--startup-timeout", type=float, default=30)
    args = parser.parse_args()
    if args.probe_legacy:
        probe_legacy(); return 0
    return start_shadow(args.port, args.hold, args.startup_timeout)


if __name__ == "__main__":
    raise SystemExit(main())
