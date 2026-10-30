import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import App from "./App";
import { api } from "./api";

vi.mock("./api", async () => {
  const actual = await vi.importActual<typeof import("./api")>("./api");
  const conversations = [
    { id: "c1", title: "设备 A 分析", created_at: "2026-10-28T00:00:00Z", updated_at: "2026-10-28T00:00:00Z" },
    { id: "c2", title: "设备 B 分析", created_at: "2026-10-28T00:00:00Z", updated_at: "2026-10-28T00:00:00Z" },
  ];
  return { ...actual, api: {
    health: vi.fn().mockResolvedValue({ status: "ok", mode: "RULE_DEMO", database: "local.sqlite", teacher_tools: [] }),
    listConversations: vi.fn().mockResolvedValue(conversations),
    createConversation: vi.fn().mockResolvedValue({ ...conversations[0], id: "c3", title: "新对话" }),
    getConversation: vi.fn(async (id: string) => ({ ...conversations.find(c => c.id === id)!, messages: [] })),
    createRun: vi.fn(), replay: vi.fn().mockResolvedValue({ events: [] }),
  }, consumeRun: vi.fn() };
});

beforeEach(() => { localStorage.clear(); vi.clearAllMocks();
  vi.mocked(api.health).mockResolvedValue({ status: "ok", mode: "RULE_DEMO", database: "local.sqlite", teacher_tools: [] });
  vi.mocked(api.listConversations).mockResolvedValue([
    { id: "c1", title: "设备 A 分析", created_at: "2026-10-28T00:00:00Z", updated_at: "2026-10-28T00:00:00Z" },
    { id: "c2", title: "设备 B 分析", created_at: "2026-10-28T00:00:00Z", updated_at: "2026-10-28T00:00:00Z" },
  ]);
});
afterEach(cleanup);
async function showInspector(){const button=screen.queryByRole("button",{name:"展开证据审查"});if(button)fireEvent.click(button)}

