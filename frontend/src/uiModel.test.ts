import { beforeEach, describe, expect, it } from "vitest";
import { aggregateClaims, agentStates, claimStatus, localRunIds, observedAgentEdges, rememberRun } from "./uiModel";
import type { ApiEvent } from "./api";

const ev=(sequence:number,type:string,agent:string,payload:Record<string,unknown>={}):ApiEvent=>({run_id:"r",sequence,type,agent,payload});
beforeEach(()=>localStorage.clear());

describe("event-derived observability model",()=>{
  it("leaves every agent pending before runtime events",()=>expect(agentStates([], ["a","b"])).toEqual({a:"pending",b:"pending"}));
  it("marks only the observed active agent as started",()=>expect(agentStates([ev(1,"agent_started","a")],["a","b"])).toEqual({a:"started",b:"pending"}));
  it("marks completion by agent_completed rather than planned order",()=>expect(agentStates([ev(1,"agent_started","a"),ev(2,"agent_completed","a")],["a","b"])).toEqual({a:"completed",b:"pending"}));
  it("marks omitted nodes skipped only after a terminal run event",()=>expect(agentStates([ev(1,"run_completed","supervisor")],["a","b"])).toEqual({a:"skipped",b:"skipped"}));
  it("marks an explicit agent failure separately from skip",()=>expect(agentStates([ev(1,"agent_failed","a")],["a","b"])).toEqual({a:"failed",b:"pending"}));
  it("builds edges only from consecutive observed starts and keeps sequence",()=>expect(observedAgentEdges([ev(3,"agent_started","b"),ev(1,"agent_started","a"),ev(2,"decision_summary","a"),ev(4,"agent_started","b"),ev(5,"agent_started","c")])).toEqual([{id:"observed:a:b:3",source:"a",target:"b",label:"已观测",animated:false},{id:"observed:b:c:5",source:"b",target:"c",label:"已观测",animated:false}]));
  it("groups repeated claims by id and exposes the latest checked record",()=>{const result=aggregateClaims([ev(1,"claim_added","diagnosis_agent",{claim_id:"c1",text:"draft"}),ev(3,"claim_checked","skeptic",{claim_id:"c1",status:"unresolved"}),ev(2,"claim_checked","auditor",{claim_id:"c1",status:"supported"})]);expect(result).toHaveLength(1);expect(result[0].latest.sequence).toBe(3);expect(result[0].history.map(x=>x.sequence)).toEqual([1,2,3])});
  it("preserves human-review state as a distinct status",()=>expect(claimStatus(ev(8,"requires_human_review","skeptic",{claim_id:"c1"}))).toBe("需人工复核"));
  it("keeps a deduplicated local run fallback newest-first",()=>{rememberRun("c","r1");rememberRun("c","r2");rememberRun("c","r1");expect(localRunIds("c")).toEqual(["r1","r2"])});
});
