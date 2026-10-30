import type { Health } from "./api";

export const EXPECTED_CONTRACT_VERSION = "aetheris-r2.0.0";
export const FRONTEND_BUILD_FINGERPRINT = __AETHER_FRONTEND_BUILD_FINGERPRINT__;

export type ContractState = "checking" | "compatible" | "legacy" | "mismatch" | "incomplete";

export function contractState(health: Health | null): ContractState {
  if (!health) return "checking";
  if (!health.contract_version) return "legacy";
  if (health.contract_version !== EXPECTED_CONTRACT_VERSION) return "mismatch";
  if (!health.capabilities || typeof health.build_fingerprint !== "string" || !health.build_fingerprint.startsWith("sha256:")) return "incomplete";
  return "compatible";
}

export function contractStateMessage(health: Health | null): string | null {
  const state = contractState(health);
  if (state === "compatible" || state === "checking") return null;
  if (state === "legacy") return `后端未提供版本握手（旧服务）；前端期望 ${EXPECTED_CONTRACT_VERSION}。当前服务仍可连接，但新版能力与请求兼容性未验证。`;
  if (state === "mismatch") return `前后端协议版本不匹配：前端期望 ${EXPECTED_CONTRACT_VERSION}，后端报告 ${health?.contract_version}。`;
  return "后端版本握手信息不完整；尚不能确认当前运行实例与前端兼容。";
}

export function capability(health: Health | null, name: string): boolean {
  return health?.capabilities?.[name] === true;
}

export function shortFingerprint(value: string | null | undefined): string {
  if (!value) return "未提供";
  return value.length > 23 ? `${value.slice(0, 19)}…${value.slice(-4)}` : value;
}
