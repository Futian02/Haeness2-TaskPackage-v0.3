import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Edge, Node } from "@xyflow/react";
import { Activity, ArrowUpRight, BookOpen, Check, ChevronDown, ChevronRight, CircleHelp, Clipboard, Clock3, FileText, GitBranch, History, LoaderCircle, Menu, Moon, PanelLeftClose, PanelLeftOpen, Plus, Search, Send, Settings, ShieldCheck, Sun, Wrench, X, Paperclip, BarChart3, Globe2 } from "lucide-react";
import { api, consumeRun, eventKind, publicRunFailureCode, publicRunFailureMessage, RunRequestError, RunStreamError, type ApiEvent, type Conversation, type ConversationDetail, type Health, type Message, type PublicRunFailureCode, type RunCreated, type RunInput, type UploadedFile, type WebMode } from "./api";
import { Button } from "./components/ui/button";
import { Badge } from "./components/ui/badge";
import { aggregateClaims, agentStates, claimStatus, localRunEventCount, localRunIds, observedAgentEdges, rememberRun } from "./uiModel";
import EngineeringReport, { type RunSnapshot } from "./EngineeringReport";
import ConversationThreadList from "./ConversationThreadList";
import { presentMessage } from "./messagePresentation";
import SettingsShell from "./SettingsShell";
import { PREFERENCES_KEY, readPreferences, writePreferences, type UserPreferences } from "./settings/preferences";
import { UsageDashboard } from "./dashboard";
import { SpeechInputButton } from "./voice/SpeechInputButton";
import { contractState, contractStateMessage, EXPECTED_CONTRACT_VERSION, FRONTEND_BUILD_FINGERPRINT, shortFingerprint } from "./runtimeContract";

const roles = ["supervisor", "evidence_agent", "diagnosis_agent", "rbi_specialist", "evidence_auditor", "skeptic", "reporting_agent"];
const AgentFlow = lazy(()=>import("./AgentFlow"));
const AssistantMessages = lazy(()=>import("./AssistantMessages"));
const roleNames: Record<string,string> = { supervisor:"任务路由", evidence_agent:"证据检索", diagnosis_agent:"候选分析", rbi_specialist:"RBI 专家", evidence_auditor:"证据审计", skeptic:"独立反证", reporting_agent:"报告汇总" };
const titleFor = (c: Conversation) => c.title || "未命名对话";
const mediaQuery=(query:string)=>typeof window.matchMedia==="function"?window.matchMedia(query):null;

