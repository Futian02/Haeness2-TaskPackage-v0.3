import { eventKind, type ApiEvent } from "../api";

export type ActivityStatus = "running" | "complete" | "incomplete" | "requires-action";
export type ActivityStep = {
  id: string;
  runId: string;
  stageKey: string;
  sequence: number;
  type: string;
  title: string;
  agent: string;
  phase: string;
  iteration?: number;
  stepId?: string;
  parentStepId?: string;
  status: ActivityStatus;
  timestamp?: string;
  durationMs?: number;
  summary: string;
  publicRationale?: string;
  tool?: { id: string; name: string; status: ActivityStatus; args: Record<string, unknown>; result?: unknown; sourceIds: string[]; durationMs?: number };
  sources: { id: string; clauseNo?: string; page?: number; verificationLevel?: string }[];
};
export type ActivityStage = {
  id: string;
  label: string;
  phase: string;
  agent: string;
  iteration?: number;
  status: ActivityStatus;
  firstSequence: number;
  lastSequence: number;
  eventCount: number;
  toolCount: number;
  tools: string[];
  reviewCount: number;
  citationCount: number;
  durationMs?: number;
  durationSource?: "reported" | "event-span";
  summary?: string;
  steps: ActivityStep[];
};

const object = (value: unknown): Record<string, unknown> => value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
const str = (value: unknown) => typeof value === "string" ? value : "";
const num = (value: unknown) => typeof value === "number" && Number.isFinite(value) ? value : undefined;
const ARG_ALLOWLIST = new Set(["keyword", "standard_code", "clause_no", "top_k", "knowledge_type", "material", "medium", "temperature_c", "pressure_mpa", "equipment_type"]);
const SENSITIVE_KEY = /api[_-]?key|token|authorization|password|secret|device.?id|serial|prompt|content|quote|text|input|file|path|cookie|email|phone/i;

