import type { Message } from "./api";

const MODEL_SECTION = "**DeepSeek 表达整理（非独立研判）**";
const FINAL_SECTION = "**本地确定性研判与证据状态（权威）**";
const OLD_FOOTER = "DEEPSEEK · 仅负责表达整理；来源等级、未知项与风险门禁由本地确定性流程控制。";

/** Split legacy persisted R9 messages into a foldable model-written section and the final local result. */
export function presentMessage(message: Message): { finalText: string; processSummary?: string } {
  if (message.role !== "assistant") return { finalText: message.content };
  const cleanedContent = message.content.replace(OLD_FOOTER, "").trim();
  const modelStart = message.content.indexOf(MODEL_SECTION);
  const finalStart = message.content.indexOf(FINAL_SECTION, modelStart + MODEL_SECTION.length);
  if (modelStart < 0 || finalStart < 0) return { finalText: cleanedContent };
  const processSummary = message.content.slice(modelStart + MODEL_SECTION.length, finalStart).trim();
  const finalText = message.content.slice(finalStart + FINAL_SECTION.length)
    .replace(OLD_FOOTER, "")
    .trim();
  return { finalText: finalText || "本地流程未形成可展示结论。", processSummary: processSummary || undefined };
}

