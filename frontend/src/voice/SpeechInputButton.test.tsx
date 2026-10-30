import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { SpeechInputButton } from "./SpeechInputButton";

type Result = { isFinal: boolean; length: number; 0: { transcript: string } };
class FakeRecognition {
  static latest: FakeRecognition;
  lang = "";
  continuous = false;
  interimResults = false;
  maxAlternatives = 0;
  onstart: (() => void) | null = null;
  onresult: ((event: { resultIndex: number; results: ArrayLike<Result> }) => void) | null = null;
  onerror: ((event: { error: string; message?: string }) => void) | null = null;
  onend: (() => void) | null = null;
  start = vi.fn(() => this.onstart?.());
  stop = vi.fn();
  abort = vi.fn();
  constructor() { FakeRecognition.latest = this; }
  result(text: string, isFinal = true) {
    const row = { isFinal, length: 1, 0: { transcript: text } } as Result;
    this.onresult?.({ resultIndex: 0, results: [row] });
  }
  fail(error: string) { this.onerror?.({ error }); }
  end() { this.onend?.(); }
}

function installRecognition(vendor = false) {
  Object.defineProperty(window, vendor ? "webkitSpeechRecognition" : "SpeechRecognition", { value: FakeRecognition, configurable: true });
}
function clearRecognition() {
  Reflect.deleteProperty(window, "SpeechRecognition");
  Reflect.deleteProperty(window, "webkitSpeechRecognition");
}

beforeEach(() => { clearRecognition(); });
afterEach(() => { cleanup(); clearRecognition(); });

describe("SpeechInputButton", () => {
  it("configures Chinese, continuous interim recognition only after an explicit click", () => {
    installRecognition();
    const onTranscript = vi.fn();
    render(<SpeechInputButton onTranscript={onTranscript} />);
    expect(FakeRecognition.latest).toBeUndefined();
    fireEvent.click(screen.getByRole("button", { name: "开始语音输入" }));
    expect(FakeRecognition.latest).toMatchObject({ lang: "zh-CN", continuous: true, interimResults: true, maxAlternatives: 1 });
    expect(FakeRecognition.latest.start).toHaveBeenCalledOnce();
    expect(onTranscript).not.toHaveBeenCalled();
  });

  it("sends interim/final transcription to the draft callback and stop never submits", () => {
    installRecognition();
    const onTranscript = vi.fn();
    const submit = vi.fn();
    render(<><SpeechInputButton onTranscript={onTranscript} /><button onClick={submit}>发送</button></>);
    fireEvent.click(screen.getByRole("button", { name: "开始语音输入" }));
    FakeRecognition.latest.result("湿硫化氢", false);
    expect(onTranscript).toHaveBeenLastCalledWith("湿硫化氢");
    fireEvent.click(screen.getByRole("button", { name: "停止语音输入" }));
    expect(FakeRecognition.latest.stop).toHaveBeenCalledOnce();
    expect(submit).not.toHaveBeenCalled();
  });

  it("supports the webkit-prefixed browser API", () => {
    installRecognition(true);
    render(<SpeechInputButton onTranscript={() => undefined} />);
    expect(screen.getByRole("button", { name: "开始语音输入" })).toBeEnabled();
  });

  it("disables the control and explains unsupported browsers", () => {
    render(<SpeechInputButton onTranscript={() => undefined} />);
    expect(screen.getByRole("button", { name: "开始语音输入" })).toBeDisabled();
    expect(screen.getByRole("status")).toHaveTextContent("不支持 Web Speech API");
  });

  it("reports a browser permission denial", () => {
    installRecognition();
    render(<SpeechInputButton onTranscript={() => undefined} />);
    fireEvent.click(screen.getByRole("button", { name: "开始语音输入" }));
    act(() => FakeRecognition.latest.fail("not-allowed"));
    expect(screen.getByRole("status")).toHaveTextContent("权限被拒绝");
  });

  it("reports a missing microphone separately from permission denial", () => {
    installRecognition();
    render(<SpeechInputButton onTranscript={() => undefined} />);
    fireEvent.click(screen.getByRole("button", { name: "开始语音输入" }));
    act(() => FakeRecognition.latest.fail("audio-capture"));
    expect(screen.getByRole("status")).toHaveTextContent("未检测到可用麦克风");
  });

  it("maps a synchronous permission exception from start()", () => {
    class DeniedRecognition extends FakeRecognition { start = vi.fn(() => { throw new DOMException("denied", "NotAllowedError"); }); }
    Object.defineProperty(window, "SpeechRecognition", { value: DeniedRecognition, configurable: true });
    render(<SpeechInputButton onTranscript={() => undefined} />);
    fireEvent.click(screen.getByRole("button", { name: "开始语音输入" }));
    expect(screen.getByRole("status")).toHaveTextContent("权限被拒绝");
  });

  it("cleans up an active recognizer on unmount", () => {
    installRecognition();
    const view = render(<SpeechInputButton onTranscript={() => undefined} />);
    fireEvent.click(screen.getByRole("button", { name: "开始语音输入" }));
    view.unmount();
    expect(FakeRecognition.latest.abort).toHaveBeenCalledOnce();
  });

  it("warns that some browser speech engines send audio to a provider", () => {
    installRecognition();
    render(<SpeechInputButton onTranscript={() => undefined} />);
    expect(screen.getByText(/可能调用厂商服务并发送音频/)).toBeInTheDocument();
  });
});
