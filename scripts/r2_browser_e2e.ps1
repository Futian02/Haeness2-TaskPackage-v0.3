param(
    [Parameter(Mandatory=$true)][ValidateSet('Edge','Chrome')][string]$Browser,
    [Parameter(Mandatory=$true)][string]$ApiBaseUrl,
    [Parameter(Mandatory=$true)][string]$FrontendUrl,
    [Parameter(Mandatory=$true)][switch]$OwnerApproved,
    [switch]$HelloSmoke,
    [switch]$ProfessionalJourneys,
    [ValidateSet('desktop','mobile')][string]$Viewport='desktop',
    [string]$OutputDirectory='docs/audits/evidence/r2_qa',
    [string]$ExpectedContractVersion='aetheris-r2.0.0'
)

$ErrorActionPreference = 'Stop'
if (-not $OwnerApproved) { throw 'Blocked: launch requires an explicit -OwnerApproved after E shadow service is ready.' }

function Assert-LoopbackCandidate([string]$Url, [string]$Name) {
    $uri = [Uri]$Url
    if ($uri.Scheme -ne 'http' -or $uri.Host -notin @('127.0.0.1','localhost','::1')) {
        throw "$Name must be a local HTTP URL; remote targets are out of scope for this QA runner."
    }
    if ($Name -eq 'API' -and $uri.Port -in @(8000,8001)) {
        throw 'Blocked: production/legacy ports 8000 and 8001 must never be used by this QA runner.'
    }
}

Assert-LoopbackCandidate $ApiBaseUrl 'API'
Assert-LoopbackCandidate $FrontendUrl 'Frontend'
$apiRoot = $ApiBaseUrl.TrimEnd('/')
$health = Invoke-RestMethod -Method Get -Uri "$apiRoot/api/health" -TimeoutSec 5
if ($health.contract_version -ne $ExpectedContractVersion) {
    throw "Backend contract mismatch: expected $ExpectedContractVersion, got '$($health.contract_version)'; browser will not start."
}
if ($health.build_fingerprint -notmatch '^sha256:[0-9a-f]{64}$') {
    throw 'Backend health must expose build_fingerprint as sha256:<64 lowercase hex>; browser will not start.'
}
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$build = $health.build
if (-not $build -or $build.source_files -isnot [array] -or -not $build.source_manifest) {
    throw 'Health must expose build.source_files and build.source_manifest so the live process can be compared to disk.'
}
$sourceFilesJson = ConvertTo-Json -InputObject @($build.source_files) -Compress
$sourceManifestJson = ConvertTo-Json -InputObject $build.source_manifest -Compress
$python = Join-Path $projectRoot '.venv-langgraph\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { $python = (Get-Command python -ErrorAction Stop).Source }
$backendFingerprintCode = @'
import hashlib,json,pathlib,sys
import base64
payload=json.loads(base64.b64decode(sys.argv[1]).decode('utf-8'))
root=pathlib.Path(payload['root']).resolve(); paths=payload['paths']; manifest=payload['manifest']
if paths != sorted(set(paths)): raise SystemExit('backend source_files must be unique and ordinally sorted')
if set(paths) != set(manifest): raise SystemExit('backend source manifest key set differs from source_files')
h=hashlib.sha256()
for rel in paths:
 p=(root/rel).resolve()
 if root not in p.parents: raise SystemExit('source path escapes project root: '+rel)
 data=p.read_bytes(); digest=hashlib.sha256(data).hexdigest()
 if manifest[rel] != digest: raise SystemExit('backend disk file hash mismatch: '+rel)
 h.update(rel.encode('utf-8')); h.update(b'\0'); h.update(len(data).to_bytes(8,'big')); h.update(data)
print('sha256:'+h.hexdigest())
'@
$backendFingerprintPayload = [ordered]@{root=$projectRoot;paths=@($build.source_files);manifest=$build.source_manifest} | ConvertTo-Json -Depth 8 -Compress
$backendFingerprintPayloadBase64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($backendFingerprintPayload))
$diskBackendFingerprint = (& $python -c $backendFingerprintCode $backendFingerprintPayloadBase64 | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $diskBackendFingerprint -ne $health.build_fingerprint) {
    throw "Backend runtime/source mismatch: live=$($health.build_fingerprint), disk=$diskBackendFingerprint"
}
$frontendRoot = Join-Path $projectRoot 'frontend'
$frontendFingerprintCode = @'
import hashlib,pathlib,sys
root=pathlib.Path(sys.argv[1]).resolve()
paths=[p for p in (root/'src').rglob('*') if p.is_file() and p.suffix.lower() in {'.tsx','.ts','.css','.html'}]
paths += [root/'package.json',root/'vite.config.ts',root/'index.html']
items=sorted(((p.relative_to(root).as_posix(),p.read_bytes()) for p in paths),key=lambda item:item[0])
h=hashlib.sha256()
for rel,data in items:
 h.update(rel.encode('utf-8')); h.update(b'\0'); h.update(data); h.update(b'\0')
