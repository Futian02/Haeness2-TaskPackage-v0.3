"""Owner P6 adversarial checks. Read-only, synthetic, no human-review records created.
Command: ./.venv-langgraph/Scripts/python.exe -B -m evals.owner_p6_adversarial_probe
"""
from __future__ import annotations
from copy import deepcopy
from jsonschema import Draft202012Validator, FormatChecker
import json
from pathlib import Path

from orchestration.p6_parallel_audit import AuditFinding, SkepticFinding, merge_findings
from evals.p6c_validate_review import validate_record

def probe_duplicate_conflict():
    a = AuditFinding("r", "claim", "std-1", "evidence_auditor", "attempt-1", {"grade": "E1", "checks": [{"status":"matched"}]})
    b = AuditFinding("r", "claim", "std-1", "evidence_auditor", "attempt-1", {"grade": "E0", "checks": [{"status":"missing"}]})
    s = SkepticFinding("r", "claim", "std-1", "skeptic", "attempt-1", {"verdict":"unresolved"})
    first = merge_findings([a,b], [s])
    reverse = merge_findings([b,a], [s])
    x = next(x for x in first if x["origin_agent"]=="evidence_auditor")
    y = next(x for x in reverse if x["origin_agent"]=="evidence_auditor")
    print("DUPLICATE_SAME_KEY_FIRST_WRITE_WINS",x["verification_level"],y["verification_level"],
          "order_invariant=",first==reverse)
    assert x["verification_level"]=="E1" and y["verification_level"]=="E0"
    return first != reverse

def probe_untrusted_grade_not_clamped():
    finding=AuditFinding("r", "c", "s", "evidence_auditor", "a1", {"grade":"E3"})
    result=merge_findings([finding],[])
    print("EXTERNAL_GRADE_E3_ACCEPTED",result[0]["verification_level"])
    assert result[0]["verification_level"]=="E3"
    return True

def probe_schema_role_invariant():
    root = Path(__file__).resolve().parent
    schema=json.loads((root/"p6c_review_schema.json").read_text(encoding="utf-8"))
    record={
        "record_type":"extraction_attestation",
        "attestation_id":"TEST_ROLE_MISMATCH",
        "reviewer":{"reviewer_identity_verified":False,"reviewer_role":"standard_extractor",
                    "reviewer_signature_ref":None,"reviewer_identity_ref":None},
        "source_sha":"1"*64,"source_clause_id":"SYNTH-1","pdf_printed_page":1,"quote_sha":"2"*64,
        "attestation_role":"independent_reviewer","attested_at":None,"status":"draft"
    }
    jsonschema_errors=list(Draft202012Validator(schema,format_checker=FormatChecker()).iter_errors(record))
    local_errors=validate_record(record)
    print("ROLE_MISMATCH", "schema_errors=",len(jsonschema_errors),
          "stdlib_errors=",local_errors)
    assert not jsonschema_errors and local_errors
    return bool(local_errors) and not jsonschema_errors

def probe_signature_reference_is_only_shape():
    from evals.p6c_test_review_schema import draft_expert_record
    record=deepcopy(draft_expert_record())
    record["reviewer"]["reviewer_identity_verified"]=True
    record["reviewer"]["reviewer_signature_ref"]="TEST_ONLY_not_a_real_signature"
    record["status"]="verified"
    record["verdict"]="supported"
    record["reviewed_at"]="2026-10-28T15:00:00+08:00"
    issues=validate_record(record,require_verified=True)
    print("SYNTHETIC_FALSE_ATTESTATION_SHAPE", "issues=",issues,
          "NOTE=shape-only not authentication, never ingest as gold")
    assert issues==[]
    return True

if __name__=="__main__":
    results=[probe_duplicate_conflict(),probe_untrusted_grade_not_clamped(),probe_schema_role_invariant(),probe_signature_reference_is_only_shape()]
    assert all(results)
    print("OWNER_P6_ADVERSARIAL_FINDINGS_REPRODUCED; this is not a production acceptance test")
