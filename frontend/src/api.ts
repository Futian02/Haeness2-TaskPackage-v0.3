export type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  createdAt?: string;
  run_id?: string | null;
  attachments?: UploadedFile[];
};

export type Conversation = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
};

export type ConversationDetail = Conversation & { messages: Message[] };

export type Health = {
  status: string;
  /** Runtime protocol contract shared by the browser and FastAPI. Missing means legacy server. */
  contract_version?: string | null;
  capabilities?: Record<string, boolean | number | string> | null;
  build_fingerprint?: string | null;
  frontend_build_fingerprint?: string | null;
  build?: Record<string, unknown>;
  flags?: Record<string, unknown>;
  mode: "RULE_DEMO" | string;
  default_mode?: "RULE_DEMO" | "DEEPSEEK";
  llm?: { configured: boolean; provider?: string | null; model?: string | null; profile_id?: string | null };
  database: string;
  teacher_tools: string[];
};

export type RunCreated = {
  /** Client-only notice: older server accepted the bounded legacy request. */
  legacy_compatibility?: boolean;
  run_id: string;
  status: string;
  mode: string;
  web_mode?: "off" | "auto" | "on";
  events_url: string;
};

export type RunSummary = { id: string; conversation_id: string; status: string; mode: string; started_at: string; ended_at?: string | null; error_code?: string | null };
export type WebMode = "off" | "auto" | "on";

export type ApiEvent = {
  schema_version?: number;
  event_id?: string;
  run_id: string;
  session_id?: string;
  sequence: number;
  ts?: string;
  /** Backend currently emits `type`; newer additive events may use `kind`. */
  type?: string;
  kind?: string;
  agent?: string | null;
  payload: Record<string, unknown>;
};

export type PublicRunFailureCode = "provider_empty" | "provider_timeout" | "provider_rejected" | "provider_payment_required" | "content_filtered" | "output_limit" | "connection_lost" | "run_queued_capacity" | "tool_timeout" | "run_failed";
export type RunRequestFailureCode = "request_rate_limited" | "request_model_unavailable" | "request_validation" | "request_server_error" | "request_rejected";

export class RunRequestError extends Error {
  readonly code: RunRequestFailureCode;
  constructor(readonly status: number, readonly retryAfterSeconds?: number, responseBody = "") {
    const code: RunRequestFailureCode = status === 429 ? "request_rate_limited" : status === 503 && /model_profile_unavailable|DeepSeek.*未配置|profile.*unavailable/i.test(responseBody) ? "request_model_unavailable" : status === 422 ? "request_validation" : status >= 500 ? "request_server_error" : "request_rejected";
    const message = code === "request_rate_limited" ? "服务当前繁忙或队列已满（HTTP 429）。草稿与幂等请求标识已保留，可稍后重试。"
      : code === "request_model_unavailable" ? "所选模型配置不可用（HTTP 503）。草稿已保留；可切换到离线 RULE_DEMO 后明确发起新运行。"
      : code === "request_validation" ? "服务拒绝了当前请求（HTTP 422），请检查前后端版本及工况字段；草稿已保留。"
      : code === "request_server_error" ? `服务端暂时异常（HTTP ${status}）；草稿与幂等请求标识已保留。`
      : `Run 请求未被服务接受（HTTP ${status}）；草稿与幂等请求标识已保留。`;
    super(message);
    this.name = "RunRequestError";
    this.code = code;
  }
}

/** A deliberately sanitized error: provider bodies, prompts, and private reasoning never cross into UI text. */
export class RunStreamError extends Error {
  readonly code: PublicRunFailureCode;
  constructor(code: PublicRunFailureCode, readonly retryAfterSeconds?: number) {
    super(publicRunFailureMessage(code));
    this.name = "RunStreamError";
    this.code = code;
  }
}

export function publicRunFailureCode(value: unknown): PublicRunFailureCode {
  const code = typeof value === "string" ? value.toLowerCase() : "";
  if (/content.?filter|safety/.test(code)) return "content_filtered";
  if (/tool.?timeout/.test(code)) return "tool_timeout";
  if (/timeout|timed.?out/.test(code)) return "provider_timeout";
  if (/payment|required|http.?402/.test(code)) return "provider_payment_required";
  if (/length|max.?token|output.?limit/.test(code)) return "output_limit";
  if (/empty.?content|provider.?empty/.test(code)) return "provider_empty";
  if (/provider.?rejected|http.?400|http.?429|invalid.?request/.test(code)) return "provider_rejected";
  return "run_failed";
}

