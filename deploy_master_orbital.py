import os, sys, re

# 1. Update engine.py with smart conversational + execution logic
engine_code = '''import http.server, json, urllib.request, subprocess, os, sys, threading

ENGINE_PORT = 5000
NUCLEUS_PORT = 11434
HIVE_NODES = set()
HIVE_MODE = "STANDALONE_OFFLINE"

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
        "system": "You are Orbital OS, an autonomous cyber-organic workstation operating locally. Answer clearly and concisely. If asked to run a PC task or PowerShell command, prepend your command with RUN_CMD: <powershell cmdlet>."
    }).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            res = json.loads(r.read().decode("utf-8"))
            reply = res.get("response", "").strip()
            if "RUN_CMD:" in reply:
                parts = reply.split("RUN_CMD:")
                text_part = parts[0].strip()
                cmd = parts[1].strip().split("\n")[0].strip()
                cmd_out = run_shell(cmd)
                return f"{text_part}\n\n[Executed: {cmd}]\n{cmd_out}".strip()
            return reply
    except Exception:
        # Fallback if port 11434 is offline
        p = prompt.strip().lower()
        if "capabilit" in p or "who are you" in p:
            return "Orbital OS Cyber-Organic Workstation is online. Active capabilities include local terminal bridging, offline shell control, optical camera feeds, and GibberLink P2P mesh networking."
        return f"Orbital Engine active on local hardware. Received: '{prompt}'. (Start Nucleus on port 11434 for advanced offline LLM reasoning.)"

def process_query(prompt):
    p = prompt.strip()
    if p.startswith("/ps ") or p.startswith("ps: "):
        return run_shell(p.split(" ", 1)[1])
    if p.startswith("/cmd ") or p.startswith("cmd: "):
        return run_shell(p.split(" ", 1)[1])
    if p.lower() in ["/hive status", "hive status"]:
        return f"[Hive Status]: Mode={HIVE_MODE} | Connected Peers={len(HIVE_NODES)} ({list(HIVE_NODES)})"
    if p.startswith("/hive join "):
        peer = p.split(" ", 2)[2].strip()
        HIVE_NODES.add(peer)
        return f"[Hive]: Added peer {peer} to mesh."
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
    http.server.HTTPServer(("0.0.0.0", ENGINE_PORT), Handler).serve_forever()
'''

with open(r"C:\Orbital\engine.py", "w", encoding="utf-8") as f:
    f.write(engine_code)
with open(r"C:\Orbital\core\engine.py", "w", encoding="utf-8") as f:
    f.write(engine_code)

# 2. Inject working Camera overlay into cyber_organic_workstation.html
html_path = r"C:\Orbital\gui\cyber_organic_workstation.html"
with open(html_path, "r", encoding="utf-8") as f:
    c = f.read()

cam_script = """
<script>
async function toggleCamera() {
    let box = document.getElementById("orbital-cam-box");
    if (!box) {
        box = document.createElement("div");
        box.id = "orbital-cam-box";
        box.style.cssText = "position:fixed; bottom:25px; right:25px; width:340px; height:260px; background:#0B0E14; border:2px solid #00E5FF; border-radius:12px; z-index:999999; box-shadow:0 0 25px rgba(0,229,255,0.4); display:flex; flex-direction:column; overflow:hidden;";
        box.innerHTML = `
            <div style="background:rgba(0,229,255,0.2); color:#00E5FF; font-size:12px; font-weight:bold; padding:8px 12px; display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid rgba(0,229,255,0.3);">
                <span>📷 OPTICAL HARDWARE FEED</span>
                <span style="cursor:pointer; font-size:14px;" onclick="document.getElementById('orbital-cam-box').remove()">✕</span>
            </div>
            <video id="orbital-cam-vid" autoplay playsinline style="width:100%; flex:1; object-fit:cover; background:#000;"></video>
        `;
        document.body.appendChild(box);
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
            document.getElementById("orbital-cam-vid").srcObject = stream;
        } catch(err) {
            alert("Camera Error: " + err.message);
            box.remove();
        }
    } else {
        box.remove();
    }
}
</script>
"""

if "toggleCamera()" not in c:
    c = c.replace("</body>", cam_script + "\n</body>")

with open(html_path, "w", encoding="utf-8") as f:
    f.write(c)

print("[✔] Master Engine & UI Camera configured successfully.")
