import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { UsageDashboard } from "./UsageDashboard";
import type { UsageStats } from "./types";

const fixture = (overrides: Partial<UsageStats> = {}): UsageStats => ({
  period: "today", timezone_offset_minutes: 480,
  range: { start_utc: "2026-10-27T16:00:00.000+00:00", end_utc_exclusive: "2026-10-28T16:00:00.000+00:00" },
  generated_at_utc: "2026-10-28T15:00:00.000+00:00", archive_policy: "included",
  counts: { conversations: 2, messages_sent: 3, messages_total: 6, runs: 3, model_calls: 1, tool_calls: 2, average_run_ms: 1240 },
  token_usage: { availability: "not_recorded", prompt_tokens: null, completion_tokens: null, total_tokens: null },
  status_distribution: { success: 1, needs_evidence: 1, failed: 1, running: 0, other: 0 },
  task_distribution: [{ key: "diagnosis", count: 2 }, { key: "general_chat", count: 1 }],
  mode_distribution: [{ key: "RULE_DEMO", count: 2 }, { key: "DEEPSEEK", count: 1 }],
  hourly_runs: [{ hour: 10, count: 2 }, { hour: 11, count: 1 }],
  ...overrides,
});

describe("UsageDashboard", () => {
  afterEach(() => cleanup());
  it("shows loading and error states", async () => {
    const pending = vi.fn(() => new Promise<UsageStats>(() => undefined));
    const view = render(<UsageDashboard fetchStats={pending} />);
    expect(screen.getByRole("status")).toHaveTextContent("正在读取本地统计");
    view.unmount();
    render(<UsageDashboard fetchStats={vi.fn().mockRejectedValue(new Error("SQLite 离线"))} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("SQLite 离线");
  });

  it("renders true counters and does not convert missing token usage to zero", async () => {
    render(<UsageDashboard fetchStats={vi.fn().mockResolvedValue(fixture())} />);
    expect(await screen.findByText("今日每小时运行")).toBeInTheDocument();
    expect(screen.getByText("Token 使用")).toBeInTheDocument();
    expect(screen.getAllByText("未记录").length).toBeGreaterThan(0);
    expect(screen.getByText("待补证")).toBeInTheDocument();
    expect(screen.getByText("工程研判")).toBeInTheDocument();
    expect(screen.getByText("运行状态")).toBeInTheDocument();
  });

  it("shows an empty state and omits decorative charts when there are no runs", async () => {
    const data = fixture({ counts: { conversations: 0, messages_sent: 0, messages_total: 0, runs: 0, model_calls: 0, tool_calls: 0, average_run_ms: null }, task_distribution: [], status_distribution: {} });
    render(<UsageDashboard fetchStats={vi.fn().mockResolvedValue(data)} />);
    expect(await screen.findByText("所选时间范围内暂无运行记录。" )).toBeInTheDocument();
    expect(screen.queryByText("任务类别")).not.toBeInTheDocument();
  });

  it("passes the local timezone offset and refetches when a period tab changes", async () => {
    const fetchStats = vi.fn().mockResolvedValue(fixture());
    render(<UsageDashboard fetchStats={fetchStats} />);
    await screen.findByText("今日每小时运行");
    expect(fetchStats).toHaveBeenCalledWith("today", -new Date().getTimezoneOffset(), expect.any(AbortSignal));
    fireEvent.click(screen.getByRole("tab", { name: "近 7 天" }));
    await waitFor(() => expect(fetchStats).toHaveBeenLastCalledWith("7d", -new Date().getTimezoneOffset(), expect.any(AbortSignal)));
  });

  it("shows exact provider token usage only when the API says it was recorded", async () => {
    const data = fixture({ token_usage: { availability: "recorded", prompt_tokens: 123, completion_tokens: 45, total_tokens: 168 } });
    render(<UsageDashboard fetchStats={vi.fn().mockResolvedValue(data)} />);
    expect(await screen.findByText("168")).toBeInTheDocument();
    expect(screen.getByText("输入 123 · 输出 45")).toBeInTheDocument();
  });
});
