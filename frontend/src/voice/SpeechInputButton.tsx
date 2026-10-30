import { useEffect, useRef, useState } from "react";
import { Mic, MicOff } from "lucide-react";
import "./speech-input.css";

export type SpeechInputStatus = "idle" | "starting" | "listening" | "unsupported" | "permission-denied" | "microphone-unavailable" | "error";
type SpeechResultAlternative = { transcript: string };
type SpeechResult = { isFinal: boolean; length: number; [index: number]: SpeechResultAlternative };
type SpeechResultEvent = { resultIndex: number; results: ArrayLike<SpeechResult> };
type SpeechErrorEvent = { error: string; message?: string };
type SpeechRecognitionLike = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  maxAlternatives: number;
  onstart: (() => void) | null;
  onresult: ((event: SpeechResultEvent) => void) | null;
  onerror: ((event: SpeechErrorEvent) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
  abort: () => void;
};
type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;
type SpeechWindow = Window & { SpeechRecognition?: SpeechRecognitionConstructor; webkitSpeechRecognition?: SpeechRecognitionConstructor };

const getRecognition = () => {
  if (typeof window === "undefined") return undefined;
  const speech = window as SpeechWindow;
  return (speech.SpeechRecognition ?? speech.webkitSpeechRecognition) as SpeechRecognitionConstructor | undefined;
};

function errorStatus(code: string): SpeechInputStatus {
  const normalized = code.toLowerCase();
  if (["not-allowed", "service-not-allowed", "permission-denied", "notallowederror", "securityerror"].includes(normalized)) return "permission-denied";
  if (["audio-capture", "no-microphone", "not-found"].includes(normalized)) return "microphone-unavailable";
  return "error";
}

const STATUS_TEXT: Record<SpeechInputStatus, string> = {
  idle: "点击麦克风开始中文语音输入。",
  starting: "正在请求语音识别权限…",
  listening: "正在听写；转写仅填入输入框，不会自动发送。",
  unsupported: "此浏览器不支持 Web Speech API 语音识别。",
  "permission-denied": "麦克风或语音识别权限被拒绝，请在浏览器站点权限中允许后重试。",
  "microphone-unavailable": "未检测到可用麦克风，请检查设备连接与系统权限。",
  error: "语音识别服务暂不可用，请重试或直接输入文字。",
};

/** Browser speech-to-text only. The caller decides how a transcript updates its draft; this component never submits. */
export function SpeechInputButton({ onTranscript, onStatus, disabled = false }: {
  onTranscript: (transcript: string) => void;
  onStatus?: (status: SpeechInputStatus) => void;
  disabled?: boolean;
}) {
  const [status, setStatus] = useState<SpeechInputStatus>(() => getRecognition() ? "idle" : "unsupported");
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const mountedRef = useRef(true);
  const supported = status !== "unsupported";
  const listening = status === "starting" || status === "listening";

  useEffect(() => {
    onStatus?.(status);
  }, [status, onStatus]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      recognitionRef.current?.abort();
      recognitionRef.current = null;
    };
  }, []);

  const stop = () => {
    const recognition = recognitionRef.current;
    if (!recognition) return;
    setStatus("idle");
    recognition.stop();
  };

  const start = () => {
    const Constructor = getRecognition();
    if (!Constructor) { setStatus("unsupported"); return; }
    let recognition: SpeechRecognitionLike;
    try {
      recognition = new Constructor();
      recognition.lang = "zh-CN";
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.maxAlternatives = 1;
    } catch {
      setStatus("error");
      return;
    }
    recognitionRef.current = recognition;
    recognition.onstart = () => { if (mountedRef.current) setStatus("listening"); };
    recognition.onresult = (event) => {
      const chunks: string[] = [];
      for (let index = 0; index < event.results.length; index += 1) {
        const transcript = event.results[index]?.[0]?.transcript?.trim();
        if (transcript) chunks.push(transcript);
      }
      const transcript = chunks.join("").trim();
      if (transcript && mountedRef.current) onTranscript(transcript);
    };
    recognition.onerror = (event) => { if (mountedRef.current) setStatus(errorStatus(event.error)); };
    recognition.onend = () => {
      if (!mountedRef.current) return;
      recognitionRef.current = null;
      setStatus((current) => current === "permission-denied" || current === "microphone-unavailable" || current === "error" ? current : "idle");
    };
    setStatus("starting");
    try {
      recognition.start();
    } catch (error) {
      recognitionRef.current = null;
      setStatus(errorStatus(error instanceof DOMException ? error.name : "error"));
    }
  };

  return <span className="speech-input">
    <button type="button" className={`speech-input-button${listening ? " is-listening" : ""}`} onClick={listening ? stop : start} disabled={disabled || !supported} aria-label={listening ? "停止语音输入" : "开始语音输入"} aria-pressed={listening} title={listening ? "停止语音输入" : "开始语音输入"}>
      {listening ? <MicOff size={17} aria-hidden="true"/> : <Mic size={17} aria-hidden="true"/>}
    </button>
    <span className={`speech-input-status status-${status}`} role="status" aria-live="polite">{STATUS_TEXT[status]}</span>
    <span className="speech-input-privacy">浏览器语音识别可能调用厂商服务并发送音频；请主动点击开始，识别结果只进入草稿。</span>
  </span>;
}

export default SpeechInputButton;
