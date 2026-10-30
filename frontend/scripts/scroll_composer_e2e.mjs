import fs from 'node:fs/promises';

const cdpUrl = 'http://127.0.0.1:9222/json/list';
const target = await fetch(cdpUrl).then(response => response.json()).then(tabs => tabs.find(tab => tab.type === 'page'));
if (!target) throw new Error('Edge CDP page target missing');
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((resolve, reject) => {
  ws.addEventListener('open', resolve, { once: true });
  ws.addEventListener('error', reject, { once: true });
});

let nextId = 0;
const pending = new Map();
ws.addEventListener('message', event => {
  const message = JSON.parse(event.data);
  if (!message.id || !pending.has(message.id)) return;
  const waiter = pending.get(message.id);
  pending.delete(message.id);
  message.error ? waiter.reject(new Error(message.error.message)) : waiter.resolve(message.result);
});
function cdp(method, params = {}) {
  const id = ++nextId;
  return new Promise((resolve, reject) => {
    pending.set(id, { resolve, reject });
    ws.send(JSON.stringify({ id, method, params }));
  });
}
async function evaluate(expression) {
  const result = await cdp('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true });
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.text);
  return result.result?.value;
}
async function waitFor(expression, label) {
  const deadline = Date.now() + 15000;
  while (Date.now() < deadline) {
    if (await evaluate(expression)) return;
    await new Promise(resolve => setTimeout(resolve, 200));
  }
  throw new Error(`timeout waiting for ${label}`);
}
async function checkViewport(width, height, mobile) {
  await cdp('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: 1, mobile });
  await new Promise(resolve => setTimeout(resolve, 500));
  const metrics = JSON.parse(await evaluate(`JSON.stringify((()=>{
    const rect=e=>{const r=e.getBoundingClientRect();return {top:Math.round(r.top),bottom:Math.round(r.bottom),height:Math.round(r.height)}};
    const shell=document.querySelector('.app-shell'), workspace=document.querySelector('.workspace');
    const scroll=document.querySelector('.chat-scroll'), composer=document.querySelector('.composer-wrap');
    const input=document.querySelector('[aria-label="发送问题"]');
    return {viewport:{width:innerWidth,height:innerHeight},body:{clientHeight:document.body.clientHeight,scrollHeight:document.body.scrollHeight},shell:rect(shell),workspace:rect(workspace),scroll:{...rect(scroll),clientHeight:scroll.clientHeight,scrollHeight:scroll.scrollHeight,overflowY:getComputedStyle(scroll).overflowY},composer:rect(composer),input:rect(input)};
  })())`));
  if (metrics.composer.height <= 0 || metrics.input.height <= 0) throw new Error(`composer hidden at ${width}x${height}: ${JSON.stringify(metrics)}`);
  if (metrics.composer.bottom > height + 1) throw new Error(`composer clipped below viewport at ${width}x${height}: ${JSON.stringify(metrics)}`);
  if (metrics.body.scrollHeight > metrics.body.clientHeight + 1) throw new Error(`outer page unexpectedly scrolls at ${width}x${height}: ${JSON.stringify(metrics)}`);
  if (metrics.scroll.overflowY !== 'auto' && metrics.scroll.overflowY !== 'scroll') throw new Error(`conversation is not the scroll container: ${JSON.stringify(metrics)}`);
  if (metrics.scroll.scrollHeight > metrics.scroll.clientHeight) {
    await evaluate(`(()=>{const e=document.querySelector('.chat-scroll');e.scrollTop=e.scrollHeight;return e.scrollTop})()`);
    const after = JSON.parse(await evaluate(`JSON.stringify((()=>{const c=document.querySelector('.composer-wrap').getBoundingClientRect();const i=document.querySelector('[aria-label="发送问题"]').getBoundingClientRect();return {composerBottom:Math.round(c.bottom),inputBottom:Math.round(i.bottom),scrollTop:document.querySelector('.chat-scroll').scrollTop}})())`));
    if (after.composerBottom > height + 1 || after.inputBottom > height + 1) throw new Error(`composer moved/clipped while scrolling conversation: ${JSON.stringify(after)}`);
  }
  return metrics;
}

await cdp('Page.enable');
await cdp('Runtime.enable');
await cdp('Page.navigate', { url: 'http://127.0.0.1:8000/' });
await waitFor("!!document.querySelector('.new-chat') && !!document.querySelector('.composer-wrap')", 'chat UI');
const desktop = await checkViewport(1440, 900, false);
const mobile = await checkViewport(390, 844, true);
const outputDir = new URL('../evidence/', import.meta.url);
await fs.mkdir(outputDir, { recursive: true });
for (const [name, width, height, isMobile] of [['scroll-fix-desktop', 1440, 900, false], ['scroll-fix-mobile', 390, 844, true]]) {
  await cdp('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: 1, mobile: isMobile });
  await new Promise(resolve => setTimeout(resolve, 300));
  const shot = await cdp('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
  await fs.writeFile(new URL(`${name}.png`, outputDir), Buffer.from(shot.data, 'base64'));
}
console.log(JSON.stringify({ desktop, mobile, result: 'PASS' }, null, 2));
ws.close();
