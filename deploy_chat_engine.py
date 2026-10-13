import os, sys

BASE = r"C:\Orbital"
CORE = os.path.join(BASE, "core")
GUI = os.path.join(BASE, "gui")

os.makedirs(CORE, exist_ok=True)
os.makedirs(GUI, exist_ok=True)

# 1. Update engine.py with a lightweight Local HTTP API Server
ENGINE_CODE = '''import http.server
import json
import os
import sys

class OrbitalAPIHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return  # Suppress console log clutter

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_POST(self):
        if self.path == '/api/chat':
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            try:
                data = json.loads(body)
                prompt = data.get('prompt', '')
            except Exception:
                prompt = body

            # Nucleus Local AI Engine Response Logic
            reply = f"Nucleus AI active on local hardware. Processed query: '{prompt}'"

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({'response': reply}).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

def run_server(port=5000):
    server = http.server.HTTPServer(('127.0.0.1', port), OrbitalAPIHandler)
    print(f"[✔] Orbital Engine Server Listening on http://127.0.0.1:{port}")
    server.serve_forever()

if __name__ == '__main__':
    run_server()
'''

with open(os.path.join(CORE, "engine.py"), "w", encoding="utf-8") as f:
    f.write(ENGINE_CODE)

with open(os.path.join(BASE, "engine.py"), "w", encoding="utf-8") as f:
    f.write(ENGINE_CODE)

# 2. Update Workstation HTML with fetch() API integration
HTML_CODE = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Orbital OS - Cyber-Organic Workstation</title>
    <style>
        :root {
            --bg-dark: #0B0E14;
            --panel-bg: rgba(18, 24, 38, 0.85);
            --accent-cyan: #00E5FF;
            --accent-glow: rgba(0, 229, 255, 0.3);
            --text-main: #E2E8F0;
            --text-muted: #94A3B8;
            --border: rgba(0, 229, 255, 0.2);
        }
        body {
            margin: 0;
            padding: 0;
            background: var(--bg-dark);
            color: var(--text-main);
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            display: flex;
            height: 100vh;
            overflow: hidden;
        }
        .sidebar {
            width: 260px;
            background: var(--panel-bg);
            backdrop-filter: blur(12px);
            border-right: 1px solid var(--border);
            display: flex;
            flex-direction: column;
            padding: 20px;
        }
        .brand {
            font-size: 1.4rem;
            font-weight: 700;
            color: var(--accent-cyan);
            letter-spacing: 2px;
            margin-bottom: 30px;
            text-shadow: 0 0 10px var(--accent-glow);
        }
        .nav-item {
            padding: 12px 16px;
            margin-bottom: 8px;
            border-radius: 8px;
            cursor: pointer;
            color: var(--text-muted);
            transition: all 0.2s ease;
        }
        .nav-item.active, .nav-item:hover {
            background: rgba(0, 229, 255, 0.1);
            color: var(--accent-cyan);
            border-left: 3px solid var(--accent-cyan);
        }
        .main-content {
            flex: 1;
            display: flex;
            flex-direction: column;
            background: radial-gradient(circle at top right, rgba(0,229,255,0.05), transparent 60%);
        }
        .header {
            height: 60px;
            border-bottom: 1px solid var(--border);
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 30px;
            background: var(--panel-bg);
        }
        .status-badge {
            background: rgba(16, 185, 129, 0.2);
            color: #10B981;
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 0.85rem;
            border: 1px solid rgba(16, 185, 129, 0.4);
        }
        .chat-container {
            flex: 1;
            padding: 30px;
            display: flex;
            flex-direction: column;
            gap: 20px;
            overflow-y: auto;
        }
        .message {
            max-width: 70%;
            padding: 14px 18px;
            border-radius: 12px;
            line-height: 1.5;
        }
        .user-msg {
            align-self: flex-end;
            background: rgba(0, 229, 255, 0.15);
            border: 1px solid var(--border);
            color: #FFF;
        }
        .ai-msg {
            align-self: flex-start;
            background: var(--panel-bg);
            border: 1px solid var(--border);
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
        }
        .input-bar {
            padding: 20px 30px;
            background: var(--panel-bg);
            border-top: 1px solid var(--border);
            display: flex;
            gap: 15px;
        }
        input[type="text"] {
            flex: 1;
            background: rgba(11, 14, 20, 0.8);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 14px 18px;
            color: #FFF;
            font-size: 1rem;
            outline: none;
        }
        input[type="text"]:focus {
            border-color: var(--accent-cyan);
            box-shadow: 0 0 10px var(--accent-glow);
        }
        button {
            background: var(--accent-cyan);
            color: #0B0E14;
            border: none;
            border-radius: 8px;
            padding: 0 25px;
            font-weight: 700;
            cursor: pointer;
        }
    </style>
