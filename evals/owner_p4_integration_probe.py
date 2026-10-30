"""Owner read-only P4 integration/adversarial probe.
All writes are confined to TemporaryDirectory, never project business DB.
"""
from __future__ import annotations
import json, tempfile
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend.store import Store
from orchestration.graph import AgentGraph
import backend.api as api

def full_context_sse() -> None:
    with tempfile.TemporaryDirectory(prefix="p4-owner-e2e-") as tmp:
        store = Store(Path(tmp)/"business.sqlite")
        graph = AgentGraph(checkpoint_path=Path(tmp)/"checkpoints.sqlite")
        with patch.object(api,"store",store),patch.object(api,"graph",graph):
            client=TestClient(api.app)
            conv=client.post("/api/conversations",json={"title":"independent evidence audit"}).json()
            params={
                "question":"塔顶水样pH 5.8，铁离子 4.1 mg/L，尚未测厚，可能的损伤机理？",
                "material":"碳钢","medium":["氯化氢"],"equipment_type":"换热器",
                "field_evidence":"塔顶水样pH 5.8，铁离子 4.1 mg/L，尚未测厚",
            }
            res=client.post(f"/api/conversations/{conv['id']}/runs",json=params)
            assert res.status_code == 200, (res.status_code,res.text[:400])
            run=res.json()["run_id"]
            stream=client.get(res.json()["events_url"])
            assert stream.status_code == 200
            evs=store.events(run)
            claims=client.get(f"/api/runs/{run}/claims").json()["claims"]
            disputes=client.get(f"/api/runs/{run}/disagreements").json()["disagreements"]
            refs=[e for e in evs if e["type"]=="reference_added"]
            print("FULL_CONTEXT", "run",run[:8],"events",len(evs),"claims",len(claims),"disagreements",len(disputes),"references",len(refs))
            print("KINDS",sorted({e["type"] for e in evs}))
            print("CLAIMS",[(c.get("claim_id"),c.get("grade"),c.get("review_status")) for c in claims][:6])
            print("RUN_STATUS",store.run(run)["status"])
            assert store.run(run)["status"] == "completed"
            assert claims and disputes and refs
            assert all(c.get("verdict")=="unresolved" for c in claims)
            assert any(c.get("grade")=="E1" for c in claims), "expected an E1 provenance-level audited claim"
            assert len(store.messages(conv["id"]))==2
            assert evs[-1]["type"]=="run_completed"

def late_worker_event() -> None:
    with tempfile.TemporaryDirectory(prefix="p4-owner-lease-") as tmp:
        store=Store(Path(tmp)/"business.sqlite")
        conv=store.create_conversation("lease")
        run=store.create_run(conv["id"],"q",{},"RULE_DEMO")
        rid=run["id"]
        assert store.claim_run(rid,"worker-a")
        with store.session() as conn:
            conn.execute("UPDATE runs SET worker_heartbeat_at=? WHERE id=?",("2000-01-01T00:00:00+00:00",rid))
        assert store.recover_stale_run(rid,stale_after_seconds=0)
        try:
            appended=store.append_event(rid,"claim_added","old-worker",{"claim_id":"late-c","grade":"E0","verdict":"unresolved"})
            print("LATE_EVENT_AFTER_FAILED_RUN_ALLOWED",appended["sequence"],"status",store.run(rid)["status"])
            assert store.run(rid)["status"]=="failed"
            assert appended["sequence"] == 2
        except Exception as exc:
            print("LATE_EVENT_AFTER_FAILED_RUN_REJECTED",type(exc).__name__)

if __name__=="__main__":
    full_context_sse()
    late_worker_event()
    print("OWNER_P4_PROBE_DONE")
