import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import App from "./App";
import { api, RunStreamError } from "./api";

vi.mock("./api", async () => {
  const actual = await vi.importActual<typeof import("./api")>("./api");
  const conversation = { id: "c1", title: "骑行 SVG 动画", created_at: "2026-10-29T00:00:00Z", updated_at: "2026-10-29T00:00:00Z" };
  return { ...actual, api: {
    health: vi.fn().mockResolvedValue({ status: "ok", mode: "DEEPSEEK", database: "test.sqlite", teacher_tools: [] }),
    listConversations: vi.fn().mockResolvedValue([conversation]),
    getConversation: vi.fn().mockResolvedValue({ ...conversation, messages: [{ id: "u1", role: "user", content: "创建HTML骑自行车动画", run_id: "failed-run" }] }),
    listFiles: vi.fn().mockResolvedValue([]), listRuns: vi.fn().mockResolvedValue([]),
    runInput: vi.fn().mockResolvedValue({ conversation_id: "c1", question: "创建HTML骑自行车动画", mode: "DEEPSEEK", context: {} }),
    replay: vi.fn().mockResolvedValue({ run_id: "failed-run", events: [{ run_id: "failed-run", sequence: 1, type: "error", payload: { code: "provider_empty", message: "PRIVATE_PROVIDER_BODY_SENTINEL" } }] }),
    createRun: vi.fn().mockResolvedValue({ run_id: "retry-run", status: "queued", mode: "RULE_DEMO", events_url: "/api/runs/retry-run/stream" }),
  }, consumeRun: vi.fn(async () => undefined) };
});

beforeEach(() => { localStorage.clear(); vi.clearAllMocks(); });
afterEach(cleanup);

describe("P13 failed-run UI", () => {
  it("restores a failed run after reload, offers retry, and never renders provider raw body", async () => {
    localStorage.setItem("aether:last-run:c1", "failed-run");
    render(<App />);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("本轮未完成");
    expect(alert).toHaveTextContent("模型没有返回可显示内容");
    expect(alert).not.toHaveTextContent("PRIVATE_PROVIDER_BODY_SENTINEL");
    expect(screen.getByRole("button", { name: /作为新运行重试/ })).toBeEnabled();
    expect(screen.queryByText(/本轮执行已结束/)).not.toBeInTheDocument();
    await waitFor(() => expect(api.replay).toHaveBeenCalledWith("failed-run", 0, expect.any(AbortSignal)));
    fireEvent.click(screen.getByRole("button", { name: /作为新运行重试/ }));
    await waitFor(() => expect(api.createRun).toHaveBeenCalledWith("c1", expect.objectContaining({
      question: "创建HTML骑自行车动画",
      web_mode: "auto",
    }), expect.any(String)));
  });
  it("defaults to auto, persists a selectable mode, and saves that mode in the Run input", async () => {
    render(<App />);
    const question = await screen.findByRole("textbox", { name: "发送问题" });
    const mode = screen.getByRole("combobox", { name: "联网模式" });
    expect(mode).toHaveValue("auto");
    fireEvent.change(mode, { target: { value: "on" } });
    expect(screen.getByRole("checkbox", { name: "确认允许本轮敏感问题文本联网检索" })).toBeInTheDocument();
    fireEvent.change(question, { target: { value: "请概括公开网页上的 HTML SVG 示例" } });
    fireEvent.click(screen.getByRole("button", { name: /发送/ }));
    await waitFor(() => expect(api.createRun).toHaveBeenCalled());
    const sent = vi.mocked(api.createRun).mock.calls[0][1];
    expect(sent.web_mode).toBe("on");
    expect(sent.allow_sensitive_web_search).toBe(false);
    expect(screen.getByRole("combobox", { name: "联网模式" })).toHaveValue("on");
    expect(localStorage.getItem("aether:web-mode:c1")).toBe("on");
    cleanup();
    render(<App />);
    expect(await screen.findByRole("combobox", { name: "联网模式" })).toHaveValue("on");
  });

  it("labels a legacy backend as a version issue rather than a connection outage", async () => {
    render(<App />);
    expect(await screen.findByText(/后端未提供版本握手（旧服务）/)).toBeInTheDocument();
    expect(screen.queryByText(/后端连接失败/)).not.toBeInTheDocument();
  });

  it("keeps the draft and the same idempotency key when Run creation fails", async () => {
    vi.mocked(api.createRun).mockRejectedValueOnce(new TypeError("Failed to fetch"));
    render(<App />);
    const prompt = await screen.findByRole("textbox", { name: "发送问题" });
    fireEvent.change(prompt, { target: { value: "壳体磕碰后如何核对" } });
    fireEvent.click(screen.getByRole("button", { name: /发送/ }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("与服务的连接中断"));
    expect(screen.getByRole("textbox", { name: "发送问题" })).toHaveValue("壳体磕碰后如何核对");
    expect(localStorage.getItem("aether:draft:c1")).toBe("壳体磕碰后如何核对");
    const firstKey = localStorage.getItem("aether:pending-run-key:c1");
    expect(firstKey).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /发送/ }));
    await waitFor(() => expect(api.createRun).toHaveBeenCalledTimes(2));
    expect(vi.mocked(api.createRun).mock.calls[0][2]).toBe(firstKey);
    expect(vi.mocked(api.createRun).mock.calls[1][2]).toBe(firstKey);
    expect(vi.mocked(api.createRun).mock.calls[1][1]).toEqual(vi.mocked(api.createRun).mock.calls[0][1]);
  });
  it("resumes the existing queued Run after capacity 429 and never POSTs a duplicate", async () => {
    const consume = await import("./api").then(m => vi.mocked(m.consumeRun));
    consume.mockRejectedValueOnce(new RunStreamError("run_queued_capacity", 2)).mockResolvedValueOnce([]);
    render(<App />);
    const prompt = await screen.findByRole("textbox", { name: "发送问题" });
    fireEvent.change(prompt, { target: { value: "排队容量恢复验证问题" } });
    fireEvent.click(screen.getByRole("button", { name: /发送/ }));
    await screen.findByRole("alert");
    expect(screen.getByRole("alert")).toHaveAttribute("data-failure-code", "run_queued_capacity");
    expect(screen.getByRole("alert")).toHaveTextContent("重新连接不会重复提交");
    const existingRun = vi.mocked(api.createRun).mock.results[0].value;
    fireEvent.click(screen.getByRole("button", { name: /继续等待原任务/ }));
    await waitFor(() => expect(consume).toHaveBeenCalledTimes(2));
    expect(api.createRun).toHaveBeenCalledTimes(1);
    expect(consume.mock.calls[1][0].run_id).toBe("retry-run");
    expect(existingRun).toBeDefined();
  });
});
