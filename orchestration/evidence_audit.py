"""Deterministic, evidence-first audit helpers for RULE_DEMO.

Membership/version/condition checks establish provenance only. They do not
decide whether standard text entails an engineering conclusion (E2) or applies
to a real item of equipment (E3).
"""
from __future__ import annotations

import json
import hashlib
import re
from pathlib import Path
from typing import Any

from orchestration.semantics import Claim


CLAUSE_PATH = Path(__file__).resolve().parents[1] / "upstream" / "05_提交区" / "clauses.jsonl"


def load_clause_index(path: Path = CLAUSE_PATH) -> dict[str, dict[str, Any]]:
    if not path.is_file():
        return {}
    result: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                row = json.loads(line)
                cid = row.get("clause_id")
                if isinstance(cid, str):
                    result[cid] = row
    return result


def canonical_record_sha256(record: dict[str, Any]) -> str:
    """Stable digest of a trusted canonical record, not a digest of a paraphrase."""
    payload = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _metadata_status(returned: dict[str, Any], canonical: dict[str, Any], key: str) -> tuple[str, Any, Any]:
    if key not in returned:
        return "missing", None, canonical.get(key)
    actual, expected = returned.get(key), canonical.get(key)
    if actual is None or actual == "":
        return "unknown", actual, expected
    if expected is None or expected == "":
        return "unknown", actual, expected
    return ("matched" if str(actual) == str(expected) else "mismatch"), actual, expected


def _observation_values(observations: list[dict[str, Any]]) -> dict[str, Any]:
    return {str(item.get("field")): item for item in observations}


