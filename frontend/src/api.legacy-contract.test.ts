import { afterEach, describe, expect, it, vi } from "vitest";
import { api, type RunInput } from "./api";

const input: RunInput = {
  question: "请解释腐蚀机理", equipment: "", equipment_type: "", material: "",
  medium: [], operating_condition: "", field_evidence: "", mode: "DEEPSEEK",
  web_mode: "auto", allow_sensitive_web_search: false,
};
const success = () => new Response(JSON.stringify({
  run_id: "run-old", status: "queued", mode: "DEEPSEEK", events_url: "/api/runs/run-old/stream",
}), { status: 200, headers: { "Content-Type": "application/json" } });
const legacy422 = () => new Response(JSON.stringify({ detail: [
  {type:"extra_forbidden", loc:["body","web_mode"], msg:"Extra inputs are not permitted", input:"auto"},
  {type:"extra_forbidden", loc:["body","allow_sensitive_web_search"], msg:"Extra inputs are not permitted", input:false},
]}), {status:422, statusText:"Unprocessable Entity",headers:{"Content-Type":"application/json"}});

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe("V2 frontend / older backend compatibility", () => {
  it("retries once with only old RunIn fields after exact extra-forbidden 422", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(legacy422()).mockResolvedValueOnce(success());
    vi.stubGlobal("fetch",fetchMock);
    const created=await api.createRun("cid",input);
    expect(created.run_id).toBe("run-old");
    expect(created.legacy_compatibility).toBe(true);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    const first=JSON.parse(fetchMock.mock.calls[0][1].body);
    const second=JSON.parse(fetchMock.mock.calls[1][1].body);
    expect(first.web_mode).toBe("auto");
    expect(second.web_mode).toBeUndefined();
    expect(second.allow_sensitive_web_search).toBeUndefined();
    expect(second.model_profile_id).toBeUndefined();
    expect(second.question).toBe(input.question);
    expect(second.mode).toBe("DEEPSEEK");
  });
  it("never retries a new backend successful submission", async () => {
    const fetchMock=vi.fn().mockResolvedValue(success());vi.stubGlobal("fetch",fetchMock);
    const result=await api.createRun("cid",input);
    expect(result.legacy_compatibility).toBeUndefined();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
  it("does not downgrade explicit online search consent", async () => {
    const fetchMock=vi.fn().mockResolvedValue(legacy422());vi.stubGlobal("fetch",fetchMock);
    await expect(api.createRun("cid",{...input,web_mode:"on",allow_sensitive_web_search:true})).rejects.toThrow("BACKEND_VERSION_MISMATCH");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
  it("does not downgrade custom model profile choice", async () => {
    const fetchMock=vi.fn().mockResolvedValue(legacy422());vi.stubGlobal("fetch",fetchMock);
    await expect(api.createRun("cid",{...input,model_profile_id:"custom-1"})).rejects.toThrow("BACKEND_VERSION_MISMATCH");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
  it("never retries 422 caused by unrelated invalid input", async () => {
    const invalid=new Response(JSON.stringify({detail:[{
      type:"string_too_long",loc:["body","question"],msg:"Too long",
    }]}),{status:422,statusText:"Unprocessable Entity"});
    const fetchMock=vi.fn().mockResolvedValue(invalid);vi.stubGlobal("fetch",fetchMock);
    await expect(api.createRun("cid",input)).rejects.toThrow("422");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
