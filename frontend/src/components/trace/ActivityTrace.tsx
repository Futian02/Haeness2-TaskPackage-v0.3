import { AssistantRuntimeProvider, MessagePrimitive, ThreadPrimitive, useExternalStoreRuntime } from "@assistant-ui/react";
import { useMemo, useState } from "react";
import type React from "react";
import { ReasoningContent, ReasoningRoot, ReasoningText, ReasoningTrigger } from "./reasoning";
import { ToolGroupContent, ToolGroupRoot, ToolGroupTrigger } from "./tool-group";
import { ToolFallback as AssistantToolFallback } from "./tool-fallback";
import { eventKind, type ApiEvent } from "../../api";
import { groupActivityStages, projectActivity, sanitizePublicText, summarizeActivity, type ActivityStage, type ActivityStep } from "../../trace-events/model";
import "./activity-trace.css";

type TraceMessage = { id: string; runId: string; steps: ActivityStep[] };
const labelAgent = (agent: string) => ({ supervisor: "总控", evidence_agent: "证据检索", diagnosis_agent: "研判", rbi_specialist: "RBI查询", evidence_auditor: "证据审核", skeptic: "独立复核", reporting_agent: "报告" }[agent] ?? agent.replaceAll("_", " "));

export function ActivityTrace({ runId, events, finalText = "", title = "本轮执行过程", theme = "system", processSummary }: { runId: string; events: readonly ApiEvent[]; finalText?: string; title?: string; theme?: "light" | "dark" | "system"; processSummary?: string }) {
  const runEvents = useMemo(() => events.filter((event) => event.run_id === runId), [events, runId]);
  const steps = useMemo(() => projectActivity(runEvents), [runEvents]);
  const stages = useMemo(() => groupActivityStages(steps), [steps]);
  const modelSummary = useMemo(() => {
    const raw = processSummary ?? [...runEvents].reverse().find((event) => eventKind(event) === "llm_completed" && typeof event.payload?.summary === "string")?.payload.summary;
    return sanitizePublicText(raw, 360) || undefined;
  }, [processSummary, runEvents]);
  const message: TraceMessage = useMemo(() => ({ id: `trace-${runId}`, runId, steps }), [runId, steps]);
  const runtimeMessage = useMemo(() => ({
    id: message.id,
    role: "assistant" as const,
    status: steps.some((step) => step.tool?.status === "running")
      ? { type: "running" as const }
      : steps.some((step) => step.status === "incomplete")
        ? { type: "incomplete" as const, reason: "error" as const }
        : { type: "complete" as const, reason: "stop" as const },
    metadata: { unstable_state: null, unstable_annotations: [], unstable_data: [], steps: [], runId: message.runId },
    content: toParts(steps, finalText),
  }), [message.id, message.runId, steps, finalText]);
  const runtimeMessages = useMemo(() => [message], [message]);
  const runtime = useExternalStoreRuntime<TraceMessage>({
    messages: runtimeMessages,
    convertMessage: () => runtimeMessage,
    onNew: async () => undefined,
  });

  return <AssistantRuntimeProvider runtime={runtime}>
    <section className={`activity-trace activity-trace-theme-${theme}`} aria-label={title} data-run-id={runId}>
      <ThreadPrimitive.Root>
      <ThreadPrimitive.Messages>{({ message: runtimePart }) => <MessagePrimitive.Root id={runtimePart.id} key={runtimePart.id}>
        {steps.length === 0 && !finalText ? <Disclosure className="execution-card" title="执行过程 · 0 步" storageKey={`r9b:trace:expanded:${runId}`} data-testid="execution-summary"><p className="trace-empty" data-testid="trace-empty">本轮暂无持久化执行事件</p></Disclosure> : <MessagePrimitive.GroupedParts groupBy={(part) => {
          if (part.type !== "reasoning" && part.type !== "tool-call") return null;
          const stageKey = (part as typeof part & { traceStageKey?: string }).traceStageKey;
          const stage = stages.find((item) => item.id === stageKey);
          if (!stage) return ["group-execution"];
          return ["group-execution", `group-stage-${encodeURIComponent(stage.id)}`, part.type === "reasoning" ? "group-reasoning" : "group-tool"];
        }}>
          {({ part, children }) => {
      if (part.type === "group-execution") return <Disclosure className="execution-card" title={`思维过程 · ${steps.length} 步 · ${executionHeading(steps, Boolean(modelSummary))}`} storageKey={`r9b:trace:expanded:${runId}`} data-testid="execution-summary"><><p className="process-note">仅展示可公开的阶段摘要、已发生工具、审核与来源，不包含模型隐藏思维链。</p>{children}{modelSummary&&<details className="model-summary"><summary>模型公开表达摘要 · 展开查看</summary><div>{modelSummary}</div></details>}<ReviewSummary steps={steps}/><CitationList steps={steps}/></></Disclosure>;
            if (part.type.startsWith("group-stage-")) {
              const encoded = part.type.slice("group-stage-".length);
              const stage = stages.find((item) => encodeURIComponent(item.id) === encoded);
              return stage ? <StageDisclosure key={stage.id} stage={stage}>{children}</StageDisclosure> : <>{children}</>;
            }
            if (part.type === "group-reasoning") return <ReasoningRoot variant="ghost" defaultOpen><ReasoningTrigger/><ReasoningContent><ReasoningText>{children}</ReasoningText></ReasoningContent></ReasoningRoot>;
            if (part.type === "group-tool") return <ToolGroupRoot variant="ghost"><ToolGroupTrigger count={part.indices.length} active={part.status.type === "running"}/><ToolGroupContent>{children}</ToolGroupContent></ToolGroupRoot>;
            if (part.type === "reasoning") return <ReasoningStep step={stepFromId(steps, part.id)} text={part.text} />;
            if (part.type === "tool-call") return part.toolUI ?? <AssistantToolFallback {...part} />;
            if (part.type === "text") return <div className="activity-answer">{part.text}</div>;
            return null;
          }}
        </MessagePrimitive.GroupedParts>}
      </MessagePrimitive.Root>}</ThreadPrimitive.Messages>
      </ThreadPrimitive.Root>
    </section>
  </AssistantRuntimeProvider>;
}

