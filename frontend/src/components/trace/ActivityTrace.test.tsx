import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import type { ApiEvent } from "../../api";
import { ActivityTrace } from "./ActivityTrace";

const e = (run_id: string, sequence: number, type: string, payload: Record<string, unknown> = {}, agent = "evidence_agent"): ApiEvent => ({ run_id, sequence, type, payload, agent, ts: "2026-10-28T00:00:00.000Z" });
const runEvents = (runId = "run-1"): ApiEvent[] => [
  e(runId, 1, "decision_summary", { route: "mechanism_analysis", evidence_count: 2, candidate_count: 1 }),
  e(runId, 2, "reference_added", { clause_id: "GB-CID-12", clause_no: "4.2", page: 18, verification_level: "E1" }),
];
const openTrace = (element = screen.getByTestId("execution-summary")) => fireEvent.click(element.querySelector("summary")!);

afterEach(cleanup);
beforeEach(() => localStorage.clear());

describe("R9-B activity UI", () => {
  it("starts collapsed and labels the disclosure as an execution record", () => {
    render(<ActivityTrace runId="run-1" events={runEvents()} />);
    const details = screen.getByTestId("execution-summary");
    expect(details).not.toHaveAttribute("open");
    expect(details.querySelector("summary")).toHaveTextContent("执行中");
  });
  it("expands only after an explicit disclosure action", () => {
    render(<ActivityTrace runId="run-1" events={runEvents()} />);
    const details = screen.getByTestId("execution-summary");
    openTrace(details);
    expect(details).toHaveAttribute("open");
    expect(details).toHaveTextContent("路由：mechanism_analysis");
    expect(details).toHaveTextContent("GB-CID-12");
  });
  it("persists expansion across an event refresh for the same run", () => {
    const view = render(<ActivityTrace runId="run-1" events={runEvents()} />);
    const details = screen.getByTestId("execution-summary");
    openTrace(details);
    expect(localStorage.getItem("r9b:trace:expanded:run-1")).toBe("true");
    view.rerender(<ActivityTrace runId="run-1" events={[...runEvents(), e("run-1", 3, "agent_completed", { status: "completed" })]} />);
    expect(screen.getByTestId("execution-summary")).toHaveAttribute("open");
  });
  it("isolates collapse state when switching to another run", () => {
    const view = render(<ActivityTrace runId="run-1" events={runEvents("run-1")} />);
    openTrace();
    view.rerender(<ActivityTrace runId="run-2" events={runEvents("run-2")} />);
    expect(screen.getByTestId("execution-summary")).not.toHaveAttribute("open");
  });
  it("renders no hidden raw reasoning or tool input", () => {
    const events = [e("run-1", 1, "decision_summary", { route: "review", public_rationale: "引用元数据不足，保持 E0", hidden_chain: "not for UI" }), e("run-1", 2, "tool_called", { tool: "standard_clause_search", args: { keyword: "sensitive input", api_key: "SECRET" } })];
    render(<ActivityTrace runId="run-1" events={events} />);
    openTrace();
    expect(screen.getByTestId("execution-summary")).toHaveTextContent("引用元数据不足，保持 E0");
    expect(screen.getByTestId("execution-summary")).not.toHaveTextContent("not for UI");
    expect(screen.getByTestId("execution-summary")).not.toHaveTextContent("SECRET");
    expect(screen.getByTestId("execution-summary")).not.toHaveTextContent("sensitive input");
  });
  it("shows only events from the selected run", () => {
    render(<ActivityTrace runId="run-1" events={[...runEvents("run-1"), e("run-2", 3, "decision_summary", { public_rationale: "wrong run" })]} />);
    openTrace();
    expect(screen.getByTestId("execution-summary")).not.toHaveTextContent("wrong run");
  });
  it("keeps public decision summary separate from assistant final answer", () => {
    render(<ActivityTrace runId="run-1" events={runEvents()} finalText="RULE_DEMO 的设备研判结果" />);
    openTrace();
    expect(screen.getByText("RULE_DEMO 的设备研判结果")).toBeInTheDocument();
    expect(screen.getByText("执行摘要")).toBeInTheDocument();
  });
  it("shows only persisted tool calls through the official tool fallback", () => {
    const events = [
      e("run-1", 1, "tool_called", { tool: "standard_clause_search", tool_call_id: "call-1", args: { keyword: "wet H2S", api_key: "SECRET" } }),
      e("run-1", 2, "tool_result", { tool: "standard_clause_search", result: { status: "ok", source: [{ clause_id: "CID-6.7", page: 51 }], document_text: "private raw source" } }),
    ];
    render(<ActivityTrace runId="run-1" events={events} />);
    openTrace();
    fireEvent.click(screen.getByRole("button", { name: /1 次工具调用/ }));
    const toolButton = screen.getByRole("button", { name: /standard_clause_search/ });
    expect(toolButton).toHaveTextContent("standard_clause_search");
    fireEvent.click(toolButton);
    expect(screen.getByTestId("execution-summary")).not.toHaveTextContent("SECRET");
    expect(screen.getByTestId("execution-summary")).not.toHaveTextContent("private raw source");
  });
  it("shows a safe per-tool projection and source references after the nested disclosure is opened", () => {
    const events = [
      e("run-1", 1, "tool_called", { tool: "rbi_lookup", tool_call_id: "call-safe", args: {
        standard_code: "GB/T 26610.1", top_k: 4, medium: "H2S", temperature_c: 160,
        prompt: "PRIVATE_PROMPT", file_path: "C:\\private\\device.xlsx", nested: { api_key: "PRIVATE_KEY" },
      } }),
      e("run-1", 2, "tool_result", { tool: "rbi_lookup", result: {
        status: "ok", source: [{ clause_id: "CID-6.7", clause_no: "5.2.3", page: 41, verification_level: "E1" }],
        content_raw: "PRIVATE_STANDARD_QUOTE", device_serial: "PRIVATE_SERIAL",
      } }),
    ];
    render(<ActivityTrace runId="run-1" events={events} />);
    const outer = screen.getByTestId("execution-summary");
    expect(outer).not.toHaveAttribute("open");
    openTrace(outer);
    fireEvent.click(screen.getByRole("button", { name: /1 次工具调用/ }));
    fireEvent.click(screen.getByRole("button", { name: /rbi_lookup/ }));
    expect(outer).toHaveTextContent("GB/T 26610.1");
    expect(outer).toHaveTextContent("具体值已脱敏");
    expect(outer).toHaveTextContent("CID-6.7");
    expect(outer).toHaveTextContent("5.2.3");
    expect(outer).not.toHaveTextContent(/PRIVATE_PROMPT|PRIVATE_KEY|device\.xlsx|160|PRIVATE_STANDARD_QUOTE|PRIVATE_SERIAL/);
  });
  it("supports explicit light and dark themes", () => {
    const { rerender } = render(<ActivityTrace runId="run-1" events={runEvents()} theme="light" />);
    expect(screen.getByLabelText("本轮执行过程")).toHaveClass("activity-trace-theme-light");
    rerender(<ActivityTrace runId="run-1" events={runEvents()} theme="dark" />);
    expect(screen.getByLabelText("本轮执行过程")).toHaveClass("activity-trace-theme-dark");
  });
  it("renders persisted execution stages as individually collapsible groups with actual timing", () => {
    const events = [
      { ...e("run-1", 1, "phase_started", { phase: "investigate", iteration: 2 }), ts: "2026-10-28T00:00:00.000Z" },
      { ...e("run-1", 2, "tool_called", { phase: "investigate", iteration: 2, step_id: "search-1", tool: "clause_search", args: { top_k: 3 } }), ts: "2026-10-28T00:00:00.100Z" },
      { ...e("run-1", 3, "tool_result", { phase: "investigate", iteration: 2, step_id: "search-1", tool: "clause_search", duration_ms: 310, result: { source: [{ clause_id: "CID-7", page: 12 }] } }), ts: "2026-10-28T00:00:00.410Z" },
      { ...e("run-1", 4, "claim_checked", { phase: "auditor", verdict: "supported", public_rationale: "来源支持该项结论", sources: [{ clause_id: "CID-7" }] }, "evidence_auditor"), ts: "2026-10-28T00:00:01.000Z" },
    ];
    render(<ActivityTrace runId="run-1" events={events} />);
    openTrace();
    const stages = screen.getAllByTestId("trace-stage");
    expect(stages).toHaveLength(2);
    expect(stages[0]).not.toHaveAttribute("open");
    expect(stages[0]).toHaveTextContent("调查");
    expect(stages[0]).toHaveTextContent("310 ms");
    fireEvent.click(stages[0].querySelector("summary")!);
    expect(stages[0]).toHaveAttribute("open");
    expect(stages[0]).toHaveTextContent("来源 1 项");
    expect(stages[1]).toHaveTextContent("审核结果");
    expect(stages[1]).toHaveTextContent("来源支持该项结论");
  });
  it("does not fabricate an execution step when SQLite/SSE supplied no events", () => {
    render(<ActivityTrace runId="empty-run" events={[]} />);
    openTrace();
    expect(screen.getByTestId("trace-empty")).toHaveTextContent("暂无持久化执行事件");
    expect(screen.queryByTestId("trace-stage")).not.toBeInTheDocument();
  });
});
