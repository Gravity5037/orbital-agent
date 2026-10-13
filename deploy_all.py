import os

# 1. Update engine.py
engine_code = """import http.server, json, subprocess, os, sys

class APIHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    def do_POST(self):
        if self.path == '/api/chat':
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length).decode('utf-8')
            try: prompt = json.loads(body).get('prompt', '')
            except: prompt = body
            p = prompt.strip()
            if p.startswith('/ps '):
                try:
                    res = subprocess.run(["powershell", "-NoProfile", "-Command", p[4:]], capture_output=True, text=True, timeout=30)
                    out = (res.stdout or '').strip() or (res.stderr or '').strip() or '[Done]'
                except Exception as e:
                    out = f'[Error]: {e}'
                reply = out
            else:
                reply = f"Orbital OS online. Received: '{prompt}'"
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({'response': reply}).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

if __name__ == '__main__':
    http.server.HTTPServer(('127.0.0.1', 5000), APIHandler).serve_forever()
"""

with open(r"C:\Orbital\engine.py", "w", encoding="utf-8") as f:
    f.write(engine_code)
with open(r"C:\Orbital\core\engine.py", "w", encoding="utf-8") as f:
    f.write(engine_code)

# 2. Update cyber_organic_workstation.html with clean UTF-8 and draggable camera
html_path = r"C:\Orbital\gui\cyber_organic_workstation.html"
with open(html_path, "r", encoding="utf-8", errors="ignore") as f:
    html = f.read()

# Fix navigation items
html = html.replace('<div class="nav-item">📷 Camera Feed (Optical)</div>', '<div class="nav-item" onclick="toggleCamera()">📷 Camera Feed (Optical)</div>')
html = html.replace('<div class="nav-item">🎨 Nebula Image Generator</div>', '<div class="nav-item" onclick="alert(\'Nebula Engine: Ready for /draw\')">🎨 Nebula Image Generator</div>')
html = html.replace('<div class="nav-item">📡 Wi-Fi CSI Radar</div>', '<div class="nav-item" onclick="alert(\'Wi-Fi CSI: Listening on UDP 5555\')">📡 Wi-Fi CSI Radar</div>')
html = html.replace('<div class="nav-item">⚙️ System Settings</div>', '<div class="nav-item" onclick="alert(\'Orbital Settings: Engine 5000 active\')">⚙️ System Settings</div>')

# Draggable camera script
cam_script = """
<script>
async function toggleCamera() {
    let box = document.getElementById("orbital-cam-box");
    if (box) {
        if (box._stream) {
            box._stream.getTracks().forEach(t => t.stop());
        }
        box.remove();
        return;
    }
    box = document.createElement("div");
    box.id = "orbital-cam-box";
    box.style.cssText = "position:fixed; bottom:25px; right:25px; width:340px; height:260px; min-width:200px; min-height:160px; background:#0B0E14; border:2px solid #00E5FF; border-radius:12px; z-index:999999; box-shadow:0 0 25px rgba(0,229,255,0.4); display:flex; flex-direction:column; overflow:hidden; resize:both;";
    box.innerHTML = `
        <div id="orbital-cam-header" style="background:rgba(0,229,255,0.25); color:#00E5FF; font-size:12px; font-weight:bold; padding:8px 12px; display:flex; justify-content:space-between; align-items:center; cursor:move; user-select:none; border-bottom:1px solid rgba(0,229,255,0.3);">
            <span>📷 OPTICAL FEED (DRAG HERE)</span>
            <span style="cursor:pointer; font-size:16px; font-weight:bold; padding:0 4px;" onclick="toggleCamera()">✕</span>
        </div>
        <video id="orbital-cam-vid" autoplay playsinline style="width:100%; flex:1; object-fit:cover; background:#000; pointer-events:none;"></video>
    `;
    document.body.appendChild(box);

    const header = document.getElementById("orbital-cam-header");
    let isDragging = false, startX, startY, initX, initY;
    header.onmousedown = (e) => {
        isDragging = true;
        startX = e.clientX;
        startY = e.clientY;
        const rect = box.getBoundingClientRect();
        initX = rect.left;
        initY = rect.top;
        box.style.right = "auto";
        box.style.bottom = "auto";
        box.style.left = initX + "px";
        box.style.top = initY + "px";
        document.onmousemove = (ev) => {
            if (!isDragging) return;
            box.style.left = (initX + (ev.clientX - startX)) + "px";
            box.style.top = (initY + (ev.clientY - startY)) + "px";
        };
        document.onmouseup = () => {
            isDragging = false;
            document.onmousemove = null;
            document.onmouseup = null;
        };
    };

    try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
        box._stream = stream;
        document.getElementById("orbital-cam-vid").srcObject = stream;
    } catch(err) {
        alert("Camera Error: " + err.message);
        box.remove();
    }
}
</script>
"""

if "function toggleCamera()" not in html:
    html = html.replace("</body>", cam_script + "\n</body>")

with open(html_path, "w", encoding="utf-8-sig") as f:
    f.write(html)

print("[✔] Backend and UI configured.")
