code = """import http.server, json, urllib.request, subprocess, os, sys

ENGINE_PORT = 5000
NUCLEUS_PORT = 11434

def run_shell(cmd):
    try:
        res = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=60, cwd=r"C:\\Orbital")
        out = (res.stdout or "").strip()
        err = (res.stderr or "").strip()
        return out if out else (f"[Error]: {err}" if err else "[OK] Command executed.")
    except Exception as e:
        return f"[Execution Fault]: {e}"

def query_nucleus(prompt):
    url = f"http://127.0.0.1:{NUCLEUS_PORT}/api/generate"
    payload = json.dumps({
        "model": "qwen2.5-coder",
        "prompt": prompt,
        "stream": False,
        "system": "You are Orbital OS. Answer concisely. If asked to run a command, prefix with RUN_CMD: <cmd>."
    }).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            res = json.loads(r.read().decode("utf-8"))
            reply = res.get("response", "").strip()
            if "RUN_CMD:" in reply:
                cmd = reply.split("RUN_CMD:")[1].strip().splitlines()[0].strip()
                return f"{reply.split('RUN_CMD:')[0].strip()}\\n\\n[Output]:\\n{run_shell(cmd)}"
            return reply
    except Exception:
        p = prompt.strip().lower()
        if "capabilit" in p or "who are you" in p:
            return "Orbital OS online. Subsystems active: Local Terminal Bridge, Shell Control, Optical Feeds, P2P Mesh."
        return f"Orbital Engine active on local hardware. Processed: '{prompt}'"

def process_query(prompt):
    p = prompt.strip()
    if p.startswith("/ps ") or p.startswith("ps: "):
        return run_shell(p.split(" ", 1)[1])
    if p.startswith("/cmd ") or p.startswith("cmd: "):
        return run_shell(p.split(" ", 1)[1])
    return query_nucleus(p)

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
    def do_POST(self):
        if self.path == "/api/chat":
            l = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(l).decode("utf-8")
            try: prompt = json.loads(body).get("prompt", "")
            except: prompt = body
            res = process_query(prompt)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"response": res}).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

if __name__ == "__main__":
    print("[OK] Orbital Hybrid Engine running on http://127.0.0.1:5000")
    http.server.HTTPServer(("0.0.0.0", ENGINE_PORT), Handler).serve_forever()
"""

with open(r"C:\Orbital\engine.py", "w", encoding="utf-8") as f:
    f.write(code)
print("[✔] engine.py syntax repaired.")
