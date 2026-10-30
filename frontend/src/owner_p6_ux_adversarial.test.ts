import {describe,it,expect} from "vitest";
import {buildEngineeringReport, type RunSnapshot} from "./EngineeringReport";
import type {Message,ApiEvent} from "./api";

const m=(content:string)=>({role:"user",content} as Message);
const e=(kind:string,payload:Record<string,unknown>,runId="run-1")=>({type:kind,kind,agent:"reporting_agent",run_id:runId,sequence:1,payload} as ApiEvent);
const snapshot=(runId="run-1",question="请分析当前设备")=>({runId,conversationId:"conversation-1",capturedAt:"2026-10-28T10:00:00Z",question,context:{material:"碳钢",medium:["氯化氢"],field_evidence:"现场水样 pH 5.8"}} as RunSnapshot);
const claim=(runId="run-1")=>[{claimId:"c",history:[e("claim_added",{claim_id:"c"},runId)],latest:e("claim_added",{claim_id:"c",grade:"E0",text:"候选需核",source_clause_ids:[]},runId)}];

describe("P7B run-bound facts and evidence UX gates",()=>{
  it("keeps an unverified agent summary in inferred, never reported/observed facts",()=>{
    const summary="设备已发生严重减薄（仅Agent推断，用户未报告）";
    const r=buildEngineeringReport([m("我想了解机理")],[e("decision_summary",{summary})],claim(),"run-1",snapshot());
    expect(r.reported.map(x=>x.value)).toContain("现场水样 pH 5.8");
    expect(r.reported.map(x=>x.value)).not.toContain(summary);
    expect(r.observed.map(x=>x.value)).not.toContain(summary);
    expect(r.inferred.map(x=>x.value)).toContain(summary);
  });

  it("does not use the latest conversation message when selected run lacks its snapshot",()=>{
    const latest="第二轮用户说现场已经有裂纹";
    const r=buildEngineeringReport([m("第一轮用户只说尚未测厚"),m(latest)],[e("claim_added",{claim_id:"c",grade:"E0"})],claim(),"old-run",null);
    expect(r.sourcePending).toBe(true);
    expect(r.reported).toEqual([]);
    expect(JSON.stringify(r)).not.toContain(latest);
  });

  it("rejects a prompt/context snapshot belonging to a different run",()=>{
    const r=buildEngineeringReport([m("latest message")],[e("claim_added",{claim_id:"c"})],claim(),"run-1",snapshot("run-2","旧run工况"));
    expect(r.sourcePending).toBe(true);
    expect(r.reported).toEqual([]);
  });

  it("filters events and claims from another run when switching history",()=>{
    const oldEvent=e("decision_summary",{summary:"旧run Agent推断"},"run-1");
    const newEvent=e("decision_summary",{summary:"新run Agent推断"},"run-2");
    const r=buildEngineeringReport([m("old"),m("new")],[oldEvent,newEvent],[...claim("run-1"),...claim("run-2")],"run-2",snapshot("run-2","本轮输入"));
    expect(r.inferred.map(x=>x.value)).toEqual(["新run Agent推断"]);
    expect(r.candidates).toHaveLength(1);
    expect(r.reported.map(x=>x.value)).toContain("本轮输入");
  });

  it("only accepts explicitly run-bound confirmed observations as observed",()=>{
    const events=[
      e("observation_added",{observation:{field:"wall_thickness",value:"4.2 mm"},source_status:"unverified"}),
      e("observation_added",{observation:{field:"temperature",value:"180 C"},source_status:"confirmed"}),
    ];
    const r=buildEngineeringReport([],events,claim(),"run-1",snapshot());
    expect(r.observed.map(x=>x.value)).toEqual(["180 C"]);
    expect(r.inferred.map(x=>x.value)).toContain("4.2 mm");
  });
});
