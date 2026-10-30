import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import App from "./App";

vi.mock("./api", async () => {
  const actual = await vi.importActual<typeof import("./api")>("./api");
  return { ...actual, api: { health: vi.fn().mockResolvedValue({ status: "ok", mode: "RULE_DEMO", database: "local", teacher_tools: ["a", "b", "c"], llm: { configured: false } }), listConversations: vi.fn().mockResolvedValue([]) }, consumeRun: vi.fn() };
});
vi.mock("./voice/SpeechInputButton", () => ({ SpeechInputButton: ({ onTranscript }: { onTranscript: (text: string) => void }) => <button type="button" onClick={() => onTranscript("设备振动异常")}>测试语音回填</button> }));
afterEach(() => { cleanup(); localStorage.clear(); vi.unstubAllGlobals(); });

function matchMedia(matches: boolean) { return vi.fn().mockImplementation((media: string) => ({ matches, media, addEventListener: vi.fn(), removeEventListener: vi.fn() })); }

describe("P11-A app shell", () => {
  it("collapses and expands the desktop sidebar, persisting the choice", async () => {
    vi.stubGlobal("matchMedia", matchMedia(true)); render(<App/>);
    await waitFor(() => expect(screen.getByRole("button", { name: "收起侧栏" })).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "收起侧栏" }));
    expect(screen.getByRole("button", { name: "展开侧栏" })).toBeInTheDocument();
    expect(localStorage.getItem("aetheris-sidebar-collapsed")).toBe("true");
    fireEvent.click(screen.getByRole("button", { name: "展开侧栏" }));
    expect(screen.getByRole("button", { name: "收起侧栏" })).toBeInTheDocument();
  });

  it("keeps the mobile history drawer entry visible instead of replacing it with the desktop rail", async () => {
    vi.stubGlobal("matchMedia", matchMedia(false)); localStorage.setItem("aetheris-sidebar-collapsed", "true"); render(<App/>);
    expect(await screen.findByRole("button", { name: "打开历史" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "展开侧栏" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "历史" })).toBeInTheDocument();
  });

  it("opens Settings from the application shell", async () => {
    vi.stubGlobal("matchMedia", matchMedia(true)); render(<App/>);
    fireEvent.click(await screen.findByRole("button", { name: "打开设置" }));
    expect(screen.getByRole("heading", { name: "常规" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "返回聊天" })).toBeInTheDocument();
  });

  it("opens the delivered UsageDashboard and requests its real local stats endpoint", async () => {
    vi.stubGlobal("matchMedia", matchMedia(true));
    const fetcher = vi.fn().mockResolvedValue({ ok: false, status: 503, json: async () => ({}) }); vi.stubGlobal("fetch", fetcher);
    render(<App/>); fireEvent.click(await screen.findByRole("button", { name: "打开统计" }));
    expect(await screen.findByRole("heading", { name: "今日活动" })).toBeInTheDocument();
    await waitFor(() => expect(fetcher).toHaveBeenCalled());
    expect(String(fetcher.mock.calls[0][0])).toMatch(/^\/api\/stats\?period=today&tz_offset=/);
    expect(screen.getByRole("button", { name: "关闭统计" })).toBeInTheDocument();
  });

  it("wires the delivered speech control to the composer draft without submitting", async () => {
    vi.stubGlobal("matchMedia", matchMedia(true)); render(<App/>);
    const draft = screen.getByRole("textbox", { name: "发送问题" });
    fireEvent.click(await screen.findByRole("button", { name: "测试语音回填" }));
    expect(draft).toHaveValue("设备振动异常");
    expect(screen.getByRole("button", { name: /发送/ })).toBeDisabled();
  });
});
