import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import type { ApiEvent } from "../../api";
import { ActivityTrace } from "../../components/trace/ActivityTrace";
import { projectActivity } from "../model";
import "./preview.css";

type Conversation = { id: string; title: string; updated_at: string };
type Run = { id: string; conversation_id: string; status: string; mode: string; started_at: string };
const json = async <T,>(url: string): Promise<T> => { const r = await fetch(url); if (!r.ok) throw new Error(`${r.status} ${r.statusText}`); return r.json() as Promise<T>; };

function Preview() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [conversationId, setConversationId] = useState("");
  const [runs, setRuns] = useState<Run[]>([]);
  const [runId, setRunId] = useState(new URLSearchParams(location.search).get("run_id") ?? localStorage.getItem("r9b:last-run") ?? "");
  const [events, setEvents] = useState<ApiEvent[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [dark, setDark] = useState(false);
  const [reload, setReload] = useState(0);

  useEffect(() => { let dead = false; (async () => {
    try {
      const cs = await json<Conversation[]>("/api/conversations"); if (dead) return; setConversations(cs);
      let chosen = cs.find((c) => c.id === conversationId);
      if (!chosen && runId) {
        for (const c of cs) { const page = await json<{ runs: Run[] }>(`/api/conversations/${c.id}/runs?limit=100&offset=0`); const found = page.runs.find((r) => r.id === runId); if (found) { chosen = c; break; } }
      }
      chosen ??= cs[0];
      if (!chosen) throw new Error("SQLite 中没有对话或运行记录");
      setConversationId(chosen.id);
      const page = await json<{ runs: Run[] }>(`/api/conversations/${chosen.id}/runs?limit=100&offset=0`); if (dead) return; setRuns(page.runs);
      const selected = page.runs.find((r) => r.id === runId) ?? page.runs[0];
      if (!selected) throw new Error("该会话没有已持久化运行");
      setRunId(selected.id); localStorage.setItem("r9b:last-run", selected.id);
      const replay = await json<{ events: ApiEvent[] }>(`/api/runs/${selected.id}/events?after_sequence=0`); if (dead) return; setEvents(replay.events); setError("");
    } catch (e) { if (!dead) setError(e instanceof Error ? e.message : String(e)); }
    finally { if (!dead) setLoading(false); }
  })(); return () => { dead = true; }; }, [conversationId, runId, reload]);

  const active = projectActivity(events.filter((event) => event.run_id === runId));
  const summary = `${active.length} 条持久化事件 · ${active.filter((step) => step.type === "tool_called").length} 次真实工具调用`;
  const changeConversation = (id: string) => { setConversationId(id); setRunId(""); setEvents([]); setLoading(true); };
  const changeRun = (id: string) => { setRunId(id); setLoading(true); setEvents([]); };
  return <main className={dark ? "preview dark" : "preview"}>
    <header className="preview-header"><div className="brand-mark">A</div><div><div className="eyebrow">AETHER / ENERGY <span>SIMULATION</span></div><h1>执行记录</h1></div><div className="header-actions"><button onClick={() => setDark(!dark)} aria-label="切换外观">{dark ? "☼" : "◐"}</button><button onClick={() => { setLoading(true); setReload((x) => x + 1); }}>↻ 刷新回放</button></div></header>
    <div className="preview-main">
      <aside className="run-rail"><div className="rail-title">本机历史 <span>SQLite</span></div><label>会话<select aria-label="会话" value={conversationId} onChange={(e) => changeConversation(e.target.value)}>{conversations.map((c) => <option key={c.id} value={c.id}>{c.title || "新对话"}</option>)}</select></label><div className="run-list">{runs.map((run) => <button className={run.id === runId ? "run-choice active" : "run-choice"} key={run.id} onClick={() => changeRun(run.id)}><span className="run-dot"/><span><b>{run.mode}</b><small>{new Date(run.started_at).toLocaleString("zh-CN")}</small></span></button>)}</div></aside>
      <section className="chat-stage"><div className="thread-label"><span className="online-dot"/> 本地运行回放 <span className="thread-meta">{summary}</span></div><article className="assistant-turn"><div className="assistant-avatar">A</div><div className="turn-content"><div className="turn-kicker">Haeness2 · RULE_DEMO</div><h2>本轮执行过程</h2>{loading ? <div className="loading-state">正在从 SQLite 读取并重放事件…</div> : error ? <div className="error-state">{error}<p>启动本机 API 后刷新即可读取真实事件。</p></div> : <ActivityTrace runId={runId} events={events} theme={dark ? "dark" : "light"}/>}<div className="honesty-note">过程来自本机 SQLite 持久化事件；只呈现已记录的执行与公开摘要，不包含模型隐藏推理。</div></div></article><footer>Haeness2 · 工业设备风险研判 · 本地演示</footer></section>
    </div>
  </main>;
}

createRoot(document.getElementById("root")!).render(<React.StrictMode><Preview/></React.StrictMode>);