export function publicRunFailureMessage(code: PublicRunFailureCode): string {
  return ({
    provider_empty: "模型没有返回可显示内容。可重试，或缩短问题后再试。",
    provider_timeout: "本轮等待模型超时，尚未生成回复。",
    provider_rejected: "模型服务未接受本轮请求，请检查模型配置后重试。",
    provider_payment_required: "模型服务要求检查账户额度或付款方式；本轮未完成。",
    content_filtered: "模型服务未返回本轮内容，请调整问题后重试。",
    output_limit: "本轮输出达到长度上限，回复可能不完整；请重试或拆分问题。",
    connection_lost: "与服务的连接中断，本轮没有确认完成。",
    run_queued_capacity: "任务已进入队列，服务繁忙；重新连接不会重复提交。",
    tool_timeout: "本轮工具执行超时，未生成完整回复；可明确选择新一次执行。",
    run_failed: "本轮执行失败，尚未生成回复。",
  })[code];
}

export type RunInput = {
  question: string;
  equipment: string;
  equipment_type: string;
  material: string;
  medium: string[];
  operating_condition: string;
  field_evidence: string;
  mode: "RULE_DEMO" | "DEEPSEEK";
  web_mode?: WebMode;
  file_ids?: string[];
  model_profile_id?: string | null;
  /** Explicit per-run opt-in; false/absent keeps the request offline. */
  web_search_enabled?: boolean;
  /** Separate consent required before sensitive engineering text can leave the app. */
  allow_sensitive_web_search?: boolean;
};

export type ModelProfile = { id: string; provider: "deepseek" | "openai-compatible"; model: string; endpoint: string; key_configured: boolean; api_key_masked: string; enabled?: boolean };

export type UploadedFile = { id:string; conversation_id:string; file_sha256:string; original_name:string; content_type:string; size_bytes:number; uploaded_at:string; extraction_status:string; preview?:{status:string;text?:string;page_count?:number;message?:string} };

export const eventKind = (event: ApiEvent) => event.kind ?? event.type ?? "unknown_event";

class ApiHttpError extends Error {
  constructor(readonly status: number, readonly responseBody: string, statusText: string, readonly retryAfterSeconds?: number) {
    super(`${status} ${statusText}: ${responseBody}`);
    this.name = "ApiHttpError";
  }
}

