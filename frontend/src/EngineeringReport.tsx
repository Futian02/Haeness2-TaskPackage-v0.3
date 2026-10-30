import type { ApiEvent, Message } from "./api";
import { eventKind } from "./api";
import type { ClaimCard } from "./uiModel";

export type RunSnapshot = {
  runId: string;
  conversationId: string;
  capturedAt: string;
  mode?: "RULE_DEMO" | "DEEPSEEK";
  webMode?: "off" | "auto" | "on";
  question: string;
  context: {
    equipment?: string;
    equipment_type?: string;
    material?: string;
    medium?: string[];
    operating_condition?: string;
    field_evidence?: string;
  };
  attachments?: {id:string;original_name:string;content_type:string;size_bytes:number;extraction_status:string}[];
  historyMessageCount?:number;
  historyMessageIds?:string[];
  historyIncluded?:boolean;
};

type Props = { messages: Message[]; events: ApiEvent[]; claims: ClaimCard[]; runId: string | null; snapshot: RunSnapshot | null };
type Fact = { label: string; value: string; provenance: "reported" | "observed" | "inferred"; source: string };

const gapLabels: Record<string, string> = {
  "condition:temperature": "操作温度", "condition:pressure": "操作压力", "condition:service_years": "投用年限", "condition:thickness": "实测壁厚",
  temperature: "操作温度", pressure: "操作压力", service_years: "投用年限", thickness: "实测壁厚",
};

function readable(value: unknown): string | undefined {
  if (typeof value === "string" && value.trim()) return value.trim();
  if (Array.isArray(value)) return value.map(readable).filter(Boolean).join("；") || undefined;
  if (value && typeof value === "object") {
    const record = value as Record<string, unknown>;
    return readable(record.value ?? record.counterevidence ?? record.contradiction ?? record.finding ?? record.summary ?? record.text);
  }
  return undefined;
}

function gapsFromClaims(claims: ClaimCard[]): string[] {
  const gaps = new Set<string>();
  for (const claim of claims) {
    const checks = claim.latest.payload.checks;
    if (!Array.isArray(checks)) continue;
    for (const item of checks) {
      if (!item || typeof item !== "object") continue;
      const check = String((item as Record<string, unknown>).check ?? "");
      const status = String((item as Record<string, unknown>).status ?? "");
      if ((status === "unknown" || status === "not_specified" || status === "missing") && (check.startsWith("condition:") || Object.hasOwn(gapLabels, check))) gaps.add(gapLabels[check] ?? check.replace(/^condition:/, ""));
    }
  }
  return [...gaps].filter(Boolean);
}

function reportedFacts(runId: string | null, snapshot: RunSnapshot | null): Fact[] {
  if (!runId || !snapshot || snapshot.runId !== runId) return [];
  const context = snapshot.context ?? {};
  const fields: [string, unknown][] = [
    ["设备名称", context.equipment], ["设备类型", context.equipment_type], ["材质", context.material],
    ["介质", context.medium], ["运行工况", context.operating_condition], ["现场证据", context.field_evidence],
  ];
  const facts = fields.flatMap(([label, value]) => { const text = readable(value); return text ? [{ label, value: text, provenance: "reported" as const, source: "本轮提交的设备/工况字段" }] : []; });
  const question = snapshot.question.trim();
  if (question) facts.push({ label: "用户问题", value: question, provenance: "reported", source: "本轮不可变输入快照" });
  return facts;
}

function eventFacts(events: ApiEvent[], runId: string | null) {
  const scoped = runId ? events.filter(event => event.run_id === runId) : [];
  const observed: Fact[] = [];
  const inferred: Fact[] = [];
  for (const event of scoped) {
    const payload = event.payload ?? {};
    const isConfirmed = payload.provenance === "user_confirmed" || payload.source_status === "confirmed";
    const candidates: [string, unknown][] = [["现场观察", payload.observation], ["现场观察", payload.observations], ["字段证据", payload.field_evidence]];
    for (const [label, value] of candidates) {
      const text = readable(value);
      if (!text) continue;
      const item = { label, value: text, provenance: isConfirmed ? "observed" as const : "inferred" as const, source: `${eventKind(event)} · #${event.sequence}` };
      (isConfirmed ? observed : inferred).push(item);
    }
    // Agent summaries are never promoted to reported/observed facts.
    const summary = readable(payload.summary);
    if (summary) inferred.push({ label: "Agent 摘要（待核）", value: summary, provenance: "inferred", source: `${eventKind(event)} · #${event.sequence}` });
  }
  return { observed, inferred };
}

