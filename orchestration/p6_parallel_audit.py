"""Isolated, bounded parallel audit experiment; never changes the production graph.

This is RULE_DEMO orchestration only. Both branches read the same immutable input
snapshot and write role-specific reducer channels. The merge is deterministic and
idempotent for an (run, claim, source, role, attempt) key.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from operator import add
from typing import Annotated, Any, TypedDict
from types import SimpleNamespace

from orchestration.evidence_audit import audit_claim, skeptic_findings


@dataclass(frozen=True)
class AuditFinding:
    run_id: str
    claim_id: str
    source_clause_id: str
    origin_agent: str
    attempt_id: str
    result: dict[str, Any]


@dataclass(frozen=True)
class SkepticFinding:
    run_id: str
    claim_id: str
    source_clause_id: str
    origin_agent: str
    attempt_id: str
    result: dict[str, Any]


class ParallelAuditState(TypedDict):
    run_id: str
    attempt_id: str
    context: dict[str, Any]
    observations: list[dict[str, Any]]
    tool_results: list[dict[str, Any]]
    claims: list[dict[str, Any]]
    clause_index: dict[str, dict[str, Any]]
    audit_updates: Annotated[list[AuditFinding], add]
    skeptic_updates: Annotated[list[SkepticFinding], add]
    merged_findings: list[dict[str, Any]]


def _source_ids(claim: dict[str, Any]) -> list[str]:
    return sorted({str(cid) for cid in claim.get("source_clause_ids", []) if cid}) or [""]


def _audit_branch(state: ParallelAuditState) -> dict[str, Any]:
    # This branch uses only raw observations/context/current tool source/canonical
    # records. It does not consume skeptic prose or mutable claims from another node.
    inputs = SimpleNamespace(context=state["context"], observations=state["observations"],
                             tool_results=state["tool_results"])
    updates = []
    for claim in state["claims"]:
        result = audit_claim(claim, inputs, state["clause_index"]).model_dump(mode="json")
        for cid in _source_ids(claim):
            updates.append(AuditFinding(state["run_id"], claim["claim_id"], cid,
                                        "evidence_auditor", state["attempt_id"], result))
    return {"audit_updates": updates}


def _skeptic_branch(state: ParallelAuditState) -> dict[str, Any]:
    # skeptic_findings derives evidence from raw observations and sources. The claim
    # text is not treated as evidence, and no audit-branch natural language is read.
    inputs = SimpleNamespace(context=state["context"], observations=state["observations"],
                             tool_results=state["tool_results"], claims=state["claims"])
    results = skeptic_findings(inputs, state["clause_index"])
    by_id = {item["claim_id"]: item for item in results}
    updates = []
    for claim in state["claims"]:
        result = by_id.get(claim["claim_id"], {"claim_id": claim["claim_id"],
                                                 "verdict": "unresolved",
                                                 "finding": "无独立审查结果；需人工复核"})
        for cid in _source_ids(claim):
            updates.append(SkepticFinding(state["run_id"], claim["claim_id"], cid,
                                          "skeptic", state["attempt_id"], result))
    return {"skeptic_updates": updates}


def finding_key(finding: AuditFinding | SkepticFinding) -> tuple[str, str, str, str, str]:
    return (finding.run_id, finding.claim_id, finding.source_clause_id,
            finding.origin_agent, finding.attempt_id)


def _payload_sha256(payload: dict[str, Any]) -> str:
    """Hash the submitted finding payload before applying trust-boundary clamps."""
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _safe_result(finding: AuditFinding | SkepticFinding) -> tuple[dict[str, Any], str | None]:
    """Copy a result while keeping caller-controlled grade fields below E2."""
    if not isinstance(finding.result, dict):
        raise ValueError("finding result must be a JSON object")
    # Validate JSON-serializability up front so hashing is deterministic and
    # malformed Python objects cannot silently enter the review projection.
    _payload_sha256(finding.result)
    result = dict(finding.result)
    reason: str | None = None
    submitted_grade = result.get("grade")
    if finding.origin_agent != "evidence_auditor" and "grade" in result:
        result["grade"] = "E0"
        reason = "only_evidence_auditor_may_emit_E0_E1_grade"
    elif "grade" in result and submitted_grade not in {"E0", "E1"}:
        result["grade"] = "E0"
        reason = "grade_outside_merge_E0_E1_allowlist"
    # A result payload must never smuggle a separate verification-level field
    # around the explicit projection-level cap below.
    if "verification_level" in result:
        submitted_level = result["verification_level"]
        if finding.origin_agent != "evidence_auditor" or submitted_level not in {"E0", "E1"}:
            result["verification_level"] = "E0"
            reason = reason or "verification_level_outside_merge_E0_E1_allowlist"
    return result, reason


def merge_findings(audits: list[AuditFinding], skeptics: list[SkepticFinding]) -> list[dict[str, Any]]:
    """Deterministic retry-safe union with fail-closed same-key conflict handling.

    Exact payload retries are deduplicated by canonical SHA-256. Different
    payloads under the same identity key remain visible as a sorted conflict;
    they cannot win by arrival order and their projected grade is E0.
    """
    by_key: dict[tuple[str, str, str, str, str], dict[str, tuple[dict[str, Any], str | None]]] = {}
    for finding in [*audits, *skeptics]:
        if not isinstance(finding, (AuditFinding, SkepticFinding)):
            raise ValueError("finding must be AuditFinding or SkepticFinding")
        if finding.origin_agent not in {"evidence_auditor", "skeptic"}:
            raise ValueError("finding origin_agent is not an allowed reviewer")
        if any(not isinstance(value, str) for value in finding_key(finding)):
            raise ValueError("finding identity fields must be strings")
        key = finding_key(finding)
        submitted_sha = _payload_sha256(finding.result)
        safe_result, gate_reason = _safe_result(finding)
        by_key.setdefault(key, {})[submitted_sha] = (safe_result, gate_reason)

    rows: list[dict[str, Any]] = []
    for key, variants in sorted(by_key.items(), key=lambda pair: pair[0]):
        run_id, claim_id, clause_id, origin_agent, attempt_id = key
        ordered = [(sha, variants[sha][0], variants[sha][1]) for sha in sorted(variants)]
        conflict = len(ordered) > 1
        if conflict:
            row_result: dict[str, Any] = {
                "grade": "E0",
                "conflict_requires_review": True,
                "conflict_payload_sha256s": [sha for sha, _, _ in ordered],
            }
            row: dict[str, Any] = {
                "run_id": run_id, "claim_id": claim_id, "source_clause_id": clause_id,
                "origin_agent": origin_agent, "attempt_id": attempt_id,
                "result": row_result,
                "conflicting_payloads": [{"sha256": sha, "result": result} for sha, result, _ in ordered],
                "conflict_requires_review": True,
                "verification_level": "E0",
                "grade_gate_reason": "same_identity_key_conflicting_payloads_require_human_review",
                "review_status": "requires_human_review",
            }
        else:
            sha, row_result, gate_reason = ordered[0]
            # E1 means only provenance checks from this branch. No caller field
            # can assert E2/E3 or human approval through this merge function.
            level = row_result.get("grade", "E0") if origin_agent == "evidence_auditor" else "E0"
            row = {
                "run_id": run_id, "claim_id": claim_id, "source_clause_id": clause_id,
                "origin_agent": origin_agent, "attempt_id": attempt_id,
                "result": row_result, "payload_sha256": sha,
                "conflict_requires_review": False,
                "verification_level": level if level in {"E0", "E1"} else "E0",
                "review_status": "requires_human_review",
            }
            if gate_reason:
                row["grade_gate_reason"] = gate_reason
        rows.append(row)
    return rows


def _merge_node(state: ParallelAuditState) -> dict[str, Any]:
    return {"merged_findings": merge_findings(state["audit_updates"], state["skeptic_updates"])}


def build_parallel_audit_graph():
    """Build a separate experimental graph; no flag is wired into AgentGraph.run."""
    from langgraph.graph import END, START, StateGraph

    builder = StateGraph(ParallelAuditState)
    builder.add_node("evidence_auditor", _audit_branch)
    builder.add_node("skeptic", _skeptic_branch)
    builder.add_node("merge", _merge_node)
    builder.add_edge(START, "evidence_auditor")
    builder.add_edge(START, "skeptic")
    builder.add_edge(["evidence_auditor", "skeptic"], "merge")
    builder.add_edge("merge", END)
    return builder.compile()


def run_parallel_audit(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Run the two read-only review branches from a caller-owned frozen snapshot."""
    required = {"run_id", "attempt_id", "context", "observations", "tool_results", "claims", "clause_index"}
    missing = required - snapshot.keys()
    if missing:
        raise ValueError(f"parallel audit snapshot missing: {sorted(missing)}")
    state: ParallelAuditState = {**snapshot, "audit_updates": [], "skeptic_updates": [], "merged_findings": []}
    return build_parallel_audit_graph().invoke(state)

