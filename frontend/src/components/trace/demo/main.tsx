import { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import type { ApiEvent } from "../../../api";
import { ActivityTrace } from "../ActivityTrace";
import "../../../styles.css";
import "./preview.css";

function TracePreview() {
  const [events, setEvents] = useState<ApiEvent[]>([]);
  const [status, setStatus] = useState("读取真实 SQLite/SSE Run 事件…");
  const runId = new URLSearchParams(location.search).get("run_id")?.trim() ?? "";
  useEffect(() => {
    if (!runId) { setStatus("请在网址添加 ?run_id=<已有 Run ID>；此预览不会创建任务。"); return; }
    const controller = new AbortController();
    fetch(`/api/runs/${encodeURIComponent(runId)}/events?after_sequence=0`, { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
        return await response.json() as { run_id: string; events: ApiEvent[] };
      })
      .then((result) => {
        if (result.run_id !== runId) throw new Error("Run ID 不匹配");
        setEvents(result.events);
        setStatus(`已从 FastAPI 回放 ${result.events.length} 条持久化事件；Run ${runId}`);
      })
      .catch((error: unknown) => { if (!controller.signal.aborted) setStatus(`读取失败：${error instanceof Error ? error.message : String(error)}`); });
    return () => controller.abort();
  }, [runId]);
  return <main className="trace-preview">
    <header><b>澄衡 Aetheris</b><span>真实执行记录预览</span></header>
    <p className="trace-preview-note">数据来源：FastAPI <code>/api/runs/:run_id/events</code> 回放本地 SQLite 事件；只读，不新建 Run，不展示隐藏思维链。</p>
    <div className="trace-preview-status" role="status">{status}</div>
    {runId && <ActivityTrace runId={runId} events={events} title="本轮执行记录" theme="light" />}
  </main>;
}

createRoot(document.getElementById("root")!).render(<TracePreview />);
