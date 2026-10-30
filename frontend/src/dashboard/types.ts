export type UsagePeriod = "today" | "7d" | "30d";

export type UsageStats = {
  period: UsagePeriod;
  timezone_offset_minutes: number;
  range: { start_utc: string; end_utc_exclusive: string };
  generated_at_utc: string;
  archive_policy: "included";
  counts: {
    conversations: number;
    messages_sent: number;
    messages_total: number;
    runs: number;
    model_calls: number;
    tool_calls: number;
    average_run_ms: number | null;
  };
  token_usage: {
    availability: "recorded" | "not_recorded";
    prompt_tokens: number | null;
    completion_tokens: number | null;
    total_tokens: number | null;
  };
  status_distribution: Record<string, number>;
  task_distribution: { key: string; count: number }[];
  mode_distribution: { key: string; count: number }[];
  hourly_runs: { hour: number; count: number }[];
};

export type UsageStatsFetcher = (period: UsagePeriod, timezoneOffsetMinutes: number, signal?: AbortSignal) => Promise<UsageStats>;
