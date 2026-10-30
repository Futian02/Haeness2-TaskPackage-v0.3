import { useEffect, useMemo, useState } from "react";
import { Archive, AudioLines, ChevronLeft, Info, Monitor, Moon, RefreshCw, RotateCcw, Settings2, SlidersHorizontal, Sparkles, Sun, Trash2, Zap } from "lucide-react";
import { api, type Conversation, type Health, type ModelProfile } from "./api";
import { EXPECTED_CONTRACT_VERSION, FRONTEND_BUILD_FINGERPRINT, contractState, shortFingerprint } from "./runtimeContract";
import type { UserPreferences } from "./settings/preferences";
import "./settings/settings.css";

type Page = "general" | "model" | "personality" | "archive" | "appearance" | "voice" | "about";
type Props = {
  health: Health | null;
  resolvedTheme: "light" | "dark";
  preferences: UserPreferences;
  onPreferencesChange: (next: UserPreferences) => void;
  archived: Conversation[];
  archiveLoading: boolean;
  onLoadArchive: () => void;
  onRestore: (conversation: Conversation) => Promise<void>;
  onBack: () => void;
  onRefreshHealth: () => Promise<void>;
};

const navigation: { id: Page; label: string; icon: typeof Settings2 }[] = [
  { id: "general", label: "常规", icon: Settings2 }, { id: "model", label: "模型", icon: SlidersHorizontal },
  { id: "personality", label: "性格", icon: Sparkles }, { id: "archive", label: "会话与归档", icon: Archive },
  { id: "appearance", label: "外观", icon: Sun }, { id: "voice", label: "语音", icon: AudioLines }, { id: "about", label: "关于", icon: Info },
];
const personality = [
  ["professional", "专业严谨"], ["natural", "自然友好"], ["companion", "知心陪伴"], ["concise", "简洁高效"],
] as const;

