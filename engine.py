import http.server, json, urllib.request, subprocess

ENGINE_PORT = 5000
HIVE_LOG = []

def run_shell(cmd):
    try:
        res = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=60, cwd="C:/Orbital")
        out = (res.stdout or "").strip()
        err = (res.stderr or "").strip()
        return out if out else (f"[Error]: {err}" if err else "[OK] Command executed.")
    except Exception as e:
        return f"[Execution Fault]: {e}"

def process_query(prompt):
    p = prompt.strip()
    if p.startswith("/ps ") or p.startswith("ps: "):
        return run_shell(p.split(" ", 1)[1])
    if p.startswith("/cmd ") or p.startswith("cmd: "):
        return run_shell(p.split(" ", 1)[1])
    return f"Orbital Engine active. Processed: '{prompt}'"

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
    def do_GET(self):
        if self.path == "/api/sync":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"log": HIVE_LOG}).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()
    def do_POST(self):
        if self.path == "/api/chat":
            l = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(l).decode("utf-8")
            try: prompt = json.loads(body).get("prompt", "")
            except: prompt = body
            
            HIVE_LOG.append({"sender": "user", "text": prompt})
            res = process_query(prompt)
            HIVE_LOG.append({"sender": "ai", "text": res})
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"response": res}).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

if __name__ == "__main__":
    print("[OK] Real-Time Hive Engine running on port 5000")
    http.server.HTTPServer(("0.0.0.0", ENGINE_PORT), Handler).serve_forever()
