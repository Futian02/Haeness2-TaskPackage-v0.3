"""Offline-only S2.6 corpus/schema/policy audit; results are never counted as model success."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from orchestration.agentic_v2 import AgenticV2Candidate, TEACHER_TOOLS
from orchestration.agentic_contracts import PlanProposal


def main() -> int:
    cases_path = ROOT / "evals" / "s26" / "synthetic_cases.jsonl"
    rows = [json.loads(x) for x in cases_path.read_text(encoding="utf-8").splitlines() if x.strip()]
    errors = []
    if len(rows) < 100:
        errors.append(f"corpus has only {len(rows)} cases")
    ids = [r["case_id"] for r in rows]
    if len(set(ids)) != len(ids):
        errors.append("duplicate case_id")
    if any(hashlib.sha256(r["question"].encode()).hexdigest() != r["prompt_sha256"] for r in rows):
        errors.append("prompt hash mismatch")
    enum_path = ROOT / "upstream" / "04_接口文档" / "enums.json"
    enum = json.loads(enum_path.read_text(encoding="utf-8"))
    materials = list(enum.get("material", {}))
    media = list(enum.get("medium", {}))
    if not materials or not media:
        errors.append("teacher enum fixture unavailable")
        return 2
    inert = lambda **kwargs: {"status": "not_called"}
    candidate = AgenticV2Candidate(
        tool_registry={name: inert for name in TEACHER_TOOLS}, clause_index={},
        enum_sets={k: set(enum.get(k, {})) for k in ("material", "medium", "equipment_type")},
    )

    def policy(action: str, tool: str, query: str = "", arguments=None, facts=None):
        p = PlanProposal(action=action, tool_name=tool, query=query, tool_arguments=arguments or {},
                         investigation_goal="offline schema-policy fixture", evidence_gap="synthetic",
                         public_rationale="offline audit fixture").model_dump(mode="json")
        state = {"plan": p, "facts": facts or {}, "iteration": 0, "tool_attempts": 0,
                 "errors": [], "run_id": "s26-offline", "thread_id": "synthetic"}
        return candidate._policy(state)

    checks = []
    checks.append(("native_schema_valid", PlanProposal.model_validate({"action": "call_tool", "tool_name": "standard_clause_search", "query": "氯化铵", "tool_arguments": {"keyword": "氯化铵", "top_k": 5, "knowledge_type": "damage_mechanism"}, "investigation_goal": "检索", "evidence_gap": "来源", "public_rationale": "核对条款", "focus_clause_ids": []}) is not None))
    checks.append(("exactly_three_tools", set(TEACHER_TOOLS) == {"damage_mechanism_query", "rbi_lookup", "standard_clause_search"}))
    good_search = policy("call_tool", "standard_clause_search", "氯化铵", {"keyword": "氯化铵", "top_k": 5, "knowledge_type": "damage_mechanism"})
    checks.append(("valid_standard_tool_args_accepted", good_search.get("policy_decision") == "execute_tool"))
    mismatch = policy("call_tool", "standard_clause_search", "氯化铵", {"keyword": "盐酸", "top_k": 5, "knowledge_type": "damage_mechanism"})
    checks.append(("query_keyword_mismatch_rejected", mismatch.get("policy_decision") == "review" and mismatch.get("finish_reason") == "policy_rejected"))
    fourth = policy("call_tool", "execute_unsafe_command", "x", {"x": "y"})
    checks.append(("fourth_tool_rejected", fourth.get("policy_decision") == "review"))
    missing_dm = policy("call_tool", "damage_mechanism_query", "裂纹", {"material": materials[0], "medium": [media[0]]}, {})
    checks.append(("dm_without_explicit_facts_rerouted_to_search", missing_dm.get("policy_decision") == "execute_tool" and missing_dm.get("plan", {}).get("tool_name") == "standard_clause_search"))
    valid_dm_facts = {"material": materials[0], "medium": [media[0]]}
    valid_dm = policy("call_tool", "damage_mechanism_query", "", {"material": materials[0], "medium": [media[0]]}, valid_dm_facts)
    checks.append(("dm_schema_and_explicit_facts_accepted", valid_dm.get("policy_decision") == "execute_tool"))
    no_rbi = policy("call_tool", "rbi_lookup", "risk", {"equipment_type": "压力容器", "material": materials[0]}, {})
    checks.append(("rbi_missing_material_rerouted_not_graded", no_rbi.get("policy_decision") == "execute_tool" and no_rbi.get("plan", {}).get("tool_name") == "standard_clause_search"))

    categories = {}
    for row in rows:
        categories[row["gold_route"]] = categories.get(row["gold_route"], 0) + 1
    result = {
        "mode": "offline_mock_and_deterministic_policy_only",
        "real_model_requests": 0,
        "mock_success_counted_as_native": 0,
        "case_count": len(rows),
        "corpus_sha256": hashlib.sha256(cases_path.read_bytes()).hexdigest(),
        "label_status": "developer_curated_provisional_not_independent_expert_gold",
        "category_counts": categories,
        "policy_checks": [{"name": n, "pass": bool(ok)} for n, ok in checks],
        "errors": errors + [name for name, ok in checks if not ok],
        "status": "PASS" if not errors and all(ok for _, ok in checks) else "FAIL",
    }
    out = ROOT / "evals" / "s26" / "offline_audit.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "case_count": len(rows), "policy_checks_passed": sum(ok for _, ok in checks), "policy_checks_total": len(checks), "real_model_requests": 0, "artifact": str(out)}, ensure_ascii=False))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