export default function SettingsShell(props: Props) {
  const [page, setPage] = useState<Page>("general");
  const [archiveQuery, setArchiveQuery] = useState("");
  const [refreshing, setRefreshing] = useState(false);
  const [restoring, setRestoring] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  const [profiles,setProfiles]=useState<ModelProfile[]>([]);
  const [activeProfile,setActiveProfile]=useState<string|null>(null);
  const [credentialStore,setCredentialStore]=useState("");
  const [provider,setProvider]=useState<"deepseek"|"openai-compatible">("deepseek");
  const [model,setModel]=useState("deepseek-chat");
  const [endpoint,setEndpoint]=useState("https://api.deepseek.com/v1");
  const [apiKey,setApiKey]=useState("");
  const [editingProfileId,setEditingProfileId]=useState<string|null>(null);
  const [savingProfile,setSavingProfile]=useState(false);
  const [testingProfile,setTestingProfile]=useState<string|null>(null);
  const [testResult,setTestResult]=useState<Record<string,unknown>|null>(null);
  const filteredArchive = useMemo(() => props.archived.filter(item => (item.title || "未命名对话").toLocaleLowerCase().includes(archiveQuery.toLocaleLowerCase())), [props.archived, archiveQuery]);
  const patch = (update: Partial<UserPreferences>) => props.onPreferencesChange({ ...props.preferences, ...update });
  const refresh = async () => { setRefreshing(true); setNotice(""); try { await props.onRefreshHealth(); setNotice("已从 /api/health 刷新服务状态"); } catch { setNotice("服务状态读取失败，请检查后端连接"); } finally { setRefreshing(false); } };
  const restore = async (conversation: Conversation) => { setRestoring(conversation.id); setNotice(""); try { await props.onRestore(conversation); setNotice("会话已恢复到历史列表"); } catch { setNotice("恢复失败，请稍后重试"); } finally { setRestoring(null); } };
  const loadProfiles=async()=>{try{const result=await api.modelProfiles();setProfiles(Array.isArray(result.profiles)?result.profiles:[]);setActiveProfile(result.active_profile_id??null);setCredentialStore(result.credential_store||"unavailable")}catch{setProfiles([]);setCredentialStore("unavailable")}};
  useEffect(()=>{if(page==="model")void loadProfiles()},[page]);
  const saveProfile=async()=>{if(!apiKey.trim()&&!editingProfileId){setNotice("请输入API Key后保存；密钥只提交一次，不会回显明文。");return}setSavingProfile(true);setNotice("");try{await api.saveModelProfile({provider,model:model.trim(),endpoint,...(apiKey.trim()?{api_key:apiKey}:{})},editingProfileId??undefined);setApiKey("");setEditingProfileId(null);setNotice("模型配置已保存到服务端加密凭据存储。请执行真实连接测试，再激活使用。");await loadProfiles()}catch(e){setNotice(`保存失败：${String((e as Error).message||e)}`)}finally{setSavingProfile(false)}};
  const editProfile=(item:ModelProfile)=>{setEditingProfileId(item.id);setProvider(item.provider);setModel(item.model);setEndpoint(item.endpoint);setApiKey("");setNotice("正在编辑配置；API Key 留空将保留已加密凭据，输入新 Key 则会替换。");};
  const activateProfile=async(id:string|null)=>{try{await api.activateModelProfile(id);setActiveProfile(id);await props.onRefreshHealth();setNotice(id?"模型已切换；后续新Run会使用此模型，旧Run保持原快照。":"已切换为环境变量/规则模式")}catch(e){setNotice(`切换失败：${String((e as Error).message||e)}`)}};
  const testProfile=async(id:string)=>{setTestingProfile(id);setTestResult(null);try{const result=await api.testModelProfile(id);setTestResult(result);setNotice(`真实供应商连接成功：${result.provider}/${result.model}，${result.latency_ms} ms`)}catch(e){setNotice(`真实连接测试失败：${String((e as Error).message||e)}`)}finally{setTestingProfile(null)}};
  const title = navigation.find(item => item.id === page)?.label ?? "设置";
  return <div className="settings-shell" data-theme={props.resolvedTheme} data-density={props.preferences.density}>
    <nav className="settings-nav" aria-label="设置分类"><div className="settings-brand">澄衡 Aetheris</div>{navigation.map(item => { const Icon = item.icon; return <button key={item.id} aria-current={page === item.id ? "page" : undefined} onClick={() => { setPage(item.id); if (item.id === "archive") props.onLoadArchive(); }}><Icon size={16}/>{item.label}</button>; })}</nav>
    <section className="settings-content" aria-label={`${title}设置`}>
      <div className="settings-top"><button onClick={props.onBack}><ChevronLeft size={16}/>返回聊天</button><span className="settings-status">本地偏好</span></div>
      <h1>{title}</h1>
      <p className="settings-subtitle">配置澄衡 Aetheris 的工作区体验。偏好保存在当前浏览器，不包含密钥或个人隐私。</p>
      {notice && <div className="settings-note" role="status">{notice}</div>}
      {page === "general" && <>
        <Card title="字体缩放" description="调整应用阅读比例；设置页面与工作区同步。"><Segments options={[[90,"90%"],[100,"100%"],[110,"110%"]]} value={props.preferences.fontScale} onChange={value => patch({ fontScale: value as UserPreferences["fontScale"] })}/></Card>
        <Card title="界面密度" description="舒适模式保留留白，紧凑模式收紧设置卡片间距。"><Segments options={[["comfortable","舒适"],["compact","紧凑"]]} value={props.preferences.density} onChange={value => patch({ density: value as UserPreferences["density"] })}/></Card>
        <Card title="执行记录" description="默认展开执行审查中的事件时间线。"><label className="settings-row"><span>默认展开事件时间线</span><input aria-label="默认展开事件时间线" type="checkbox" checked={props.preferences.autoExpandTrace} onChange={event => patch({ autoExpandTrace: event.target.checked })}/></label></Card>
      </>}
      {page === "model" && <>
        <Card title="当前服务" description="状态来自后端 /api/health；只显示是否已配置，不读取或展示密钥。">
          <div className="settings-row"><span>工作模式</span><b>{props.health?.mode || "读取中"}</b></div>
          <div className="settings-row"><span>服务商</span><b>{props.health?.llm?.provider || (props.health ? "规则引擎" : "读取中")}</b></div>
          <div className="settings-row"><span>模型</span><b>{props.health?.llm?.model || "—"}</b></div>
          <div className="settings-row"><span>凭据状态</span><b>{props.health ? (props.health.llm?.configured ? "已配置" : "未配置") : "读取中"}</b></div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 12 }}><button className="settings-action" disabled={refreshing} onClick={() => void refresh()}><RefreshCw size={14}/>{refreshing ? "检查中…" : "刷新后端状态"}</button></div>
        </Card>
        <Card title={editingProfileId?"编辑模型配置":"新增模型配置"} description="凭据仅一次提交到本机服务端 DPAPI CurrentUser 加密存储；不会写入浏览器存储、SQLite、日志或 SSE。">
          <label className="settings-row"><span>服务商</span><select className="settings-field" value={provider} onChange={e=>{const next=e.target.value as typeof provider;setProvider(next);setEndpoint(next==="deepseek"?"https://api.deepseek.com/v1":"https://api.openai.com/v1");setModel(next==="deepseek"?"deepseek-chat":"gpt-4o-mini")}}><option value="deepseek">DeepSeek</option><option value="openai-compatible">OpenAI Compatible（官方 OpenAI endpoint）</option></select></label>
          <label className="settings-row"><span>模型名称</span><input className="settings-field" value={model} onChange={e=>setModel(e.target.value)} maxLength={80}/></label>
          <label className="settings-row"><span>API endpoint</span><input className="settings-field" value={endpoint} onChange={e=>setEndpoint(e.target.value)} maxLength={300}/></label>
          <label className="settings-row"><span>API Key</span><input className="settings-field" type="password" autoComplete="new-password" value={apiKey} onChange={e=>setApiKey(e.target.value)} placeholder="仅保存时提交；保存后不再回显"/></label>
          <div style={{display:"flex",gap:8,flexWrap:"wrap",marginTop:12}}><button className="settings-action" disabled={savingProfile||credentialStore!=="Windows DPAPI (CurrentUser)"} onClick={()=>void saveProfile()}><SlidersHorizontal size={14}/>{savingProfile?"加密保存中…":editingProfileId?"更新配置":"保存配置"}</button>{editingProfileId&&<button className="settings-action" onClick={()=>{setEditingProfileId(null);setApiKey("");setNotice("已取消编辑")}}>取消编辑</button>}<small>凭据存储：{credentialStore||"检查中"}</small></div>
        </Card>
        <Card title="已保存配置" description="连接测试会发送固定的非敏感短提示并可能产生供应商费用；不发送设备或会话内容。">
          {profiles.length===0?<p>尚无已保存模型配置。环境变量配置仍可作为兼容模式。</p>:profiles.map(item=><div className="settings-archive-item" key={item.id} style={{marginTop:8}}><span><b>{item.provider} · {item.model}</b><small>{item.endpoint} · Key {item.api_key_masked||"未配置"} · {activeProfile===item.id?"当前激活":"未激活"}</small></span><div style={{display:"flex",gap:6,flexWrap:"wrap"}}><button className="settings-action" onClick={()=>editProfile(item)}>编辑</button><button className="settings-action" disabled={testingProfile===item.id||!item.key_configured} onClick={()=>void testProfile(item.id)}><Zap size={13}/>{testingProfile===item.id?"测试中…":"真实连接测试"}</button><button className="settings-action" disabled={activeProfile===item.id||!item.key_configured} onClick={()=>void activateProfile(item.id)}>切换</button><button className="settings-action" aria-label={`删除 ${item.model}`} onClick={()=>void api.deleteModelProfile(item.id).then(loadProfiles).then(props.onRefreshHealth)}><Trash2 size={13}/>删除</button></div></div>)}
          {activeProfile&&<button className="settings-action" style={{marginTop:12}} onClick={()=>void activateProfile(null)}>取消激活已保存配置</button>}
          {testResult&&<pre className="settings-note" role="status">{JSON.stringify(testResult,null,2)}</pre>}
        </Card>
        <div className="settings-note">刷新只检查 /api/health；不调用模型、不产生推理费用。管理接口只允许本机 Loopback Host；APP_ENV=production 时 fail-closed。未启用账户认证/多租户托管，因此不要把本机开发服务暴露公网。模型切换按新Run快照生效，历史Run不回写；环境 DEEPSEEK_* 继续兼容。</div>
      </>}
      {page === "personality" && <>
        <Card title="本地语气偏好" description="仅保存在本机，当前服务端未接入，因此不会改变模型回复；工程审查提示词和证据门禁不受此项覆盖。">
          <div className="settings-segment">{personality.map(([id, label]) => <button key={id} aria-pressed={props.preferences.personality === id} onClick={() => patch({ personality: id })}>{label}</button>)}</div>
          <label style={{ display: "block", marginTop: 18 }}>自定义指令 <small>（最多 500 字，仅本地偏好）</small><textarea className="settings-field" aria-label="自定义指令" maxLength={500} rows={5} value={props.preferences.customInstructions} onChange={event => patch({ customInstructions: event.target.value.slice(0, 500) })} placeholder="记录希望使用的表达习惯；当前服务端未接入。"/><small>{props.preferences.customInstructions.length}/500</small></label>
        </Card>
      </>}
      {page === "archive" && <Card title="已归档会话" description="仅从历史列表隐藏，可恢复；不会删除会话或附件。">
        <div className="settings-row"><input className="settings-field" aria-label="搜索归档会话" placeholder="搜索归档会话" value={archiveQuery} onChange={event => setArchiveQuery(event.target.value)}/><button className="settings-action" onClick={props.onLoadArchive} disabled={props.archiveLoading}><RefreshCw size={14}/>{props.archiveLoading ? "读取中…" : "刷新列表"}</button></div>
        {props.archiveLoading ? <p>正在读取归档列表…</p> : filteredArchive.length ? <div className="settings-archive-list" style={{ marginTop: 12 }}>{filteredArchive.map(item => <div className="settings-archive-item" key={item.id}><span><b>{item.title || "未命名对话"}</b><small>{new Date(item.updated_at).toLocaleString()}</small></span><button className="settings-action" disabled={restoring === item.id} onClick={() => void restore(item)}><RotateCcw size={14}/>{restoring === item.id ? "恢复中…" : "恢复"}</button></div>)}</div> : <p>没有匹配的归档会话。</p>}
      </Card>}
      {page === "appearance" && <Card title="主题" description="跟随系统时根据操作系统深浅色偏好自动切换；兼容旧 aether-theme 选择。"><div className="settings-segment">{([["light","浅色",Sun],["dark","深色",Moon],["system","跟随系统",Monitor]] as const).map(([value,label,Icon]) => <button key={value} aria-pressed={props.preferences.theme === value} onClick={() => patch({ theme: value })}><Icon size={14}/> {label}</button>)}</div></Card>}
      {page === "voice" && <div className="settings-note"><AudioLines size={16}/> 语音输入位于聊天输入栏。浏览器支持情况与权限状态会在你主动点击麦克风后显示；识别结果只填入草稿，不自动发送。浏览器语音识别可能调用厂商服务并传送音频。</div>}
      {page === "about" && <Card title="澄衡 Aetheris" description="智能工程助手。围绕设备、工况与现场观察组织分析，并保留来源、适用条件与复核状态。"><p>运行时版本握手由页面构建元数据与服务端 /api/health 分别提供。</p><div className="settings-row"><span>前后端协议</span><b>{contractState(props.health)} · 期望 {EXPECTED_CONTRACT_VERSION}</b></div><div className="settings-row"><span>后端状态</span><b>{props.health?.status || "未连接"}</b></div><div className="settings-row"><span>后端 build_fingerprint</span><code>{shortFingerprint(props.health?.build_fingerprint)}</code></div><div className="settings-row"><span>前端源码 fingerprint</span><code>{shortFingerprint(FRONTEND_BUILD_FINGERPRINT)}</code></div></Card>}
    </section>
  </div>;
}

function Card({ title, description, children }: { title: string; description: string; children: React.ReactNode }) { return <section className="settings-card"><h2>{title}</h2><p>{description}</p><div style={{ marginTop: 14 }}>{children}</div></section>; }
function Segments<T extends string | number>({ options, value, onChange }: { options: readonly (readonly [T, string])[]; value: T; onChange: (value: T) => void }) { return <div className="settings-segment">{options.map(([key, label]) => <button key={key} aria-pressed={value === key} onClick={() => onChange(key)}>{label}</button>)}</div>; }