describe("P4C actual UI behavior", () => {
  it("loads the first SQLite conversation and exposes its title", async () => {
    render(<App />); await waitFor(() => expect(screen.getAllByText("设备 A 分析").length).toBeGreaterThan(0));
    expect(api.getConversation).toHaveBeenCalledWith("c1", expect.any(AbortSignal));
  });
  it("switches conversation from the history list", async () => {
    render(<App />); await screen.findAllByText("设备 B 分析"); fireEvent.click(screen.getAllByText("设备 B 分析")[0]);
    await waitFor(() => expect(api.getConversation).toHaveBeenCalledWith("c2", expect.any(AbortSignal)));
  });
  it("filters conversation history as the query changes", async () => {
    render(<App />); await screen.findByText("设备 B 分析"); fireEvent.change(screen.getByPlaceholderText("搜索历史分析"), { target: { value: "设备 B" } });
    expect(screen.getByText("设备 B 分析")).toBeInTheDocument(); expect(document.querySelector(".conversation-list")?.textContent).not.toContain("设备 A 分析");
  });
  it("enters focus chat and restores the inspector through an accessible toggle", async () => {
    render(<App />); const toggle = await screen.findByRole("button", { name: "展开证据审查" });
    fireEvent.click(toggle); expect(screen.getByText("执行审查")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "收起证据审查，专注聊天" })); expect(document.querySelector(".app-shell")?.classList.contains("focus-chat")).toBe(true);
  });
  it("opens and closes the mobile history drawer", async () => {
    render(<App />); await screen.findAllByText("设备 A 分析"); fireEvent.click(screen.getByRole("button", { name: "打开历史" }));
    expect(document.querySelector(".sidebar.mobile-visible")).toBeInTheDocument(); fireEvent.click(screen.getByRole("button", { name: "关闭历史" }));
    expect(document.querySelector(".sidebar.mobile-visible")).not.toBeInTheDocument();
  });
  it("starter prompt populates the composer instead of sending immediately", async () => {
    render(<App />); const starter = await screen.findByRole("button", { name: /梳理缺失工况/ }); fireEvent.click(starter);
    expect(screen.getByRole("textbox", { name: "发送问题" })).toHaveValue("请基于现有设备信息梳理需要补充的工况与证据。");
    expect(api.createRun).not.toHaveBeenCalled();
  });
  it("expands and collapses structured engineering context fields", async () => {
    render(<App />); const context = await screen.findByRole("button", { name: /设备与工况/ }); fireEvent.click(context);
    fireEvent.change(screen.getByRole("textbox", { name: "设备名称" }), { target: { value: "泵-A17" } });
    expect(screen.getByRole("textbox", { name: "设备名称" })).toHaveValue("泵-A17"); fireEvent.click(context);
    expect(screen.queryByRole("textbox", { name: "设备名称" })).not.toBeInTheDocument();
  });
  it("toggles dark mode and persists the selected theme", async () => {
    render(<App />); fireEvent.click(await screen.findByRole("button", { name: "切换深浅色" }));
    expect(document.documentElement.dataset.theme).toBe("dark"); expect(localStorage.getItem("aether-theme")).toBe("dark");
  });
  it("discloses that the local run index is not cross-device history", async () => {
    render(<App />); await showInspector(); expect(await screen.findByText(/跨设备不可恢复/)).toBeInTheDocument();
  });
  it("opens a large observed-path graph drawer and closes it accessibly", async () => {
    render(<App />); await showInspector(); fireEvent.click(await screen.findByRole("button", { name: "放大执行图" }));
    expect(screen.getByRole("dialog", { name: "放大执行图" })).toBeInTheDocument();
    expect(screen.getByText(/只绘制已观察到的 agent_started 顺序/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "关闭放大执行图" }));
    expect(screen.queryByRole("dialog", { name: "放大执行图" })).not.toBeInTheDocument();
  });
  it("renders canonical E1 quote, hash, page and unknown conditions in the evidence drawer", async () => {
    const runId="fixture-run-e1"; localStorage.setItem("aether:last-run:c1",runId);
    const claim={claim_id:"claim-e1",text:"候选机理（待复核）",grade:"E1",verdict:"unresolved",review_status:"requires_human_review",provenance_status:"verified",canonical_evidence:[{clause_id:"GBT30579-2022-5.1",canonical_record_sha256:"abc123",printed_page:2,canonical_version:"v1",content_raw:"已核对的原文引用",tool_source:{standard_code:"GB/T 30579-2022"}}],checks:[{check:"condition:temperature",status:"not_specified"}]};
    vi.mocked(api.replay).mockResolvedValue({run_id:runId,events:[{run_id:runId,sequence:1,type:"claim_added",agent:"evidence_auditor",payload:claim},{run_id:runId,sequence:2,type:"requires_human_review",agent:"evidence_auditor",payload:claim},{run_id:runId,sequence:3,type:"contradiction_found",agent:"skeptic",payload:{claim_id:"claim-e1",counterevidence:"壁厚尚未测量，不能确认减薄"}}]});
    render(<App />); await showInspector(); fireEvent.click(await screen.findByRole("button",{name:/候选机理（待复核）/}));
    expect(await screen.findByText("E1：条款已定位，但专业适用性待复核")).toBeInTheDocument();
    fireEvent.click(screen.getByText(/原始证据与审计详情/));
    expect(await screen.findByText("abc123")).toBeInTheDocument(); expect(screen.getByText("已核对的原文引用")).toBeInTheDocument();
    expect(screen.getAllByText(/condition:temperature: not_specified/).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByText(/独立反证与核验过程/));
    expect(screen.getByText(/壁厚尚未测量/)).toBeInTheDocument(); expect(screen.getAllByText(/GBT30579-2022-5.1/).length).toBeGreaterThan(0);
  });
  it("shows a missing-source E0 card as unresolved rather than a supported conclusion", async () => {
    const runId="fixture-run-e0"; localStorage.setItem("aether:last-run:c1",runId);
    vi.mocked(api.replay).mockResolvedValue({run_id:runId,events:[{run_id:runId,sequence:1,type:"claim_added",agent:"evidence_auditor",payload:{claim_id:"claim-e0",text:"来源待核候选",grade:"E0",verdict:"unresolved",review_status:"requires_human_review",provenance_status:"partial",checks:[{check:"current_run_source",status:"missing"}],canonical_evidence:[]}}]});
    render(<App />); await showInspector(); fireEvent.click(await screen.findByRole("button",{name:/来源待核候选/}));
    expect(await screen.findByText("E0：来源不足，当前记录不支持该判断")).toBeInTheDocument(); fireEvent.click(screen.getByText(/原始证据与审计详情/));
    expect((await screen.findAllByText("E0")).length).toBeGreaterThan(0); expect(screen.getByText("partial")).toBeInTheDocument();
    expect(screen.getByText(/current_run_source: missing/)).toBeInTheDocument(); expect(screen.queryByText(/E2|E3|L1|L2|低风险/)).not.toBeInTheDocument();
  });
  it("keeps claim event history while the latest review event controls the card", async () => {
    const runId="fixture-run-history"; localStorage.setItem("aether:last-run:c1",runId);
    const base={claim_id:"claim-history",text:"同一Claim",grade:"E0",verdict:"unresolved",review_status:"requires_human_review"};
    vi.mocked(api.replay).mockResolvedValue({run_id:runId,events:[{run_id:runId,sequence:1,type:"claim_added",payload:{...base,review_status:"draft_needs_review"}},{run_id:runId,sequence:2,type:"claim_checked",payload:{...base,checks:[{check:"metadata",status:"missing"}]}},{run_id:runId,sequence:3,type:"requires_human_review",payload:base}]});
    render(<App />); await showInspector(); fireEvent.click(await screen.findByRole("button",{name:/同一Claim/}));
    expect(await screen.findByText(/#1 claim_added/)).toBeInTheDocument(); expect(screen.getAllByText(/#2 claim_checked/).length).toBeGreaterThan(0); expect(screen.getAllByText(/#3 requires_human_review/).length).toBeGreaterThan(0);
  });
  it("does not render or serialize an unsupported business risk level", async () => {
    const runId="fixture-risk-filter"; localStorage.setItem("aether:last-run:c1",runId);
    vi.mocked(api.replay).mockResolvedValue({run_id:runId,events:[{run_id:runId,sequence:1,type:"claim_added",payload:{claim_id:"risk-claim",text:"仅供核查",grade:"E0",verdict:"unresolved",review_status:"requires_human_review"}}]});
    render(<App />); await showInspector(); fireEvent.click(await screen.findByRole("button",{name:/仅供核查/}));
    const modal=document.querySelector(".evidence-modal")!;
    expect(modal.textContent).not.toMatch(/风险等级|低风险|L1|L2/); expect(modal.textContent).toContain("E0");
  });
  it("opens raw reference-added SSE events in the same source drawer", async () => {
    const runId="fixture-reference"; localStorage.setItem("aether:last-run:c1",runId);
    vi.mocked(api.replay).mockResolvedValue({run_id:runId,events:[{run_id:runId,sequence:1,type:"reference_added",agent:"evidence_agent",payload:{clause_id:"GBT30579-2022-5.1",standard_code:"GB/T 30579-2022",page:2,verification_level:"E0",canonical_record_sha256:"hash-from-event",content_raw:"完整条文引文"}}]});
    render(<App />); await showInspector(); fireEvent.click(await screen.findByRole("button",{name:/reference_added/}));
    expect(await screen.findByText("hash-from-event")).toBeInTheDocument(); expect(screen.getByText("完整条文引文")).toBeInTheDocument();
    expect(screen.getAllByText(/印刷页码/).length).toBeGreaterThan(0);
  });
  it("shows a readable first-screen report and keeps a long assistant report folded", async () => {
    const runId="fixture-p6b-report"; localStorage.setItem("aether:last-run:c1",runId);
    const claim={claim_id:"p6b-claim",text:"候选机理（待复核）",grade:"E1",verdict:"unresolved",review_status:"requires_human_review",provenance_status:"verified",source_clause_ids:["GBT30579-2022-5.1"],checks:[{check:"condition:temperature",status:"not_specified"},{check:"condition:thickness",status:"unknown"}]};
    vi.mocked(api.getConversation).mockResolvedValue({id:"c1",title:"设备 A 分析",created_at:"2026-10-28T00:00:00Z",updated_at:"2026-10-28T00:00:00Z",messages:[{id:"u1",role:"user",content:"塔顶水样 pH 5.8，尚未测厚，可能的损伤机理？"},{id:"a1",role:"assistant",content:"工程研判摘要。"+"候选条款与工况核对；结论仍需人工复核。".repeat(50)}]});
    vi.mocked(api.replay).mockResolvedValue({run_id:runId,events:[{run_id:runId,sequence:1,type:"claim_added",agent:"evidence_auditor",payload:claim},{run_id:runId,sequence:2,type:"contradiction_found",agent:"skeptic",payload:{claim_id:"p6b-claim",counterevidence:"壁厚未测，不能确认减薄"}}]});
    render(<App />); await showInspector();
    expect(await screen.findByRole("region",{name:"工程研判摘要"})).toBeInTheDocument();
    expect(screen.getByText("操作温度、实测壁厚")).toBeInTheDocument();
    expect(screen.getByText("E1 · 条款已定位，但专业适用性待复核")).toBeInTheDocument();
    expect(screen.getByText("壁厚未测，不能确认减薄")).toBeInTheDocument();
    expect(screen.getByText(/展开完整报告原文/)).toBeInTheDocument();
    expect(document.querySelector(".full-report")?.hasAttribute("open")).toBe(false);
  });
});



