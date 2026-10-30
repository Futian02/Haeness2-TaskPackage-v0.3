"""Offline 10-scenario chat-mode smoke matrix through FastAPI/SQLite/SSE.

All LLM calls are deterministic mocks. This script never reads or contacts the
configured provider. Teacher tools are the real local registry used by the
application. Output is an evidence artifact, not a model-quality benchmark.
"""
from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend import api, deepseek
from backend.store import Store


CASES = [
    ("greeting", "你好", "general_chat", None),
    ("identity", "你是什么模型？", "general_chat", None),
    ("capabilities", "你可以干什么？", "general_chat", None),
    ("poem", "帮我写一首关于深秋的小诗", "general_chat", None),
    ("rbi_concept", "什么是RBI？", "general_chat", None),
    ("standard_lookup", "GB/T 26610.3-2014 风险等级的确定 标准条款", "standard_lookup", None),
    ("underspecified_risk", "请依据标准判断这台设备的风险等级", "missing_context", None),
    ("wet_h2s", "材质碳钢、介质湿硫化氢，可能存在哪些损伤机理？", "diagnosis", {
        "equipment": "测试管道", "equipment_type": "管道", "material": "碳钢", "medium": ["湿硫化氢"],
        "field_evidence": "pH 5.8，H2S 12 ppm，测厚未知",
    }),
    ("pdf_not_read", "帮我分析这份文档", "general_chat", {"pdf_fixture": True}),
    ("llm_failure", "你好", "general_chat", {"llm_failure": True}),
]


def _event_type(event: dict) -> str:
    return str(event.get("type") or event.get("kind") or "")


