# R9-A Industrial Graph Candidate — Acceptance Record

**Status: `READY_FOR_OWNER_REVIEW`**  
**Execution date:** 2026-10-28 (Asia/Shanghai)  
**Mode:** isolated `RULE_DEMO` candidate only. No production wiring, deployment, commit, or teacher-data mutation.

## 1. Scope and change boundary

Executed as taskbook role **A / isolated graph candidate**. Only these R9-A paths were created or updated:

- `orchestration/r9_industrial_candidate.py`
- `tests/test_r9a_industrial_candidate.py`
- `evals/r9a_cases.jsonl`
- `evals/r9a_graph_comparison.py`
- `evals/r9a_comparison.json`
- `docs/audits/R9A_GRAPH_CANDIDATE_ACCEPTANCE.md`

No edits were made to `backend/`, `frontend/`, `upstream/`, `orchestration/graph.py`, `orchestration/p6_parallel_audit.py`, `tests/test_p7a_merge_consistency.py`, R8 work files, RBI tables, official JSONL, shared state documents, or UI files. The pre-existing parent Git worktree contains extensive unrelated/untracked project files; no add/commit/reset/clean/branch command was run. Baseline reference clones were placed under `%TEMP%\r9a-oss-review`, outside the project.

At the final read-only `git -C upstream status --short --branch` snapshot, upstream showed a modified RBI workbook and an R8 candidate workbook/backup. These were observed only; R9-A did not open, diff, write, move, or validate those workbook contents. The full official validator had passed immediately before that final status check.

The project collaboration protocol names `docs/CONTRACT_LOCK.md`, but that path is absent in the current checkout. The authoritative teacher README, `upstream/04_接口文档/工具接口规范.md`, current state, and executable contract tests were read and used instead. The role-specific `docs/progress/A.md` instruction conflicts with the R9-A whitelist; this acceptance record is the only in-scope progress artifact.

## 2. OSS source review and licensing decision

Shallow source checkouts were read at the following exact refs. No external repository source file was copied into this project; no third-party NOTICE file is required for this change. The candidate uses the already-pinned local LangGraph runtime and reuses this project’s existing `p6_parallel_audit.merge_findings` conflict-safe merge, not a third-party implementation.