print(h.hexdigest())
'@
$diskFrontendFingerprint = (& $python -c $frontendFingerprintCode $frontendRoot | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $diskFrontendFingerprint -notmatch '^[0-9a-f]{64}$') {
    throw "Could not compute frontend source fingerprint: $diskFrontendFingerprint"
}
$required = @('runs_create','runs_sse_stream','runs_replay','run_input_snapshot','model_profiles','professional_guidance','file_upload','explicit_web_consent','conversation_history','conversation_memory','sensitive_web_consent_gate')
foreach ($name in $required) {
    $property = $health.capabilities.PSObject.Properties[$name]
    if (-not $property -or $property.Value -isnot [bool]) { throw "Health capability missing/not boolean: $name" }
}
if ($health.capabilities.teacher_tool_count -ne 3) { throw 'Teacher tool count must remain exactly 3.' }
$frontendStatus = (& curl.exe --silent --show-error --output NUL --write-out '%{http_code}' --max-time 5 $FrontendUrl | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $frontendStatus -ne '200') { throw "Frontend HTTP status $frontendStatus; browser will not start." }

$browserPath = if ($Browser -eq 'Edge') { 'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe' } else { 'C:\Program Files\Google\Chrome\Application\chrome.exe' }
if (-not (Test-Path -LiteralPath $browserPath)) { throw "Browser executable not found: $browserPath" }
$node = (Get-Command node -ErrorAction Stop).Source
$null = New-Item -ItemType Directory -Force -Path $OutputDirectory
$outputFull = (Resolve-Path -LiteralPath $OutputDirectory).Path
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$profile = Join-Path $env:TEMP "aetheris-r2-qa-$stamp-$([guid]::NewGuid().ToString('N'))"
$cdpPort = (Get-Random -Minimum 21000 -Maximum 49000)
$screenshot = Join-Path $outputFull "${Browser}_${Viewport}_${stamp}_welcome.png"
$answerScreenshot = Join-Path $outputFull "${Browser}_${Viewport}_${stamp}_hello.png"
$jsonPath = Join-Path $outputFull "${Browser}_${Viewport}_${stamp}.json"
$dimensions = if ($Viewport -eq 'mobile') { @{ width=390; height=844; mobile=$true } } else { @{ width=1440; height=900; mobile=$false } }
$args = @(
    "--remote-debugging-port=$cdpPort", '--remote-allow-origins=*', "--user-data-dir=$profile",
    '--no-first-run', '--no-default-browser-check', '--disable-sync', '--disable-extensions',
    '--disable-background-networking', '--disable-features=MetricsReporting', $FrontendUrl
)
$proc = $null
try {
    $proc = Start-Process -FilePath $browserPath -ArgumentList $args -PassThru -WindowStyle Hidden
    $versionInfo = $null
    $deadline = (Get-Date).AddSeconds(20)
    while ((Get-Date) -lt $deadline) {
        try { $versionInfo = Invoke-RestMethod -Uri "http://127.0.0.1:$cdpPort/json/version" -TimeoutSec 1; break } catch { Start-Sleep -Milliseconds 250 }
    }
    if (-not $versionInfo) { throw 'Browser DevTools endpoint did not become ready.' }
    $targets = @(); $target = $null
    $targetDeadline = (Get-Date).AddSeconds(15)
    while ((Get-Date) -lt $targetDeadline -and -not $target) {
        try {
            $targets = Invoke-RestMethod -Uri "http://127.0.0.1:$cdpPort/json/list" -TimeoutSec 2
            foreach ($entry in $targets) {
                if ($entry.type -eq 'page' -and $entry.url -like "$FrontendUrl*" -and $entry.webSocketDebuggerUrl) { $target = $entry; break }
            }
        } catch { Start-Sleep -Milliseconds 250 }
    }
    if (-not $target) { throw 'Browser CDP has no page target.' }

    $nodeProgram = @'
const fs = require('node:fs/promises');
const config=JSON.parse(Buffer.from(process.argv[2],'base64').toString('utf8'));
const {wsUrl,targetUrl,shotPath,answerShotPath,jsonPath,outputDir,browserName,viewport,widthText,heightText,mobileText,expectedContract,expectedFingerprint,expectedBackendFingerprint,helloSmoke,professionalJourneys,browserPid}=config;
const ws = new WebSocket(wsUrl); let id=0; const pending=new Map(); const network=[]; const errors=[]; const failedRequests=[]; let targetMeta=null;
const target=config.target;
const journeys=[];
ws.addEventListener('message', e => { const m=JSON.parse(e.data); if(m.id && pending.has(m.id)){const p=pending.get(m.id);clearTimeout(p.timer);pending.delete(m.id);m.error?p.reject(Object.assign(new Error(m.error.message),{cdpError:m.error,method:p.method})):p.resolve(m.result)} else if(m.method==='Runtime.exceptionThrown'){errors.push(m.params.exceptionDetails)} else if(m.method==='Runtime.consoleAPICalled' && m.params.type==='error'){errors.push(m.params.args.map(a=>a.value??a.description).join(' '))} else if(m.method==='Network.responseReceived' && m.params.response.url.includes('/api/')){network.push({url:new URL(m.params.response.url).pathname,status:m.params.response.status})} else if(m.method==='Network.loadingFailed'){failedRequests.push({requestId:m.params.requestId,errorText:m.params.errorText,canceled:m.params.canceled})}});
const send=(method,params={})=>new Promise((resolve,reject)=>{const n=++id;const timer=setTimeout(()=>{pending.delete(n);reject(Object.assign(new Error('CDP command timeout'),{method,timeoutMs:15000}))},15000);pending.set(n,{resolve,reject,timer,method});try{ws.send(JSON.stringify({id:n,method,params}))}catch(e){clearTimeout(timer);pending.delete(n);reject(e)}});
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
async function evaluate(expression){try{const x=await send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(x.exceptionDetails)throw Object.assign(new Error(x.exceptionDetails.text||x.exceptionDetails.exception?.description||'Runtime.evaluate exception'),{exceptionDetails:x.exceptionDetails,expressionHash:require('node:crypto').createHash('sha256').update(expression).digest('hex'),expressionPrefix:expression.slice(0,180)});return x.result?.value}catch(e){e.expressionHash??=require('node:crypto').createHash('sha256').update(expression).digest('hex');e.expressionPrefix??=expression.slice(0,180);throw e}}
async function main(){
  await new Promise((r,j)=>{ws.addEventListener('open',r,{once:true});ws.addEventListener('error',j,{once:true})});
  await send('Page.enable');await send('Runtime.enable');await send('Network.enable');targetMeta=JSON.parse(await evaluate('JSON.stringify({href:location.href,title:document.title})'));
  await send('Emulation.setDeviceMetricsOverride',{width:Number(widthText),height:Number(heightText),deviceScaleFactor:1,mobile:mobileText==='true'});
  await send('Page.navigate',{url:targetUrl});
  const end=Date.now()+20000;let state;
  while(Date.now()<end){
    await sleep(250);
    state=JSON.parse(await evaluate(`JSON.stringify({ready:document.readyState,title:document.title,url:location.href,body:(document.body?.innerText||'').slice(0,500),contractVersion:document.querySelector('meta[name="aetheris-contract-version"]')?.content||null,buildFingerprint:document.querySelector('meta[name="aetheris-build-fingerprint"]')?.content||null,composer:[...document.querySelectorAll('textarea,input,[contenteditable=true]')].filter(x=>x.getClientRects().length).map(x=>({tag:x.tagName,aria:x.getAttribute('aria-label'),placeholder:x.getAttribute('placeholder')})),viewport:{width:innerWidth,height:innerHeight,scrollWidth:document.documentElement.scrollWidth}})`));
    if(state.ready==='complete'&&state.composer.length)break;
  }
  if(!state?.composer?.length)throw new Error('No visible composer found; inspect frontend selectors/console before claiming browser readiness.');
  if(state.contractVersion!==expectedContract)throw new Error(`frontend contract meta mismatch: ${state.contractVersion}`);
  if(state.buildFingerprint!==expectedFingerprint)throw new Error(`frontend source fingerprint mismatch: page=${state.buildFingerprint} disk=${expectedFingerprint}`);
  const proxiedHealth=await evaluate('fetch("/api/health").then(async r=>({status:r.status,body:await r.json()}))');
  if(proxiedHealth.status!==200||proxiedHealth.body.contract_version!==expectedContract||proxiedHealth.body.build_fingerprint!==expectedBackendFingerprint)throw new Error(`frontend proxy/backend mismatch: ${JSON.stringify({status:proxiedHealth.status,contract:proxiedHealth.body.contract_version,fingerprint:proxiedHealth.body.build_fingerprint})}`);
  const welcomePng=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});await fs.writeFile(shotPath,Buffer.from(welcomePng.data,'base64'));
  let hello=null;
  if(helloSmoke==='true'){
    let conversations=JSON.parse(await evaluate('fetch("/api/conversations").then(r=>r.json()).then(JSON.stringify)'));
    if(!conversations.length){
      const create=await evaluate(`(()=>{const b=document.querySelector('.new-chat');if(!b)throw new Error('new conversation button missing');b.click();return true})()`);
      const createDeadline=Date.now()+12000;
      while(Date.now()<createDeadline){await sleep(250);conversations=JSON.parse(await evaluate('fetch("/api/conversations").then(r=>r.json()).then(JSON.stringify)'));if(conversations.length)break;}
      if(!conversations.length)throw new Error('UI new-chat did not persist a conversation');
    }
    const cid=conversations[0].id;
    await evaluate(`(()=>{const x=document.querySelector('[aria-label="发送问题"]');if(!x)throw new Error('composer aria-label missing');x.focus()})()`);
    await send('Input.insertText',{text:'你好'});
    const entered=await evaluate(`document.querySelector('[aria-label="发送问题"]')?.value`);
    if(entered!=='你好')throw new Error(`hello text entry failed: ${entered}`);
    await evaluate(`(()=>{const b=document.querySelector('.send-button');if(!b||b.disabled)throw new Error('send button missing/disabled');b.click()})()`);
    const runDeadline=Date.now()+45000;let runId=null;let events=[];let detail=null;
    while(Date.now()<runDeadline){
      await sleep(400);
      const runList=JSON.parse(await evaluate(`fetch('/api/conversations/'+encodeURIComponent(${JSON.stringify(cid)})+'/runs').then(r=>r.json()).then(JSON.stringify)`));
      const runs=Array.isArray(runList)?runList:(runList.runs||[]);
      if(runs.length){runId=runs[0].id;events=JSON.parse(await evaluate(`fetch('/api/runs/'+encodeURIComponent(${JSON.stringify(runId)})+'/events?after_sequence=0').then(r=>r.json()).then(x=>JSON.stringify(x.events))`));if(events.some(e=>['run_completed','error','run_failed'].includes(e.type))){detail=JSON.parse(await evaluate(`fetch('/api/conversations/'+encodeURIComponent(${JSON.stringify(cid)})).then(r=>r.json()).then(JSON.stringify)`));break;}}
    }
    const assistants=(detail?.messages||[]).filter(m=>m.role==='assistant');const answer=String(assistants.at(-1)?.content||'');
    if(!runId||!events.some(e=>e.type==='run_completed'))throw new Error(`hello run missing successful terminal event: ${JSON.stringify({runId,types:events.map(e=>e.type)})}`);
    if(!answer.trim())throw new Error('hello run completed but persisted assistant answer is empty');
    const answerText=String(await evaluate('document.body?.innerText||""'));
    if(!answerText.includes('你好')||!answerText.includes(answer.slice(0,Math.min(8,answer.length))))throw new Error('assistant answer is not visible in the browser DOM');
    const composerRect=JSON.parse(await evaluate(`(()=>{const r=document.querySelector('.composer-wrap').getBoundingClientRect();return JSON.stringify({top:r.top,bottom:r.bottom,height:r.height,viewport:innerHeight})})()`));
    if(composerRect.bottom>composerRect.viewport+2)throw new Error(`composer fell below viewport: ${JSON.stringify(composerRect)}`);
    const answerPng=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});await fs.writeFile(answerShotPath,Buffer.from(answerPng.data,'base64'));
    hello={conversation_id:cid,run_id:runId,question:'你好',assistant_answer:answer,terminal_types:events.map(e=>e.type),event_sequences:events.map(e=>e.sequence),composer_rect:composerRect};
  }
  if(professionalJourneys==='true'){
    async function waitUntil(fn,ms,label){const end=Date.now()+ms;while(Date.now()<end){const x=await fn();if(x)return x;await sleep(200)}throw new Error('timeout: '+label)}
    async function newConversation(){const before=JSON.parse(await evaluate(`fetch('/api/conversations').then(r=>r.json()).then(JSON.stringify)`));const old=new Set(before.map(x=>x.id));await evaluate(`(()=>{const b=document.querySelector('.new-chat');if(!b)throw Error('new-chat missing');b.click();return true})()`);return await waitUntil(async()=>{const rows=JSON.parse(await evaluate(`fetch('/api/conversations').then(r=>r.json()).then(JSON.stringify)`));return rows.find(x=>!old.has(x.id))?.id||null},15000,'new conversation')}
    async function setFields(fields){if(!Object.keys(fields).length)return;await evaluate(`(()=>{if(!document.querySelector('.context-grid'))document.querySelector('.context-toggle')?.click();return true})()`);for(const [label,value] of Object.entries(fields)){const selector='[aria-label='+JSON.stringify(label)+']';const result=await evaluate(`(()=>{const x=document.querySelector(${JSON.stringify(selector)});if(!x)throw Error('context field missing '+${JSON.stringify(label)});const set=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;set.call(x,${JSON.stringify(value)});x.dispatchEvent(new Event('input',{bubbles:true}));x.dispatchEvent(new Event('change',{bubbles:true}));return x.value})()`);if(result!==value)throw Error('context fill mismatch '+label)}}
    async function sendJourney(label,cid,question,fields={}){
      await setFields(fields);const before=JSON.parse(await evaluate(`fetch('/api/conversations/'+encodeURIComponent(${JSON.stringify(cid)})+'/runs').then(r=>r.json()).then(JSON.stringify)`));const prior=new Set((Array.isArray(before)?before:before.runs||[]).map(x=>x.id));
      await evaluate(`(()=>{const x=document.querySelector('[aria-label="发送问题"]');x.focus();return true})()`);await send('Input.insertText',{text:question});if(await evaluate(`document.querySelector('[aria-label="发送问题"]')?.value`)!==question)throw Error(label+': question entry mismatch');await waitUntil(async()=>await evaluate(`Boolean(document.querySelector('.send-button')&&!document.querySelector('.send-button').disabled)`),10000,label+' send ready');await evaluate(`(()=>{const b=document.querySelector('.send-button');if(!b||b.disabled)throw Error('send disabled after readiness wait');b.click();return true})()`);
      const run=await waitUntil(async()=>{const raw=JSON.parse(await evaluate(`fetch('/api/conversations/'+encodeURIComponent(${JSON.stringify(cid)})+'/runs').then(r=>r.json()).then(JSON.stringify)`));const rows=Array.isArray(raw)?raw:(raw.runs||[]);return rows.find(x=>!prior.has(x.id))||null},20000,label+' createRun');
      let events=[];await waitUntil(async()=>{const e=JSON.parse(await evaluate(`fetch('/api/runs/'+encodeURIComponent(${JSON.stringify(run.id)})+'/events?after_sequence=0').then(r=>r.json()).then(x=>JSON.stringify(x.events))`));events=e;return e.some(x=>['run_completed','run_failed','error'].includes(x.type))},90000,label+' terminal');
      const detail=JSON.parse(await evaluate(`fetch('/api/conversations/'+encodeURIComponent(${JSON.stringify(cid)})).then(r=>r.json()).then(JSON.stringify)`));const messages=detail.messages||[];const answers=messages.filter(x=>x.role==='assistant'&&x.run_id===run.id);const answer=String((answers.at(-1)||messages.filter(x=>x.role==='assistant').at(-1))?.content||'');if(!answer.trim())throw Error(label+': missing main answer');if(answers.length>1)throw Error(label+': duplicate assistant messages for run '+run.id);const snapshot=JSON.parse(await evaluate(`fetch('/api/runs/'+encodeURIComponent(${JSON.stringify(run.id)})+'/input').then(r=>r.json()).then(JSON.stringify)`));const finalRun=JSON.parse(await evaluate(`fetch('/api/runs/'+encodeURIComponent(${JSON.stringify(run.id)})).then(r=>r.json()).then(JSON.stringify)`));
      const replay=JSON.parse(await evaluate(`fetch('/api/runs/'+encodeURIComponent(${JSON.stringify(run.id)})+'/events?after_sequence=0').then(r=>r.json()).then(x=>JSON.stringify(x.events))`));if(JSON.stringify(events.map(x=>[x.sequence,x.type]))!==JSON.stringify(replay.map(x=>[x.sequence,x.type])))throw Error(label+': replay differs');if(events.some((x,i)=>i&&x.sequence<=events[i-1].sequence))throw Error(label+': sequence is not monotonic');if(events.at(-1)?.type!=='run_completed')throw Error(label+': terminal '+events.at(-1)?.type);
      const sse=await evaluate(`(async()=>{const url='/api/runs/'+encodeURIComponent(${JSON.stringify(run.id)})+'/stream';const ctl=new AbortController();const r=await fetch(url,{headers:{Accept:'text/event-stream'},signal:ctl.signal});if(!r.ok)throw Error('SSE reconnect status '+r.status);const reader=r.body.getReader(),decoder=new TextDecoder();let first='',last=0;while(!last){const n=await reader.read();if(n.done)break;first+=decoder.decode(n.value,{stream:true});const line=first.split(/\\r?\\n/).find(x=>x.startsWith('id: '));if(line)last=Number(line.slice(4).trim())}ctl.abort();try{await reader.cancel()}catch{};if(!last)throw Error('disconnect got no SSE id');const resumed=await fetch(url,{headers:{Accept:'text/event-stream','Last-Event-ID':String(last)}});const body=await resumed.text();const ids=body.split(/\\r?\\n/).filter(x=>x.startsWith('id: ')).map(x=>Number(x.slice(4).trim()));return {status:r.status,first_sequence:last,resumed_status:resumed.status,resumed_sequences:ids,duplicate_sequences:ids.filter(x=>x<=last)}})()`);if(sse.status!==200||sse.resumed_status!==200||sse.duplicate_sequences.length)throw Error(label+': SSE discontinuity '+JSON.stringify(sse));
      const sourceIds=new Set();const tools=[];for(const ev of events){if(/tool_(called|result|completed)/.test(ev.type))tools.push(ev.payload?.tool||ev.payload?.tool_name||ev.agent);const walk=(v,k='')=>{if(v&&typeof v==='object'){for(const [key,val] of Object.entries(v))walk(val,key)}else if(typeof v==='string'&&/(clause|source|reference).*id/i.test(k)&&/[A-Z0-9][A-Z0-9._:-]{3,}/i.test(v))sourceIds.add(v)};walk(ev.payload||{})}
      await evaluate(`(()=>{for(const d of document.querySelectorAll('details.full-report')){if(!d.open)d.querySelector('summary')?.click()}return true})()`);
      await waitUntil(async()=>String(await evaluate('document.body?.innerText||""')).includes(question.slice(0,Math.min(8,question.length))),15000,label+' visible question');
      const body=String(await evaluate('document.body?.innerText||""'));const evidence=String(await evaluate(`document.querySelector('.evidence-section')?.innerText||''`));const shot=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});const shotPath=`${outputDir}/Edge_${viewport}_${label}_${Date.now()}.png`;await fs.writeFile(shotPath,Buffer.from(shot.data,'base64'));
      let sourceAuditText='';let sourceAuditScreenshot=null;if(label==='source_review'||label==='professional_B_shell_impact'){await evaluate(`(()=>{const b=document.querySelector('.inspector-toggle');if(b&&b.getAttribute('aria-expanded')!=='true')b.click();return true})()`);await waitUntil(async()=>await evaluate(`Boolean(document.querySelector('.inspector-section .event-item'))`),10000,label+' audit timeline');const opened=await evaluate(`(()=>{const rows=[...document.querySelectorAll('.inspector-section .event-item')];const row=rows.find(x=>x.innerText.includes('a2_candidate_retrieval'))||rows.find(x=>x.innerText.includes('tool_result'));if(!row)throw Error('source audit event missing');row.click();return true})()`);if(!opened)throw Error(label+': could not open source audit event');await waitUntil(async()=>await evaluate(`Boolean(document.querySelector('[aria-label="来源与事件详情"]'))`),10000,label+' source detail modal');await evaluate(`(()=>{const d=document.querySelector('[aria-label="来源与事件详情"] details.audit-details');if(d&&!d.open)d.querySelector('summary')?.click();return true})()`);sourceAuditText=String(await evaluate(`document.querySelector('[aria-label="来源与事件详情"]')?.innerText||''`));const auditShot=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});sourceAuditScreenshot=`${outputDir}/Edge_${viewport}_${label}_source_audit_${Date.now()}.png`;await fs.writeFile(sourceAuditScreenshot,Buffer.from(auditShot.data,'base64'));await evaluate(`document.querySelector('[aria-label="关闭"]')?.click()`)}
      const row={label,conversation_id:cid,run_id:run.id,question,mode:snapshot.mode,status:finalRun.status,terminal_event:events.at(-1)?.type,assistant_messages_for_run:answers.length,input_snapshot:{question:snapshot.question,mode:snapshot.mode,context:snapshot.context},events:events.map(x=>({sequence:x.sequence,type:x.type,agent:x.agent||null,tool:x.payload?.tool||x.payload?.tool_name||null})),sse_disconnect_replay:sse,teacher_tools:[...new Set(tools.filter(Boolean))],source_ids:[...sourceIds],main_answer:answer,visible_in_dom:body.includes(question.slice(0,Math.min(8,question.length)))&&body.replace(/[*#_>~]/g,'').replace(/\s+/g,'').includes(answer.replace(/[*#_>~]/g,'').replace(/\s+/g,'').slice(0,8)),dom_excerpt:body.slice(-1800),evidence_panel:evidence.slice(0,800),source_audit_text:sourceAuditText,source_audit_screenshot:sourceAuditScreenshot,screenshot:shotPath};journeys.push(row);if(finalRun.status!=='completed')throw Error(label+': SQLite run status '+finalRun.status);if(!row.visible_in_dom)throw Error(label+': main answer/question not visible in DOM');return row;
    }
    // Real 503 from the isolated backend's unconfigured model profile; no provider call. Then a genuine UI Rule Demo retry.
    const cidRecovery=await newConversation();const failed=await evaluate(`fetch('/api/conversations/'+encodeURIComponent(${JSON.stringify(cidRecovery)})+'/runs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:'provider unavailable probe',mode:'DEEPSEEK',web_mode:'off'})}).then(async r=>({status:r.status,body:await r.json()}))`);if(failed.status!==503)throw Error('unconfigured DeepSeek must fail closed with 503: '+JSON.stringify(failed));journeys.push({label:'unconfigured_model_503',conversation_id:cidRecovery,http_status:failed.status,error:failed.body.detail||failed.body.code,run_created:false});await sendJourney('rule_demo_recovery',cidRecovery,'你好');
    const cidScc=await newConversation();const scc=await sendJourney('scc_concept',cidScc,'什么是应力腐蚀开裂？');for(const word of ['拉应力','腐蚀环境','易感材料','裂纹'])if(!scc.main_answer.includes(word))throw Error('SCC answer missing '+word);
    const cidA=await newConversation();const known={'设备名称':'塔顶碱液管线弯头','材质':'300系列不锈钢','介质':'碱式酸性水','运行工况':'60°C，1.0 MPa'};const a=await sendJourney('professional_A_60C',cidA,'设备局部减薄可能属于哪类腐蚀机理？请列来源及适用条件未知项。',known);const actx=JSON.stringify(a.input_snapshot.context);for(const word of ['300系列不锈钢','碱式酸性水','60'])if(!actx.includes(word))throw Error('professional A snapshot lost '+word);
    await sendJourney('professional_A_80C',cidA,'若温度更正为80°C，是否足以排除碱式酸性水腐蚀？',{'运行工况':'80°C，1.0 MPa'});
    await sendJourney('source_review',cidA,'请审查本会话出现的来源ID、来源等级、支持范围、未知条件，并说明这些来源是否足以证明本设备可继续运行。');
    const cidB=await newConversation();await sendJourney('professional_B_shell_impact',cidB,'设备发生壳体磕碰损伤，什么情况需要停机维修？验收判定标准是什么？请列来源和未知条件。');
    const cidFacts=await newConversation();await sendJourney('fact_original',cidFacts,'设备甲材质为碳钢，湿H2S介质，70°C、2.0 MPa，请梳理候选机理。',{'设备名称':'设备甲','材质':'碳钢','介质':'湿H2S','运行工况':'70°C，2.0 MPa'});const correctedRow=await sendJourney('fact_corrected',cidFacts,'更正：材质不是碳钢，而是316L；继续分析设备腐蚀机理。',{'材质':'316L'});const correctedContext=correctedRow.input_snapshot.context;const correctedMaterial=String(correctedContext.material||'');if(!/316L|奥氏体不锈钢/.test(correctedMaterial)||/碳钢/.test(correctedMaterial))throw Error('fact correction did not override current material');const correctionAudit=correctedContext._context_conflicts||[];if(!correctionAudit.some(x=>x.field==='material'&&x.resolution==='explicit_correction_supersedes_prior'))throw Error('fact correction audit trail missing');
    const anonymousRow=await sendJourney('new_anonymous_device_same_cid',cidFacts,'另外一台未命名设备发生腐蚀，应该如何排查？',{'设备名称':'','设备类型':'','材质':'','介质':'','运行工况':'','现场证据':''});const anon=JSON.stringify(anonymousRow.input_snapshot.context);if(/316L|碳钢|湿H2S|设备甲/.test(anon))throw Error('new anonymous device inherited old facts');
    const followRow=await sendJourney('anonymous_followup_same_cid',cidFacts,'继续分析该设备的腐蚀机理。',{'设备名称':'','设备类型':'','材质':'','介质':'','运行工况':'','现场证据':''});if(/316L|碳钢|湿H2S|设备甲/.test(JSON.stringify(followRow.input_snapshot.context)))throw Error('anonymous follow-up resurrected old facts');
    const cidCross=await newConversation();const crossRow=await sendJourney('cross_conversation_isolation',cidCross,'继续分析设备腐蚀机理。');if(/316L|碳钢|湿H2S|设备甲/.test(JSON.stringify(crossRow.input_snapshot.context)))throw Error('cross-conversation context leaked');
  }
  const out={browserPid:Number(browserPid),target:{id:target.id,type:target.type,url:target.url,webSocketDebuggerUrl:wsUrl},browserVersion:await evaluate('navigator.userAgent'),state,proxiedHealth:{status:proxiedHealth.status,contract_version:proxiedHealth.body.contract_version,build_fingerprint:proxiedHealth.body.build_fingerprint},hello,professionalJourneys:journeys,layout:await evaluate(`(()=>{const r=document.querySelector('.composer-wrap').getBoundingClientRect();return {bottom:r.bottom,height:innerHeight,scroll:document.documentElement.scrollWidth,width:innerWidth}})()`),apiResponses:network,failedRequests,consoleErrors:errors, screenshots:[shotPath,...(hello?[answerShotPath]:[]),...journeys.map(x=>x.screenshot).filter(Boolean)]};
  await fs.writeFile(jsonPath,JSON.stringify(out,null,2));console.log(JSON.stringify(out));ws.close();
}
main().catch(async e=>{const detail={error:String(e),stack:e.stack||null,cdpError:e.cdpError||null,exceptionDetails:e.exceptionDetails||null,expressionHash:e.expressionHash||null,expressionPrefix:e.expressionPrefix||null,method:e.method||null,timeoutMs:e.timeoutMs||null,nodePid:process.pid,browserPid:Number(browserPid),target:{id:target.id,type:target.type,url:target.url,webSocketDebuggerUrl:wsUrl},completedJourneys:journeys,events:network,failedRequests,consoleErrors:errors};try{await fs.writeFile(jsonPath,JSON.stringify(detail,null,2))}catch{};console.error(JSON.stringify(detail));process.exitCode=1;try{ws.close()}catch{}});
'@
    Write-Output "CDP target: id=$($target.id) type=$($target.type) url=$($target.url) websocket=$($target.webSocketDebuggerUrl)"
    $nodeScript = Join-Path $env:TEMP "r2_browser_cdp_$stamp.cjs"
    $nodeStdout = Join-Path $env:TEMP "r2_browser_cdp_$stamp.stdout.log"
    $nodeStderr = Join-Path $env:TEMP "r2_browser_cdp_$stamp.stderr.log"
    [IO.File]::WriteAllText($nodeScript, $nodeProgram, [Text.UTF8Encoding]::new($false))
    $config = [ordered]@{wsUrl=$target.webSocketDebuggerUrl;targetUrl=$FrontendUrl;shotPath=$screenshot;answerShotPath=$answerScreenshot;jsonPath=$jsonPath;outputDir=$outputFull;browserName=$Browser;viewport=$Viewport;widthText=[string]$dimensions.width;heightText=[string]$dimensions.height;mobileText=([string]$dimensions.mobile).ToLowerInvariant();expectedContract=$ExpectedContractVersion;expectedFingerprint=$diskFrontendFingerprint;expectedBackendFingerprint=$health.build_fingerprint;helloSmoke=([string]$HelloSmoke.IsPresent).ToLowerInvariant();professionalJourneys=([string]$ProfessionalJourneys.IsPresent).ToLowerInvariant();browserPid=[string]$proc.Id;target=[ordered]@{id=$target.id;type=$target.type;url=$target.url;webSocketDebuggerUrl=$target.webSocketDebuggerUrl}} | ConvertTo-Json -Depth 6 -Compress
    $configBase64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($config))
    $nodeArguments = '"' + $nodeScript + '" "' + $configBase64 + '"'
    $nodeProcess = Start-Process -FilePath $node -ArgumentList $nodeArguments -PassThru -Wait -WindowStyle Hidden -RedirectStandardOutput $nodeStdout -RedirectStandardError $nodeStderr
    $stdoutText = if (Test-Path $nodeStdout) { Get-Content -LiteralPath $nodeStdout -Raw } else { '' }
    $stderrText = if (Test-Path $nodeStderr) { Get-Content -LiteralPath $nodeStderr -Raw } else { '' }
    if ($nodeProcess.ExitCode -ne 0) { throw "CDP validation failed (exit=$($nodeProcess.ExitCode)); stdout=$stdoutText; stderr=$stderrText; diagnostics=$jsonPath" }
    $result = $stdoutText
    $result | Write-Output
    Write-Output "Screenshot: $screenshot"
    if ($HelloSmoke) { Write-Output "Hello screenshot: $answerScreenshot" }
    Write-Output "Evidence: $jsonPath"
    Write-Output "Backend contract: $($health.contract_version)"
    Write-Output "Backend fingerprint: $($health.build_fingerprint)"
    Write-Output "Frontend source fingerprint: $diskFrontendFingerprint"
    Write-Output "Backend capabilities: $($health.capabilities | ConvertTo-Json -Compress)"
} finally {
    if ($proc -and -not $proc.HasExited) { Stop-Process -Id $proc.Id -ErrorAction SilentlyContinue }
    # The isolated profile is deliberately retained for forensic inspection and is under TEMP.
    Write-Output "Isolated browser profile retained at: $profile"
}