def run_matrix() -> list[dict]:
    results: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="aether-r10-matrix-") as temp:
        root = Path(temp)
        store = Store(root / "matrix.sqlite3")
        upload_root = root / "uploads"
        upload_root.mkdir()
        model_calls = {"count": 0}
        # Current API resolves/snapshots profiles independently of the legacy
        # deepseek.is_configured() helper. Keep this test offline and avoid .env.local.
        fake_profile = {"profile_id": "r10-offline-mock", "provider": "mock",
                        "model": "offline-mock", "api_key": "MOCK_ONLY", "base_url": "https://mock.invalid",
                        "endpoint": "https://mock.invalid/chat/completions", "timeout": 0.1}

        def mock_chat(question: str, *_args, **_kwargs):
            model_calls["count"] += 1
            return ("我使用服务端配置的 DeepSeek 模型；Aether 是应用名。" if "模型" in question else
                    "你好！我是 Aether，可以聊天、解释概念并协助查证标准。" if question.strip() == "你好" else
                    "RBI 是基于风险的检验方法。" if "RBI" in question else
                    "深秋微凉，银杏落满长街；灯火把归途，写成温柔的诗。" if "小诗" in question else
                    "我可以聊天、解释技术概念，也能查询机械损伤机理、RBI 与标准条款。", 3)

        def mock_report(_question: str, output: dict, _context: dict, *_args, **_kwargs):
            model_calls["count"] += 1
            return (str(output.get("conclusion") or "结果待核。"), 3)

        def fail_chat(_question: str, *_args, **_kwargs):
            model_calls["count"] += 1
            raise RuntimeError("offline provider failure")

        with patch.dict(os.environ, {"APP_ENV": "development"}), \
             patch.object(api, "store", store), \
             patch.object(api, "UPLOAD_ROOT", upload_root), \
             patch.object(api.model_profiles, "safe_profile", return_value=fake_profile), \
             patch.object(api.model_profiles, "resolve_snapshot", return_value=fake_profile), \
             patch.object(deepseek, "is_configured", return_value=True), \
             patch.object(deepseek, "settings", return_value={"model": "offline-mock"}), \
             patch.object(deepseek, "generate_chat", side_effect=mock_chat), \
             patch.object(deepseek, "generate_report", side_effect=mock_report):
            with TestClient(api.app) as client:
                for name, question, expected_route, options in CASES:
                    options = options or {}
                    cid = client.post("/api/conversations", json={"title": f"R10 {name}"}).json()["id"]
                    file_ids: list[str] = []
                    if options.get("pdf_fixture"):
                        pdf = b"%PDF-1.4\n% offline placeholder fixture\n%%EOF\n"
                        upload = client.post(f"/api/conversations/{cid}/files",
                            files=[("files", ("fixture.pdf", pdf, "application/pdf"))])
                        assert upload.status_code == 200, upload.text
                        file_ids = [row["id"] for row in upload.json()["files"]]

                    for mode in ("RULE_DEMO", "DEEPSEEK"):
                        model_calls["count"] = 0
                        if options.get("llm_failure") and mode == "DEEPSEEK":
                            deepseek.generate_chat.side_effect = fail_chat
                        else:
                            deepseek.generate_chat.side_effect = mock_chat
                        before = time.perf_counter()
                        payload = {key: value for key, value in options.items() if key not in {"pdf_fixture", "llm_failure"}}
                        payload.update({"question": question, "mode": mode, "file_ids": file_ids})
                        created = client.post(f"/api/conversations/{cid}/runs", json=payload)
                        assert created.status_code == 200, (name, mode, created.text)
                        run_id = created.json()["run_id"]
                        streamed = client.get(created.json()["events_url"])
                        assert streamed.status_code == 200, streamed.text
                        elapsed_ms = round((time.perf_counter() - before) * 1000, 3)
                        full = client.get(f"/api/runs/{run_id}/events").json()["events"]
                        midpoint = full[len(full) // 2]["sequence"] if full else 0
                        tail = client.get(f"/api/runs/{run_id}/events?after_sequence={midpoint}").json()["events"]
                        replay_consistent = full == [event for event in full if event["sequence"] <= midpoint] + tail
                        persisted = store.run(run_id)
                        messages = store.messages(cid)
                        assistant = [m for m in messages if m.get("role") == "assistant" and m.get("run_id") == run_id]
                        tool_calls = sum(_event_type(event) == "tool_called" for event in full)
                        route_event = next((e for e in full if _event_type(e) == "phase_started" and
                                            str(e.get("payload", {}).get("phase")) == "route"), None)
                        route = str(route_event["payload"].get("public_rationale", "")).removeprefix("route=") if route_event else expected_route
                        if name == "llm_failure" and mode == "DEEPSEEK":
                            assert persisted["status"] == "failed"
                            assert any(_event_type(e) == "error" for e in full)
                            assert not assistant
                        else:
                            assert persisted["status"] == "completed"
                            assert len(assistant) == 1
                        answer = assistant[0]["content"] if assistant else ""
                        if name == "pdf_not_read" and mode == "DEEPSEEK":
                            assert "文档内容" not in answer and "PDF内容" not in answer
                            assert file_ids
                        if name == "wet_h2s" and mode == "RULE_DEMO":
                            assert any(_event_type(e) == "tool_called" for e in full), "expected real local teacher-tool execution"
                        if name == "standard_lookup" and mode == "RULE_DEMO":
                            assert any(_event_type(e) == "tool_called" for e in full), f"expected real standard_clause_search execution; events={[(_event_type(e), e.get('payload')) for e in full]}"
                        results.append({
                            "case": name, "mode": mode, "run_id": run_id, "route": route,
                            "llm_backend": "MOCK_OFFLINE" if mode == "DEEPSEEK" else "NONE",
                            "model_request_count": model_calls["count"], "real_tool_calls": int(tool_calls),
                            "final_answer": answer, "trace_replay_consistent": replay_consistent,
                            "latency_ms": elapsed_ms, "run_status": persisted["status"],
                            "expected_route": expected_route,
                        })
                        assert replay_consistent, f"SQLite replay mismatch: {name}/{mode}"
                    deepseek.generate_chat.side_effect = mock_chat
    return results


if __name__ == "__main__":
    rows = run_matrix()
    output = Path(__file__).with_name("r10_offline_chat_matrix_s2_20261029.jsonl")
    output.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    print(json.dumps({"runs": len(rows), "modes": {mode: sum(row["mode"] == mode for row in rows) for mode in ("RULE_DEMO", "DEEPSEEK")},
                      "output": str(output), "all_replay_consistent": all(r["trace_replay_consistent"] for r in rows)}, ensure_ascii=False, indent=2))
