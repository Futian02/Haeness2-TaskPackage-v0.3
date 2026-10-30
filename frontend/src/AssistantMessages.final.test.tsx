import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import AssistantMessages from "./AssistantMessages";
import type { ApiEvent, Message } from "./api";

const messages: Message[] = [
  { id: "u1", role: "user", content: "查标准", run_id: "run-1" },
  { id: "a1", role: "assistant", content: "检索结果待复核。", run_id: "run-1" },
];
const events: ApiEvent[] = [
  { run_id: "run-1", sequence: 1, type: "tool_called", agent: "evidence_agent", payload: { tool: "standard_clause_search", phase: "investigate", args: { top_k: 5 } } },
  { run_id: "run-1", sequence: 2, type: "tool_result", agent: "evidence_agent", payload: { tool: "standard_clause_search", phase: "investigate", sources: [{ clause_id: "CID-7", clause_no: "5.1", page: 12, verification_level: "E0" }], result: { status: "ok", source: [{ clause_id: "CID-7", clause_no: "5.1", page: 12, verification_level: "E0" }] } } },
  { run_id: "run-1", sequence: 3, type: "agent_completed", agent: "skeptic", payload: { phase: "skeptic", public_rationale: "独立反证分支已完成" } },
  { run_id: "run-1", sequence: 4, type: "llm_completed", agent: "reporting_agent", payload: { provider: "DeepSeek", summary_label: "DeepSeek 表达整理（非思维链）", summary: "仅依据现有证据整理的过程摘要" } },
];

describe("final chat activity integration", () => {
  beforeEach(() => localStorage.clear());
  afterEach(cleanup);
  it("renders a collapsed, run-scoped trace from persisted events inside the assistant turn", () => {
    render(<AssistantMessages messages={messages} events={events} />);
    expect(screen.getByText("检索结果待复核。" )).toBeInTheDocument();
    expect(screen.getByText(/查询 1 次/)).toBeInTheDocument();
    expect(document.querySelector(".execution-card")?.hasAttribute("open")).toBe(false);
    expect(screen.getByText(/执行中 · 查询 1 次/)).toBeInTheDocument();
    expect(document.querySelector(".model-summary")?.hasAttribute("open")).toBe(false);
    fireEvent.click(screen.getByText(/执行中 · 查询 1 次/));
    expect(document.querySelector(".execution-card")?.hasAttribute("open")).toBe(true);
    expect(document.querySelector(".model-summary")?.hasAttribute("open")).toBe(false);
    fireEvent.click(screen.getByText("模型公开表达摘要 · 展开查看"));
    expect(screen.getAllByText("仅依据现有证据整理的过程摘要")).toHaveLength(2);
    fireEvent.click(screen.getByText("1 次工具调用"));
    expect(screen.getByText("CID-7")).toBeInTheDocument();
    expect(screen.getAllByText("独立反证分支已完成")).toHaveLength(2);
  });
  it("does not attach another run's events to an assistant response", () => {
    render(<AssistantMessages messages={messages.map(message=>({...message,id:`new-${message.id}`,run_id:"run-2"}))} events={events.map(event => ({ ...event, run_id: "other-run" }))} />);
    expect(document.querySelector(".activity-trace")?.getAttribute("data-run-id")).toBe("run-2");
    expect(screen.queryByText(/查询 1 次/)).not.toBeInTheDocument();
    expect(screen.getByText(/执行过程 · 0 步/)).toBeInTheDocument();
    expect(screen.queryByText("CID-7")).not.toBeInTheDocument();
  });
  it("renders the full HTML code block and offers a copy action", async () => {
    const html = `<html>\n<body>\n<svg>${"<circle cx=\"8\" cy=\"8\" r=\"2\"/>".repeat(30)}</svg>\n</body>\n</html>`;
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } });
    render(<AssistantMessages messages={[{ id: "code", role: "assistant", content: `\`\`\`html\n${html}\n\`\`\`` }]} />);
    const code = document.querySelector(".markdown-code-wrap pre code");
    expect(code?.textContent).toContain("<html>");
    expect(code?.textContent).toContain("</html>");
    expect(screen.getByRole("button", { name: "复制代码" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "复制代码" }));
    expect(writeText).toHaveBeenCalledWith(expect.stringContaining("</html>"));
  });
});