/** Only the old backend's extra-forbidden V2 fields authorize a legacy retry. */
function isLegacyRunContractError(error: unknown): boolean {
  if (!(error instanceof ApiHttpError) || error.status !== 422) return false;
  try {
    const parsed = JSON.parse(error.responseBody) as { detail?: { type?: string; loc?: unknown[] }[] };
    if (!Array.isArray(parsed.detail) || parsed.detail.length === 0) return false;
    return parsed.detail.every(item => item.type === "extra_forbidden" &&
      Array.isArray(item.loc) && item.loc[0] === "body" &&
      ["web_mode", "web_search_enabled", "allow_sensitive_web_search", "model_profile_id"].includes(String(item.loc[1])));
  } catch { return false; }
}

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), 12_000);
  try {
    const response = await fetch(url, {
      ...init,
      signal: init?.signal ?? controller.signal,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
    if (!response.ok) {
      const message = (await response.text()).slice(0, 4000);
      const retryAfter = Number(response.headers.get("Retry-After"));
      throw new ApiHttpError(response.status, message, response.statusText, Number.isFinite(retryAfter) ? retryAfter : undefined);
    }
    return (await response.json()) as T;
  } finally {
    window.clearTimeout(timer);
  }
}

export const api = {
  health: () => requestJson<Health>("/api/health"),
  modelProfiles: () => requestJson<{ profiles: ModelProfile[]; active_profile_id: string | null; credential_store: string }>("/api/model-profiles"),
  saveModelProfile: (input: { provider:string; model:string; endpoint:string; api_key?:string }, id?:string) => requestJson<ModelProfile>(id ? `/api/model-profiles/${encodeURIComponent(id)}` : "/api/model-profiles", { method:id?"PATCH":"POST", body:JSON.stringify(input) }),
  deleteModelProfile: (id:string) => requestJson<{deleted:boolean}>(`/api/model-profiles/${encodeURIComponent(id)}`,{method:"DELETE"}),
  activateModelProfile: (id:string|null) => requestJson<{active_profile_id:string|null}>("/api/model-profiles/active",{method:"POST",body:JSON.stringify({profile_id:id})}),
  testModelProfile: (id:string) => requestJson<{ok:boolean;provider:string;model:string;latency_ms:number;usage:Record<string,number>;cost_warning:string}>(`/api/model-profiles/${encodeURIComponent(id)}/test`,{method:"POST",body:"{}"}),
  listConversations: (includeArchived = false) => requestJson<Conversation[]>(`/api/conversations${includeArchived ? "?include_archived=true" : ""}`),
  createConversation: (title = "新对话") =>
    requestJson<Conversation>("/api/conversations", {
      method: "POST",
      body: JSON.stringify({ title }),
    }),
  getConversation: (id: string, signal?: AbortSignal) =>
    requestJson<ConversationDetail>(`/api/conversations/${encodeURIComponent(id)}`, { signal }),
  listRuns: async (conversationId: string, signal?: AbortSignal) => {
    const result: RunSummary[]=[];
    const limit=100;let offset=0;let total=0;
    do {const page=await requestJson<{runs:RunSummary[];total:number}>(`/api/conversations/${encodeURIComponent(conversationId)}/runs?limit=${limit}&offset=${offset}`,{signal});result.push(...page.runs);total=page.total;offset+=page.runs.length;if(page.runs.length===0)break;} while(offset<total);
    return result;
  },
  createRun: async (conversationId: string, input: RunInput, idempotencyKey?: string) => {
    const endpoint = `/api/conversations/${encodeURIComponent(conversationId)}/runs`;
    const headers = idempotencyKey ? { "Idempotency-Key": idempotencyKey } : undefined;
    try {
      return await requestJson<RunCreated>(endpoint, { method: "POST", body: JSON.stringify(input), headers });
    } catch (error) {
      if (!isLegacyRunContractError(error)) {
        if (error instanceof ApiHttpError) throw new RunRequestError(error.status, error.retryAfterSeconds, error.responseBody);
        throw error;
      }
      // A legacy server cannot honor the explicit network or profile choice.
      // Do not silently downgrade an opt-in web request or selected provider.
      if (input.web_mode === "on" || input.web_search_enabled || input.model_profile_id || input.allow_sensitive_web_search) {
        throw new Error("BACKEND_VERSION_MISMATCH: 旧版后端不支持当前联网或模型配置，请升级运行中的服务。");
      }
      const legacy = {
        question: input.question, equipment: input.equipment, equipment_type: input.equipment_type,
        material: input.material, medium: input.medium, operating_condition: input.operating_condition,
        field_evidence: input.field_evidence, mode: input.mode, file_ids: input.file_ids ?? [],
      };
      try {
        const created = await requestJson<RunCreated>(endpoint, { method: "POST", body: JSON.stringify(legacy), headers });
        return { ...created, legacy_compatibility: true };
      } catch (retryError) {
        if (retryError instanceof ApiHttpError) throw new RunRequestError(retryError.status, retryError.retryAfterSeconds, retryError.responseBody);
        throw retryError;
      }
    }
  },
  uploadFiles: async (conversationId:string, files:File[]) => {
    if(files.length>5)throw new Error("每次最多选择 5 个文件");
    const form=new FormData();files.forEach(file=>form.append("files",file));
    const response=await fetch(`/api/conversations/${encodeURIComponent(conversationId)}/files`,{method:"POST",body:form});
    if(!response.ok)throw new Error(`${response.status}: ${(await response.text()).slice(0,300)}`);
    return (await response.json() as {files:UploadedFile[]}).files;
  },
  listFiles: async (conversationId:string) => (await requestJson<{files:UploadedFile[]}>(`/api/conversations/${encodeURIComponent(conversationId)}/files`)).files,
  previewFile: (conversationId:string,fileId:string) => requestJson<{status:string;text?:string;page_count?:number;message?:string}>(`/api/conversations/${encodeURIComponent(conversationId)}/files/${encodeURIComponent(fileId)}/preview`),
  renameConversation: (id:string,title:string) => requestJson<Conversation>(`/api/conversations/${encodeURIComponent(id)}`,{method:"PATCH",body:JSON.stringify({title})}),
  archiveConversation: (id:string,archived=true) => requestJson<Conversation>(`/api/conversations/${encodeURIComponent(id)}`,{method:"PATCH",body:JSON.stringify({archived})}),
  runInput: (runId:string) => requestJson<Record<string,unknown>>(`/api/runs/${encodeURIComponent(runId)}/input`),
  replay: (runId: string, afterSequence: number, signal?: AbortSignal) =>
    requestJson<{ run_id: string; events: ApiEvent[] }>(
      `/api/runs/${encodeURIComponent(runId)}/events?after_sequence=${afterSequence}`,
      { signal },
    ).then(result => ({ ...result, events: result.events.map(sanitizeApiEvent) })),
};

function parseSseBlock(block: string): ApiEvent | null {
  const data = block
    .split(/\r?\n/)
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice(5).trimStart())
    .join("\n");
  if (!data) return null;
  try {
    return sanitizeApiEvent(JSON.parse(data) as ApiEvent);
  } catch {
    return null;
  }
}

