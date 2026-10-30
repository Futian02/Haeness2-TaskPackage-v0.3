import { useEffect, useMemo, useState } from "react";
import { fetchUsageStats } from "./client";
import type { UsagePeriod, UsageStats, UsageStatsFetcher } from "./types";
import "./usage-dashboard.css";

const PERIODS: { key: UsagePeriod; label: string }[] = [
  { key: "today", label: "今天" }, { key: "7d", label: "近 7 天" }, { key: "30d", label: "近 30 天" },
];
const TASK_LABELS: Record<string, string> = {
  general_chat: "日常聊天", standard_lookup: "标准查询", diagnosis: "工程研判",
  missing_context: "补充信息", unknown: "未分类",
};
const STATUS_LABELS: Record<string, string> = {
  success: "已完成", needs_evidence: "待补证", failed: "失败", running: "进行中", other: "其他",
};
const COLORS = ["#6da98b", "#7d9fc4", "#e6b36b", "#bb7d7d", "#9a91bd", "#8ca6a1"];

export type UsageDashboardProps = {
  /** If omitted, the dashboard owns its period tabs. */
  period?: UsagePeriod;
  onPeriodChange?: (period: UsagePeriod) => void;
  fetchStats?: UsageStatsFetcher;
};

export function UsageDashboard({ period, onPeriodChange, fetchStats = fetchUsageStats }: UsageDashboardProps) {
  const [localPeriod, setLocalPeriod] = useState<UsagePeriod>(period ?? "today");
  const activePeriod = period ?? localPeriod;
  const [stats, setStats] = useState<UsageStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    fetchStats(activePeriod, -new Date().getTimezoneOffset(), controller.signal)
      .then((data) => { if (!controller.signal.aborted) setStats(data); })
      .catch((cause: unknown) => {
        if (controller.signal.aborted) return;
        setError(cause instanceof Error ? cause.message : "统计读取失败");
      })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [activePeriod, fetchStats]);

  const changePeriod = (next: UsagePeriod) => {
    setLocalPeriod(next);
    onPeriodChange?.(next);
  };
  const statsEmpty = !stats || stats.counts.runs === 0;
  const taskData = useMemo(() => (stats?.task_distribution ?? []).map((item) => ({
    key: item.key, label: TASK_LABELS[item.key] ?? item.key, count: item.count,
  })), [stats]);
  const statusData = useMemo(() => Object.entries(stats?.status_distribution ?? {})
    .filter(([, count]) => count > 0)
    .map(([key, count]) => ({ key, label: STATUS_LABELS[key] ?? key, count })), [stats]);

  return <section className="usage-dashboard" aria-label="今日活动与使用统计">
    <header className="usage-dashboard__header">
      <div><p className="usage-dashboard__eyebrow">活动概览</p><h2>今日活动</h2>
        {stats && <p className="usage-dashboard__range">{formatRange(stats.range.start_utc, stats.range.end_utc_exclusive)} · SQLite 历史记录（含已归档会话）</p>}
      </div>
      <div className="usage-dashboard__period" role="tablist" aria-label="统计时间范围">
        {PERIODS.map((item) => <button key={item.key} type="button" role="tab" aria-selected={activePeriod === item.key}
          className={activePeriod === item.key ? "is-active" : ""} onClick={() => changePeriod(item.key)}>{item.label}</button>)}
      </div>
    </header>

    {loading && <div className="usage-dashboard__state" role="status">正在读取本地统计…</div>}
    {!loading && error && <div className="usage-dashboard__state usage-dashboard__state--error" role="alert">{error}</div>}
    {!loading && !error && stats && <>
      <div className="usage-dashboard__metrics">
        <Metric label="对话" value={stats.counts.conversations} />
        <Metric label="发送消息" value={stats.counts.messages_sent} />
        <Metric label="运行" value={stats.counts.runs} />
        <Metric label="模型调用" value={stats.counts.model_calls} />
        <Metric label="工具调用" value={stats.counts.tool_calls} />
        <Metric label="平均耗时" value={stats.counts.average_run_ms === null ? "—" : `${formatDuration(stats.counts.average_run_ms)}`} />
        <Metric label="Token 使用" value={formatTokens(stats.token_usage.total_tokens)} detail={stats.token_usage.availability === "recorded" ? `输入 ${formatTokens(stats.token_usage.prompt_tokens)} · 输出 ${formatTokens(stats.token_usage.completion_tokens)}` : "未记录（未从模型响应取得 usage）"} />
      </div>
      {statsEmpty ? <div className="usage-dashboard__empty">所选时间范围内暂无运行记录。</div> : <>
        <div className="usage-dashboard__charts">
          <DonutChart title="任务类别" data={taskData} emptyLabel="暂无任务分类数据" />
          <DonutChart title="运行状态" data={statusData} emptyLabel="暂无状态数据" />
        </div>
        {activePeriod === "today" && <HourlyChart data={stats.hourly_runs} />}
      </>}
      <footer className="usage-dashboard__footer">Token 仅统计 SQLite 中模型响应实际记录的 usage；无数据时显示“未记录”。</footer>
    </>}
    {!loading && !error && !stats && <div className="usage-dashboard__empty">暂无统计数据。</div>}
  </section>;
}

