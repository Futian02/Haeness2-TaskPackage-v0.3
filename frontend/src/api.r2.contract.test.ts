import { afterEach, describe, expect, it, vi } from "vitest";
import { api, type RunInput } from "./api";

afterEach(() => vi.unstubAllGlobals());

describe("R2 Run contract", () => {
  it("sends the stable Idempotency-Key header without adding body fields", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      run_id: "run-1", status: "queued", mode: "RULE_DEMO", events_url: "/api/runs/run-1/stream",
    }), { status: 201, headers: { "Content-Type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);
    const input: RunInput = {
      question: "你好", equipment: "", equipment_type: "", material: "", medium: [],
      operating_condition: "", field_evidence: "", mode: "RULE_DEMO", web_mode: "off",
    };
    const key = "r2-test-stable-idempotency-key";
    await api.createRun("cid-1", input, key);
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(new Headers(init.headers).get("Idempotency-Key")).toBe(key);
    expect(JSON.parse(String(init.body))).toEqual(input);
  });
});