async function readSse(
  url: string,
  runId: string,
  seen: Map<number, ApiEvent>,
  onEvent: (event: ApiEvent) => void,
  signal?: AbortSignal,
): Promise<boolean> {
  const response = await fetch(url, { headers: { Accept: "text/event-stream" }, signal });
  if (!response.ok) {
    let payload: any = null;
    try { payload = await response.clone().json(); } catch { /* sanitized below */ }
    const retryAfter = Number(response.headers.get("Retry-After"));
    if (response.status === 429 && payload?.detail?.code === "WORKER_CAPACITY")
      throw new RunStreamError("run_queued_capacity", Number.isFinite(retryAfter) ? retryAfter : undefined);
    throw new Error(`SSE 连接失败 (${response.status})`);
  }
  if (!response.body) throw new Error("SSE 响应缺少数据流");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let terminal = false;
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const blocks = buffer.split(/\r?\n\r?\n/);
      buffer = blocks.pop() ?? "";
      for (const block of blocks) {
        const event = parseSseBlock(block);
        if (!event || event.run_id !== runId || !Number.isFinite(event.sequence)) continue;
        if (seen.has(event.sequence)) continue;
        seen.set(event.sequence, event);
        onEvent(event);
        const kind = eventKind(event);
        if (kind === "run_completed" || kind === "run_failed" || kind === "error") terminal = true;
      }
    }
    if (buffer.trim()) {
      const event = parseSseBlock(buffer);
      if (event && event.run_id === runId && !seen.has(event.sequence)) {
        seen.set(event.sequence, event);
        onEvent(event);
        terminal = ["run_completed", "run_failed", "error"].includes(eventKind(event));
      }
    }
  } finally {
    reader.releaseLock();
  }
  return terminal;
}

/**
 * Attach only to the already-created run. Reconnect uses replay-after-sequence;
 * it never POSTs a second run. Event ids are de-duplicated by run_id+sequence.
 */
export async function consumeRun(
  run: RunCreated,
  onEvent: (event: ApiEvent) => void,
  signal?: AbortSignal,
  maxReconnects = 5,
): Promise<ApiEvent[]> {
  const seen = new Map<number, ApiEvent>();
  let url = new URL(run.events_url, window.location.origin).toString();
  let terminal = false;
  let attempts = 0;
  while (!terminal) {
    try {
      terminal = await readSse(url, run.run_id, seen, onEvent, signal);
    } catch (error) {
      if (signal?.aborted) throw error;
      // POST already created this run. Capacity 429 is not a dropped SSE
      // connection: surface queued state and let the UI reattach to this rid.
      if (error instanceof RunStreamError && error.code === "run_queued_capacity") throw error;
      if (attempts >= maxReconnects) throw error;
    }
    if (terminal) break;
    const replayed = await api.replay(run.run_id, Math.max(0, ...seen.keys()), signal);
    for (const event of replayed.events) {
      if (seen.has(event.sequence)) continue;
      seen.set(event.sequence, event);
      onEvent(event);
      if (["run_completed", "run_failed", "error"].includes(eventKind(event))) terminal = true;
    }
    if (terminal) break;
    if (attempts >= maxReconnects) throw new Error("SSE 多次重连仍未收到 run 终态事件");
    attempts += 1;
    await new Promise<void>((resolve, reject) => {
      const timer = window.setTimeout(resolve, Math.min(500 * 2 ** attempts, 3_000));
      signal?.addEventListener(
        "abort",
        () => {
          window.clearTimeout(timer);
          reject(signal.reason ?? new DOMException("已取消", "AbortError"));
        },
        { once: true },
      );
    });
    url = new URL(run.events_url, window.location.origin).toString();
  }
  const ordered = [...seen.values()].sort((a, b) => a.sequence - b.sequence);
  const failure = ordered.find((event) => ["run_failed", "error"].includes(eventKind(event)));
  if (failure) throw new RunStreamError(publicRunFailureCode(failure.payload?.code ?? failureKind(failure)));
  if (!ordered.some((event) => eventKind(event) === "run_completed")) throw new RunStreamError("connection_lost");
  return ordered;
}

function failureKind(event: ApiEvent): unknown { return eventKind(event); }

function sanitizeApiEvent(event: ApiEvent): ApiEvent {
  if (!["error", "run_failed"].includes(eventKind(event))) return event;
  return { ...event, payload: { code: publicRunFailureCode(event.payload?.code ?? eventKind(event)) } };
}
