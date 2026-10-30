import { useState } from "react";
import { createRoot } from "react-dom/client";
import SpeechInputButton from "../SpeechInputButton";
import "./preview.css";

function VoicePreview() {
  const [draft, setDraft] = useState("");
  return <main className="voice-preview">
    <header><span className="voice-preview-mark">澄</span><div><b>澄衡 Aetheris</b><small>语音输入组件预览</small></div></header>
    <h1>语音转写</h1>
    <p>点击麦克风，中文识别结果只会填入下面的草稿框；此预览没有发送按钮，也不会提交内容。</p>
    <label htmlFor="voice-draft">草稿</label>
    <textarea id="voice-draft" value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="识别内容会填入这里；你也可以编辑。" />
    <SpeechInputButton onTranscript={setDraft} />
    <footer>识别由浏览器 SpeechRecognition 实现；不同浏览器可能使用厂商云端服务处理音频，并非承诺离线识别。</footer>
  </main>;
}

createRoot(document.getElementById("root")!).render(<VoicePreview />);
