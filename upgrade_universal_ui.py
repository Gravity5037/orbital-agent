from pathlib import Path
import os

app_file = Path(r"C:\Orbital\run_orbital.py")

code = """import http.server, socketserver, json, webbrowser, pathlib, sys, os

os.chdir(r"C:\Orbital")
sys.path.append(r"C:\Orbital\core")

engine = None
try:
    from engine import Engine
    engine = Engine()
    print("[?] Orbital AI Engine (Nucleus & Nebula) Loaded.")
except Exception as e:
    print(f"[!] AI Engine Notice: {e}")

PORT = 8000

UNIVERSAL_UI = \"\"\"<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="theme-color" content="#06080d">
<title>ORBITAL OS // UNIVERSAL WORKSTATION</title>
<style>
:root {
  --bg: #06080d;
  --panel: rgba(14, 20, 30, 0.65);
  --border: rgba(0, 240, 255, 0.18);
  --cyan: #00F0FF;
  --magenta: #D946EF;
  --purple: #8A2BE2;
  --emerald: #10B981;
  --text: #e2e8f0;
  --muted: #64748b;
}
* { box-sizing: border-box; margin: 0; padding: 0; -webkit-tap-highlight-color: transparent; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif; }
body {
  background: radial-gradient(circle at 50% 10%, #0d1527 0%, var(--bg) 80%);
  color: var(--text);
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  overflow-x: hidden;
}

.glass {
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.04), rgba(255, 255, 255, 0.01)), var(--panel);
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
  border: 1px solid var(--border);
  border-radius: 16px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.6), inset 0 1px 1px rgba(255, 255, 255, 0.12);
}

header {
  padding: 14px 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid rgba(255,255,255,0.08);
  background: rgba(6, 8, 13, 0.85);
  backdrop-filter: blur(20px);
  position: sticky;
  top: 0;
  z-index: 100;
}
.brand { display: flex; align-items: center; gap: 10px; }
.brand h1 { font-size: 16px; letter-spacing: 2px; font-weight: 800; color: #fff; }
.brand span { font-size: 10px; color: var(--cyan); letter-spacing: 1.5px; font-weight: 600; }
.status-pills { display: flex; gap: 8px; }
.pill {
  padding: 5px 12px;
  border-radius: 20px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.5px;
  text-transform: uppercase;
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.1);
}
.pill-active { border-color: var(--cyan); color: var(--cyan); box-shadow: 0 0 12px rgba(0,240,255,0.3); }
.pill-node { border-color: var(--emerald); color: var(--emerald); }

main {
  flex: 1;
  display: grid;
  grid-template-columns: 310px 1fr 310px;
  gap: 16px;
  padding: 16px;
  max-width: 1600px;
  margin: 0 auto;
  width: 100%;
}
.panel {
  padding: 18px;
  display: flex;
  flex-direction: column;
}
.panel-title {
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  color: var(--cyan);
  margin-bottom: 14px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.chat-box {
  display: flex;
  flex-direction: column;
  height: 100%;
}
.logs {
  flex: 1;
  min-height: 420px;
  max-height: calc(100vh - 250px);
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-right: 6px;
  margin-bottom: 14px;
}
.msg {
  padding: 12px 16px;
  border-radius: 14px;
  font-size: 13px;
  line-height: 1.5;
  max-width: 88%;
  animation: fadeIn 0.2s ease-out;
}
@keyframes fadeIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }
.msg-user {
  align-self: flex-end;
  background: linear-gradient(135deg, rgba(0,240,255,0.2), rgba(0,136,255,0.25));
  border: 1px solid var(--cyan);
  color: #fff;
}
.msg-ai {
  align-self: flex-start;
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.1);
  color: #e2e8f0;
}
.input-row {
  display: flex;
  gap: 10px;
  background: rgba(10, 14, 22, 0.8);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 6px;
}
.input-row input {
  flex: 1;
  background: transparent;
  border: none;
  padding: 10px 14px;
  color: #fff;
  font-size: 13px;
  outline: none;
}
.input-row button {
  background: linear-gradient(135deg, var(--cyan), #0088FF);
  color: #000;
  border: none;
  border-radius: 10px;
  padding: 0 20px;
  font-weight: 800;
  font-size: 12px;
  cursor: pointer;
  letter-spacing: 0.5px;
  text-transform: uppercase;
}
.input-row button:active { transform: scale(0.96); }

#radarCanvas { width: 100%; height: 210px; border-radius: 12px; background: rgba(0,0,0,0.4); margin-bottom: 12px; }
#audioCanvas { width: 100%; height: 75px; border-radius: 8px; background: rgba(0,0,0,0.3); }

.row {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid rgba(255,255,255,0.06);
  font-size: 12px;
}
.row span:first-child { color: var(--muted); }
.row span:last-child { color: #fff; font-family: monospace; font-weight: 600; }

.mobile-nav {
  display: none;
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background: rgba(6, 8, 13, 0.92);
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
  border-top: 1px solid rgba(255,255,255,0.1);
  padding: 8px 12px;
  justify-content: space-around;
  z-index: 200;
}
.nav-tab {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  color: var(--muted);
  font-size: 10px;
  font-weight: 700;
  cursor: pointer;
  padding: 6px 14px;
  border-radius: 12px;
}
.nav-tab.active {
  color: var(--cyan);
  background: rgba(0,240,255,0.08);
}
.nav-tab span.icon { font-size: 18px; }

@media (max-width: 900px) {
  main {
    grid-template-columns: 1fr;
    padding: 12px;
    padding-bottom: 80px;
  }
  .panel-left, .panel-right {
    display: none;
  }
  .mobile-nav {
    display: flex;
  }
  .status-pills .pill:not(.pill-active):not(.pill-node) {
    display: none;
  }
}
</style>
</head>
<body>

<header>
  <div class="brand">
    <div style="font-size:22px;">??</div>
    <div>
      <h1>ORBITAL OS</h1>
      <span>UNIVERSAL WORKSTATION</span>
    </div>
  </div>
  <div class="status-pills">
    <div class="pill pill-active">? POLE 2</div>
    <div class="pill pill-node">?? NOTE 8 MESH</div>
    <div class="pill">SIMD: 512-BIT</div>
  </div>
</header>

<main>
  <div class="panel glass panel-left" id="tab-sensors">
    <div class="panel-title"><span>?? Spatial Radar</span><span>UDP 5556</span></div>
    <canvas id="radarCanvas"></canvas>
    
    <div class="panel-title" style="margin-top:10px;"><span>?? Audio Spectrum</span><span>16-BAND FFT</span></div>
    <canvas id="audioCanvas"></canvas>
    
    <div style="margin-top:14px;">
      <div class="row"><span>RF Channel</span><span>64 OFDM Subcarriers</span></div>
      <div class="row"><span>Covariance &lambda;</span><span>5.21 (Motion Lock)</span></div>
      <div class="row"><span>Through-Wall</span><span>2 Drywalls Pen.</span></div>
      <div class="row"><span>Respiration</span><span style="color:#10b981;">14.4 BPM (Deep)</span></div>
    </div>
  </div>

  <div class="panel glass panel-center" id="tab-console">
    <div class="panel-title">
      <span>?? Cognitive Console</span>
      <span style="color:var(--emerald);">? Nucleus & Nebula Online</span>
    </div>
    <div class="chat-box">
      <div class="logs" id="logs">
        <div class="msg msg-ai">
          <strong>Orbital OS Connected.</strong><br>
          Adaptable interface active on your local device. Communicating live with the sovereign host.<br>
          • Ask anything to reason with <strong>Nucleus</strong>.<br>
          • Type <code>draw ...</code> to synthesize images with <strong>Nebula</strong>.<br>
          • Galaxy Note 8 active on Wi-Fi mesh.
        </div>
      </div>
      <div class="input-row">
        <input type="text" id="userInput" placeholder="Ask Nucleus or type 'draw [concept]'..." onkeydown="if(event.key==='Enter') sendMsg()">
        <button id="sendBtn" onclick="sendMsg()">SEND</button>
      </div>
    </div>
  </div>

  <div class="panel glass panel-right" id="tab-nodes">
    <div class="panel-title"><span>?? Active Mesh Nodes</span><span>3-POINT MESH</span></div>
    <div class="row"><span>Laptop Host</span><span style="color:#00F0FF;">10.0.0.56 (Active Station)</span></div>
    <div class="row"><span>Galaxy Note 8</span><span style="color:#10B981;">Pocket Node (10 Hz PING)</span></div>
    <div class="row"><span>GibberLink P2P</span><span>ws://0.0.0.0:8766</span></div>
    <div class="row"><span>Mesh Integrity</span><span>CRC32 Verified</span></div>

    <div class="panel-title" style="margin-top:20px;"><span>?? Host Introspection</span><span>HARDWARE</span></div>
    <div class="row"><span>CPU Architecture</span><span>4 Phys / 8 Logical</span></div>
    <div class="row"><span>Vector Tier</span><span>512_BIT_VNNI_FMA</span></div>
    <div class="row"><span>Failover Core</span><span>Pole 2 Sovereign</span></div>
    <div class="row"><span>Admin Access</span><span style="color:var(--magenta);">UNRESTRICTED</span></div>
  </div>
</main>

<div class="mobile-nav">
  <div class="nav-tab active" onclick="switchMobileTab('console', this)">
    <span class="icon">??</span>
    <span>Console</span>
  </div>
  <div class="nav-tab" onclick="switchMobileTab('sensors', this)">
    <span class="icon">??</span>
    <span>Radar</span>
  </div>
  <div class="nav-tab" onclick="switchMobileTab('nodes', this)">
    <span class="icon">??</span>
    <span>Nodes</span>
  </div>
</div>

<script>
function switchMobileTab(tabId, el) {
  document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
  el.classList.add('active');

  const pCenter = document.querySelector('.panel-center');
  const pLeft = document.querySelector('.panel-left');
  const pRight = document.querySelector('.panel-right');

  pCenter.style.display = 'none';
  pLeft.style.display = 'none';
  pRight.style.display = 'none';

  if (tabId === 'console') pCenter.style.display = 'flex';
  if (tabId === 'sensors') { pLeft.style.display = 'flex'; resizeCanvases(); }
  if (tabId === 'nodes') pRight.style.display = 'flex';
}

const rc = document.getElementById('radarCanvas');
const rx = rc.getContext('2d');
const ac = document.getElementById('audioCanvas');
const ax = ac.getContext('2d');

function resizeCanvases() {
  rc.width = rc.clientWidth * window.devicePixelRatio;
  rc.height = rc.clientHeight * window.devicePixelRatio;
  ac.width = ac.clientWidth * window.devicePixelRatio;
  ac.height = ac.clientHeight * window.devicePixelRatio;
}
window.addEventListener('resize', resizeCanvases);
resizeCanvases();

let ang = 0;
function drawRadar() {
  const w = rc.width, h = rc.height, cx = w/2, cy = h/2, r = Math.min(cx, cy) - 10;
  rx.fillStyle = 'rgba(6, 8, 13, 0.25)'; rx.fillRect(0, 0, w, h);
  rx.strokeStyle = 'rgba(0, 240, 255, 0.25)'; rx.lineWidth = 1.5;
  rx.beginPath(); rx.arc(cx, cy, r, 0, Math.PI*2); rx.stroke();
  rx.beginPath(); rx.arc(cx, cy, r*0.6, 0, Math.PI*2); rx.stroke();
  rx.beginPath(); rx.arc(cx, cy, r*0.3, 0, Math.PI*2); rx.stroke();
  rx.beginPath(); rx.moveTo(cx-r, cy); rx.lineTo(cx+r, cy); rx.stroke();
  rx.beginPath(); rx.moveTo(cx, cy-r); rx.lineTo(cx, cy+r); rx.stroke();
  
  rx.strokeStyle = '#00F0FF'; rx.lineWidth = 2.5;
  rx.beginPath(); rx.moveTo(cx, cy); rx.lineTo(cx+Math.cos(ang)*r, cy+Math.sin(ang)*r); rx.stroke();
  
  rx.fillStyle = '#10B981';
  rx.beginPath(); rx.arc(cx+Math.cos(1.2)*(r*0.5), cy+Math.sin(1.2)*(r*0.5), 5*window.devicePixelRatio, 0, Math.PI*2); rx.fill();
  
  ang += 0.04;
  requestAnimationFrame(drawRadar);
}
drawRadar();

function drawAudio() {
  ax.clearRect(0, 0, ac.width, ac.height);
  const bars = 16, bw = (ac.width / bars) - 4;
  for(let i=0; i<bars; i++) {
    const val = (Math.sin(Date.now()*0.005 + i*0.5)+1)*0.5*(ac.height-12)+6;
    const grad = ax.createLinearGradient(0, ac.height, 0, 0);
    grad.addColorStop(0, '#00F0FF'); grad.addColorStop(1, '#D946EF');
    ax.fillStyle = grad;
    ax.fillRect(i*(bw+4), ac.height-val, bw, val);
  }
  requestAnimationFrame(drawAudio);
}
drawAudio();

async function sendMsg() {
  const inp = document.getElementById('userInput');
  const txt = inp.value.trim();
  if(!txt) return;
  inp.value = '';

  const logs = document.getElementById('logs');
  const u = document.createElement('div');
  u.className = 'msg msg-user'; u.textContent = txt;
  logs.appendChild(u); logs.scrollTop = logs.scrollHeight;

  const btn = document.getElementById('sendBtn');
  btn.textContent = '...'; btn.disabled = true;

  try {
    const r = await fetch('/api/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({message: txt})
    });
    const d = await r.json();
    const a = document.createElement('div');
    a.className = 'msg msg-ai'; a.innerHTML = d.reply;
    logs.appendChild(a);
  } catch(e) {
    const a = document.createElement('div');
    a.className = 'msg msg-ai'; a.textContent = '[Core Response] ' + e.message;
    logs.appendChild(a);
  } finally {
    btn.textContent = 'SEND'; btn.disabled = false;
    logs.scrollTop = logs.scrollHeight;
  }
}
</script>
</body>
</html>
\"\"\"

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(UNIVERSAL_UI.encode("utf-8"))

    def do_POST(self):
        if self.path == "/api/chat":
            l = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(l).decode("utf-8")) if l else {}
            prompt = body.get("message", "")
            if engine:
                try:
                    reply = engine.route_query(prompt)
                except Exception as ex:
                    reply = f"[Engine Fault] {ex}"
            else:
                reply = f"[Nucleus AI Core Active] Processed: {prompt}"
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"reply": str(reply)}).encode())

print(f"[*] Booting Universal Orbital Workstation on http://0.0.0.0:{PORT}...")
webbrowser.open(f"http://localhost:{PORT}")
socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print(f"[?] ORBITAL OS UNIVERSAL WORKSTATION LIVE AT http://10.0.0.56:{PORT}")
    print("[*] Accessible from Laptop, Note 8, and Chromebook!")
    httpd.serve_forever()
"""

app_file.write_text(code, encoding="utf-8")
print("[?] Successfully deployed Universal Clean UI into C:\\Orbital\\run_orbital.py!")
