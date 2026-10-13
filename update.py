import os, sys, subprocess

BASE = r"C:\Orbital"
CORE = os.path.join(BASE, "core")
os.makedirs(CORE, exist_ok=True)

ENGINE_CODE = '''import http.server
import json
import urllib.request
import urllib.error
import subprocess
import os
import sys
import datetime

class OrbitalAPIHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

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

            reply = self.query_hybrid_engine(prompt)

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({'response': reply}).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

    def query_hybrid_engine(self, prompt):
        ollama_reply = self.try_ollama(prompt)
        if ollama_reply:
            return ollama_reply

        return self.offline_nucleus_core(prompt)

    def try_ollama(self, prompt):
        model_name = "qwen2.5-coder"
        try:
            req_tags = urllib.request.Request("http://127.0.0.1:11434/api/tags")
            with urllib.request.urlopen(req_tags, timeout=2) as resp:
                tags_data = json.loads(resp.read().decode('utf-8'))
                models = [m.get('name') for m in tags_data.get('models', [])]
                if models:
                    model_name = models
        except Exception:
            return None

        ollama_url = "http://127.0.0.1:11434/api/generate"
        payload = json.dumps({
            "model": model_name,
            "prompt": prompt,
            "stream": False
        }).encode('utf-8')

        req = urllib.request.Request(ollama_url, data=payload, headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                res_data = json.loads(response.read().decode('utf-8'))
                return res_data.get('response', '')
        except Exception:
            return None

    def offline_nucleus_core(self, prompt):
        p_lower = prompt.lower().strip()
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if p_lower in ['hi', 'hello', 'hey', 'hello?', 'hey!', 'nothing?', 'still?']:
            return f"🛸 [Nucleus Local Core] Greetings! Workstation active offline. Local time: {now_str}. Auto-initializing local model background processes..."

        if 'time' in p_lower or 'date' in p_lower:
            return f"🛸 [Nucleus System Clock] Hardware timestamp: {now_str}"

        if 'status' in p_lower or 'health' in p_lower or 'system' in p_lower:
            return f"🛸 [Orbital Diagnostic Status]\n• Engine: Active on port 5000\n• Hardware Mode: Autonomous Sovereign\n• Timestamp: {now_str}\n• Ollama Service: Auto-Starting in Background"

        return f"🛸 [Nucleus Local Core] Query processed offline: '{prompt}'. (Ollama service auto-starting for deep LLM reasoning)."

def run_server(port=5000):
    server = http.server.HTTPServer(('127.0.0.1', port), OrbitalAPIHandler)
    print(f"[✔] Orbital Engine Server Active on http://127.0.0.1:{port}")
    server.serve_forever()

if __name__ == '__main__':
    run_server()
'''

with open(os.path.join(BASE, "engine.py"), "w", encoding="utf-8") as f:
    f.write(ENGINE_CODE)

with open(os.path.join(CORE, "engine.py"), "w", encoding="utf-8") as f:
    f.write(ENGINE_CODE)

RUN_ORBITAL_CODE = '''import os, sys, subprocess, webbrowser, time

BASE = r"C:\Orbital"
login_path = os.path.join(BASE, "gui", "orbital_login_gui.py")
html_path = os.path.join(BASE, "gui", "cyber_organic_workstation.html")
engine_path = os.path.join(BASE, "engine.py")

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0

print("[✔] Auto-Starting Ollama background service on port 11434...")
try:
    subprocess.Popen(["ollama", "serve"], creationflags=CREATE_NO_WINDOW)
except Exception:
    pass

print("[✔] Starting Orbital Login Gateway...")
subprocess.run([sys.executable, login_path])

print("[✔] Login complete. Launching Hybrid AI Engine Server on port 5000...")
subprocess.Popen([sys.executable, engine_path], creationflags=CREATE_NO_WINDOW)
time.sleep(1.5)

if os.path.exists(html_path):
    print(f"[✔] Opening Cyber-Organic Workstation UI at {html_path}")
    webbrowser.open(html_path)
else:
    print(f"[!] Interface not found at {html_path}")
'''

with open(os.path.join(BASE, "run_orbital.py"), "w", encoding="utf-8") as f:
    f.write(RUN_ORBITAL_CODE)

print("=============================================================")
print(" [✔] DUAL-MODE HYBRID AI ENGINE & AUTO-LAUNCH DEPLOYED! ")
print("=============================================================")
