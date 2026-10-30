import { AssistantRuntimeProvider, MessagePrimitive, ThreadPrimitive, useExternalStoreRuntime, MessagePartPrimitive, useMessagePartText } from "@assistant-ui/react";
import { useRef, useState, type ComponentProps, type ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Message } from "./api";
import type { ApiEvent } from "./api";
import { ActivityTrace } from "./components/trace/ActivityTrace";
import { presentMessage } from "./messagePresentation";

export default function AssistantMessages({messages,events=[]}:{messages:Message[];events?:ApiEvent[]}){
 const runtime=useExternalStoreRuntime<Message>({
   messages,
   convertMessage:m=>{const presentation=presentMessage(m);const longProse=presentation.finalText.length>500&&!presentation.finalText.includes("```");return {id:m.id,role:m.role,content:[{type:"text",text:m.role==="assistant"&&longProse?"长篇研判报告已折叠，请展开下方原文。":presentation.finalText}]}},
   onNew:async()=>undefined,
 });
 return <AssistantRuntimeProvider runtime={runtime}><ThreadPrimitive.Root className="assistant-thread">
   <ThreadPrimitive.Messages>{({message})=>{const source=messages.find(item=>item.id===message.id);const presentation=source?presentMessage(source):{finalText:""};return <MessagePrimitive.Root id={`message-${message.id}`} key={message.id} className={`message-row ${message.role}`}>
     {message.role==="assistant"&&<div className="avatar bot"><img src="/assets/aether-icon.png" alt="AETHER" /></div>}
     <div className="message-bubble">{source?.attachments?.map(file=><a className="message-attachment" key={file.id} href={`/api/conversations/${encodeURIComponent(file.conversation_id)}/files/${encodeURIComponent(file.id)}/download`}>{file.original_name}</a>)}{message.role==="assistant"&&source?.run_id&&<ActivityTrace runId={String(source.run_id)} events={events} title="本轮过程摘要" processSummary={presentation.processSummary}/>}<MessagePrimitive.Parts>{({part})=>part.type==="text"?<MessagePartPrimitive.Text smooth={false} render={<MarkdownText/>}/>:null}</MessagePrimitive.Parts></div>
   </MessagePrimitive.Root>}}</ThreadPrimitive.Messages>
 </ThreadPrimitive.Root></AssistantRuntimeProvider>;
}
export function LongReports({messages}:{messages:Message[]}){return <div className="long-report-list">{messages.map(message=>({message,presentation:presentMessage(message)})).filter(({message,presentation})=>message.role==="assistant"&&presentation.finalText.length>500).map(({message,presentation})=><details className="full-report" key={message.id}><summary>展开完整报告原文（{presentation.finalText.length} 字）</summary><ReactMarkdown remarkPlugins={[remarkGfm]}>{presentation.finalText}</ReactMarkdown></details>)}</div>}
function MarkdownText(){const part=useMessagePartText();return <ReactMarkdown remarkPlugins={[remarkGfm]} components={{pre:CopyableCodeBlock}}>{part.text}</ReactMarkdown>}
function CopyableCodeBlock({children,...props}:ComponentProps<"pre">){
 const codeRef=useRef<HTMLPreElement>(null);const [copied,setCopied]=useState(false);
 const copy=async()=>{const text=codeRef.current?.textContent||"";if(!text)return;try{await navigator.clipboard?.writeText(text);setCopied(true);window.setTimeout(()=>setCopied(false),1400)}catch{/* Clipboard may be unavailable on non-secure origins; text remains selectable. */}};
 return <div className="markdown-code-wrap"><button type="button" aria-label="复制代码" title="复制完整代码" onClick={()=>void copy()}>{copied?"已复制":"复制代码"}</button><pre {...props} ref={codeRef}>{children as ReactNode}</pre></div>;
}