def _condition_checks(clause: dict[str, Any], context: dict[str, Any], observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    conditions = clause.get("applicable_conditions") or {}
    obs = _observation_values(observations)
    checks: list[dict[str, Any]] = []

    for field in ("material", "medium", "equipment_type"):
        allowed = conditions.get(field) or []
        actual = context.get(field)
        if not allowed:
            checks.append({"check": f"condition:{field}", "status": "not_specified"})
            continue
        actuals = actual if isinstance(actual, list) else ([actual] if actual not in (None, "", []) else [])
        if not actuals:
            checks.append({"check": f"condition:{field}", "status": "unknown"})
        elif all(value in allowed for value in actuals):
            checks.append({"check": f"condition:{field}", "status": "matched"})
        elif any(value in allowed for value in actuals):
            checks.append({"check": f"condition:{field}", "status": "not_sufficient", "observed": actuals, "allowed": allowed,
                           "reason": "mixed values include both in-scope and out-of-scope/ambiguous items"})
        else:
            checks.append({"check": f"condition:{field}", "status": "mismatch", "observed": actuals, "allowed": allowed})

    for field, key in (("temperature", "temperature_c"), ("pressure", "pressure_mpa")):
        bounds = conditions.get(key)
        if not isinstance(bounds, list) or len(bounds) != 2 or bounds == [None, None]:
            checks.append({"check": f"condition:{field}", "status": "not_specified"})
            continue
        item = obs.get(field)
        value = item.get("normalized_value") if item and item.get("observation_state") != "unknown" else None
        if not isinstance(value, (int, float)):
            checks.append({"check": f"condition:{field}", "status": "unknown"})
        elif ((bounds[0] is not None and value < bounds[0]) or
              (bounds[1] is not None and value > bounds[1])):
            checks.append({"check": f"condition:{field}", "status": "mismatch", "observed": value, "bounds": bounds})
        else:
            checks.append({"check": f"condition:{field}", "status": "matched"})
    return checks


def audit_claim(claim_data: dict[str, Any], state: Any,
                clause_index: dict[str, dict[str, Any]] | None = None) -> Claim:
    """Verify exact clause membership, this-run provenance, metadata and explicit applicability.

    Successful checks are capped at E1. Semantic support and equipment-specific
    applicability remain unresolved pending independent review.
    """
    index = clause_index if clause_index is not None else load_clause_index()
    current_sources = {
        str(source.get("clause_id")): source
        for call in state.tool_results
        for source in ((call.get("result") or {}).get("source") or [])
        if call.get("tool") == "standard_clause_search"
        if isinstance(source, dict) and source.get("clause_id")
    }
    claim = Claim.model_validate(claim_data)
    checks: list[dict[str, Any]] = []
    all_membership = bool(claim.source_clause_ids)
    required_metadata = ("standard_code", "clause_no", "page")
    canonical_evidence: list[dict[str, Any]] = []

    for cid in claim.source_clause_ids:
        canonical = index.get(cid)
        returned = current_sources.get(cid)
        if canonical is None:
            checks.append({"clause_id": cid, "check": "official_membership", "status": "missing"})
            all_membership = False
            continue
        checks.append({"clause_id": cid, "check": "official_membership", "status": "matched"})
        if returned is None:
            checks.append({"clause_id": cid, "check": "current_run_source", "status": "missing"})
            all_membership = False
            continue
        checks.append({"clause_id": cid, "check": "current_run_source", "status": "matched"})
        metadata_ok = True
        for key in required_metadata:
            status, actual, expected = _metadata_status(returned, canonical, key)
            checks.append({"clause_id": cid, "check": f"metadata:{key}", "status": status,
                           "returned": actual, "canonical": expected})
            if status != "matched":
                all_membership = False
                metadata_ok = False
        if "version" in returned:
            status, actual, expected = _metadata_status(returned, canonical, "version")
            checks.append({"clause_id": cid, "check": "metadata:version", "status": status,
                           "returned": actual, "canonical": expected})
            if status != "matched":
                all_membership = False
        raw = canonical.get("content_raw")
        if not isinstance(raw, str) or not raw.strip():
            checks.append({"clause_id": cid, "check": "canonical_content", "status": "missing"})
            all_membership = False
        else:
            checks.append({"clause_id": cid, "check": "canonical_content", "status": "matched"})
            version_status = "matched" if canonical.get("version") else "unknown"
            checks.append({"clause_id": cid, "check": "canonical_version", "status": version_status, "version": canonical.get("version")})
            canonical_evidence.append({
                "clause_id": cid, "canonical_record_sha256": canonical_record_sha256(canonical),
                "printed_page": canonical.get("page"), "canonical_version": canonical.get("version"),
                "tool_source": {key: returned.get(key) for key in ("clause_id", *required_metadata)},
                "content_raw": raw,
            })
        condition_checks = _condition_checks(canonical, state.context, state.observations)
        checks.extend({"clause_id": cid, **item} for item in condition_checks)

    claim.checks = checks
    # A deterministic condition mismatch is a review signal, not a final
    # semantic contradiction verdict. P3B keeps every new claim unresolved
    # until an independent human review records a supported/contradicted state.
    claim.verdict = "unresolved"
    claim.review_status = "requires_human_review"
    # E1 is provenance only. A risk-level claim needs independent reviewed
    # likelihood/consequence evidence, which this deterministic verifier lacks.
    if claim.kind == "risk_level":
        all_membership = False
        checks.append({"check": "risk_claim_gate", "status": "missing",
                       "reason": "RBI lookup labels alone do not establish equipment likelihood/consequence or risk level"})
    claim.grade = "E1" if all_membership else "E0"
    claim.provenance_status = "verified" if all_membership else ("partial" if claim.source_clause_ids else "failed")
    claim.canonical_evidence = canonical_evidence
    claim.independent_validation = None
    return claim


def audit_reference(ref: dict[str, Any], state: Any,
                    index: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    """Add provenance fields to a citation without changing the teacher payload."""
    index = index if index is not None else load_clause_index()
    cid = str(ref.get("clause_id", ""))
    canonical = index.get(cid)
    source = next((item for call in state.tool_results if call.get("tool") == "standard_clause_search"
                   for item in ((call.get("result") or {}).get("source") or [])
                   if isinstance(item, dict) and str(item.get("clause_id")) == cid), None)
    result = dict(ref)
    checks = []
    if canonical is None:
        checks.append({"check": "official_membership", "status": "missing"})
    else:
        checks.append({"check": "official_membership", "status": "matched"})
    if source is None:
        checks.append({"check": "current_run_source", "status": "missing"})
    else:
        checks.append({"check": "current_run_source", "status": "matched"})
        for key in ("standard_code", "clause_no", "page"):
            status, actual, expected = _metadata_status(source, canonical or {}, key)
            checks.append({"check": f"metadata:{key}", "status": status, "returned": actual, "canonical": expected})
        if "version" in source:
            status, actual, expected = _metadata_status(source, canonical or {}, "version")
            checks.append({"check": "metadata:version", "status": status, "returned": actual, "canonical": expected})
    raw = canonical.get("content_raw") if canonical else None
    if not isinstance(raw, str) or not raw.strip():
        checks.append({"check": "canonical_content", "status": "missing"})
    else:
        checks.append({"check": "canonical_content", "status": "matched"})
    valid = bool(canonical and source and raw and all(item["status"] == "matched" for item in checks if item["check"].startswith("metadata:")))
    result.update({
        "verification_level": "E1" if valid else "E0",
        "provenance_status": "verified" if valid else "partial",
        "review_status": "requires_human_review",
        "provenance_checks": checks,
    })
    if canonical and raw:
        result["canonical_evidence"] = {
            "clause_id": cid, "canonical_record_sha256": canonical_record_sha256(canonical),
            "printed_page": canonical.get("page"), "canonical_version": canonical.get("version"),
            "content_raw": raw, "tool_source": {key: source.get(key) for key in ("clause_id", "standard_code", "clause_no", "page")} if source else None,
        }
    return result


_TERM_RE = re.compile(r"[A-Za-z0-9]+|[\u4e00-\u9fff]{2,}")


def independent_retrieve(observations: list[dict[str, Any]], context: dict[str, Any],
                         index: dict[str, dict[str, Any]], limit: int = 12) -> list[dict[str, Any]]:
    """Lexical second-pass search from observations/context only; never semantic proof."""
    raw = " ".join([str(item.get("raw_span", "")) for item in observations] +
                   [str(context.get(k, "")) for k in ("material", "medium", "equipment_type", "operating_condition")])
    terms = {term.lower() for term in _TERM_RE.findall(raw) if len(term) > 1}
    scored = []
    for cid, row in index.items():
        text = " ".join(str(row.get(k, "")) for k in ("title", "content_raw", "mechanism_detail", "rbi_detail"))
        normalized = text.lower()
        hits = sorted(term for term in terms if term in normalized)
        if hits:
            scored.append({"clause_id": cid, "score": len(hits), "matched_terms": hits,
                           "applicable_conditions": row.get("applicable_conditions") or {},
                           "printed_page": row.get("page"), "canonical_record_sha256": canonical_record_sha256(row)})
    scored.sort(key=lambda item: (-item["score"], item["clause_id"]))
    return scored[:limit]


def skeptic_findings(state: Any, clause_index: dict[str, dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Run a separate observation/source pass without using the diagnosis prose as evidence."""
    observations = state.observations
    fields = {str(item.get("field")): item for item in observations}
    known = {name for name, item in fields.items() if item.get("observation_state") not in {"unknown", None}}
    raw_sources = {
        str(source.get("clause_id")): source
        for call in state.tool_results
        if call.get("tool") == "standard_clause_search"
        for source in ((call.get("result") or {}).get("source") or [])
        if isinstance(source, dict) and source.get("clause_id")
    }
    source_ids = set(raw_sources)
    findings: list[dict[str, Any]] = []
    index = clause_index if clause_index is not None else load_clause_index()
    second_pass = independent_retrieve(observations, state.context, index)
    for claim in state.claims:
        # This independent checklist reads raw observations and tool-result sources;
        # the claim text is merely the item being compared, never an evidence source.
        matched_sources = [raw_sources[cid] for cid in claim.get("source_clause_ids", []) if cid in raw_sources]
        source_recheck = []
        for source in matched_sources:
            canonical = index.get(str(source.get("clause_id")), {})
            quote = str(canonical.get("content_raw") or "")
            source_recheck.append({
                "clause_id": source.get("clause_id"),
                "title": canonical.get("title"),
                "quote_present": bool(quote),
                "quote_length": len(quote),
                "quote_sha256": hashlib.sha256(quote.encode("utf-8")).hexdigest() if quote else None,
                "canonical_record_sha256": canonical_record_sha256(canonical) if canonical else None,
                "printed_page": canonical.get("page"),
                "tool_source": {key: source.get(key) for key in ("clause_id", "standard_code", "clause_no", "page")},
                "semantic_entailment": "not_machine_verified",
                "equipment_applicability": "not_machine_verified",
            })
        corroborating_observations = [f"obs-{name}" for name in sorted(known)]
        reasons: list[str] = []
        if not set(claim.get("source_clause_ids", [])) & source_ids:
            reasons.append("声明引用未在本轮原始工具source中出现")
        if not matched_sources or any(not str(index.get(str(source.get("clause_id")), {}).get("content_raw") or "") for source in matched_sources):
            reasons.append("trusted canonical clauses.jsonl缺少可檢查原文/版本；来源降为E0并需人工复核")
        else:
            reasons.append("Skeptic已通过本轮tool source定位可信canonical原文；规则程序未验证语义蕴含或设备适用性")
        if second_pass:
            cited = set(claim.get("source_clause_ids", []))
            alternatives = [item for item in second_pass if item["clause_id"] not in cited][:8]
            if alternatives:
                reasons.append("独立词法检索发现待核对的替代/漏检条款：" + ",".join(x["clause_id"] for x in alternatives))
        if "wall_thinning" not in fields or fields["wall_thinning"].get("observation_state") == "unknown":
            reasons.append("没有有效测厚证据；unknown不能作为无减薄或有减薄")
        missing_process = [field for field in ("temperature", "pressure", "service_years")
                           if field not in fields or fields[field].get("observation_state") == "unknown"]
        if missing_process:
            reasons.append("现场工况字段缺失/unknown：" + ",".join(missing_process))
        # Even a matching standard source does not independently establish an
        # equipment condition, and this RULE_DEMO has no semantic entailment model.
        if not reasons:
            reasons.append("标准来源与原始观测尚未形成独立的设备级蕴含证明")
        findings.append({
            "disagreement_id": f"{claim['claim_id']}-skeptic",
            "claim_id": claim["claim_id"],
            "kind": "independent_evidence_gap",
            "verdict": "unresolved",
            "basis_observation_ids": corroborating_observations,
            "basis_source_clause_ids": sorted(set(claim.get("source_clause_ids", [])) & source_ids),
            "source_recheck": source_recheck,
            "independent_retrieval": second_pass,
            "review_scope": "lexical_only_no_semantic_entailment",
            "finding": "；".join(reasons),
            "review_status": "requires_human_review",
        })
    return findings