function App() {
  const [health,setHealth]=useState<Health|null>(null);
  const [conversations,setConversations]=useState<Conversation[]>([]);
  const [selected,setSelected]=useState<string|null>(null);
  const [detail,setDetail]=useState<ConversationDetail|null>(null);
  const [events,setEvents]=useState<ApiEvent[]>([]);
  const [eventHistory,setEventHistory]=useState<Record<string,ApiEvent[]>>({});
  const [running,setRunning]=useState(false);
  const [runningSessions,setRunningSessions]=useState<Record<string,string>>({});
  const [runHistory,setRunHistory]=useState<string[]>([]);
  const [viewRun,setViewRun]=useState<string|null>(null);
  const [runSnapshot,setRunSnapshot]=useState<RunSnapshot|null>(null);
  const [error,setError]=useState("");
  const [runFailure,setRunFailure]=useState<{runId:string;code:PublicRunFailureCode}|null>(null);
  const [query,setQuery]=useState("");
  const [prompt,setPrompt]=useState("");
  const [webMode,setWebModeState]=useState<WebMode>("auto");
  const [allowSensitiveWebSearch,setAllowSensitiveWebSearch]=useState(false);
  const [preferences,setPreferences]=useState<UserPreferences>(()=>{
    const saved=readPreferences();
    if(!localStorage.getItem(PREFERENCES_KEY)){const legacy=localStorage.getItem("aether-theme");if(legacy==="light"||legacy==="dark")return {...saved,theme:legacy};}
    return saved;
  });
  const [mode,setMode]=useState<"light"|"dark">(()=>{
    const saved=readPreferences();const legacy=localStorage.getItem("aether-theme");const theme=localStorage.getItem(PREFERENCES_KEY)?saved.theme:(legacy==="light"||legacy==="dark"?legacy:saved.theme);
    return theme==="system"?(mediaQuery("(prefers-color-scheme: dark)")?.matches?"dark":"light"):theme;
  });
  const [settingsOpen,setSettingsOpen]=useState(false);
  const [statsOpen,setStatsOpen]=useState(false);
  const [sidebarCollapsed,setSidebarCollapsed]=useState(()=>localStorage.getItem("aetheris-sidebar-collapsed")==="true");
  const [desktopViewport,setDesktopViewport]=useState(()=>mediaQuery("(min-width: 701px)")?.matches??true);
  const [archivedConversations,setArchivedConversations]=useState<Conversation[]>([]);
  const [archiveLoading,setArchiveLoading]=useState(false);
  const [mobilePanel,setMobilePanel]=useState<"chat"|"history"|"evidence">("chat");
  const [inspector,setInspector]=useState(false);
  const [evidence,setEvidence]=useState<Record<string,unknown>|null>(null);
  const [flowExpanded,setFlowExpanded]=useState(false);
  const [eventsOpen,setEventsOpen]=useState(()=>readPreferences().autoExpandTrace);
  const [mobileMenu,setMobileMenu]=useState(false);
  const [contextOpen,setContextOpen]=useState(false);
  const [context,setContext]=useState({equipment:"",equipment_type:"",material:"",medium:"",operating_condition:"",field_evidence:""});
  const emptyContext=()=>({equipment:"",equipment_type:"",material:"",medium:"",operating_condition:"",field_evidence:""});
  const clearPendingSubmission=(cid:string)=>{for(const suffix of ["key","question","body"])localStorage.removeItem(`aether:pending-run-${suffix}:${cid}`)};
  const updateContext=(next:typeof context)=>{setContext(next);const cid=selectedRef.current;if(cid){localStorage.setItem(`aether:context:${cid}`,JSON.stringify(next));clearPendingSubmission(cid)}};
  const [files,setFiles]=useState<UploadedFile[]>([]);
  const [selectedFileIds,setSelectedFileIds]=useState<string[]>([]);
  const [uploading,setUploading]=useState(false);
  const [preview,setPreview]=useState<{name:string;text:string}|null>(null);
  const fileInput=useRef<HTMLInputElement>(null);
  const selectedRef=useRef<string|null>(null);
  const loadEpoch=useRef(0);
  const viewRunRef=useRef<string|null>(null);
  const loadController=useRef<AbortController|null>(null);
  const runControllers=useRef(new Map<string,AbortController>());
  const runBySession=useRef(new Map<string,string>());
  const runHistoryForResume=useRef(new Map<string,string>());
  const resumeExistingRun=useCallback(async(sessionId:string,runId:string)=>{
    if(runBySession.current.has(sessionId))return;
    const controller=new AbortController();runBySession.current.set(sessionId,runId);runControllers.current.set(runId,controller);setRunningSessions(previous=>({...previous,[sessionId]:runId}));if(selectedRef.current===sessionId)setRunning(true);
    const run:RunCreated={run_id:runId,status:"running",mode:"RULE_DEMO",events_url:`/api/runs/${encodeURIComponent(runId)}/stream`};
    try{
      await consumeRun(run,event=>{
        const cached=JSON.parse(localStorage.getItem(`aether:run-events:${sessionId}:${runId}`)||"[]") as ApiEvent[];
        if(!cached.some(item=>item.run_id===event.run_id&&item.sequence===event.sequence)){cached.push(event);cached.sort((a,b)=>a.sequence-b.sequence);localStorage.setItem(`aether:run-events:${sessionId}:${runId}`,JSON.stringify(cached))}
        setEventHistory(previous=>({...previous,[runId]:[...(previous[runId]||[]).filter(item=>item.sequence!==event.sequence),event].sort((a,b)=>a.sequence-b.sequence)}));
        if(selectedRef.current===sessionId&&viewRunRef.current===runId)setEvents(previous=>{const next=previous.some(item=>item.sequence===event.sequence)?previous:[...previous,event];setRunFailureFromEvents(runId,next,setRunFailure);return next});
      },controller.signal,5);
      const detailNext=await api.getConversation(sessionId,controller.signal);if(selectedRef.current===sessionId)setDetail(detailNext);
    }catch(error){if(!controller.signal.aborted&&selectedRef.current===sessionId)setError("运行仍可从持久事件恢复；实时连接暂未恢复，请稍后重新连接。")}
    finally{if(runControllers.current.get(runId)===controller)runControllers.current.delete(runId);if(runBySession.current.get(sessionId)===runId)runBySession.current.delete(sessionId);setRunningSessions(previous=>{const next={...previous};delete next[sessionId];return next});if(selectedRef.current===sessionId)setRunning(false)}
  },[]);
  const changeWebMode=(value:WebMode)=>{
    setWebModeState(value);
    const cid=selectedRef.current;
    if(cid){localStorage.setItem(`aether:web-mode:${cid}`,value);clearPendingSubmission(cid)}
    if(value!=="on")setAllowSensitiveWebSearch(false);
  };

  const reloadConversations=useCallback(async()=>{setConversations(await api.listConversations())},[]);
  const loadConversation=useCallback(async(id:string,clearEvents=true)=>{
    const epoch=++loadEpoch.current;loadController.current?.abort();const controller=new AbortController();loadController.current=controller;
    selectedRef.current=id;setSelected(id);setPrompt(localStorage.getItem(`aether:draft:${id}`)||"");try{const savedContext=JSON.parse(localStorage.getItem(`aether:context:${id}`)||"null");setContext(savedContext&&typeof savedContext==="object"?{...emptyContext(),...savedContext}:emptyContext())}catch{setContext(emptyContext())}const savedWebMode=localStorage.getItem(`aether:web-mode:${id}`);setWebModeState(savedWebMode==="off"||savedWebMode==="on"||savedWebMode==="auto"?savedWebMode:"auto");setAllowSensitiveWebSearch(false);setRunHistory(localRunIds(id));let selectedRun=localStorage.getItem(`aether:last-run:${id}`);viewRunRef.current=selectedRun;setViewRun(selectedRun);setRunSnapshot(readRunSnapshot(id,selectedRun));
    if(clearEvents)setEvents([]);if(clearEvents)setEventHistory({});if(clearEvents)setRunFailure(null);setError("");setRunning(Boolean(runBySession.current.get(id)));
    try {const next=await api.getConversation(id,controller.signal);if(epoch!==loadEpoch.current||selectedRef.current!==id)return;setDetail(next);setSelectedFileIds([]);if(api.listFiles)setFiles(await api.listFiles(id));
      try{const persisted=await api.listRuns(id,controller.signal);if(epoch===loadEpoch.current&&selectedRef.current===id){for(const run of persisted)runHistoryForResume.current.set(run.id,run.status);const ids=[...persisted.map(run=>run.id),...localRunIds(id).filter(runId=>!persisted.some(run=>run.id===runId))];setRunHistory(ids);if(!selectedRun&&persisted.length){selectedRun=persisted[0].id;viewRunRef.current=selectedRun;setViewRun(selectedRun);setRunSnapshot(readRunSnapshot(id,selectedRun));}const selectedSummary=persisted.find(run=>run.id===selectedRun);if(selectedSummary?.status==="failed")setRunFailure({runId:selectedSummary.id,code:publicRunFailureCode(selectedSummary.error_code)});const history=await Promise.all(persisted.map(async run=>{try{return [run.id,(await api.replay(run.id,0,controller.signal)).events] as const}catch{return [run.id,[]] as const}}));if(epoch===loadEpoch.current&&selectedRef.current===id)setEventHistory(Object.fromEntries(history))}}catch{/* older API: keep localStorage run index */}
      if(clearEvents){const previousRun=selectedRun;if(previousRun){try{const serverSnapshot=await api.runInput(previousRun) as Record<string,any>;if(serverSnapshot.conversation_id===id){const restoredSnapshot=fromServerRunSnapshot(id,previousRun,serverSnapshot);setRunSnapshot(restoredSnapshot);localStorage.setItem(`aether:run-snapshot:${id}:${previousRun}`,JSON.stringify(restoredSnapshot))}}catch{/* no snapshot endpoint on an older backend: retain local display only */}try{const replay=await api.replay(previousRun,0,controller.signal);if(epoch!==loadEpoch.current||selectedRef.current!==id)return;const restored=replay.events.filter(e=>e.run_id===previousRun).sort((a,b)=>a.sequence-b.sequence);setEvents(restored);setRunFailureFromEvents(previousRun,restored,setRunFailure);localStorage.setItem(`aether:run-events:${id}:${previousRun}`,JSON.stringify(restored));const summary=runHistoryForResume.current.get(previousRun);const terminal=restored.some(e=>["run_completed","run_failed","error"].includes(eventKind(e)));if(!terminal&&summary&&["queued","running","claimed","pending"].includes(summary))void resumeExistingRun(id,previousRun);}catch(e){if(!controller.signal.aborted){const cached=localStorage.getItem(`aether:run-events:${id}:${previousRun}`);if(cached){const restored=JSON.parse(cached) as ApiEvent[];setEvents(restored);setRunFailureFromEvents(previousRun,restored,setRunFailure);}}}}}
    } catch(e){if(!controller.signal.aborted&&epoch===loadEpoch.current)setError(`对话加载失败：${String((e as Error).message||e)}`)}
  },[resumeExistingRun]);
  useEffect(()=>{document.documentElement.dataset.theme=mode;localStorage.setItem("aether-theme",mode);document.title="澄衡 Aetheris · 智能工程助手"},[mode]);
  useEffect(()=>{writePreferences(preferences);const applyTheme=()=>setMode(preferences.theme==="system"?(mediaQuery("(prefers-color-scheme: dark)")?.matches?"dark":"light"):preferences.theme);applyTheme();if(preferences.theme!=="system")return;const query=mediaQuery("(prefers-color-scheme: dark)");query?.addEventListener?.("change",applyTheme);return()=>query?.removeEventListener?.("change",applyTheme)},[preferences]);
  useEffect(()=>{const query=mediaQuery("(min-width: 701px)");if(!query)return;const update=()=>setDesktopViewport(query.matches);update();query.addEventListener?.("change",update);return()=>query.removeEventListener?.("change",update)},[]);
  useEffect(()=>{localStorage.setItem("aetheris-sidebar-collapsed",String(sidebarCollapsed))},[sidebarCollapsed]);
  useEffect(()=>{Promise.all([api.health(),api.listConversations()]).then(([h,c])=>{setHealth(h);setConversations(c);if(c.length) void loadConversation(c[0].id)}).catch(e=>setError(`后端连接失败：${String(e.message||e)}`))},[loadConversation]);

  const reconnectBackend=async()=>{
    setError("");
    try {
      const [updatedHealth, rows]=await Promise.all([api.health(),api.listConversations()]);
      setHealth(updatedHealth);
      setConversations(rows);
      const target=selectedRef.current && rows.some(row=>row.id===selectedRef.current)
        ? selectedRef.current : rows[0]?.id;
      if(target) await loadConversation(target,true);
    } catch(e) {
      setError(`服务恢复失败：${String((e as Error).message||e)}`);
    }
  };
  const createConversation=async()=>{try{const c=await api.createConversation();await reloadConversations();await loadConversation(c.id);setMobilePanel("chat")}catch(e){setError(String((e as Error).message||e))}};
  const upload=async(list:FileList|null)=>{const cid=selectedRef.current;if(!cid||!list?.length)return;setUploading(true);setError("");try{const added=await api.uploadFiles(cid,Array.from(list).slice(0,5));setFiles(old=>[...old,...added.filter(x=>!old.some(y=>y.id===x.id))]);setSelectedFileIds(old=>[...new Set([...old,...added.map(x=>x.id)])])}catch(e){setError(`上传失败：${String((e as Error).message||e)}`)}finally{setUploading(false);if(fileInput.current)fileInput.current.value=""}};
  const rename=async(c:Conversation)=>{const value=window.prompt("重命名会话",c.title);if(value?.trim()){const updated=await api.renameConversation(c.id,value.trim());setConversations(rows=>rows.map(x=>x.id===c.id?updated:x));if(selectedRef.current===c.id)setDetail(d=>d?{...d,...updated}:d)}};
  const archiveConversation=async(item:Conversation)=>{
    if(runBySession.current.has(item.id)){window.alert("当前对话正在执行，请先结束后再移出列表。");return;}
    if(!window.confirm(`将「${titleFor(item)}」移出历史列表？\n记录仍保存在本地数据库，可恢复。`))return;
    try{
      await api.archiveConversation(item.id,true);
      const available=await api.listConversations();
      setConversations(available);
      if(selectedRef.current===item.id){
        if(available.length)await loadConversation(available[0].id);
        else{selectedRef.current=null;setSelected(null);setDetail(null);setEvents([]);setEventHistory({});setRunHistory([]);setViewRun(null);setRunSnapshot(null);}
      }
    }catch(e){setError(`移出列表失败：${String((e as Error).message||e)}`);}
  };
  const loadArchivedConversations=async()=>{setArchiveLoading(true);try{const rows=await api.listConversations(true);setArchivedConversations(rows.filter(item=>Boolean((item as Conversation&{archived_at?:string|null}).archived_at)));}catch(e){setError(`归档读取失败：${String((e as Error).message||e)}`)}finally{setArchiveLoading(false)}};
  const restoreConversation=async(item:Conversation)=>{await api.archiveConversation(item.id,false);const [active,archived]=await Promise.all([api.listConversations(),api.listConversations(true)]);setConversations(active);setArchivedConversations(archived.filter(row=>Boolean((row as Conversation&{archived_at?:string|null}).archived_at)));};
  const refreshHealth=async()=>{const next=await api.health();setHealth(next)};
  const postRun=async(text:string)=>{
    const sessionId=selectedRef.current;if(!sessionId||!text.trim()||runBySession.current.has(sessionId))return;
    const question=text.trim();setError("");setRunFailure(null);setRunning(true);setEvents([]);localStorage.setItem(`aether:draft:${sessionId}`,text);
    const optimistic:Message={id:`pending-${Date.now()}`,role:"user",content:question};
    const input:RunInput={question,equipment:context.equipment,equipment_type:context.equipment_type,material:context.material,medium:context.medium.split(/[,，、]/).map(x=>x.trim()).filter(Boolean),operating_condition:context.operating_condition,field_evidence:context.field_evidence,mode:health?.default_mode||"RULE_DEMO",model_profile_id:health?.llm?.profile_id||undefined,file_ids:selectedFileIds,web_mode:webMode,allow_sensitive_web_search:webMode==="on"&&allowSensitiveWebSearch};
    setAllowSensitiveWebSearch(false);
    const controller=new AbortController();runBySession.current.set(sessionId,"pending");
    const pendingKeyName=`aether:pending-run-key:${sessionId}`;
    const pendingQuestionName=`aether:pending-run-question:${sessionId}`;
    const pendingBodyName=`aether:pending-run-body:${sessionId}`;
    const previousPendingKey=localStorage.getItem(pendingKeyName);
    const idempotencyKey=previousPendingKey&&localStorage.getItem(pendingQuestionName)===question?previousPendingKey:createIdempotencyKey();
    let exactInput=input;
    if(previousPendingKey&&localStorage.getItem(pendingQuestionName)===question){try{const saved=JSON.parse(localStorage.getItem(pendingBodyName)||"null") as RunInput|null;if(saved?.question===question)exactInput=saved}catch{/* create a fresh immutable request snapshot */}}
    localStorage.setItem(pendingKeyName,idempotencyKey);
    localStorage.setItem(pendingQuestionName,question);
    localStorage.setItem(pendingBodyName,JSON.stringify(exactInput));
    setDetail(d=>d&&!d.messages.some(m=>m.id===optimistic.id)?{...d,messages:[...d.messages,optimistic]}:d);
    try { const run=await api.createRun(sessionId,exactInput,idempotencyKey);
      clearPendingSubmission(sessionId);
      if(run.legacy_compatibility) setError("当前运行的是旧版后端：本轮已按基础协议发送。自动联网、独立模型配置及新版执行能力未启用，请更新运行服务。");
      setSelectedFileIds([]);runBySession.current.set(sessionId,run.run_id);runControllers.current.set(run.run_id,controller);rememberRun(sessionId,run.run_id);const snapshot:RunSnapshot={runId:run.run_id,conversationId:sessionId,capturedAt:new Date().toISOString(),mode:exactInput.mode,webMode:exactInput.web_mode,question,context:{equipment:exactInput.equipment,equipment_type:exactInput.equipment_type,material:exactInput.material,medium:exactInput.medium,operating_condition:exactInput.operating_condition,field_evidence:exactInput.field_evidence}};localStorage.setItem(`aether:run-snapshot:${sessionId}:${run.run_id}`,JSON.stringify(snapshot));setRunSnapshot(snapshot);setRunHistory(localRunIds(sessionId));viewRunRef.current=run.run_id;if(selectedRef.current===sessionId)setViewRun(run.run_id);setRunningSessions(prev=>({...prev,[sessionId]:run.run_id}));
      const serverSnapshot=await api.runInput(run.run_id) as Record<string,any>;const persisted=fromServerRunSnapshot(sessionId,run.run_id,serverSnapshot);localStorage.setItem(`aether:run-snapshot:${sessionId}:${run.run_id}`,JSON.stringify(persisted));setRunSnapshot(persisted);
      await consumeRun(run,e=>{const cached=JSON.parse(localStorage.getItem(`aether:run-events:${sessionId}:${run.run_id}`)||"[]") as ApiEvent[];if(!cached.some(x=>x.run_id===e.run_id&&x.sequence===e.sequence)){cached.push(e);cached.sort((a,b)=>a.sequence-b.sequence);localStorage.setItem(`aether:run-events:${sessionId}:${run.run_id}`,JSON.stringify(cached))}setEventHistory(prev=>({...prev,[run.run_id]:[...(prev[run.run_id]||[]).filter(x=>x.sequence!==e.sequence),e].sort((a,b)=>a.sequence-b.sequence)}));if(selectedRef.current===sessionId&&viewRunRef.current===run.run_id){setEvents(prev=>{const next=prev.some(x=>x.run_id===e.run_id&&x.sequence===e.sequence)?prev:[...prev,e];setRunFailureFromEvents(run.run_id,next,setRunFailure);return next})}},controller.signal,5);
      localStorage.removeItem(`aether:draft:${sessionId}`);setPrompt(current=>current===text?"":current);
      const refreshed=await api.getConversation(sessionId,controller.signal);if(selectedRef.current===sessionId)setDetail(refreshed);try{const persisted=await api.listRuns(sessionId,controller.signal);if(selectedRef.current===sessionId)setRunHistory(persisted.map(item=>item.id))}catch{/* localStorage remains the compatible fallback */}await reloadConversations();
    }
    catch(e){if(!controller.signal.aborted&&selectedRef.current===sessionId){const runId=runBySession.current.get(sessionId);const code=e instanceof RunStreamError?e.code:"connection_lost";if(runId&&runId!=="pending")setRunFailure({runId,code});const detail=e instanceof Error&&e.message.startsWith("BACKEND_VERSION_MISMATCH:")?e.message.replace(/^BACKEND_VERSION_MISMATCH:\s*/,""):null;setError(detail||(e instanceof RunRequestError?e.message:publicRunFailureMessage(code)));}try{const refreshed=await api.getConversation(sessionId);if(selectedRef.current===sessionId)setDetail(refreshed)}catch{/* retain visible failure */}}
    finally{const runId=runBySession.current.get(sessionId);if(runId&&runId!=="pending")runControllers.current.delete(runId);runBySession.current.delete(sessionId);setRunningSessions(prev=>{const next={...prev};delete next[sessionId];return next});if(selectedRef.current===sessionId)setRunning(false)}
  };
  const resumeSameRun=()=>{const cid=selectedRef.current;const rid=runFailure?.runId;if(cid&&rid&&["run_queued_capacity","connection_lost"].includes(runFailure?.code||""))void resumeExistingRun(cid,rid)};
  const retry=()=>{const last=[...(detail?.messages||[])].reverse().find(m=>m.role==="user");if(last){clearPendingSubmission(selectedRef.current||"");void postRun(last.content)}};
  const retrySubmission=()=>{const cid=selectedRef.current;const draft=cid?localStorage.getItem(`aether:draft:${cid}`):null;if(draft)void postRun(draft)};
  const openRun=async(runId:string)=>{const sessionId=selectedRef.current;if(!sessionId)return;viewRunRef.current=runId;setViewRun(runId);setRunFailure(null);setRunSnapshot(readRunSnapshot(sessionId,runId));try{const data=await api.runInput(runId) as Record<string,any>;if(data.conversation_id===sessionId&&selectedRef.current===sessionId){const snap=fromServerRunSnapshot(sessionId,runId,data);setRunSnapshot(snap);localStorage.setItem(`aether:run-snapshot:${sessionId}:${runId}`,JSON.stringify(snap))}}catch{/* use cached snapshot only if server snapshot is unavailable */}try{const replay=await api.replay(runId,0);if(selectedRef.current===sessionId){const records=replay.events.sort((a,b)=>a.sequence-b.sequence);setEventHistory(prev=>({...prev,[runId]:records}));if(viewRunRef.current===runId){setEvents(records);setRunFailureFromEvents(runId,records,setRunFailure)}localStorage.setItem(`aether:run-events:${sessionId}:${runId}`,JSON.stringify(records))}}catch(e){if(selectedRef.current===sessionId&&viewRunRef.current===runId)setError("运行记录读取失败；请稍后重试。")}};
  useEffect(()=>{const onPageHide=()=>{for(const controller of runControllers.current.values())controller.abort();loadController.current?.abort()};window.addEventListener("pagehide",onPageHide);return()=>{window.removeEventListener("pagehide",onPageHide);onPageHide()}},[]);
  useEffect(()=>{viewRunRef.current=viewRun},[viewRun]);
  useEffect(()=>{setRunning(Boolean(selected&&runBySession.current.has(selected)))},[selected,runningSessions]);
  const filtered=conversations.filter(c=>titleFor(c).toLowerCase().includes(query.toLowerCase()));
  const statusByRole=useMemo(()=>agentStates(events,roles),[events]);
  const graphNodes:Node[]=roles.map((role,i)=>({id:role,position:{x:20+(i%3)*155,y:25+Math.floor(i/3)*110},data:{label:<div className="flow-card"><span className={`flow-dot ${statusByRole[role]}`}/><b>{roleNames[role]}</b><small>{{pending:"等待事件",started:"进行中",completed:"已完成",failed:"失败",skipped:"本次未触发"}[statusByRole[role]]}</small></div>},style:{width:138,padding:0,border:"0",background:"transparent"}}));
  const graphEdges:Edge[]=useMemo(()=>observedAgentEdges(events).map(e=>({...e,style:{stroke:"#79b6a7",strokeWidth:2},label:e.label,labelStyle:{fill:"#668276",fontSize:8}})),[events]);
  const claims=useMemo(()=>aggregateClaims(events),[events]);
  const failedCode=runFailure?.runId===viewRun?runFailure.code:failureCodeFromEvents(events);
  const runtimeContractStatus=contractState(health);
  const runtimeContractNotice=contractStateMessage(health);
  const renderTimeline=(compact=false)=><div className="timeline">{events.length===0?<div className="quiet">{running?<><LoaderCircle className="spin" size={15}/> 正在等待 SSE 事件…</>:"选择一个运行或发送问题后，此处显示真实事件"}</div>:events.map(e=>{const k=eventKind(e);return <button key={`${e.run_id}-${e.sequence}`} className="event-item" onClick={()=>setEvidence(eventEvidenceDetail(e))}><span className={`event-mark ${k.includes("error")?"red":k.includes("claim")||k.includes("contradiction")?"amber":""}`}/><span className="event-copy"><b>{roleNames[e.agent||""]||e.agent||k}</b><small>{k} · #{e.sequence}</small>{!compact&&<small className="event-note">{eventSummary(e)}</small>}</span><ChevronRight size={14}/></button>})}</div>;
  const compactSidebar=sidebarCollapsed&&desktopViewport&&mobilePanel!=="history"&&!mobileMenu;
  return <main className={`app-shell ${inspector?"":"focus-chat"}`} data-density={preferences.density} style={{ ...(compactSidebar?{gridTemplateColumns:inspector?"64px minmax(0,1fr) 340px":"64px minmax(0,1fr)"}:{}), zoom:preferences.fontScale/100 }}>
    <aside className={`sidebar ${mobilePanel==="history"||mobileMenu?"mobile-visible":""}`}>
      {compactSidebar?<div className="sidebar-collapsed-content"><button className="brand-mark" title="澄衡 Aetheris" aria-label="澄衡 Aetheris"><img src="/assets/aetheris-icon.svg" alt="" onLoad={event=>{const sibling=event.currentTarget.nextElementSibling as HTMLElement|null;if(sibling)sibling.style.display="none"}} onError={event=>{event.currentTarget.style.display="none"}}/><span>澄</span></button><button className="icon-button" aria-label="展开侧栏" title="展开侧栏" onClick={()=>setSidebarCollapsed(false)}><PanelLeftOpen size={17}/></button><button className="icon-button" aria-label="新建分析" title="新建分析" onClick={()=>void createConversation()}><Plus size={17}/></button><button className="icon-button" aria-label="打开设置" title="设置" onClick={()=>setSettingsOpen(true)}><Settings size={17}/></button></div>:<>
      <div className="brand"><div className="brand-mark"><img src="/assets/aetheris-icon.svg" alt="澄衡 Aetheris 标识" onLoad={event=>{const sibling=event.currentTarget.nextElementSibling as HTMLElement|null;if(sibling)sibling.style.display="none"}} onError={event=>{event.currentTarget.style.display="none"}}/><span>澄</span></div><div><strong>澄衡 Aetheris</strong><small>智能工程助手</small></div><button className="icon-button sidebar-collapse" aria-label="收起侧栏" title="收起侧栏" onClick={()=>setSidebarCollapsed(true)}><PanelLeftClose size={16}/></button><button className="icon-button mobile-close" aria-label="关闭历史" onClick={()=>{setMobilePanel("chat");setMobileMenu(false)}}><X size={18}/></button></div>
      <Button className="new-chat" onClick={()=>void createConversation()}><Plus size={16}/> 新建分析 <span>⌘ K</span></Button>
      <div className="sidebar-label"><span>工作区</span><button className="icon-button" aria-label="收起历史"><ChevronDown size={14}/></button></div>
      <label className="search-box"><Search size={15}/><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="搜索历史分析"/><kbd>⌘ /</kbd></label>
      <ConversationThreadList items={filtered} selected={selected} onCreate={()=>void createConversation()} onSelect={id=>{void loadConversation(id);setMobilePanel("chat")}} onRename={item=>void rename(item)} onArchive={item=>void archiveConversation(item)}/>{filtered.length===0&&<div className="empty-history">{query?"没有匹配的分析":"暂无历史分析"}</div>}
      <div className="sidebar-bottom"><div className="user-card"><div className="user-avatar">研</div><div><b>研究工作区</b><small>本地 · SQLite 持久化</small></div><span className="online-dot"/></div><div className="side-foot"><span className="status-pill"><i/> API {health?"在线":"连接中"}</span><span>v0.3 · {health?.mode||"RULE_DEMO"}</span></div></div>
      </>}
    </aside>
    <section className={`workspace ${mobilePanel==="chat"?"mobile-active":""}`}>
      <header className="topbar"><div className="crumbs"><button className="icon-button mobile-only" aria-label="打开历史" onClick={()=>setMobileMenu(true)}><Menu size={19}/></button><span>工程研判</span><ChevronRight size={14}/><b>{detail?titleFor(detail):"新建分析"}</b></div><div className="top-actions"><Badge className="mode-badge"><i/> {health?.mode||"连接中"}</Badge><button className="icon-button" onClick={()=>setPreferences(previous=>({...previous,theme:mode==="light"?"dark":"light"}))} aria-label="切换深浅色">{mode==="light"?<Moon size={17}/>:<Sun size={17}/>}</button><button className="icon-button" aria-label="打开设置" title="设置" onClick={()=>{setStatsOpen(false);setSettingsOpen(true)}}><Settings size={17}/></button><button className="icon-button" aria-label="打开统计" title="活动统计" onClick={()=>{setSettingsOpen(false);setStatsOpen(true)}}><BarChart3 size={17}/></button><button className="icon-button mobile-only" aria-label="打开审查" onClick={()=>{if(inspector)setMobilePanel("evidence");else{setInspector(true);setMobilePanel("evidence")}}}><Activity size={18}/></button><button className="inspector-toggle" aria-expanded={inspector} aria-label={inspector?"收起证据审查，专注聊天":"展开证据审查"} onClick={()=>setInspector(!inspector)}>{inspector?<ChevronRight size={15}/>:<GitBranch size={15}/>} <span>{inspector?"专注聊天":"证据审查"}</span></button></div></header>
      {health&&runtimeContractStatus!=="compatible"&&<div className={`contract-notice ${runtimeContractStatus}`} role="status" data-contract-state={runtimeContractStatus}><b>{runtimeContractStatus==="legacy"?"旧版后端":"版本握手异常"}</b><span>{runtimeContractNotice}</span><small>前端 {EXPECTED_CONTRACT_VERSION} · {shortFingerprint(FRONTEND_BUILD_FINGERPRINT)}；后端 {health.contract_version||"未提供版本"} · {shortFingerprint(health.build_fingerprint)}</small></div>}
      <div className="chat-scroll" id="chat-scroll"><div className="chat-inner">
        {(!detail||detail.messages.length===0)&&<div className="welcome"><div className="welcome-icon"><img src="/assets/aetheris-icon.svg" alt="澄衡 Aetheris 标识" /></div><div className="eyebrow">澄衡 Aetheris · 智能工程助手</div><h1>从证据开始，<em>逐步研判。</em></h1><p>围绕设备、工况与现场观察组织分析。每项判断都保留来源、适用条件与复核状态。</p><div className="starter-cards"><button onClick={()=>setPrompt("请基于现有设备信息梳理需要补充的工况与证据。")}> <span><BookOpen size={17}/></span><b>梳理缺失工况</b><small>定位需要补充的现场信息</small><ArrowUpRight size={15}/></button><button onClick={()=>setPrompt("请检索适用的标准条款，并列出原文范围与适用条件。")}> <span><FileText size={17}/></span><b>查找标准条款</b><small>核对条款与适用范围</small><ArrowUpRight size={15}/></button><button onClick={()=>setPrompt("请列出当前结论的证据依据、反证与待人工复核问题。")}> <span><ShieldCheck size={17}/></span><b>检查证据边界</b><small>查看依据、反证与待核项</small><ArrowUpRight size={15}/></button></div></div>}
        {detail?.messages.length? <>
          <div className="turn-jump" aria-label="本会话问题轮次">{detail.messages.filter(m=>m.role==="user").map((m,i)=><button key={m.id} title={m.content} onClick={()=>document.getElementById(`message-${m.id}`)?.scrollIntoView({behavior:"smooth",block:"center"})}>问题 {i+1}</button>)}</div>
          <EngineeringReport messages={detail.messages} events={events} claims={claims} runId={viewRun} snapshot={runSnapshot}/>
          {runSnapshot?.runId===viewRun&&<details className="run-context-snapshot"><summary>本轮服务端输入快照 · {runSnapshot.mode||health?.mode||"RULE_DEMO"} · 联网 {runSnapshot.webMode||"off"}</summary><p><b>问题：</b>{runSnapshot.question}</p><p><b>结构化工况：</b>{Object.entries(runSnapshot.context).filter(([,v])=>v!==undefined&&v!==""&&(!Array.isArray(v)||v.length)).map(([k,v])=>`${k}: ${Array.isArray(v)?v.join("、"):v}`).join("；")||"未填写"}</p><p><b>明确选择的附件：</b>{runSnapshot.attachments?.map(f=>f.original_name).join("、")||"无"}</p><p><b>可用历史消息：</b>{runSnapshot.historyMessageCount??0} 条；本轮历史纳入：{runSnapshot.historyIncluded?"是":"否（不自动纳入）"}</p></details>}
          <Suspense fallback={<div className="quiet">正在载入对话…</div>}><AssistantMessages messages={detail.messages} events={Object.values(eventHistory).flat()}/></Suspense>
          <LongReportDisclosure messages={detail.messages}/>
        </>:null}
        {running&&<div className="assistant-pending"><div className="avatar bot"><img src="/assets/aetheris-icon.svg" alt="澄衡 Aetheris" /></div><div><b>正在组织证据审查</b><p><LoaderCircle className="spin" size={14}/> 后端执行中 · SSE 实时事件已连接</p></div></div>}
        {events.some(e=>eventKind(e)==="run_completed")&&!failedCode&&<div className="run-footer"><span><Check size={14}/> 本轮执行已结束</span><button onClick={retry}>重试本轮 <ArrowUpRight size={13}/></button><button onClick={()=>setMobilePanel("evidence")}>查看审查轨迹</button></div>}
        {failedCode&&<div className="error-banner run-failure-card" role="alert" data-failure-code={failedCode}><CircleHelp size={16}/><span><b>本轮未完成 · </b>{publicRunFailureMessage(failedCode)}</span>{["run_queued_capacity","connection_lost"].includes(failedCode)?<button onClick={resumeSameRun} disabled={running}>继续等待原任务</button>:<button onClick={retry} disabled={running}>作为新运行重试 <ArrowUpRight size={14}/></button>}</div>}
        {error&&!failedCode&&<div className="error-banner" role="alert"><CircleHelp size={16}/><span>{error}</span>{localStorage.getItem(`aether:pending-run-key:${selected||""}`)?<button onClick={retrySubmission} disabled={running}>使用原请求重试</button>:<button onClick={()=>void reconnectBackend()}>重新连接</button>}</div>}
      </div></div>
      <div className="composer-wrap" onDragOver={e=>e.preventDefault()} onDrop={e=>{e.preventDefault();void upload(e.dataTransfer.files)}}>
        <div className="composer">
          <button className={`context-toggle ${contextOpen?"open":""}`} onClick={()=>setContextOpen(!contextOpen)}><Plus size={13}/><span>设备与工况 {Object.values(context).some(Boolean)?"· 已填写":"· 机理研判需填写材质/介质"}</span><ChevronDown size={13}/></button>
          {contextOpen&&<div className="context-grid">
            <input aria-label="设备名称" placeholder="设备名称" value={context.equipment} onChange={e=>updateContext({...context,equipment:e.target.value})}/>
            <input aria-label="设备类型" placeholder="设备类型" value={context.equipment_type} onChange={e=>updateContext({...context,equipment_type:e.target.value})}/>
            <input aria-label="材质" placeholder="材质" value={context.material} onChange={e=>updateContext({...context,material:e.target.value})}/>
            <input aria-label="介质" placeholder="介质（逗号分隔）" value={context.medium} onChange={e=>updateContext({...context,medium:e.target.value})}/>
            <input aria-label="运行工况" placeholder="温度、压力、年限等运行工况" value={context.operating_condition} onChange={e=>updateContext({...context,operating_condition:e.target.value})}/>
            <input aria-label="现场证据" placeholder="现场现象 / 检测证据" value={context.field_evidence} onChange={e=>updateContext({...context,field_evidence:e.target.value})}/>
          </div>}
          <textarea aria-label="发送问题" placeholder="描述设备、工况，或提出需要核查的问题…" value={prompt} onChange={e=>{const value=e.target.value;setPrompt(value);const cid=selectedRef.current;if(cid){localStorage.setItem(`aether:draft:${cid}`,value);if(localStorage.getItem(`aether:pending-run-question:${cid}`)!==value.trim())clearPendingSubmission(cid)}}} onKeyDown={e=>{if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();void postRun(prompt)}}}/>
          {files.length>0&&<div className="attached-files">{files.map(f=><span key={f.id}><button onClick={()=>void api.previewFile(f.conversation_id,f.id).then(p=>setPreview({name:f.original_name,text:p.text||p.message||`${p.page_count||0} 页 PDF`}))}>{f.original_name}</button><small>{selectedFileIds.includes(f.id)?"已选择本轮":f.extraction_status}</small><button aria-label={`${selectedFileIds.includes(f.id)?"取消选择":"选择"} ${f.original_name}`} onClick={()=>setSelectedFileIds(old=>old.includes(f.id)?old.filter(id=>id!==f.id):[...old,f.id])}><X size={12}/></button></span>)}</div>}
          <div aria-label="联网与隐私选项" style={{display:"flex",flexWrap:"wrap",alignItems:"center",gap:8,margin:"5px 0",fontSize:10}}><label className="web-mode-control" title="联网模式按会话保存，并在每个Run快照中记录"><Globe2 size={14}/><span>联网</span><select aria-label="联网模式" value={webMode} onChange={e=>changeWebMode(e.target.value as WebMode)}><option value="off">关闭</option><option value="auto">自动</option><option value="on">开启</option></select></label>{webMode==="on"&&<label className="sensitive-web-consent" title="仅发送本轮问题文本"><input aria-label="确认允许本轮敏感问题文本联网检索" type="checkbox" checked={allowSensitiveWebSearch} onChange={e=>setAllowSensitiveWebSearch(e.target.checked)}/>确认允许敏感问题文本外发</label>}</div>
          <div className="composer-bottom"><div className="composer-tools"><input ref={fileInput} hidden type="file" multiple accept=".txt,.md,.pdf,.docx,.csv,.xlsx,.png,.jpg,.jpeg,.webp" onChange={e=>void upload(e.target.files)}/><button className="attach-button" title="添加附件" aria-label="添加附件" onClick={()=>fileInput.current?.click()}><Paperclip size={15}/></button><span>{uploading?"正在安全保存…":"拖放附件或选择文件 · 单个≤15MiB，最多5个"}</span><SpeechInputButton disabled={running} onTranscript={transcript=>setPrompt(transcript)}/></div><button className="send-button" disabled={!prompt.trim()||running||!selected} onClick={()=>void postRun(prompt)}>{running?<LoaderCircle className="spin" size={16}/>:<Send size={15}/>}<span>发送</span><kbd>↵</kbd></button></div>
        </div><p className="composer-note">{health?.mode||"RULE_DEMO"} · {health?.llm?.configured?"仅发送问题与有界摘要到DeepSeek；附件始终只保存在本地":"附件仅本地保存，不发送到第三方模型"} · 联网 {webMode}；设备工况、附件与标准原文不会自动上传外网搜索服务</p>
      </div>
      <nav className="mobile-tabs"><button className={mobilePanel==="history"?"selected":""} onClick={()=>setMobilePanel("history")}><History size={17}/>历史</button><button className={mobilePanel==="chat"?"selected":""} onClick={()=>setMobilePanel("chat")}><Send size={17}/>对话</button><button className={mobilePanel==="evidence"?"selected":""} onClick={()=>setMobilePanel("evidence")}><GitBranch size={17}/>审查</button></nav>
    </section>
    {inspector&&<aside className={`inspector ${mobilePanel==="evidence"?"mobile-visible":""}`}>
      <div className="inspector-head"><div><span className="eyebrow">OBSERVABILITY</span><h2>执行审查</h2></div><button className="icon-button mobile-close" aria-label="关闭审查" onClick={()=>setMobilePanel("chat")}><X size={18}/></button><span className="live-label"><i/>{running?"LIVE":"本地记录"}</span></div>
      <section className="inspector-section"><div className="section-head"><div><Activity size={15}/><b>Agent 执行图</b></div><small>{events.length?`${graphEdges.length} 条实测跳转`:"暂无运行"}</small></div><div className="flow-wrap"><Suspense fallback={<div className="flow-loading">正在载入执行图…</div>}><AgentFlow nodes={graphNodes} edges={graphEdges}/></Suspense></div><div className="role-legend"><span><i className="done"/>已观测节点</span><span><i className="working"/>运行中</span><span>仅画出SSE真实agent_started顺序；无边不代表存在跳转</span></div><button className="flow-expand" aria-label="放大执行图" onClick={()=>setFlowExpanded(true)}><ArrowUpRight size={13}/> 放大执行图</button></section>
      <section className="inspector-section"><button className="section-head clickable" onClick={()=>setEventsOpen(!eventsOpen)}><div><Clock3 size={15}/><b>事件时间线</b></div><span>{events.length} 条 <ChevronDown size={14} className={eventsOpen?"":"rotate"}/></span></button>{eventsOpen&&renderTimeline()}</section>
      <section className="inspector-section evidence-section"><div className="section-head"><div><ShieldCheck size={15}/><b>证据与复核</b></div><Badge variant="outline">辅助研判</Badge></div><div className="evidence-empty"><div><BookOpen size={16}/></div><b>依据随事件呈现</b><p>仅聚合可识别 claim_id 的最新核查状态；时间线仍保留全部事件。未收到来源证据时不推断风险。</p></div>{claims.length===0&&<div className="quiet">暂无结构化 claim 审查结果</div>}{claims.map(({claimId,latest:claim,history})=><button key={claimId} className="citation-card claim-card" data-claim-id={claimId} onClick={()=>setEvidence(claimEvidenceDetail(claimId,claim,history,events))}><span className="citation-grade">{String(claim.payload.grade||claim.payload.review_level||claim.payload.verification_level||claim.payload.evidence_grade||"E?")}</span><div><b>{String(claim.payload.claim??claim.payload.statement??claim.payload.text??claim.payload.title??claimId)}</b><small>{claimId} · {claimStatus(claim)} · #{claim.sequence}</small><small>{String(claim.payload.standard_code||claim.payload.standard||(Array.isArray(claim.payload.source_clause_ids)?String(claim.payload.source_clause_ids[0]):undefined)||claim.payload.clause_id||"来源待复核")}{claim.payload.printed_page?` · 印刷页 ${String(claim.payload.printed_page)}`:""}</small></div><ArrowUpRight size={14}/></button>)}</section>
      <section className="inspector-section run-history-section"><div className="section-head"><div><History size={15}/><b>本机会话运行</b></div><small>{runHistory.length} 条 · 跨设备不可恢复</small></div>{runHistory.map(runId=><button key={runId} className={`run-history-item ${viewRun===runId?"selected":""}`} onClick={()=>void openRun(runId)}><span>{runningSessions[selected||""]===runId?"运行中":"Run"}</span><code>{runId.slice(0,14)}</code><small>{localRunEventCount(selected||"",runId)} events</small></button>)}</section>
      <div className="inspector-bottom"><Wrench size={14}/><span>工具输出仅显示实际返回内容</span><button onClick={()=>setEvidence({mode:health?.mode,database:health?.database,teacher_tools:[]})}>运行信息</button></div>
    </aside>}
    {settingsOpen&&<div className="settings-overlay"><SettingsShell health={health} resolvedTheme={mode} preferences={preferences} onPreferencesChange={setPreferences} archived={archivedConversations} archiveLoading={archiveLoading} onLoadArchive={()=>void loadArchivedConversations()} onRestore={restoreConversation} onBack={()=>setSettingsOpen(false)} onRefreshHealth={refreshHealth}/></div>}
    {statsOpen&&<div className="dashboard-overlay" role="dialog" aria-modal="true" aria-label="活动统计"><header className="dashboard-top"><div><span className="eyebrow">AETHERIS · ANALYTICS</span><h1>活动统计</h1></div><button className="settings-action" onClick={()=>setStatsOpen(false)} aria-label="关闭统计"><X size={16}/>返回聊天</button></header><div className="dashboard-scroll"><UsageDashboard/></div></div>}
    {evidence&&<div className="modal-backdrop" onClick={()=>setEvidence(null)}><section className="evidence-modal" role="dialog" aria-modal="true" aria-label="来源与事件详情" onClick={e=>e.stopPropagation()}><div className="modal-title"><div><span className="eyebrow">SOURCE DETAIL</span><h2>来源与事件详情</h2></div><button className="icon-button" aria-label="关闭" onClick={()=>setEvidence(null)}><X size={18}/></button></div><div className="source-grade-note">{evidence.review_level === "E1" || evidence.verification_level === "E1" ? "E1：条款已定位，但专业适用性待复核" : evidence.review_level === "E0" || evidence.verification_level === "E0" ? "E0：来源不足，当前记录不支持该判断" : "仅展示本轮来源核验状态；不代表设备结论成立"}</div><dl className="evidence-fields">{Object.entries(evidence).filter(([key,value])=>!['debug_payload','history','claim_id','canonical_sha256','canonical_version','canonical_quote','evidence_checks','contradictions','unknown_conditions','source_gate','verdict','review_status','review_level','verification_level'].includes(key)&&value!==undefined&&value!==null).map(([key,value])=><div key={key}><dt>{fieldLabel(key)}</dt><dd>{typeof value==="object"?JSON.stringify(value):String(value)}</dd></div>)}</dl>{Array.isArray(evidence.unknown_conditions)&&evidence.unknown_conditions.length>0&&<p className="source-detail-line"><b>未提供 / 未知：</b>{evidence.unknown_conditions.map(String).join("；")}</p>}{Array.isArray(evidence.contradictions)&&evidence.contradictions.length>0&&<details className="audit-details"><summary>独立反证与核验过程（{evidence.contradictions.length}）</summary>{evidence.contradictions.map((item,index)=><p key={index}>{readableAuditItem(item)}</p>)}</details>}{Array.isArray(evidence.history)&&<details className="audit-details"><summary>复核状态历史（{evidence.history.length} 个事件）</summary><div className="claim-history">{evidence.history.map((event,index)=><span key={index}>#{String((event as Record<string,unknown>).sequence)} {String((event as Record<string,unknown>).event)} · {JSON.stringify((event as Record<string,unknown>).payload||{})}</span>)}</div></details>}<details className="audit-details"><summary>原始证据与审计详情（默认折叠）</summary><dl className="evidence-fields audit-fields">{Object.entries(evidence).filter(([key,value])=>['claim_id','canonical_sha256','canonical_version','canonical_quote','evidence_checks','source_gate','verdict','review_status','review_level','verification_level'].includes(key)&&value!==undefined&&value!==null).map(([key,value])=><div key={key}><dt>{fieldLabel(key)}</dt><dd>{typeof value==="object"?JSON.stringify(value):String(value)}</dd></div>)}</dl><pre>{JSON.stringify(evidence.debug_payload??evidence,null,2)}</pre></details><div className="modal-foot"><span>来源等级只描述证据状态；适用性待复核，unknown 保持未知。</span><button onClick={()=>navigator.clipboard?.writeText(JSON.stringify(evidence,null,2))}><Clipboard size={14}/>复制</button></div></section></div>}
    {preview&&<div className="modal-backdrop" role="dialog" aria-label="附件预览" onClick={()=>setPreview(null)}><section className="evidence-modal" onClick={e=>e.stopPropagation()}><div className="modal-title"><h2>{preview.name}</h2><button className="icon-button" onClick={()=>setPreview(null)} aria-label="关闭预览"><X size={18}/></button></div><pre className="file-preview">{preview.text}</pre></section></div>}
    {flowExpanded&&<div className="modal-backdrop flow-backdrop" role="dialog" aria-label="放大执行图" onClick={()=>setFlowExpanded(false)}><section className="flow-modal" onClick={e=>e.stopPropagation()}><div className="modal-title"><div><span className="eyebrow">OBSERVED SSE PATHS</span><h2>Agent 执行图 · 实测跳转</h2></div><button className="icon-button" aria-label="关闭放大执行图" onClick={()=>setFlowExpanded(false)}><X size={18}/></button></div><div className="flow-expanded-canvas"><Suspense fallback={<div className="flow-loading">载入执行图…</div>}><AgentFlow nodes={graphNodes} edges={graphEdges}/></Suspense></div><p className="flow-modal-note">只绘制已观察到的 agent_started 顺序；未执行节点明确显示为本次未触发，不推断计划边。</p></section></div>}
    {mobileMenu&&<button className="scrim" aria-label="关闭菜单" onClick={()=>setMobileMenu(false)}/>}
  </main>;
}

function eventSummary(e:ApiEvent){const p=e.payload||{};const value=p.summary??p.message??p.tool??p.status??p.title??p.review_status??p.verdict??p.claim_id??p.clause_id;return value===undefined?"展开查看事件参数":String(value).slice(0,110)}
function failureCodeFromEvents(events:ApiEvent[]):PublicRunFailureCode|null{const failed=[...events].reverse().find(event=>["error","run_failed"].includes(eventKind(event)));return failed?publicRunFailureCode(failed.payload?.code??eventKind(failed)):null}
function setRunFailureFromEvents(runId:string,events:ApiEvent[],setFailure:(value:{runId:string;code:PublicRunFailureCode}|null)=>void){const code=failureCodeFromEvents(events);setFailure(code?{runId,code}:null)}
function readRunSnapshot(sessionId:string,runId:string|null):RunSnapshot|null{if(!runId)return null;try{const value=JSON.parse(localStorage.getItem(`aether:run-snapshot:${sessionId}:${runId}`)||"null") as RunSnapshot|null;return value?.runId===runId&&value.conversationId===sessionId?value:null}catch{return null}}
function fromServerRunSnapshot(sessionId:string,runId:string,data:Record<string,any>):RunSnapshot{return {runId,conversationId:sessionId,capturedAt:String(data.started_at||new Date().toISOString()),mode:data.mode==="DEEPSEEK"?"DEEPSEEK":"RULE_DEMO",webMode:(data.context?.web_mode||"off") as WebMode,question:String(data.question||""),context:(data.context||{}) as RunSnapshot["context"],attachments:Array.isArray(data.attachments)?data.attachments:[],historyMessageCount:Number(data.history_message_count||0),historyMessageIds:Array.isArray(data.history_message_ids)?data.history_message_ids:[],historyIncluded:false}}

function createIdempotencyKey():string {
  if(typeof crypto!="undefined"&&"randomUUID" in crypto)return crypto.randomUUID();
  return `r2-${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}-${Math.random().toString(36).slice(2)}`;
}
function LongReportDisclosure({messages}:{messages:Message[]}){const long=messages.map(message=>({message,presentation:presentMessage(message)})).filter(({message,presentation})=>message.role==="assistant"&&presentation.finalText.length>500&&!presentation.finalText.includes("```"));return long.length?<div className="long-report-list">{long.map(({message,presentation})=><details className="full-report" key={message.id}><summary>展开完整报告原文（{presentation.finalText.length} 字）</summary><pre>{presentation.finalText}</pre></details>)}</div>:null}
function claimEvidenceDetail(claimId:string,latest:ApiEvent,history:ApiEvent[],events:ApiEvent[]){const p=latest.payload||{};const evs=Array.isArray(p.canonical_evidence)?p.canonical_evidence as Record<string,unknown>[]:[];const source=evs[0]||{};const checks=Array.isArray(p.checks)?p.checks as Record<string,unknown>[]:[];const clauseIds=Array.isArray(p.source_clause_ids)?p.source_clause_ids.map(String).join(", "):undefined;const related=events.filter(e=>String(e.payload.claim_id||"")===claimId&&/contradiction|skeptic|human_review|claim_checked/.test(eventKind(e)));return {claim_id:claimId,statement:p.text??p.claim??p.statement??p.title??claimId,verdict:p.verdict??"unknown",review_status:p.review_status??claimStatus(latest),review_level:p.grade??p.review_level??p.verification_level??"E0",source_clause_id:source.clause_id??clauseIds,standard:((source.tool_source as Record<string,unknown>|undefined)?.standard_code)??p.standard_code,printed_page:source.printed_page??p.printed_page,canonical_version:source.canonical_version,canonical_sha256:source.canonical_record_sha256,canonical_quote:source.content_raw,source_gate:p.provenance_status??"unknown",unknown_conditions:checks.filter(x=>x.status==="not_specified"||x.status==="unknown").map(x=>`${x.check}: ${x.status}`),evidence_checks:checks.map(x=>`${x.check}: ${x.status}`),contradictions:related.map(e=>({sequence:e.sequence,event:eventKind(e),payload:e.payload})),history:history.map(e=>({sequence:e.sequence,event:eventKind(e),payload:e.payload})),debug_payload:p}}
function eventEvidenceDetail(event:ApiEvent){const p=event.payload||{};return {event:eventKind(event),sequence:event.sequence,run_id:event.run_id,clause_id:p.clause_id,standard_code:p.standard_code,clause_no:p.clause_no,printed_page:p.printed_page??p.page,verification_level:p.verification_level??p.grade,canonical_sha256:p.canonical_record_sha256??p.canonical_sha256,canonical_quote:p.content_raw??p.quote_span,source_gate:p.provenance_status??p.source_gate,unknown_conditions:p.unknown_conditions??p.unknown_fields,contradiction:p.contradiction??p.counterevidence,review_status:p.review_status,debug_payload:p}}
function readableAuditItem(value:unknown){if(!value||typeof value!=="object")return String(value??"");const item=value as Record<string,unknown>;const nested=item.payload&&typeof item.payload==="object"?item.payload as Record<string,unknown>:{};return `#${String(item.sequence??"")} ${String(item.event??"")} · ${String(item.counterevidence??item.contradiction??item.finding??item.summary??nested.counterevidence??nested.contradiction??nested.finding??nested.summary??nested.status??"已记录")}`}
function fieldLabel(key:string){return ({claim_id:"Claim ID（审计标识）",status:"审查状态",statement:"候选判断",source_clause_id:"条款ID",standard:"标准号",printed_page:"印刷页码",conditions:"适用条件",metadata_match:"元数据匹配",review_level:"来源核验等级",contradiction:"反证",sequence:"事件序号",canonical_sha256:"原文记录 SHA-256",canonical_version:"来源版本",canonical_quote:"标准原文摘录",source_gate:"来源门禁",verdict:"审查结论",review_status:"复核状态",evidence_checks:"证据检查项",unknown_conditions:"未知工况",event:"事件类型",run_id:"Run ID",standard_code:"标准号",clause_no:"条款号",verification_level:"来源核验等级"} as Record<string,string>)[key]||key}
export default App;

