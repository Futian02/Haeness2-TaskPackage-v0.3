import type { UsagePeriod, UsageStats, UsageStatsFetcher } from "./types";

/** Offset is minutes east of UTC (inverse of Date#getTimezoneOffset). */
export const fetchUsageStats: UsageStatsFetcher = async (period: UsagePeriod, timezoneOffsetMinutes: number, signal?: AbortSignal) => {
  const query = new URLSearchParams({ period, tz_offset: String(timezoneOffsetMinutes) });
  const response = await fetch(`/api/stats?${query.toString()}`, { signal, headers: { Accept: "application/json" } });
  if (!response.ok) throw new Error(`统计读取失败 (${response.status})`);
  return await response.json() as UsageStats;
};
