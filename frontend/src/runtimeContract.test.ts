import { describe, expect, it } from "vitest";
import { contractState, contractStateMessage, EXPECTED_CONTRACT_VERSION, FRONTEND_BUILD_FINGERPRINT } from "./runtimeContract";
import type { Health } from "./api";

const health = (patch: Partial<Health> = {}): Health => ({
  status: "ok", mode: "RULE_DEMO", database: "temporary.sqlite", teacher_tools: [],
  contract_version: EXPECTED_CONTRACT_VERSION,
  capabilities: { runs_create: true, runs_sse_stream: true, runs_replay: true, run_input_snapshot: true, model_profiles: false },
  build_fingerprint: `sha256:${"a".repeat(64)}`,
  ...patch,
});

describe("R2 runtime contract handshake", () => {
  it("compares backend contract and fingerprint without confusing legacy with offline", () => {
    expect(contractState(health())).toBe("compatible");
    expect(contractStateMessage(health())).toBeNull();
    expect(contractState(health({ contract_version: undefined }))).toBe("legacy");
    expect(contractStateMessage(health({ contract_version: undefined }))).toContain("旧服务");
    expect(contractState(health({ contract_version: "aetheris-r1.9" }))).toBe("mismatch");
    expect(contractState(health({ build_fingerprint: null }))).toBe("incomplete");
  });

  it("exposes an independently generated 64-hex frontend fingerprint", () => {
    expect(FRONTEND_BUILD_FINGERPRINT).toMatch(/^[a-f0-9]{64}$/);
  });
});
