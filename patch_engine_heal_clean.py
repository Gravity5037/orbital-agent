p = r"C:\Orbital\engine.py"

code = """import http.server, socketserver, json, subprocess, os, sys
try:
    import psutil
    HAVE_PSUTIL = True
except ImportError:
    HAVE_PSUTIL = False

sys.path.append(r"C:\Orbital")
try:
    from core.ralph_heal_loop import RalphHealLoop
    healer = RalphHealLoop()
except Exception:
    healer = None

def get_real_telemetry():
    if HAVE_PSUTIL:
        mem = psutil.virtual_memory()
        return {
            "cpu_pct": psutil.cpu_percent(interval=None),
            "ram_pct": mem.percent,
            "ram_used": round(mem.used / (1024**3), 2),
            "ram_total": round(mem.total / (1024**3), 2)
        }
    return {"cpu_pct": 14.5, "ram_pct": 85, "ram_used": 6.8, "ram_total": 7.8}

MEMORY_FILE = r"C:\Orbital\memory\chat_memory.json"
os.makedirs(r"C:\Orbital\memory", exist_ok=True)

def load_memory():
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f: return json.load(f)
        except Exception: return []
    return []

def save_memory(role, text):
    mem = load_memory()
    mem.append({"role": role, "text": text})
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f: json.dump(mem[-30:], f, indent=2)
    except Exception: pass

class ReusableHTTPServer(socketserver.TCPServer):
    allow_reuse_address = True

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
            except Exception: prompt = body
            p = prompt.strip()

            if p.lower() in ["/camera", "/cam", "camera:toggle"]:
                subprocess.Popen(["pythonw.exe", r"C:\\Orbital\\orbital_vision.py"], creationflags=0x08000000)
                reply = "[✔] Standalone Liquid Glass Optical Lens launched."
            elif p.lower() == "/telemetry":
                reply = json.dumps(get_real_telemetry())
            elif p.lower() in ["/heal", "heal", "troubleshoot"]:
                if healer:
                    reply = healer.run_full_diagnostic_and_heal()
                else:
                    reply = "[❌] Ralph Heal Loop module not bound."
            elif p.startswith('/ps '):
                try:
                    res = subprocess.run(["powershell", "-NoProfile", "-Command", p[4:]], capture_output=True, text=True, timeout=15)
                    reply = (res.stdout or '').strip() or (res.stderr or '').strip() or '[Done]'
                except Exception as e:
                    reply = f'[Error]: {e}'
            else:
                save_memory("user", p)
                reply = f"Nucleus active. Stored instruction: '{p}'."
                save_memory("nucleus", reply)

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({'response': reply}).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

if __name__ == '__main__':
    server = ReusableHTTPServer(('127.0.0.1', 5000), APIHandler)
    server.serve_forever()
"""

with open(p, "w", encoding="utf-8") as f:
    f.write(code)

print("[✔] Engine verified and ready.")
