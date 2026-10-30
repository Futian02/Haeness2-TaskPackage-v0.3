import { describe, expect, it } from "vitest";
import type { Message } from "./api";
import { presentMessage } from "./messagePresentation";

const message = (content: string): Message => ({ id: "legacy-1", role: "assistant", content });

describe("legacy persisted assistant message projection", () => {
  it("moves the old DeepSeek prose into a foldable summary without modifying the stored message", () => {
    const original = "**DeepSeek 表达整理（非独立研判）**\n模型写的摘要。\n\n**本地确定性研判与证据状态（权威）**\n待人工复核。\n\nDEEPSEEK · 仅负责表达整理；来源等级、未知项与风险门禁由本地确定性流程控制。";
    const row = message(original);
    const view = presentMessage(row);
    expect(view).toEqual({ finalText: "待人工复核。", processSummary: "模型写的摘要。" });
    expect(row.content).toBe(original);
  });

  it("leaves current plain replies and user messages unchanged", () => {
    expect(presentMessage(message("你好！"))).toEqual({ finalText: "你好！" });
    expect(presentMessage({ ...message("user text"), role: "user" })).toEqual({ finalText: "user text" });
  });
});
