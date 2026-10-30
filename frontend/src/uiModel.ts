import { eventKind, type ApiEvent } from "./api";

export type ClaimCard = { claimId: string; latest: ApiEvent; history: ApiEvent[] };

const agentName = (event: ApiEvent) => {
  const payloadAgent = event.payload.agent;
  return String(event.agent || (typeof payloadAgent === "string" ? payloadAgent : "") || "");
};

export function agentStates(events: ApiEvent[], roles: string[]) {
  const terminal = events.some(e => ["run_completed", "error"].includes(eventKind(e)));
  return Object.fromEntries(roles.map(role => {
    const agentEvents = events.filter(e => agentName(e) === role);
    const completed = agentEvents.some(e => /agent_completed|agent_finished|agent_reviewed/.test(eventKind(e)));
    const failed = agentEvents.some(e => /agent_failed|agent_error/.test(eventKind(e)));
    return [role, failed ? "failed" : completed ? "completed" : agentEvents.length ? "started" : terminal ? "skipped" : "pending"];
  })) as Record<string, "failed" | "completed" | "started" | "skipped" | "pending">;
}

/** Only emits edges explicitly witnessed by sequential agent_started events. */
export function observedAgentEdges(events: ApiEvent[]) {
  const starts = events.filter(e => eventKind(e) === "agent_started").sort((a,b) => a.sequence-b.sequence);
  const edges: { id: string; source: string; target: string; label: string; animated: boolean }[] = [];
  for (let i=1;i<starts.length;i++) {
    const source=agentName(starts[i-1]), target=agentName(starts[i]);
    if (!source || !target || source===target) continue;
    const id=`observed:${source}:${target}:${starts[i].sequence}`;
    if (!edges.some(edge=>edge.id===id)) edges.push({id,source,target,label:"已观测",animated:false});
  }
  return edges;
}

export function aggregateClaims(events: ApiEvent[]): ClaimCard[] {
  const claimEvents=events.filter(e=>/claim_added|claim_checked|claim_review_required|requires_human_review|claim_verification/.test(eventKind(e)) && typeof e.payload.claim_id === "string");
  const grouped=new Map<string,ApiEvent[]>();
  for(const event of claimEvents){const id=String(event.payload.claim_id);grouped.set(id,[...(grouped.get(id)||[]),event]);}
  return [...grouped].map(([claimId,history])=>{
    const ordered=history.sort((a,b)=>a.sequence-b.sequence);
    const latest=ordered[ordered.length-1];
    // Review events often carry only a decision envelope. Keep the strongest
    // structured Claim payload as the base while the newest event owns status
    // and sequence; never let an empty review payload erase its source proof.
    const richness=(event:ApiEvent)=>{
      const p=event.payload;const canonical=Array.isArray(p.canonical_evidence)?p.canonical_evidence.length:0;
      const checks=Array.isArray(p.checks)?p.checks.length:0;
      return canonical*100+checks*5+(typeof p.text==="string"?Math.min(p.text.length,200):0)+(typeof p.grade==="string"?10:0)+(Array.isArray(p.source_clause_ids)?p.source_clause_ids.length*10:0);
    };
    const source=ordered.reduce((best,event)=>richness(event)>richness(best)?event:best,ordered[0]);
    const payload={...source.payload,...latest.payload};
    for(const key of ["canonical_evidence","checks","source_clause_ids","observation_ids","assumptions","text","kind","grade","provenance_status"]){
      const value=latest.payload[key];const empty=value===undefined||value===null||(Array.isArray(value)&&value.length===0)||(typeof value==="string"&&!value.trim());
      if(empty&&source.payload[key]!==undefined)payload[key]=source.payload[key];
    }
    return {claimId,latest:{...latest,payload},history:ordered};
  });
}

export function claimStatus(event: ApiEvent) {
  const p=event.payload;
  if (/requires_human_review|claim_review_required/.test(eventKind(event))) return "需人工复核";
  return String(p.status ?? p.verdict ?? p.review_status ?? "已核查");
}

export function localRunIds(sessionId: string): string[] {
  try { return JSON.parse(localStorage.getItem(`aether:runs:${sessionId}`)||"[]").filter((x:unknown)=>typeof x==="string"); }
  catch { return []; }
}

export function rememberRun(sessionId: string, runId: string) {
  const ids=[runId,...localRunIds(sessionId).filter(id=>id!==runId)].slice(0,50);
  localStorage.setItem(`aether:runs:${sessionId}`,JSON.stringify(ids));
  localStorage.setItem(`aether:last-run:${sessionId}`,runId);
}

export function localRunEventCount(sessionId: string, runId: string) {
  try { const value=JSON.parse(localStorage.getItem(`aether:run-events:${sessionId}:${runId}`)||"[]");return Array.isArray(value)?value.length:0; }
  catch { return 0; }
}