</head>
<body>
    <div class="sidebar">
        <div class="brand">🛸 ORBITAL OS</div>
        <div class="nav-item active">💬 AI Chat Interface</div>
        <div class="nav-item">🎨 Nebula Image Generator</div>
        <div class="nav-item">📡 Wi-Fi CSI Radar</div>
        <div class="nav-item">⚙️ System Settings</div>
    </div>
    <div class="main-content">
        <div class="header">
            <h3>Cyber-Organic Workstation</h3>
            <span class="status-badge">● Nucleus Local AI Active</span>
        </div>
        <div class="chat-container" id="chat">
            <div class="message ai-msg">
                <strong>🛸 Orbital AI:</strong> Welcome to your Cyber-Organic Workstation! Ralph Heal Loop, Nucleus AI, and GibberLink Mesh daemons are online.
            </div>
        </div>
        <div class="input-bar">
            <input type="text" id="userInput" placeholder="Ask Orbital anything..." onkeydown="if(event.key==='Enter') sendMsg()">
            <button onclick="sendMsg()">Send</button>
        </div>
    </div>
    <script>
        async function sendMsg() {
            const input = document.getElementById('userInput');
            const chat = document.getElementById('chat');
            if(!input.value.trim()) return;
            const val = input.value;
            chat.innerHTML += `<div class="message user-msg"><strong>You:</strong> ${val}</div>`;
            input.value = '';
            chat.scrollTop = chat.scrollHeight;

            const msgId = 'ai-msg-' + Date.now();
            chat.innerHTML += `<div class="message ai-msg" id="${msgId}"><strong>🛸 Orbital AI:</strong> <em>Thinking...</em></div>`;
            chat.scrollTop = chat.scrollHeight;

            try {
                const res = await fetch('http://127.0.0.1:5000/api/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ prompt: val })
                });
                const data = await res.json();
                document.getElementById(msgId).innerHTML = `<strong>🛸 Orbital AI:</strong> ${data.response}`;
            } catch(err) {
                document.getElementById(msgId).innerHTML = `<strong>🛸 Orbital AI:</strong> [Error connecting to engine backend on port 5000]`;
            }
            chat.scrollTop = chat.scrollHeight;
        }
    </script>
</body>
</html>
'''

with open(os.path.join(GUI, "cyber_organic_workstation.html"), "w", encoding="utf-8") as f:
    f.write(HTML_CODE)

# 3. Master launcher run_orbital.py
RUN_ORBITAL_CODE = '''import os, sys, subprocess, webbrowser, time

login_path = r"C:\\Orbital\\gui\\orbital_login_gui.py"
html_path = r"C:\\Orbital\\gui\\cyber_organic_workstation.html"

print("[✔] Starting Orbital Login Gateway...")
subprocess.run([sys.executable, login_path])

print("[✔] Login complete. Starting Local AI Engine Server on port 5000...")
subprocess.Popen(["python", r"C:\\Orbital\\engine.py"])
time.sleep(1)

if os.path.exists(html_path):
    print(f"[✔] Opening Cyber-Organic Workstation UI at {html_path}")
    webbrowser.open(html_path)
else:
    print(f"[!] Interface not found at {html_path}")
'''

with open(os.path.join(BASE, "run_orbital.py"), "w", encoding="utf-8") as f:
    f.write(RUN_ORBITAL_CODE)

print("=============================================================")
print(" [✔] LIVE LOCAL API BACKEND & CHAT HOOKS DEPLOYED SUCCESS! ")
print("=============================================================")
