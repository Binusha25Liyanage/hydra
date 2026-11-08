"""Fake WhatsApp Web for testing Hydra without a phone (python tools/mock_whatsapp.py, then set
Settings → WhatsApp URL to http://127.0.0.1:8766).

It copies the parts of WhatsApp Web that Hydra uses: the QR screen, the chat list and search
box, the attach menu with its two file inputs, the caption box, the send button and the
clock → double-tick on outgoing messages.

  POST /scan     pretend the phone scanned the QR code
  GET  /sent     JSON list of every message "sent"
  POST /reset    forget sent messages and the scan
"""
from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

CHATS = ["Lakmee Management", "Sales Admin Team", "NSM Reports", "IT Department"]
STATE = {"scanned": False, "sent": []}

PAGE = r"""<!doctype html><html><head><meta charset="utf-8"><title>WhatsApp</title><style>
body{margin:0;font-family:Segoe UI,Arial;background:#111b21;color:#e9edef;display:flex;height:100vh}
#landing{margin:auto;text-align:center}#landing canvas{background:#fff;padding:12px;border-radius:8px}
#app{display:none;flex:1}#pane-side{width:340px;border-right:1px solid #333;padding:10px}
[data-tab="3"]{border:1px solid #444;border-radius:8px;padding:8px;min-height:20px;margin-bottom:10px}
#list div{padding:10px;border-bottom:1px solid #222;cursor:pointer}#main{flex:1;display:flex;flex-direction:column}
#msgs{flex:1;overflow:auto;padding:12px}.message-out{background:#005c4b;margin:6px 0 6px auto;max-width:60%;padding:8px;border-radius:8px}
footer{display:flex;gap:8px;padding:10px;border-top:1px solid #333}footer [contenteditable]{flex:1;border:1px solid #444;border-radius:8px;padding:8px}
#menu{display:none;position:absolute;bottom:60px;left:360px;background:#233138;padding:10px;border-radius:8px}
#preview{display:none;position:fixed;inset:0;background:#0b141a;padding:40px}#preview [contenteditable]{border:1px solid #555;padding:8px;margin:20px 0}
span[data-icon]{cursor:pointer;display:inline-block;padding:6px 10px;background:#2a3942;border-radius:6px}
</style></head><body>
<div id="landing"><h2>Use WhatsApp on your computer</h2><canvas aria-label="Scan this QR code to link a device!" width="160" height="160"></canvas></div>
<div id="app"><div id="pane-side"><div contenteditable="true" data-tab="3" aria-label="Search input textbox"></div><div id="list"></div></div>
<div id="main"><header id="hdr" style="padding:12px;border-bottom:1px solid #333"></header><div id="msgs"></div>
<footer style="display:none" id="foot"><span data-icon="plus-rounded" title="Attach">+</span><div contenteditable="true" data-tab="10" aria-label="Type a message"></div></footer></div></div>
<div id="menu"><label>Photos &amp; videos<input type="file" accept="image/*,video/mp4,video/3gpp,video/quicktime" multiple style="display:none"></label><br>
<label>Document<input type="file" accept="*" multiple style="display:none"></label></div>
<div id="preview"><div id="pfiles"></div><div contenteditable="true" aria-label="Add a caption" data-tab="10"></div><span data-icon="send" aria-label="Send">Send</span></div>
<script>
const CHATS = __CHATS__;
let chat = null, pending = [];
const store = {};
function draw(){ const c=document.querySelector('canvas').getContext('2d'); for(let i=0;i<16;i++)for(let j=0;j<16;j++){c.fillStyle=Math.random()>.5?'#000':'#fff';c.fillRect(i*10,j*10,10,10);} }
function linked(){ return localStorage.getItem('linked')==='1'; }
function boot(){
  if(!linked()){ draw(); const t=setInterval(async()=>{ const r=await fetch('/scanned'); if((await r.json()).scanned){ clearInterval(t); localStorage.setItem('linked','1'); localStorage.setItem('last-wid-md','"94771234567:7@c.us"'); boot(); } else draw(); },600); return; }
  document.getElementById('landing').style.display='none'; document.getElementById('app').style.display='flex';
  list(''); const p=new URLSearchParams(location.search).get('phone'); if(location.pathname==='/send'&&p){ if(p.length<9){document.getElementById('hdr').textContent='Phone number shared via url is invalid.';return;} open('+'+p); }
}
function list(q){ document.getElementById('list').innerHTML=CHATS.filter(c=>c.toLowerCase().includes(q.toLowerCase())).map(c=>`<div><span title="${c}">${c}</span></div>`).join(''); }
document.querySelector('[data-tab="3"]').addEventListener('input',e=>list(e.target.textContent));
document.getElementById('list').addEventListener('click',e=>{const s=e.target.closest('span[title]'); if(s) open(s.title);});
function open(name){ chat=name; document.getElementById('hdr').textContent=name; document.getElementById('foot').style.display='flex'; render(); }
function render(){ document.getElementById('msgs').innerHTML=(store[chat]||[]).map(m=>`<div class="message-out"><div>${m.text}</div><span data-icon="${m.ok?'msg-dblcheck':'msg-time'}"></span></div>`).join(''); }
function push(files,text){ const m={text:(files.length?'['+files.join(', ')+'] ':'')+text,ok:false}; (store[chat]=store[chat]||[]).push(m); render();
  fetch('/sent',{method:'POST',body:JSON.stringify({chat,files,text})}); setTimeout(()=>{m.ok=true;render();},700); }
document.querySelector('[data-icon="plus-rounded"]').onclick=()=>{document.getElementById('menu').style.display='block';};
document.querySelectorAll('#menu input').forEach(i=>i.addEventListener('change',()=>{ pending=[...i.files].map(f=>f.name); document.getElementById('menu').style.display='none';
  document.getElementById('pfiles').textContent=pending.join(', '); document.getElementById('preview').style.display='block'; }));
document.querySelector('#preview [data-icon="send"]').onclick=()=>{ const cap=document.querySelector('[aria-label="Add a caption"]'); push(pending, cap.innerText.trim()); cap.textContent=''; pending=[]; document.getElementById('preview').style.display='none'; document.querySelectorAll('#menu input').forEach(i=>i.value=''); };
document.querySelector('footer [contenteditable]').addEventListener('keydown',e=>{ if(e.key==='Enter'&&!e.shiftKey){ e.preventDefault(); push([], e.target.innerText.trim()); e.target.textContent=''; } });
boot();
</script></body></html>"""


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, body, ctype="application/json", code=200):
        b = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path.startswith("/scanned"):
            return self._send(json.dumps({"scanned": STATE["scanned"]}))
        if self.path.startswith("/sent"):
            return self._send(json.dumps(STATE["sent"]))
        return self._send(PAGE.replace("__CHATS__", json.dumps(CHATS)), "text/html; charset=utf-8")

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n) if n else b""
        if self.path == "/scan":
            STATE["scanned"] = True
        elif self.path == "/reset":
            STATE.update(scanned=False, sent=[])
        elif self.path == "/sent":
            STATE["sent"].append(json.loads(body or b"{}"))
        return self._send("{}")


def serve(port=8766, background=False):
    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    if background:
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        return srv
    print(f"Mock WhatsApp on http://127.0.0.1:{port}  (POST /scan to link)")
    srv.serve_forever()


if __name__ == "__main__":
    serve(int(sys.argv[1]) if len(sys.argv) > 1 else 8766)