/** Public trace is a projection, never a copy of raw tool payloads. */
export function sanitizePublicText(value: unknown, maxLength = 240): string {
  if (typeof value !== "string") return "";
  let safe = value.slice(0, maxLength);
  if (/^\s*[\[{]/.test(safe) && /["'][\w-]+["']\s*:/.test(safe)) return "已记录公开摘要（详细原始数据已隐藏）";
  safe = safe
    .replace(/(api[_-]?key|access[_-]?token|authorization|password|secret|cookie)\s*[:=]\s*[^\s,;，；：]+/gi, "$1=[已脱敏]")
    .replace(/[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}/g, "[邮箱已脱敏]")
    .replace(/\b(?:\+?\d[\d ()-]{7,}\d)\b/g, "[联系方式已脱敏]")
    .replace(/设备(?:编号|ID)[：:=#-]?\s*[A-Za-z0-9_-]{4,}/gi, "设备标识[已脱敏]")
    .replace(/(?:SN|S\/N|serial)\s*[:：=#-]?\s*[A-Za-z0-9_-]{4,}/gi, "设备标识[已脱敏]")
    .replace(/\b-?\d+(?:\.\d+)?\s*(?:℃|°C|MPa|kPa|bar|psi)(?=\s|[,，;；。]|$)/gi, "[工况数值已脱敏]");
  return safe;
}

const safeArgs = (value: unknown): Record<string, unknown> => {
  const args = object(value);
  const result: Record<string, unknown> = {};
  for (const [key, val] of Object.entries(args)) {
    if (!ARG_ALLOWLIST.has(key) || SENSITIVE_KEY.test(key)) continue;
    if (key === "keyword") {
      result[key] = "已记录（查询条件已脱敏）";
    } else if (["material", "medium", "temperature_c", "pressure_mpa", "equipment_type"].includes(key)) {
      result[key] = "已记录（具体值已脱敏）";
    } else if (key === "top_k" && typeof val === "number" && Number.isFinite(val)) {
      result[key] = Math.max(1, Math.min(50, Math.trunc(val)));
    } else if (typeof val === "string") {
      result[key] = sanitizePublicText(val, 80);
    } else if (typeof val === "number" && Number.isFinite(val)) {
      result[key] = val;
    }
  }
  return result;
};
const sourceRows = (payload: Record<string, unknown>) => {
  const direct = str(payload.clause_id ?? payload.id) ? [payload] : [];
  const raw = Array.isArray(payload.sources) ? payload.sources : Array.isArray(payload.source) ? payload.source : direct;
  return raw.flatMap((item) => {
    const row = object(item);
    const id = str(row.clause_id ?? row.id);
    if (!id) return [];
    return [{ id, clauseNo: str(row.clause_no) || undefined, page: num(row.page), verificationLevel: str(row.verification_level) || undefined }];
  });
};

const TITLES: Record<string, string> = {
  run_started: "任务开始", phase_started: "阶段开始", phase_completed: "阶段完成", agent_started: "执行阶段", agent_completed: "阶段完成", agent_finished: "阶段完成",
  subtask_started: "子任务开始", subtask_completed: "子任务完成", subtask_skipped: "子任务跳过",
  tool_called: "调用工具", tool_result: "工具结果", reference_added: "来源引用", decision_summary: "公开决策摘要",
  claim_added: "结论待核", claim_checked: "结论核验", contradiction_found: "发现矛盾", requires_human_review: "待人工审核",
  verification: "证据核验", token_delta: "回答生成", run_completed: "任务完成", error: "执行错误",
  llm_started: "模型整理开始", llm_completed: "模型文字整理（非内部思维链）",
};
const STATUS_TERMINAL = new Set(["run_completed", "error"]);

/** Converts only persisted API events. Missing phase/iteration stay legacy rather than being guessed. */
export function projectActivity(events: readonly ApiEvent[]): ActivityStep[] {
  const seen = new Map<string, ApiEvent>();
  for (const event of events) {
    if (!event.run_id || !Number.isFinite(event.sequence)) continue;
    const key = `${event.run_id}:${event.sequence}`;
    if (!seen.has(key)) seen.set(key, event);
  }
  const ordered = [...seen.values()].sort((a, b) => a.run_id.localeCompare(b.run_id) || a.sequence - b.sequence);
  const pendingByStep = new Map<string, ActivityStep>();
  const pendingByName = new Map<string, ActivityStep[]>();
  const steps: ActivityStep[] = [];
  for (const event of ordered) {
    const type = eventKind(event);
    const payload = object(event.payload);
    const agent = str(event.agent ?? payload.agent) || "unknown";
    const phase = str(payload.phase) || "legacy";
    const iteration = num(payload.iteration);
    const callName = str(payload.tool ?? payload.tool_name);
    const callId = str(payload.tool_call_id ?? payload.call_id) || `${event.run_id}:${event.sequence}`;
    const step: ActivityStep = {
      id: `${event.run_id}:${event.sequence}`, runId: event.run_id, stageKey: "", sequence: event.sequence, type,
      title: TITLES[type] ?? type.replaceAll("_", " "), agent, phase, iteration,
      stepId: str(payload.step_id) || undefined, parentStepId: str(payload.parent_step_id) || undefined,
      status: type === "tool_called" ? "running" : type === "error" ? "incomplete" : type === "requires_human_review" ? "requires-action" : "complete",
      timestamp: event.ts, durationMs: num(payload.duration_ms),
      summary: sanitizePublicText(payload.public_rationale ?? payload.summary ?? payload.message ?? payload.status ?? payload.verdict ?? ""),
      publicRationale: sanitizePublicText(payload.public_rationale) || publicEventSummary(type, payload),
      sources: sourceRows(payload),
    };
    if (type === "tool_called") {
      step.tool = { id: callId, name: callName || "unknown_tool", status: "running", args: safeArgs(payload.args), sourceIds: [] };
      const byStepKey = step.stepId ? `${event.run_id}:${step.stepId}` : `${event.run_id}:${callId}`;
      pendingByStep.set(byStepKey, step);
      const byNameKey = `${event.run_id}:${callName}`;
      pendingByName.set(byNameKey, [...(pendingByName.get(byNameKey) ?? []), step]);
      steps.push(step);
      continue;
    }
    if (type === "tool_result") {
      const resultStepId = str(payload.step_id);
      const byStepKey = resultStepId ? `${event.run_id}:${resultStepId}` : "";
      const byNameKey = `${event.run_id}:${callName}`;
      const queue = pendingByName.get(byNameKey) ?? [];
      const invoked = (byStepKey && pendingByStep.get(byStepKey)) || queue.find((candidate) => candidate.tool?.status === "running");
      if (invoked?.tool) {
        const result = object(payload.result);
        invoked.tool.status = str(result.status) === "error" || result.status === "failed" ? "incomplete" : "complete";
        invoked.tool.result = sanitizeSummary(result);
        invoked.tool.sourceIds = sourceRows(result).map((x) => x.id);
        invoked.tool.durationMs = num(payload.duration_ms);
        invoked.summary = `工具已返回${invoked.tool.sourceIds.length ? ` · ${invoked.tool.sourceIds.length} 项来源` : ""}`;
        if (invoked.stepId) pendingByStep.delete(`${event.run_id}:${invoked.stepId}`);
        else pendingByStep.delete(`${event.run_id}:${invoked.tool.id}`);
        pendingByName.set(byNameKey, queue.filter((candidate) => candidate !== invoked));
      }
    }
    if (STATUS_TERMINAL.has(type)) {
      for (const item of pendingByStep.values()) if (item.runId === event.run_id && item.tool) item.tool.status = "incomplete";
    }
    steps.push(step);
  }
  return assignStageKeys(steps);
}

function stageBase(step: ActivityStep) {
  if (["claim_added", "claim_checked", "contradiction_found", "requires_human_review", "review_result"].includes(step.type)) return "review:claims";
  if (step.type === "llm_started" || step.type === "llm_completed" || step.phase === "report") return "report:summary";
  if (step.phase !== "legacy") return `${step.phase}:${step.iteration ?? "-"}`;
  return `legacy:${step.agent}`;
}

function assignStageKeys(steps: ActivityStep[]) {
  let previous = "";
  let ordinal = 0;
  for (const step of steps) {
    const base = stageBase(step);
    if (base !== previous) ordinal += 1;
    step.stageKey = `${step.runId}:stage-${ordinal}:${base}`;
    previous = base;
  }
  return steps;
}

const PHASE_LABELS: Record<string, string> = {
  route: "任务分流", plan: "调查规划", investigate: "调查", evidence_gate: "证据门禁",
  review_dispatch: "审核调度", auditor: "证据审核", evidence_auditor: "证据审核",
  skeptic: "独立反证", review_merge: "审核汇总", review_gate: "审核门禁",
  report: "报告整理", legacy: "执行记录",
};

function stageLabel(step: ActivityStep) {
  if (step.type === "claim_added" || step.type === "claim_checked" || step.type === "contradiction_found" || step.type === "requires_human_review" || step.type === "review_result") return "审核结果";
  if (step.type === "llm_started" || step.type === "llm_completed") return "模型文字整理";
  if (step.phase === "legacy") return step.title;
  return PHASE_LABELS[step.phase] ?? (step.phase !== "legacy" ? step.phase.replaceAll("_", " ") : step.title);
}

function eventSpan(steps: readonly ActivityStep[]) {
  const instants = steps.map((step) => Date.parse(step.timestamp ?? "")).filter(Number.isFinite);
  return instants.length > 1 ? Math.max(...instants) - Math.min(...instants) : undefined;
}

/** Groups adjacent real SQLite/SSE steps by their recorded phase and iteration. */
export function groupActivityStages(steps: readonly ActivityStep[]): ActivityStage[] {
  const stages: ActivityStage[] = [];
  for (const step of steps) {
    let stage = stages.at(-1);
    if (!stage || stage.id !== step.stageKey) {
      stage = {
        id: step.stageKey, label: stageLabel(step), phase: step.phase, agent: step.agent,
        iteration: step.iteration, status: "complete", firstSequence: step.sequence,
        lastSequence: step.sequence, eventCount: 0, toolCount: 0, tools: [], reviewCount: 0,
        citationCount: 0, steps: [],
      };
      stages.push(stage);
    }
    stage.steps.push(step);
    stage.eventCount += 1;
    stage.lastSequence = step.sequence;
    if (step.type === "tool_called") { stage.toolCount += 1; if (step.tool?.name && !stage.tools.includes(step.tool.name)) stage.tools.push(step.tool.name); }
    if (["review_started", "review_result", "claim_checked", "contradiction_found", "requires_human_review"].includes(step.type)) stage.reviewCount += 1;
    stage.citationCount = new Set(stage.steps.flatMap((item) => [...item.sources.map((source) => source.id), ...(item.tool?.sourceIds ?? [])])).size;
    if (step.type === "error" || step.status === "incomplete") stage.status = "incomplete";
    else if (step.status === "requires-action") stage.status = "requires-action";
    else if (step.tool?.status === "running") stage.status = "running";
    const reported = stage.steps.map((item) => item.durationMs).filter((value): value is number => typeof value === "number" && value > 0);
    const span = eventSpan(stage.steps);
    if (reported.length) { stage.durationMs = reported.reduce((sum, value) => sum + value, 0); stage.durationSource = "reported"; }
    else if (span !== undefined && span > 0) { stage.durationMs = span; stage.durationSource = "event-span"; }
    stage.summary = stage.steps.map((item) => item.publicRationale).filter((value): value is string => Boolean(value)).slice(0, 2).join(" · ") || undefined;
  }
  const allEnded = steps.some((step) => step.type === "run_completed" || step.type === "error");
  if (!allEnded && stages.length && stages.at(-1)?.status === "complete") stages[stages.length - 1].status = "running";
  return stages;
}

function publicEventSummary(type: string, payload: Record<string, unknown>) {
  if (type === "subtask_started" || type === "subtask_completed" || type === "subtask_skipped") {
    const id = safeEnum(payload.subtask_id);
    const kind = safeEnum(payload.kind);
    const status = safeEnum(payload.status);
    const sources = Array.isArray(payload.source_ids) ? payload.source_ids.length : 0;
    return [id ? `子任务 ${id}` : "子任务", kind, status, sources ? `来源 ${sources} 项` : ""].filter(Boolean).join(" · ");
  }
  if (type === "llm_completed") return sanitizePublicText(payload.summary, 360) || "模型已完成文字整理";
  if (type === "decision_summary") return decisionSummary(payload);
  if (type === "agent_started") return `已记录阶段启动${safeEnum(payload.route) ? ` · ${safeEnum(payload.route)}` : ""}`;
  if (type === "agent_completed" || type === "agent_finished") return `阶段已结束${safeEnum(payload.status) ? ` · ${safeEnum(payload.status)}` : ""}`;
  if (type === "requires_human_review") return `审核状态：${safeEnum(payload.review_status ?? payload.status) || "需人工复核"}`;
  if (type === "contradiction_found") return `记录到矛盾事件${safeEnum(payload.verdict) ? ` · ${safeEnum(payload.verdict)}` : ""}`;
  if (type === "reference_added") {
    const refs = sourceRows(payload);
    return refs.length ? `已关联来源 ${refs.map((ref) => `${ref.id}${ref.page ? ` · p.${ref.page}` : ""}${ref.verificationLevel ? ` · ${ref.verificationLevel}` : ""}`).join("；")}` : undefined;
  }
  if (type === "error") return sanitizePublicText(payload.message, 120) ? `执行错误：${sanitizePublicText(payload.message, 120)}` : "执行遇到错误";
  return undefined;
}

function safeEnum(value: unknown) {
  if (typeof value !== "string" || !/^[a-zA-Z0-9_.-]{1,48}$/.test(value)) return "";
  return value;
}

function decisionSummary(payload: Record<string, unknown>) {
  const fields = [
    safeEnum(payload.route) ? `路由：${safeEnum(payload.route)}` : "",
    typeof payload.evidence_count === "number" ? `证据 ${payload.evidence_count} 项` : "",
    typeof payload.candidate_count === "number" ? `候选 ${payload.candidate_count} 项` : "",
    typeof payload.claim_count === "number" ? `声明 ${payload.claim_count} 项` : "",
    typeof payload.gap_count === "number" && payload.gap_count > 0 ? `信息缺口 ${payload.gap_count} 项` : "",
  ].filter(Boolean);
  return fields.length ? fields.join(" · ") : undefined;
}

function sanitizeSummary(value: unknown): unknown {
  if (Array.isArray(value)) return value.slice(0, 8).map(sanitizeSummary);
  if (value && typeof value === "object") {
    const visible = /^(status|in_domain|count|total|clause_id|clause_no|standard_code|title|name|score|match_level|verification_level|page|hits|mechanisms|source|sources|result|message)$/i;
    return Object.fromEntries(Object.entries(value as Record<string, unknown>).filter(([key]) => visible.test(key) && !SENSITIVE_KEY.test(key)).slice(0, 16).map(([key, item]) => [key, sanitizeSummary(item)]));
  }
  return typeof value === "string" ? sanitizePublicText(value, 120) : typeof value === "number" || typeof value === "boolean" ? value : undefined;
}

export function summarizeActivity(steps: readonly ActivityStep[]) {
  const tools = steps.filter((step) => step.type === "tool_called");
  const pendingReview = steps.filter((step) => step.status === "requires-action").length;
  const citations = new Set(steps.flatMap((step) => [...step.sources.map((source) => source.id), ...(step.tool?.sourceIds ?? [])])).size;
  const reviewCount = steps.filter((step) => step.type === "review_started").length;
  const elapsedMs = eventSpan(steps);
  const failed = steps.some((step) => step.type === "error");
  const completed = steps.some((step) => step.type === "run_completed");
  const running = !completed && !failed && steps.length > 0;
  const status = running ? "执行中" : failed ? "执行失败" : tools.length ? "调查完成" : steps.some((step) => step.type === "llm_completed") ? "对话完成" : completed ? "任务完成" : "执行记录";
  return { stepCount: steps.length, toolCount: tools.length, reviewCount, pendingReview, citations, elapsedMs, running, failed, completed, status };
}
