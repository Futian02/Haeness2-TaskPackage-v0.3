import { describe, expect, it, vi, afterEach } from "vitest";
import { consumeRun, eventKind, RunStreamError, type ApiEvent, type RunCreated } from "./api";

afterEach(()=>vi.restoreAllMocks());

describe("SSE adapter",()=>{
  it("accepts additive unknown event kinds without dropping data",()=>{
    const future={run_id:"r",sequence:1,kind:"evidence_conflict_v2",payload:{claim_id:"c"}} as ApiEvent;
    expect(eventKind(future)).toBe("evidence_conflict_v2");
    expect(eventKind({...future,kind:undefined,type:"tool_result"})).toBe("tool_result");
    expect(eventKind({...future,kind:undefined,type:undefined})).toBe("unknown_event");
  });
  it("parses actual SSE and ignores other run ids and duplicate sequences",async()=>{
    const records=[
      {run_id:"r1",sequence:1,type:"agent_started",payload:{agent:"planner"}},
      {run_id:"r1",sequence:1,type:"agent_started",payload:{agent:"planner"}},
      {run_id:"wrong",sequence:2,type:"claim",payload:{}},
      {run_id:"r1",sequence:2,kind:"claim_recorded",payload:{id:"cl-1"}},
      {run_id:"r1",sequence:3,type:"run_completed",payload:{}},
    ];
    const body=records.map(e=>`data: ${JSON.stringify(e)}\n\n`).join("");
    vi.stubGlobal("fetch",vi.fn().mockResolvedValue(new Response(body,{status:200,headers:{"Content-Type":"text/event-stream"}})));
    const got:ApiEvent[]=[];
    const run:RunCreated={run_id:"r1",events_url:"/api/runs/r1/stream",status:"queued",mode:"RULE_DEMO"};
    await consumeRun(run,e=>got.push(e));
    expect(got.map(e=>e.sequence)).toEqual([1,2,3]);
    expect(eventKind(got[1])).toBe("claim_recorded");
  });
  it("recovers a dropped stream through replay without creating another run",async()=>{
    const sequenceZero=new ReadableStream<Uint8Array>({start(c){c.enqueue(new TextEncoder().encode(`data: ${JSON.stringify({run_id:"r2",sequence:1,type:"agent_started",payload:{}})}\n\n`));c.close()}});
    const fetchMock=vi.fn().mockResolvedValueOnce(new Response(sequenceZero,{status:200})).mockResolvedValueOnce(new Response(JSON.stringify({run_id:"r2",events:[{run_id:"r2",sequence:1,type:"agent_started",payload:{}},{run_id:"r2",sequence:2,type:"run_completed",payload:{}}]}),{status:200,headers:{"Content-Type":"application/json"}}));
    vi.stubGlobal("fetch",fetchMock);
    const events:ApiEvent[]=[];
    await consumeRun({run_id:"r2",events_url:"/api/runs/r2/stream",status:"queued",mode:"RULE_DEMO"},e=>events.push(e));
    expect(events.map(e=>e.sequence)).toEqual([1,2]);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(String(fetchMock.mock.calls[1][0])).toContain("after_sequence=1");
  });
  it("surfaces WorkerCapacity 429 as an already-created queued run and retains Retry-After",async()=>{
    vi.stubGlobal("fetch",vi.fn().mockResolvedValue(new Response(JSON.stringify({detail:{code:"WORKER_CAPACITY",detail:"queued run retained"}}),{status:429,headers:{"Content-Type":"application/json","Retry-After":"2"}})));
    const run={run_id:"queued-existing",events_url:"/api/runs/queued-existing/stream",status:"queued" as const,mode:"RULE_DEMO" as const};
    await expect(consumeRun(run,()=>undefined)).rejects.toMatchObject({name:"RunStreamError",code:"run_queued_capacity",retryAfterSeconds:2});
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(String(vi.mocked(fetch).mock.calls[0][0])).toContain("queued-existing");
  });
  it("treats an SSE error event as a failed terminal and strips provider detail",async()=>{
    const secret="PRIVATE_PROVIDER_BODY_SENTINEL";
    const body=`data: ${JSON.stringify({run_id:"r-fail",sequence:1,type:"error",payload:{code:"RuntimeError",message:secret}})}\n\n`;
    vi.stubGlobal("fetch",vi.fn().mockResolvedValue(new Response(body,{status:200,headers:{"Content-Type":"text/event-stream"}})));
    const received:ApiEvent[]=[];
    await expect(consumeRun({run_id:"r-fail",events_url:"/api/runs/r-fail/stream",status:"running",mode:"DEEPSEEK"},event=>received.push(event)))
      .rejects.toMatchObject<Partial<RunStreamError>>({name:"RunStreamError",code:"run_failed"});
    expect(received).toHaveLength(1);
    expect(received[0].payload).toEqual({code:"run_failed"});
    expect(JSON.stringify(received)).not.toContain(secret);
  });
});
