"""Deterministic, offline SQLite concurrency checks for the P13 hard gate."""
from __future__ import annotations

import statistics
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import BoundedSemaphore, Lock
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend import api
from backend.store import Store


class P13LocalLoadTests(unittest.TestCase):
    def test_100_local_runs_at_concurrency_1_4_8_have_single_ordered_terminal(self):
        measurements = []
        for concurrency in (1, 4, 8):
            with tempfile.TemporaryDirectory(prefix=f"p13-load-{concurrency}-") as temp:
                store = Store(Path(temp) / "stress.sqlite3")
                conversation = store.create_conversation(f"stress-{concurrency}")
                latencies: list[float] = []
                failures: list[str] = []
                lock = Lock()

                def one_run(index: int) -> None:
                    started = time.perf_counter()
                    run = store.create_run_with_message(
                        conversation["id"], f"混合本地负载输入 #{index}",
                        {"web_mode": "off", "load_case": index}, "RULE_DEMO", [],
                    )
                    token = f"worker-{concurrency}-{index}"
                    if not store.claim_run(run["id"], token):
                        with lock:
                            failures.append(f"claim:{index}")
                        return
                    store.append_event(run["id"], "agent_started", "supervisor",
                                       {"phase": "local-stress", "case": index}, worker_token=token)
                    if not store.finish_run_with_message(run["id"], token, f"local-answer-{index}",
                                                         {"status": "completed", "case": index}):
                        with lock:
                            failures.append(f"finish:{index}")
                        return
                    elapsed = (time.perf_counter() - started) * 1000
                    with lock:
                        latencies.append(elapsed)

                started_all = time.perf_counter()
                with ThreadPoolExecutor(max_workers=concurrency) as pool:
                    list(pool.map(one_run, range(100)))
                total_ms = (time.perf_counter() - started_all) * 1000
                runs = store.list_runs_by_conversation(conversation["id"], limit=100)[0]
                self.assertEqual(len(runs), 100)
                self.assertFalse(failures)
                for item in runs:
                    detail = store.run(item["id"])
                    self.assertEqual(item["status"], "completed")
                    records = store.events(item["id"])
                    self.assertEqual([e["sequence"] for e in records], [1, 2])
                    self.assertEqual([e["type"] for e in records].count("run_completed"), 1)
                    messages = [m for m in store.messages(conversation["id"]) if m.get("run_id") == item["id"]]
                    self.assertEqual([m["role"] for m in messages], ["user", "assistant"])
                    self.assertEqual(messages[-1]["content"], f"local-answer-{detail['question'].split('#')[-1].strip()}")
                ordered = sorted(latencies)
                p50 = statistics.median(ordered)
                p95 = ordered[min(len(ordered) - 1, int(len(ordered) * .95))]
                metrics = {"concurrency": concurrency, "runs": 100, "errors": len(failures),
                           "p50_ms": round(p50, 3), "p95_ms": round(p95, 3),
                           "max_ms": round(max(ordered), 3), "batch_ms": round(total_ms, 3)}
                measurements.append(metrics)
                print(f"P13_LOCAL_LOAD {metrics}")
        self.assertEqual([item["runs"] for item in measurements], [100, 100, 100])

    def test_worker_capacity_returns_explicit_429_without_losing_queued_run(self):
        with tempfile.TemporaryDirectory(prefix="p13-capacity-") as temp:
            store = Store(Path(temp) / "isolated.sqlite3")
            with patch.dict("os.environ", {"APP_ENV": "development"}), \
                 patch.object(api, "store", store), \
                 patch.object(api, "_worker_slots", BoundedSemaphore(0)):
                with TestClient(api.app) as client:
                    cid = client.post("/api/conversations", json={}).json()["id"]
                    created = client.post(f"/api/conversations/{cid}/runs", json={"question": "capacity fixture"}).json()
                    response = client.get(created["events_url"])
                self.assertEqual(response.status_code, 429)
                self.assertEqual(store.run(created["run_id"])["status"], "queued")


if __name__ == "__main__":
    unittest.main()
