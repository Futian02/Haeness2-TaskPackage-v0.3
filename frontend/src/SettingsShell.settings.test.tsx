import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import SettingsShell from "./SettingsShell";
import { api } from "./api";
import { DEFAULT_PREFERENCES, PREFERENCES_KEY, readPreferences, writePreferences } from "./settings/preferences";
import type { Conversation, Health } from "./api";

afterEach(cleanup);
const archived: Conversation[] = [{ id: "c-old", title: "历史泵组分析", created_at: "2026-01-01", updated_at: "2026-01-02", archived_at: "2026-01-03" } as Conversation];
const noKeyHealth: Health = { status: "ok", mode: "RULE_DEMO", default_mode: "RULE_DEMO", llm: { configured: false }, database: "local", teacher_tools: ["rbi_lookup", "standard_lookup", "history_lookup"] };

function Harness({ health = noKeyHealth, theme = "light", onRestore = vi.fn(), onHealth = vi.fn().mockResolvedValue(undefined) }: { health?: Health; theme?: "light"|"dark"; onRestore?: (item: Conversation) => Promise<void>; onHealth?: () => Promise<void> }) {
  return <SettingsShell health={health} resolvedTheme={theme} preferences={readPreferences()} onPreferencesChange={next => writePreferences(next)} archived={archived} archiveLoading={false} onLoadArchive={vi.fn()} onRestore={onRestore} onBack={vi.fn()} onRefreshHealth={onHealth}/>;
}

describe("P11-A settings", () => {
  it("persists the general font, density, and trace preferences", () => {
    localStorage.clear(); render(<Harness/>);
    fireEvent.click(screen.getByRole("button", { name: "110%" }));
    expect(readPreferences().fontScale).toBe(110);
    fireEvent.click(screen.getByRole("button", { name: "紧凑" }));
    expect(readPreferences().density).toBe("compact");
    fireEvent.click(screen.getByRole("checkbox", { name: "默认展开事件时间线" }));
    expect(readPreferences().autoExpandTrace).toBe(false);
  });

  it("shows the backend's no-key state without exposing secret fields", async () => {
    localStorage.clear(); render(<Harness/>);
    fireEvent.click(screen.getByRole("button", { name: "模型" }));
    expect(screen.getByText("RULE_DEMO")).toBeInTheDocument();
    expect(screen.getByText("未配置")).toBeInTheDocument();
    expect(screen.getByText(/不调用模型、不产生推理费用/)).toBeInTheDocument();
    expect(screen.queryByText(/sk-[A-Za-z0-9]+/)).not.toBeInTheDocument();
  });

  it("restores an archived conversation without deleting it", async () => {
    localStorage.clear(); const restore = vi.fn().mockResolvedValue(undefined); render(<Harness onRestore={restore}/>);
    fireEvent.click(screen.getByRole("button", { name: "会话与归档" }));
    expect(screen.getByText("历史泵组分析")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "恢复" }));
    await waitFor(() => expect(restore).toHaveBeenCalledWith(archived[0]));
  });

  it("persists light/dark/system preferences and keeps the legacy theme key readable", () => {
    localStorage.setItem("aether-theme", "dark");
    expect(readPreferences()).toEqual(DEFAULT_PREFERENCES);
    const prefs = { ...DEFAULT_PREFERENCES, theme: "system" as const };
    writePreferences(prefs);
    expect(JSON.parse(localStorage.getItem(PREFERENCES_KEY) || "{}").theme).toBe("system");
  });

  it("pins the settings palette to the actual resolved theme", () => {
    const view=render(<Harness theme="dark" />);
    expect(view.container.querySelector(".settings-shell")).toHaveAttribute("data-theme", "dark");
    view.rerender(<Harness theme="light" />);
    expect(view.container.querySelector(".settings-shell")).toHaveAttribute("data-theme", "light");
  });

  it("refreshes only the actual service health endpoint", async () => {
    const refresh = vi.fn().mockResolvedValue(undefined); render(<Harness onHealth={refresh}/>);
    fireEvent.click(screen.getByRole("button", { name: "模型" }));
    fireEvent.click(screen.getByRole("button", { name: "刷新后端状态" }));
    await waitFor(() => expect(refresh).toHaveBeenCalledTimes(1));
    expect(await screen.findByRole("status")).toHaveTextContent("/api/health");
  });

  it("stores model credentials server-side, offers a true provider test, and can activate the profile", async () => {
    localStorage.clear();
    vi.spyOn(api,"modelProfiles").mockResolvedValue({profiles:[{id:"p1",provider:"deepseek",model:"deepseek-chat",endpoint:"https://api.deepseek.com/v1",key_configured:true,api_key_masked:"••••••••"}],active_profile_id:null,credential_store:"Windows DPAPI (CurrentUser)"});
    vi.spyOn(api,"testModelProfile").mockResolvedValue({ok:true,provider:"deepseek",model:"deepseek-chat",latency_ms:22,usage:{total_tokens:4},cost_warning:"cost"});
    vi.spyOn(api,"activateModelProfile").mockResolvedValue({active_profile_id:"p1"});
    const save=vi.spyOn(api,"saveModelProfile").mockResolvedValue({id:"p2",provider:"deepseek",model:"deepseek-chat",endpoint:"https://api.deepseek.com/v1",key_configured:true,api_key_masked:"••••••••"});
    render(<Harness/>); fireEvent.click(screen.getByRole("button", { name: "模型" }));
    await screen.findByText(/Windows DPAPI \(CurrentUser\)/);
    fireEvent.click(screen.getByRole("button", { name: "真实连接测试" }));
    expect(await screen.findByText(/"total_tokens": 4/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "切换" }));
    await waitFor(()=>expect(api.activateModelProfile).toHaveBeenCalledWith("p1"));
    fireEvent.click(screen.getByRole("button", { name: "编辑" }));
    expect(screen.getByRole("heading", { name: "编辑模型配置" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "更新配置" }));
    await waitFor(()=>expect(api.saveModelProfile).toHaveBeenCalledWith({provider:"deepseek",model:"deepseek-chat",endpoint:"https://api.deepseek.com/v1"},"p1"));
    fireEvent.change(screen.getByLabelText("API Key"),{target:{value:"synthetic-ui-key-123"}});
    fireEvent.click(screen.getByRole("button", { name: "保存配置" }));
    await waitFor(()=>expect(save).toHaveBeenCalled());
    expect(save.mock.calls.at(-1)?.[0].api_key).toBe("synthetic-ui-key-123");
    expect(localStorage.length).toBe(0);
  });
});
