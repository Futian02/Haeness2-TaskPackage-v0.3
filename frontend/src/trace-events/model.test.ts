import { describe, expect, it } from "vitest";
import type { ApiEvent } from "../api";
import { groupActivityStages, projectActivity, sanitizePublicText, summarizeActivity } from "./model";

const event = (sequence: number, type: string, payload: Record<string, unknown> = {}, extra: Partial<ApiEvent> = {}): ApiEvent => ({
  run_id: "run-A", sequence, type, agent: "evidence_agent", ts: `2026-10-28T00:00:0${sequence}.000Z`, payload, ...extra,
});

describe("SQLite/SSE activity projection", () => {
  it("deduplicates SSE and replay overlap by run_id + sequence", () => {
    const result = projectActivity([event(2, "agent_started"), event(2, "agent_started"), event(1, "run_started")]);
    expect(result.map((x) => x.sequence)).toEqual([1, 2]);
  });
  it("does not merge events from distinct runs with equal sequence", () => {
    const result = projectActivity([event(1, "run_started"), event(1, "run_started", {}, { run_id: "run-B" })]);
    expect(result).toHaveLength(2);
  });
  it("sorts out-of-order replay to persisted sequence order", () => {
    expect(projectActivity([event(9, "run_completed"), event(2, "agent_started")]).map((x) => x.sequence)).toEqual([2, 9]);
  });
  it("keeps absent phase and iteration as legacy rather than inventing rounds", () => {
    const [step] = projectActivity([event(1, "agent_started")]);
    expect(step.phase).toBe("legacy");
    expect(step.iteration).toBeUndefined();
  });
  it("preserves only explicitly recorded phase and iteration", () => {
    const [step] = projectActivity([event(1, "agent_started", { phase: "auditor", iteration: 2, step_id: "s2", parent_step_id: "root" })]);
    expect(step).toMatchObject({ phase: "auditor", iteration: 2, stepId: "s2", parentStepId: "root" });
  });
  it("maps real tool_called and tool_result into a completed invocation", () => {
    const result = projectActivity([event(1, "tool_called", { tool: "standard_clause_search", args: { keyword: "腐蚀", top_k: 2 } }), event(2, "tool_result", { tool: "standard_clause_search", result: { status: "ok", source: [{ clause_id: "CID-1", clause_no: "5.1", page: 22, verification_level: "E1" }] } })]);
    expect(result[0].tool).toMatchObject({ name: "standard_clause_search", status: "complete", sourceIds: ["CID-1"] });
    expect(result[0].tool?.args).toEqual({ keyword: "已记录（查询条件已脱敏）", top_k: 2 });
  });
  it("marks an unresolved invocation incomplete at terminal error", () => {
    const result = projectActivity([event(1, "tool_called", { tool: "rbi_lookup", args: {} }), event(2, "error")]);
    expect(result[0].tool?.status).toBe("incomplete");
  });
  it("exposes only the model's public wording inside the foldable execution event", () => {
    const result = projectActivity([event(1, "llm_completed", { summary_label: "DeepSeek 表达整理（非思维链）", summary: "已整理可公开的工程结论", hidden_chain: "PRIVATE_MODEL_INTERNAL" })]);
    expect(result[0].publicRationale).toBe("已整理可公开的工程结论");
    expect(result[0].title).toContain("非内部思维链");
    expect(JSON.stringify(result)).not.toContain("PRIVATE_MODEL_INTERNAL");
  });
  it("uses only public_rationale or factual event summary, never arbitrary hidden fields", () => {
    const result = projectActivity([event(1, "decision_summary", { public_rationale: "引用不足，转入复核", hidden_chain: "private reasoning", route: "review", evidence_count: 1 })]);
    expect(result[0].publicRationale).toBe("引用不足，转入复核");
    expect(JSON.stringify(result)).not.toContain("private reasoning");
  });
  it("redacts secrets and sensitive text fields from displayed tool arguments/results", () => {
    const result = projectActivity([event(1, "tool_called", { tool: "standard_clause_search", args: { keyword: "设备", api_key: "SECRET", device_id: "ASSET-44", top_k: 2 } }), event(2, "tool_result", { tool: "standard_clause_search", result: { status: "ok", content_raw: "copyright text", access_token: "TOKEN", source: [{ clause_id: "CID-9" }] } })]);
    expect(JSON.stringify(result)).not.toMatch(/SECRET|ASSET-44|copyright text|TOKEN/);
    expect(result[0].tool?.args).toEqual({ keyword: "已记录（查询条件已脱敏）", top_k: 2 });
  });
  it("keeps citation IDs but removes rich raw tool text", () => {
    const result = projectActivity([
      event(1, "tool_called", { tool: "standard_clause_search", args: { keyword: "wet H2S" } }),
      event(2, "tool_result", { tool: "standard_clause_search", result: { status: "ok", in_domain: true, result: { hits: [{ clause_id: "CID-6.7", title: "湿硫化氢破坏", score: 0.91, snippet: "verbatim source text", description: "full source description" }] }, source: [{ clause_id: "CID-6.7", page: 51 }] } }),
    ]);
    const serialized = JSON.stringify(result[0].tool?.result);
    expect(serialized).toContain("CID-6.7");
    expect(serialized).toContain("湿硫化氢破坏");
    expect(serialized).not.toContain("verbatim source text");
    expect(serialized).not.toContain("full source description");
  });
  it("projects only allowlisted arguments and masks nested operational values", () => {
    const result = projectActivity([event(1, "tool_called", { tool: "rbi_lookup", args: {
      top_k: 6, pressure_mpa: 7.1, material: "X70", nested: { api_key: "nested-secret" },
      file_path: "C:\\private\\ledger.xlsx", prompt: "hidden prompt", custom_blob: "unapproved",
    } })]);
    expect(result[0].tool?.args).toEqual({ top_k: 6, pressure_mpa: "已记录（具体值已脱敏）", material: "已记录（具体值已脱敏）" });
    expect(JSON.stringify(result)).not.toMatch(/nested-secret|ledger|hidden prompt|X70|7\.1/);
  });
  it("scrubs credentials, contact data, equipment identifiers and process values from public wording", () => {
    const safe = sanitizePublicText("access_token=abc123，设备ID: VSL-4409，联系人 a@b.com，壁温 160℃，压力 0.5 MPa");
    expect(safe).not.toMatch(/abc123|VSL-4409|a@b\.com|160℃|0\.5 MPa/);
    expect(safe).toContain("已脱敏");
  });
  it("counts observed calls and human review gates", () => {
    const result = projectActivity([event(1, "tool_called", { tool: "damage_mechanism_query" }), event(2, "requires_human_review", { claim_id: "c-1" })]);
    expect(summarizeActivity(result)).toMatchObject({ stepCount: 2, toolCount: 1, pendingReview: 1, running: true });
  });
  it("ignores malformed events without run id or finite sequence", () => {
    const result = projectActivity([{ ...event(1, "agent_started"), run_id: "", sequence: Number.NaN }]);
    expect(result).toEqual([]);
  });
  it("normalizes additive kind field without requiring event type migration", () => {
    expect(projectActivity([{ run_id: "run-A", sequence: 3, kind: "requires_human_review", payload: { status: "pending" } }])[0].status).toBe("requires-action");
  });
  it("groups recorded phases and iterations, preserving sequence, review, citations and measured duration", () => {
    const events = [
      event(1, "phase_started", { phase: "investigate", iteration: 1 }, { ts: "2026-10-28T00:00:00.000Z" }),
      event(2, "tool_called", { phase: "investigate", iteration: 1, step_id: "tool-a", tool: "clause_search" }, { ts: "2026-10-28T00:00:01.000Z" }),
      event(3, "tool_result", { phase: "investigate", iteration: 1, step_id: "tool-a", tool: "clause_search", duration_ms: 240, result: { source: [{ clause_id: "CID-7", page: 12 }] } }, { ts: "2026-10-28T00:00:01.240Z" }),
      event(4, "claim_checked", { phase: "auditor", iteration: 1, verdict: "supported", sources: [{ clause_id: "CID-7" }] }, { agent: "evidence_auditor", ts: "2026-10-28T00:00:02.000Z" }),
      event(5, "run_completed", {}, { ts: "2026-10-28T00:00:03.000Z" }),
    ];
    const stages = groupActivityStages(projectActivity(events));
    expect(stages).toHaveLength(3);
    expect(stages[0]).toMatchObject({ phase: "investigate", iteration: 1, firstSequence: 1, lastSequence: 3, eventCount: 3, toolCount: 1, tools: ["clause_search"], citationCount: 1, durationMs: 240, durationSource: "reported" });
    expect(stages[1]).toMatchObject({ label: "审核结果", phase: "auditor", reviewCount: 1, citationCount: 1 });
    expect(stages[2]).toMatchObject({ phase: "legacy", label: "任务完成", lastSequence: 5 });
  });
  it("pairs parallel same-name tool results by persisted step_id, independent of return order", () => {
    const projected = projectActivity([
      event(1, "tool_called", { tool: "search", step_id: "first", args: { top_k: 1 } }),
      event(2, "tool_called", { tool: "search", step_id: "second", args: { top_k: 2 } }),
      event(3, "tool_result", { tool: "search", step_id: "second", result: { status: "ok", source: [{ clause_id: "SECOND" }] } }),
      event(4, "tool_result", { tool: "search", step_id: "first", result: { status: "error", source: [{ clause_id: "FIRST" }] } }),
    ]);
    expect(projected[0].tool).toMatchObject({ id: "run-A:1", status: "incomplete", sourceIds: ["FIRST"] });
    expect(projected[1].tool).toMatchObject({ id: "run-A:2", status: "complete", sourceIds: ["SECOND"] });
  });
  it("reports citation count once per unique source and elapsed time from persisted timestamps", () => {
    const projected = projectActivity([
      event(1, "reference_added", { clause_id: "CID-A" }, { ts: "2026-10-28T00:00:00.000Z" }),
      event(2, "claim_checked", { sources: [{ clause_id: "CID-A" }, { clause_id: "CID-B" }] }, { ts: "2026-10-28T00:00:02.500Z" }),
      event(3, "run_completed", {}, { ts: "2026-10-28T00:00:03.000Z" }),
    ]);
    expect(summarizeActivity(projected)).toMatchObject({ citations: 2, elapsedMs: 3000, completed: true });
  });
  it("scales stage grouping to many persisted events without losing or reordering rows", () => {
    const events = Array.from({ length: 240 }, (_, index) => event(index + 1, "agent_started", { phase: index < 120 ? "investigate" : "auditor", iteration: Math.floor(index / 60) + 1 }, { agent: index < 120 ? "evidence_agent" : "evidence_auditor" }));
    const steps = projectActivity(events);
    const stages = groupActivityStages(steps);
    expect(steps).toHaveLength(240);
    expect(stages.reduce((sum, stage) => sum + stage.eventCount, 0)).toBe(240);
    expect(steps.map((step) => step.sequence)).toEqual(Array.from({ length: 240 }, (_, index) => index + 1));
  });
});