| Source | Commit / license | Source and tests inspected | Reuse decision |
|---|---|---|---|
| [Enterprise Agentic RAG Diagnosis / project-a-rag-platform](https://github.com/wyjhfl/project-a-rag-platform) | `28a61fcce40ccfa104b71b4acd0c00205524a8a7`; `git ls-files '*LICENSE*'` returned none. No explicit repository license found in this ref. | `backend/app/rag/diagnosis_agent.py` (security→plan→route→retrieve→risk/escalate graph); `backend/app/rag/agentic.py` (quality score, one rewrite/retry, merge); `backend/tests/test_diagnosis_agent_llm.py`; `backend/tests/test_agentic_diagnosis_api.py`; `docs/agentic_rag_deep_dive.md`. | Behavioral/control-flow study only; no copied code. Adapted the concept of retry-on-low-quality retrieval and risk-floor enforcement into locally authored bounded/fail-closed rules. The candidate does not use their code or their LLM prompts. |
| [Intel Predictive Maintenance Pipeline](https://github.com/intel/predictive-maintenance-pipeline) | `3ec0a9bb3ef49ac8042dfe18804f6bf8f895d1e3`; Apache-2.0 in `LICENSE.md` (third-party program terms remain separate). | `src/agents/graph_builder.py`, `src/agents/meta_agent.py`, `src/agents/utility/state.py`; `tests/test_agent_composition.py`, `tests/test_nway_fusion.py`, `tests/test_oil_gas_chat_routing.py`. | Used the licensed project’s public hub/spoke + parallel branch composition as an architectural reference. No implementation file copied. No OpenVINO, YOLO, video inference or Intel binary dependency imported. |
| [Industrial Maintenance Copilot](https://github.com/ten10do/industrial-maintenance-copilot) | `4e5b79efe09c7ddad5a74d707307c251d16ed1df`; MIT in `LICENSE`. | `apps/api/app/ai/copilot.py`, `apps/api/app/ai/knowledge_search.py`, `apps/api/tests/test_intelligent_maintenance.py`, `apps/api/tests/test_alarm_intelligence.py`, `docs/observability.md`. | Used the licensed project’s source-vs-inference, traceability, deterministic mock, and human-approval boundaries as design references. No code copied. Its PLC is a simulator; none is treated as production-certified. |

The candidate itself implements the merge by calling the in-project P7A/P6 parallel merger. All source/citation outputs remain provisional; successful source membership is capped at E1 and does not establish semantic entailment, applicability, or human sign-off.

## 3. Implemented candidate

`orchestration/r9_industrial_candidate.py` builds a separate LangGraph StateGraph:

```text
START → route → investigator ↔ evidence_gate
                         ├─ missing field / exhausted / unresolved → report → END
                         └─ review_dispatch → auditor ∥ skeptic → merge → review_gate
                                                                     ├─ bounded targeted recheck → investigator
                                                                     └─ report → END
```

- The tool registry is validated to contain **exactly** `damage_mechanism_query`, `rbi_lookup`, and `standard_clause_search`; the production graph/import path is untouched.
- Standard-clause requests route before material checks and can search without material. Diagnosis uses the frozen tools, optional deterministic query rewrite, per-call retry (two attempts), tool budget (≤8 calls), investigation budget (≤3 iterations), and review correction budget (≤2 retries).
- Calls are keyed by canonical tool+args+context hash; evidence gain is keyed by tool+source IDs+result hash. Repeated identical query/evidence therefore stops instead of spinning.
- Missing measured `wall_thinning` blocks review and returns an E0 insufficient-evidence report. Tool/RBI/reviewer risk labels never populate final device risk; `risk_level` remains null and `human_signed` false.
- Auditor and Skeptic are distinct read-only fanout branches over the same graph snapshot. Auditor compares returned source IDs and bibliographic metadata to canonical records. Skeptic reads raw field evidence and source records, not Investigator prose. Merge delegates to the existing deterministic conflict-safe merger; conflicting same-key payloads remain visible, conflict grade is E0.
- Graph events carry `phase`, `iteration`, `step_id`, `parent_step_id`, `public_rationale`, `retry_reason`, `source_ids`, `duration_ms`; this is an isolated trace proposal, not an SSE/backend contract change.
- Mode is fixed to `RULE_DEMO`; no real model provider is called or claimed. There is no device control operation.

## 4. R9-A test outcomes

Targeted command:

```powershell
.\.venv-langgraph\Scripts\python.exe -B -m unittest tests.test_r9a_industrial_candidate -q
```

Observed: **16 tests, 16 PASS** (1.653 s on final targeted run). Coverage includes:

1. exact three-tool registry; standard lookup with no material;
2. missing material/medium stops without tools;
3. low-quality retrieval rewrite/retry with new traceable source;
4. zero-information-gain stop;
5. missing wall-thickness gate;
6. sufficient evidence dispatches both reviewers;
7. barrier-based proof that Auditor and Skeptic overlap in parallel fanout;
8. conflicting review payloads retained and clamped E0;
9. wrong page rejected by bibliographic comparison;
10. injected E3/risk claim stays E0 and final risk remains null;
11. teacher RBI `L5` output does not become final equipment risk;
12. review correction stops after two retries;
13. transient tool exception retries and records attempts;
14. permanent tool exception produces unresolved output, not a graph crash;
15. tool-call budget exhaustion;
16. repeat run with same run key preserves deterministic tool-call keys and cannot sign.

Representative recorded state transitions from `evals/r9a_comparison.json`:

```text
standard_lookup_no_material:
route(standard_lookup) → investigate[1] → standard_clause_search → evidence_gate(report) → final
candidate: 1 tool call, 5 citations, E1 provenance, risk=null, human_signed=false

missing_wall_thickness:
route(diagnosis) → investigate[1] → damage_mechanism_query → standard_clause_search
→ evidence_gate(ask_user: field_measurement_required) → final(insufficient_evidence, E0)

measured_field_review:
route(diagnosis) → investigate[1] → two teacher tools → evidence_gate(review)
→ review_started → auditor ∥ skeptic → review_result → review_gate(report) → final
candidate: 2 tool calls, 5 citations, E1 provenance, risk=null, human_signed=false
```

No UI screenshot was produced: R9-A creates no UI route and the task boundary forbids frontend changes. The acceptance evidence is the actual LangGraph execution trace in `evals/r9a_comparison.json` plus the fanout barrier test, not a fabricated UI image.

The comparison file records same-input calls to the frozen existing R1 seven-role path and R9-A candidate. For this one-shot RULE_DEMO probe, candidate latency was **5.358–15.689 ms, median 6.443 ms** across three cases. Baseline values are recorded per case in the JSON. The first run is cold-start affected, samples are N=1/case, candidate and baseline do not have fully equivalent route semantics (R1 asks for material before standard lookup; R9 intentionally fixes that), and the three synthetic cases are **not gold data**. These numbers are trace evidence only; they do not establish a quality or performance win.

## 5. Required regression and official contract checks

Executed against the isolated pinned environment:

```text
python -B upstream/04_接口文档/validate.py --final
  PASS: 554/554 clauses; 200/200 trajectories; multi_step=144;
        exclusion=15, insufficient_info=15, out_of_domain=15.

python -B -m unittest discover -s tests -q
  122 tests run; 121 passed; 1 failed.
  Existing unrelated failure:
    tests.test_p6a_parallel_evidence.P6AParallelEvidenceTests
    .test_merge_deduplicates_retry_but_preserves_distinct_attempts
    expected merged[0]['verification_level'] == 'E1'; actual 'E0'.
```

The R9-A targeted suite passes. The failing P6A assertion is outside the R9-A file whitelist and was not edited or masked. This full-suite failure blocks a repository-wide PASS; it needs separate Owner triage. The official teacher validator is green and the teacher tool registry/signatures/schema/data were not changed.

## 6. Acceptance decision / remaining review

**Decision: `READY_FOR_OWNER_REVIEW` for the isolated candidate only.** R9-A has a bounded loop, a tested parallel fanout/fanin, evidence gates, conservative risk handling, retry and exception handling, source metadata checks, and same-snapshot smoke traces. It is not a replacement for the existing graph and has not been integrated, deployed, or promoted to production.

Owner review items:

1. Decide whether to address the independent P6A legacy merger test/assertion mismatch in a separate task.
2. Review whether the `wall_thinning` presence gate is the desired minimum for every diagnosis type; this candidate currently uses the strict conservative rule.
3. Replace the small synthetic comparison with a frozen, owner-reviewed gold set before drawing quality/latency conclusions. Do not interpret E1 as expert confirmation.
4. Decide separately whether the candidate should be wired into a product API. No such wiring occurred in R9-A.

Rollback is a path-scoped revert/removal of the six R9-A artifacts listed in §1 only; do not reset or clean the parent repository, and do not touch R8 or upstream files.