function toParts(steps: ActivityStep[], finalText: string) {
  const parts: Record<string, unknown>[] = [];
  let group: ActivityStep[] = [];
  const flush = () => {
    const visible = group.filter((step) => step.publicRationale && !["agent_started", "agent_completed", "agent_finished"].includes(step.type));
    if (group.length) {
      const summary = visible.map((step) => step.publicRationale).filter(Boolean).join("；") || "该阶段有持久化事件，无额外公开摘要";
      const decision = visible.find((step) => step.type === "decision_summary");
      const anchor = decision ?? visible[0] ?? group[0];
      parts.push({ type: "reasoning", id: anchor.id, traceStageKey: anchor.stageKey, text: `${summary} · ${group.length} 条事件`, status: { type: "complete" } });
    }
    group = [];
  };
  for (const step of steps) {
    if (step.type === "tool_called" && step.tool) {
      flush();
      parts.push({ type: "tool-call", toolCallId: step.tool.id, traceStageKey: step.stageKey, toolName: step.tool.name, args: step.tool.args, argsText: JSON.stringify(step.tool.args), result: step.tool.result ?? (step.tool.status === "running" ? undefined : { status: step.tool.status, sources: step.tool.sourceIds }), isError: step.tool.status === "incomplete", ...(step.tool.status === "running" ? {} : { status: { type: step.tool.status === "incomplete" ? "incomplete" : "complete", reason: "tool-calls" } }) });
      continue;
    }
    if (group.length && (group.at(-1)?.agent !== step.agent || group.at(-1)?.phase !== step.phase || group.at(-1)?.iteration !== step.iteration)) flush();
    group.push(step);
  }
  flush();
  if (finalText) parts.push({ type: "text", text: finalText, id: `answer:${steps[0]?.runId ?? "trace"}` });
  return parts as never;
}

function stepFromId(steps: ActivityStep[], id?: string) { return steps.find((step) => step.id === id || step.tool?.id === id); }
function executionHeading(steps: ActivityStep[], hasModelSummary = false) {
  const summary = summarizeActivity(steps);
  const elapsed = summary.elapsedMs && summary.elapsedMs > 0 ? ` · ${formatDuration(summary.elapsedMs)}` : "";
  const work = summary.toolCount ? ` · 查询 ${summary.toolCount} 次` : hasModelSummary ? " · 模型整理 1 次" : "";
  const reviews = summary.reviewCount ? ` · 审查 ${summary.reviewCount} 次` : summary.pendingReview ? ` · 待审 ${summary.pendingReview} 项` : "";
  return `${summary.status}${work}${reviews}${elapsed}`;
}