function Metric({ label, value, detail }: { label: string; value: string | number; detail?: string }) {
  return <article className="usage-metric"><span>{label}</span><strong>{value}</strong>{detail && <small>{detail}</small>}</article>;
}

function DonutChart({ title, data, emptyLabel }: { title: string; data: { key: string; label: string; count: number }[]; emptyLabel: string }) {
  const total = data.reduce((sum, item) => sum + item.count, 0);
  const radius = 37;
  const circumference = 2 * Math.PI * radius;
  let offset = 0;
  return <article className="usage-chart-card"><h3>{title}</h3>
    {total === 0 ? <p className="usage-chart-empty">{emptyLabel}</p> : <div className="usage-donut-layout">
      <svg className="usage-donut" viewBox="0 0 100 100" role="img" aria-label={`${title}，共 ${total} 项`}>
        <circle cx="50" cy="50" r={radius} fill="none" stroke="var(--usage-track)" strokeWidth="12" />
        {data.map((item, index) => {
          const length = circumference * item.count / total;
          const circle = <circle key={item.key} cx="50" cy="50" r={radius} fill="none" stroke={COLORS[index % COLORS.length]} strokeWidth="12"
            strokeDasharray={`${length} ${circumference - length}`} strokeDashoffset={-offset} transform="rotate(-90 50 50)" />;
          offset += length;
          return circle;
        })}
        <text x="50" y="49" textAnchor="middle" className="usage-donut__value">{total}</text>
        <text x="50" y="61" textAnchor="middle" className="usage-donut__caption">总运行</text>
      </svg>
      <ul className="usage-legend">{data.map((item, index) => <li key={item.key}><i style={{ background: COLORS[index % COLORS.length] }} />
        <span>{item.label}</span><strong>{item.count}</strong></li>)}</ul>
    </div>}
  </article>;
}

function HourlyChart({ data }: { data: { hour: number; count: number }[] }) {
  const counts = Array.from({ length: 24 }, (_, hour) => data.find((row) => row.hour === hour)?.count ?? 0);
  const max = Math.max(1, ...counts);
  return <article className="usage-chart-card usage-hourly"><h3>今日每小时运行</h3>
    <div className="usage-hourly__bars" role="img" aria-label={`今日每小时运行次数，总计 ${counts.reduce((sum, n) => sum + n, 0)}`}>
      {counts.map((count, hour) => <div key={hour} className="usage-hourly__column" title={`${String(hour).padStart(2, "0")}:00 · ${count} 次`}>
        <span className="usage-hourly__bar" style={{ height: `${count ? Math.max(5, count / max * 100) : 0}%` }} />
        {hour % 3 === 0 && <small>{String(hour).padStart(2, "0")}</small>}
      </div>)}
    </div>
  </article>;
}

function formatTokens(value: number | null) { return value === null ? "未记录" : value.toLocaleString(); }
function formatDuration(ms: number) { return ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(1)} s`; }
function formatRange(start: string, endExclusive: string) {
  const startDate = new Date(start);
  const last = new Date(new Date(endExclusive).getTime() - 1);
  const date = (value: Date) => new Intl.DateTimeFormat("zh-CN", { month: "2-digit", day: "2-digit" }).format(value);
  return date(startDate) === date(last) ? date(startDate) : `${date(startDate)} – ${date(last)}`;
}