export function buildEngineeringReport(_messages: Message[], events: ApiEvent[], claims: ClaimCard[], runId: string | null = null, snapshot: RunSnapshot | null = null) {
  const scopedEvents = runId ? events.filter(event => event.run_id === runId) : [];
  const scopedClaims = claims.filter(claim => claim.history.every(event => event.run_id === runId));
  const reported = reportedFacts(runId, snapshot);
  const { observed, inferred } = eventFacts(scopedEvents, runId);
  const gaps = gapsFromClaims(scopedClaims);
  const counterevidence = scopedEvents
    .filter(event => /contradiction|counterevidence|skeptic|disagreement/i.test(`${eventKind(event)} ${event.agent ?? ""}`))
    .map(event => readable(event.payload.counterevidence ?? event.payload.contradiction ?? event.payload.finding ?? event.payload.summary ?? event.payload.text))
    .filter((value): value is string => Boolean(value));
  return {
    reported, observed, inferred,
    sourcePending: !runId || !snapshot || snapshot.runId !== runId,
    gaps,
    candidates: scopedClaims.map(({ claimId, latest }) => ({
      id: claimId,
      text: readable(latest.payload.text ?? latest.payload.claim ?? latest.payload.statement) ?? "候选判断待查看",
      grade: String(latest.payload.grade ?? latest.payload.review_level ?? latest.payload.verification_level ?? "E0"),
      clause: Array.isArray(latest.payload.source_clause_ids) ? latest.payload.source_clause_ids.map(String).join("、") : readable(latest.payload.clause_id),
    })),
    counterevidence: [...new Set(counterevidence)],
  };
}

export default function EngineeringReport({ messages, events, claims, runId, snapshot }: Props) {
  if (!events.length || !claims.length) return null;
  const report = buildEngineeringReport(messages, events, claims, runId, snapshot);
  return <section className="engineering-report" aria-label="工程研判摘要">
    <div className="report-heading"><div><span className="eyebrow">ENGINEERING SUMMARY</span><h2>本轮工程摘要</h2></div><span className="report-mode">RULE_DEMO · 待核查</span></div>
    <p className="report-disclaimer">规则样例整理，非真实多模型审核或专家结论；所有候选均需结合设备适用条件复核。</p>
    <div className="report-grid">
      <section><h3>本轮输入与现场信息状态</h3>{report.sourcePending && <p role="status" className="report-source-pending">来源待确认：当前设备事实快照不可用或与所选 Run 不匹配，不从会话最新消息补填。</p>}
        {report.reported.length ? <ul>{report.reported.map((fact,index)=><li key={`reported-${index}`}><b>{fact.label} · 用户报告</b><span>{fact.value}</span><small>来源：{fact.source}；尚未独立验证设备真实性</small></li>)}</ul> : !report.sourcePending && <p>本轮未记录结构化现场输入；保持未知，不据此推定已知。</p>}
        {report.observed.length > 0 && <details className="report-audit-disclosure"><summary>经确认观察（{report.observed.length}）</summary><ul>{report.observed.map((fact,index)=><li key={`observed-${index}`}><b>{fact.label}</b><span>{fact.value}</span><small>来源：{fact.source}</small></li>)}</ul></details>}
        <p className="report-unknown"><b>仍未知：</b>{report.gaps.length ? report.gaps.join("、") : "本轮结构化记录未标明；不据此推定已知"}</p>
      </section>
      <section><h3>可能机理（待核）</h3>{report.candidates.map((candidate) => <button className="report-candidate" key={candidate.id} onClick={() => document.querySelector<HTMLButtonElement>(`.claim-card[data-claim-id=${JSON.stringify(candidate.id)}]`)?.click()}>
        <span className={`citation-grade grade-${candidate.grade.toLowerCase()}`}>{candidate.grade}</span><span><b>{candidate.text}</b><small>{candidate.clause || "未关联可确认条款"} · 尚未形成设备结论</small></span>
      </button>)}
        {report.inferred.length > 0 && <details className="report-audit-disclosure"><summary>Agent 推断与过程摘要（待核，{report.inferred.length}）</summary><ul>{report.inferred.map((fact,index)=><li key={`inferred-${index}`}><b>{fact.label}</b><span>{fact.value}</span><small>来源：{fact.source}；不得作为已确认现场事实</small></li>)}</ul></details>}
      </section>
      <section><h3>需补证据</h3><p>{report.gaps.length ? `当前结构化审查标记待补：${report.gaps.join("、")}。` : "对候选结论适用性有影响的现场参数，按实际设备和检验方案补齐；未记录项继续保持未知。"}</p><small>可结合测厚、操作温度/压力、投用年限等适用证据核验，不以缺省值替代实测。</small></section>
      <section><h3>来源与独立反证</h3>{report.candidates.map((candidate) => <p className="report-source" key={`source-${candidate.id}`}><b>{candidate.grade === "E1" ? "E1 · 条款已定位，但专业适用性待复核" : "E0 · 来源不足"}</b><small>{candidate.clause || "本轮无可确认条款"}</small></p>)}
        {report.counterevidence.length ? <details className="report-audit-disclosure"><summary>展开独立反证记录（{report.counterevidence.length}）</summary><ul>{report.counterevidence.map((item, index) => <li key={index}>{item}</li>)}</ul></details> : <p>本轮未收到可读的结构化反证摘要。</p>}
      </section>
    </div>
  </section>;
}