function formatDuration(ms: number) { return ms < 1000 ? `${Math.max(1, Math.round(ms))} ms` : `${(ms / 1000).toFixed(1)} s`; }

function StageDisclosure({ stage, children }: React.PropsWithChildren<{ stage: ActivityStage }>) {
  const status = stage.status === "running" ? "进行中" : stage.status === "incomplete" ? "未完成" : stage.status === "requires-action" ? "待审核" : "完成";
  const duration = stage.durationMs && stage.durationMs > 0 ? `${stage.durationSource === "event-span" ? "约 " : ""}${formatDuration(stage.durationMs)}` : "耗时未记录";
  return <details className={`trace-stage status-${stage.status}`} data-stage-id={stage.id} data-testid="trace-stage">
    <summary><span className="trace-stage-dot" aria-hidden="true"/><span className="trace-stage-title">{stage.label}</span><span className="trace-stage-meta">{labelAgent(stage.agent)}{stage.iteration ? ` · 第 ${stage.iteration} 轮` : ""}</span><span className="trace-stage-status">{status}</span><span className="trace-stage-duration">{duration}</span></summary>
    <div className="trace-stage-body"><p className="trace-stage-summary">{stage.summary || "该阶段没有额外公开摘要；仅列出持久化事件。"}</p>{stage.tools.length > 0 && <p className="trace-stage-tools"><span>工具</span>{stage.tools.join(" · ")}</p>}<div className="trace-stage-counts">{stage.eventCount} 条事件{stage.toolCount ? ` · 工具 ${stage.toolCount} 次` : ""}{stage.reviewCount ? ` · 审查记录 ${stage.reviewCount} 条` : ""}{stage.citationCount ? ` · 来源 ${stage.citationCount} 项` : ""} · 序号 {stage.firstSequence}{stage.lastSequence !== stage.firstSequence ? `–${stage.lastSequence}` : ""}</div>{children}</div>
  </details>;
}

function Disclosure({ children, className, title, storageKey, ...props }: React.PropsWithChildren<{ className: string; title: string; storageKey: string; "data-testid"?: string }>) {
  const [expanded, setExpanded] = useState(() => typeof localStorage !== "undefined" && localStorage.getItem(storageKey) === "true");
  const update = (next: boolean) => { setExpanded(next); localStorage.setItem(storageKey, String(next)); };
  // Keep the disclosure controlled and persist only the explicit summary
  // click. Combining this with `onToggle` races in Edge: the native toggle
  // event can write the previous state back and leave the panel stuck closed.
  return <details className={className} open={expanded} {...props}><summary onClick={(event) => { event.preventDefault(); update(!expanded); }}><span className="trace-spark" aria-hidden="true">✳</span><span>{title}</span><span className="trace-chevron" aria-hidden="true">⌄</span></summary><div className="execution-body">{children}</div></details>;
}
function ReasoningStep({ step, text }: { step?: ActivityStep; text: string }) {
  if (!step?.publicRationale) return null;
  return <article className="reasoning-step"><div className="step-title"><i className="step-dot" />{step.type === "decision_summary" ? "公开决策摘要" : step.title}<span>{labelAgent(step.agent)}</span></div><p>{text}</p></article>;
}
function CitationList({ steps }: { steps: ActivityStep[] }) {
  const citations = new Map<string, ActivityStep["sources"][number]>();
  for (const step of steps) for (const source of step.sources) citations.set(source.id, source);
  if (!citations.size) return null;
  return <ul className="trace-citations" aria-label="已记录引用">{[...citations.values()].map((source) => <li key={source.id}><strong>{source.id}</strong>{source.clauseNo ? <span> · {source.clauseNo}</span> : null}{source.page ? <span> · p.{source.page}</span> : null}{source.verificationLevel ? <span> · {source.verificationLevel}</span> : null}</li>)}</ul>;
}
function ReviewSummary({ steps }: { steps: ActivityStep[] }) {
  const rows = steps.filter(step => ["review_result", "agent_completed", "requires_human_review", "contradiction_found"].includes(step.type)
    && (step.type !== "agent_completed" || ["evidence_auditor", "skeptic"].includes(step.agent)));
  if (!rows.length) return null;
  return <ul className="trace-review-summary" aria-label="审查结果摘要">{rows.map(step=><li key={step.id}><strong>{labelAgent(step.agent)}</strong><span>{step.publicRationale || step.summary || step.title}</span></li>)}</ul>;
}
