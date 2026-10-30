"""Read-only headless Edge DOM bounds check against local Aetheris 8000.

Never submits a form or edits server data. Starts an isolated temporary profile.
"""
import asyncio, json, subprocess, tempfile, time, urllib.request
from pathlib import Path
import websockets

EDGE=r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
PORT=19341
EVAL=r"""(() => {
 const box=(s)=>{const el=document.querySelector(s);if(!el)return null;
   const r=el.getBoundingClientRect(),c=getComputedStyle(el);
   return {x:Math.round(r.x),y:Math.round(r.y),height:Math.round(r.height),
     width:Math.round(r.width),bottom:Math.round(r.bottom),
     display:c.display,visibility:c.visibility,overflow:c.overflow,
     disabled:!!el.disabled};};
 return {innerWidth,innerHeight,documentHeight:document.documentElement.scrollHeight,
  composer:box('.composer-wrap'),textarea:box('textarea[aria-label="发送问题"]'),
  send:box('.send-button'),sidebar:box('.sidebar'),topbar:box('.topbar'),
  scroll:box('.chat-scroll'),errorCount:document.querySelectorAll('.error-banner').length,
  selectedCount:document.querySelectorAll('.conversation-row.active').length,
  sidebarItems:document.querySelectorAll('.conversation-row').length};
})()"""

async def main():
    with tempfile.TemporaryDirectory(prefix="aether-edge-probe-") as temp:
        proc=subprocess.Popen([EDGE,"--headless=new","--no-first-run","--disable-gpu",
            f"--remote-debugging-port={PORT}","--remote-allow-origins=*",
            f"--user-data-dir={temp}","--window-size=1717,813",
            "http://127.0.0.1:8000/"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            url=f"http://127.0.0.1:{PORT}/json"
            for _ in range(80):
                try:
                    pages=json.load(urllib.request.urlopen(url,timeout=1))
                    match=next((x for x in pages if x.get("type")=="page" and "127.0.0.1:8000" in x.get("url","")),None)
                    if match: break
                except Exception: pass
                await asyncio.sleep(.1)
            else:
                print(json.dumps({"status":"NO_BROWSER_DEBUG_SESSION"}));return
            async with websockets.connect(match["webSocketDebuggerUrl"],open_timeout=5,max_size=2_000_000) as ws:
                await asyncio.sleep(3)
                await ws.send(json.dumps({"id":1,"method":"Runtime.evaluate",
                    "params":{"expression":EVAL,"returnByValue":True}}))
                for _ in range(30):
                    m=json.loads(await asyncio.wait_for(ws.recv(),timeout=4))
                    if m.get("id")==1:
                        print(json.dumps(m.get("result",{}).get("result",{}).get("value",{}),ensure_ascii=False))
                        break
        finally:
            proc.terminate()
            try:proc.wait(timeout=3)
            except subprocess.TimeoutExpired:proc.kill()

if __name__=="__main__":asyncio.run(main())
