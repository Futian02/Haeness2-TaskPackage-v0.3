import fs from 'node:fs/promises';

const base='http://127.0.0.1:5173';
const apiBase='http://127.0.0.1:8000';
const output=new URL('../../docs/audits/',import.meta.url);
const targets=await fetch('http://127.0.0.1:9222/json/list').then(r=>r.json());
const target=targets.find(x=>x.type==='page');
if(!target)throw new Error('Edge CDP target missing');
const ws=new WebSocket(target.webSocketDebuggerUrl);
await new Promise((resolve,reject)=>{ws.addEventListener('open',resolve,{once:true});ws.addEventListener('error',reject,{once:true})});
let id=0;const pending=new Map();const consoleErrors=[];const network=[];
ws.addEventListener('message',event=>{const m=JSON.parse(event.data);if(m.id&&pending.has(m.id)){const p=pending.get(m.id);pending.delete(m.id);m.error?p.reject(new Error(`${p.method}: ${m.error.message}`)):p.resolve(m.result)}else if(m.method==='Runtime.exceptionThrown'){consoleErrors.push(m.params.exceptionDetails.text)}else if(m.method==='Runtime.consoleAPICalled'&&['error','warning'].includes(m.params.type)){consoleErrors.push(`${m.params.type}: ${m.params.args.map(a=>a.value??a.description).join(' ')}`)}else if(m.method==='Network.responseReceived'&&m.params.response.url.includes('/api/'))network.push({url:m.params.response.url,status:m.params.response.status})});
function cdp(method,params={}){const requestId=++id;return new Promise((resolve,reject)=>{pending.set(requestId,{resolve,reject,method});ws.send(JSON.stringify({id:requestId,method,params}))})}
async function evaluate(expression){const r=await cdp('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(r.exceptionDetails)throw new Error(`${expression.slice(0,150)}: ${r.exceptionDetails.text}`);return r.result?.value}
async function waitFor(expression,label,timeout=30000){const end=Date.now()+timeout;while(Date.now()<end){const found=await evaluate(expression);if(found)return found;await new Promise(r=>setTimeout(r,150))}throw new Error(`timeout waiting for ${label}`)}
async function screenshot(name){const result=await cdp('Page.captureScreenshot',{format:'png',captureBeyondViewport:true});await fs.writeFile(new URL(`${name}.png`,output),Buffer.from(result.data,'base64'))}
async function setValue(selector,value){return evaluate(`(()=>{const x=document.querySelector(${JSON.stringify(selector)});if(!x)throw Error('missing ${selector}');const p=x instanceof HTMLTextAreaElement?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;Object.getOwnPropertyDescriptor(p,'value').set.call(x,${JSON.stringify(value)});x.dispatchEvent(new Event('input',{bubbles:true}));x.dispatchEvent(new Event('change',{bubbles:true}));return true})()`)}
async function setViewport(width,height,mobile=false){await cdp('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile});await new Promise(r=>setTimeout(r,450))}
await cdp('Page.enable');await cdp('Runtime.enable');await cdp('Network.enable');await cdp('Log.enable');
await setViewport(1280,900,false);await cdp('Page.navigate',{url:base});await waitFor("!!document.querySelector('.new-chat')",'UI shell');
await evaluate('localStorage.clear();location.reload()');await waitFor("!!document.querySelector('.new-chat')",'clean UI');
const apiHealth=await fetch(`${apiBase}/api/health`).then(r=>r.json());
if(apiHealth.status!=='ok'||apiHealth.mode!=='RULE_DEMO')throw new Error(`unexpected health ${JSON.stringify(apiHealth)}`);
const conv=await fetch(`${apiBase}/api/conversations`,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({title:'P5C 完整证据流验证'})}).then(r=>r.json());
await cdp('Page.reload',{ignoreCache:true});await waitFor(`!![...document.querySelectorAll('.conversation')].find(x=>x.textContent.includes('P5C 完整证据流验证'))`,'test conversation visible');
await waitFor(`document.querySelector('.crumbs b')?.textContent==='P5C 完整证据流验证'`,'target conversation selected');
await evaluate(`document.querySelector('.context-toggle').click()`);
await setValue('[aria-label="材质"]','碳钢');await setValue('[aria-label="介质"]','氯化氢');await setValue('[aria-label="设备类型"]','换热器');
await setValue('[aria-label="设备名称"]','P5C本机E2E样例');
await setValue('[aria-label="现场证据"]','塔顶水样pH 5.8，铁离子 4.1 mg/L，尚未测厚');
const question='塔顶水样pH 5.8，铁离子 4.1 mg/L，尚未测厚，可能的损伤机理？';
await setValue('[aria-label="发送问题"]',question);await evaluate("document.querySelector('.send-button').click()");
const runId=await waitFor(`localStorage.getItem(${JSON.stringify(`aether:last-run:${conv.id}`)})`,'run id');
await waitFor("!!document.querySelector('.run-footer')",'completed UI run',45000);
const [runResponse,claimsResponse,disagreementsResponse,streamResponse]=await Promise.all([
  fetch(`${apiBase}/api/runs/${runId}`).then(r=>r.json()),
  fetch(`${apiBase}/api/runs/${runId}/claims`).then(r=>r.json()),
  fetch(`${apiBase}/api/runs/${runId}/disagreements`).then(r=>r.json()),
  fetch(`${apiBase}/api/runs/${runId}/events?after_sequence=0`).then(r=>r.json()),
]);
const events=streamResponse.events,claims=claimsResponse.claims,disagreements=disagreementsResponse.disagreements;
const refs=events.filter(e=>e.type==='reference_added');
const grades=[...new Set(claims.map(c=>c.grade))].sort();
if(runResponse.status!=='completed'||claims.length<2||!grades.includes('E0')||!grades.includes('E1')||refs.length===0||!events.some(e=>e.type==='requires_human_review')||disagreements.length===0)throw new Error(`full-evidence assertions failed: ${JSON.stringify({status:runResponse.status,claims:claims.length,grades,refs:refs.length,disagreements:disagreements.length})}`);
if(claims.some(c=>/risk_level|risk_grade|likelihood|severity/i.test(JSON.stringify(c))||/\bL[1-5]\b|低风险|高风险/.test(JSON.stringify(c))))throw new Error('unsupported risk conclusion leaked in claims JSON');
const replay5=await fetch(`${apiBase}/api/runs/${runId}/events?after_sequence=5`).then(r=>r.json());
if(!replay5.events.length||replay5.events[0].sequence!==6||replay5.events.some((e,i)=>i&&e.sequence!==replay5.events[i-1].sequence+1))throw new Error('SQLite replay after_sequence is not contiguous');
const typeCounts=Object.fromEntries([...new Set(events.map(e=>e.type))].map(type=>[type,events.filter(e=>e.type===type).length]));
// Keep counts on their own population: reference events are not Claim grades.
const referenceEventGates=Object.fromEntries([...new Set(refs.map(e=>String(e.payload.verification_level??'unknown')))].map(level=>[level,refs.filter(e=>String(e.payload.verification_level??'unknown')===level).length]));
const claimGradeCounts=Object.fromEntries([...new Set(claims.map(c=>String(c.grade??'unknown')))].map(grade=>[grade,claims.filter(c=>String(c.grade??'unknown')===grade).length]));
await waitFor(`document.querySelectorAll('.claim-card').length>=2`,'claim evidence cards');
const desktopLayout=JSON.parse(await evaluate(`JSON.stringify({width:innerWidth,bodyWidth:document.body.scrollWidth,flowWidth:Math.round(document.querySelector('.react-flow')?.getBoundingClientRect().width||0),claimCards:document.querySelectorAll('.claim-card').length})`));
await screenshot('P5C_DESKTOP_1280');
// Open E1 source drawer and verify stable clause/page/hash/quote/unknown/review data is readable.
await evaluate(`document.querySelector('.claim-card[data-claim-id*="mechanism-1"]')?.click()`);
await waitFor("!!document.querySelector('.evidence-modal')",'E1 source drawer open',5000);
const e1Detail=await evaluate(`(()=>{const m=document.querySelector('.evidence-modal');return {text:m.innerText,html:m.innerHTML}})()`);
if(!e1Detail.text.includes('canonical_sha256')){const diagnostic=await evaluate(`JSON.stringify({claimCards:[...document.querySelectorAll('.claim-card')].map(x=>({id:x.dataset.claimId,text:x.innerText})),modal:document.querySelector('.evidence-modal')?.innerText})`);throw new Error(`E1 drawer missing canonical evidence: ${diagnostic}`)}
if(!/E1/.test(e1Detail.text)||!/canonical_quote/.test(e1Detail.text)||!/印刷页/.test(e1Detail.text)||!/not_specified|unknown/.test(e1Detail.text))throw new Error('E1 source drawer misses required provenance/unknown fields');
await screenshot('P5C_E1_SOURCE_DRAWER_1280');
await evaluate("document.querySelector('.evidence-modal [aria-label=\"关闭\"]')?.click()");
// Verify E0/missing source drawer separately; no E2/E3 or L-level risk claim can appear.
await evaluate(`document.querySelector('.claim-card[data-claim-id*="mechanism-2"]')?.click()`);
const e0Detail=await waitFor("document.querySelector('.evidence-modal')?.innerText.includes('E0')",'E0 source drawer');
const e0Text=await evaluate("document.querySelector('.evidence-modal')?.innerText||''");
if(!/missing|partial|来源待复核/.test(e0Text)||/\bE2\b|\bE3\b|\bL[1-5]\b|低风险|高风险/.test(e0Text))throw new Error(`E0 drawer gate/risk check failed: ${e0Text}`);
await screenshot('P5C_E0_SOURCE_DRAWER_1280');
await evaluate("document.querySelector('.evidence-modal [aria-label=\"关闭\"]')?.click()");
// Explicitly open a raw reference event from the retained SSE timeline.
await evaluate(`[...document.querySelectorAll('.event-item')].find(x=>x.innerText.includes('reference_added'))?.click()`);
await waitFor("document.querySelector('.evidence-modal')?.innerText.includes('clause_id')",'reference source drawer');
const refText=await evaluate("document.querySelector('.evidence-modal')?.innerText||''");
if(!/GBT30579-2022/.test(refText)||!/印刷页码/.test(refText))throw new Error(`reference-added drawer missing clause/page: ${refText}`);
await screenshot('P5C_REFERENCE_DRAWER_1280');await evaluate("document.querySelector('.evidence-modal [aria-label=\"关闭\"]')?.click()");
// Open the independent graph drawer and ensure all seven role labels can be rendered in a large canvas.
await evaluate("document.querySelector('.flow-expand').click()");
const flowMetrics=JSON.parse(await waitFor("document.querySelector('.flow-expanded-canvas .react-flow__node')?JSON.stringify({nodes:document.querySelectorAll('.flow-expanded-canvas .react-flow__node').length,width:Math.round(document.querySelector('.flow-expanded-canvas .react-flow').getBoundingClientRect().width),height:Math.round(document.querySelector('.flow-expanded-canvas .react-flow').getBoundingClientRect().height)}):null",'expanded graph nodes'));
if(flowMetrics.nodes!==7||flowMetrics.width<800)throw new Error(`expanded graph unreadable: ${JSON.stringify(flowMetrics)}`);
await screenshot('P5C_GRAPH_EXPANDED_1280');await evaluate("document.querySelector('[aria-label=\"关闭放大执行图\"]').click()");
// Fast-switch to another persisted conversation: old claims must not bleed into it.
const second=await fetch(`${apiBase}/api/conversations`,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({title:'P5C 会话隔离验证'})}).then(r=>r.json());
await cdp('Page.reload',{ignoreCache:true});await waitFor(`!![...document.querySelectorAll('.conversation')].find(x=>x.textContent.includes('P5C 会话隔离验证'))`,'second conversation visible');
await evaluate(`[...document.querySelectorAll('.conversation')].find(x=>x.textContent.includes('P5C 会话隔离验证')).click()`);await waitFor(`document.querySelector('.crumbs b')?.textContent==='P5C 会话隔离验证'`,'second selected');
await new Promise(r=>setTimeout(r,400));if(await evaluate("document.querySelectorAll('.claim-card').length")!==0)throw new Error('claims crossed between conversations');
await evaluate(`[...document.querySelectorAll('.conversation')].find(x=>x.textContent.includes('P5C 完整证据流验证')).click()`);await waitFor(`document.querySelector('.crumbs b')?.textContent==='P5C 完整证据流验证'`,'first selected again');
await waitFor(`document.querySelectorAll('.claim-card').length>=2`,'first claims restored');
// Reconnect/refresh path: app reloads the completed run from the SQLite replay endpoint.
await cdp('Page.reload',{ignoreCache:true});await waitFor(`!![...document.querySelectorAll('.conversation')].find(x=>x.textContent.includes('P5C 完整证据流验证'))`,'first conversation after reload');
await evaluate(`if(document.querySelector('.crumbs b')?.textContent!=='P5C 完整证据流验证')[...document.querySelectorAll('.conversation')].find(x=>x.textContent.includes('P5C 完整证据流验证')).click()`);
await waitFor(`document.querySelector('.crumbs b')?.textContent==='P5C 完整证据流验证'&&document.querySelectorAll('.claim-card').length>=2`,'claims rehydrated from persisted SSE replay');
const restored=JSON.parse(await evaluate(`JSON.stringify({events:document.querySelectorAll('.event-item').length,claims:document.querySelectorAll('.claim-card').length,run:document.querySelector('.run-history-section')?.innerText})`));
if(restored.events!==events.length||restored.claims!==claims.length)throw new Error(`refresh restore mismatch ${JSON.stringify(restored)}`);
await screenshot('P5C_REPLAY_RESTORED_1280');
// Responsive, dark and long-input visual passes. Capture drawer in mobile mode too.
await setViewport(1440,960,false);await screenshot('P5C_DESKTOP_1440');
await setViewport(390,844,true);await screenshot('P5C_MOBILE_390');
await evaluate("document.querySelector('[aria-label=\"打开审查\"]')?.click()");await new Promise(r=>setTimeout(r,250));await evaluate(`document.querySelector('.claim-card[data-claim-id*="mechanism-1"]')?.click()`);await waitFor("!!document.querySelector('.evidence-modal')",'mobile source drawer');await screenshot('P5C_MOBILE_SOURCE_DRAWER_390');
await evaluate("document.querySelector('.evidence-modal [aria-label=\"关闭\"]')?.click()");await setViewport(1280,900,false);await evaluate("document.querySelector('[aria-label=\"切换深浅色\"]').click()");await new Promise(r=>setTimeout(r,250));await screenshot('P5C_DARK_MODE_1280');
const longText='请核对设计、材料、介质、操作温度、压力与实测壁厚；未检测项目必须标记未知，不得将检索候选写成设备结论。'.repeat(12);
await setValue('[aria-label="发送问题"]',longText);await screenshot('P5C_LONG_CHINESE_1280');
const viewportAudit=await evaluate(`JSON.stringify({width:innerWidth,bodyWidth:document.body.scrollWidth,modal:!!document.querySelector('.evidence-modal'),longInput:document.querySelector('[aria-label="发送问题"]').value.length})`);
const result={status:'READY_FOR_OWNER_REVIEW',run_id:runId,conversation_id:conv.id,second_conversation_id:second.id,mode:apiHealth.mode,health_status:apiHealth.status,full_context:{material:'碳钢',medium:['氯化氢'],equipment_type:'换热器',question,run_status:runResponse.status,event_count:events.length,event_types:typeCounts,claim_count:claims.length,claim_grades:grades,claims:claims.map(c=>({claim_id:c.claim_id,grade:c.grade,review_status:c.review_status,verdict:c.verdict,provenance_status:c.provenance_status,source_clause_ids:c.source_clause_ids,canonical_hashes:(c.canonical_evidence||[]).map(x=>x.canonical_record_sha256)})),disagreements:disagreements.length,reference_events:refs.length,reference_event_gates:referenceEventGates,claim_grade_counts:claimGradeCounts,all_claims_require_human_review:claims.every(c=>c.review_status==='requires_human_review'&&c.verdict==='unresolved')},sse:{sequences:events.map(e=>e.sequence),replay_after_sequence_5:replay5.events.length,first_replay_sequence:replay5.events[0]?.sequence,refresh_restored:restored},ui:{desktop_1280:desktopLayout,expanded_graph:flowMetrics,fast_switch_isolated:true,e1_drawer_verified:true,e0_drawer_verified:true,reference_drawer_verified:true,responsive:{desktop1440:'P5C_DESKTOP_1440.png',mobile390:'P5C_MOBILE_390.png',mobileSourceDrawer:'P5C_MOBILE_SOURCE_DRAWER_390.png',dark:'P5C_DARK_MODE_1280.png',longChinese:'P5C_LONG_CHINESE_1280.png'},viewport_audit:JSON.parse(viewportAudit)},api_statuses:network.filter(x=>x.url.includes('/api/')),console_errors:consoleErrors};
if(consoleErrors.length)throw new Error(`browser console errors: ${consoleErrors.join('; ')}`);
if(result.api_statuses.some(x=>x.status!==200))throw new Error('API request returned non-200');
await fs.writeFile(new URL('P5C_FULL_EVIDENCE_E2E.json',output),JSON.stringify(result,null,2));
console.log(JSON.stringify(result,null,2));ws.close();
