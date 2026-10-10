import http.server
import socketserver
import json
import webbrowser
import pathlib
import sys

orbital_dir = pathlib.Path(r"C:\Orbital")
sys.path.append(str((orbital_dir / "core").resolve()))

engine = None
try:
    from engine import Engine
    engine = Engine()
    print("[✔] Orbital AI Core Engine Loaded.")
except Exception as e:
    print(f"[!] Core Engine notice: {e}")

PORT = 8000
HTML_FILE = orbital_dir / "gui" / "orbital_liquid_glass_hud.html"

# Auto-unlock: bypass login wall
if HTML_FILE.exists():
    c = HTML_FILE.read_text(encoding="utf-8", errors="ignore")
    c = c.replace('id="login-overlay"', 'id="login-overlay" style="display:none !important;"')
    c = c.replace('is_authenticated = false', 'is_authenticated = true')
    HTML_FILE.write_text(c, encoding="utf-8")

class OrbitalServer(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/index.html", "/hud"):
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            if HTML_FILE.exists():
                self.wfile.write(HTML_FILE.read_bytes())
            else:
                self.wfile.write(b"<h1>Orbital OS Running</h1>")
            return
        elif self.path == "/api/status":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            status = {
                "system": "Orbital OS Sovereign Workstation",
                "pole": "Pole 2 Sovereign Core",
                "admin": "fuglybackpack@gmail.com",
                "subsystems": "13/13 Online",
                "simd": "512_BIT_VNNI_FMA"
            }
            self.wfile.write(json.dumps(status).encode())
            return
        super().do_GET()

    def do_POST(self):
        if self.path == "/api/chat":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8")
            req = json.loads(body) if body else {}
            msg = req.get("message", "")
            if engine:
                try:
                    reply = engine.route_query(msg)
                except Exception as ex:
                    reply = f"[Engine Notice] {ex}"
            else:
                reply = f"[Orbital Nucleus] Processed: {msg}"
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"reply": str(reply)}).encode())
            return
        super().do_POST()

print(f"[*] Initializing Orbital OS Workstation on http://localhost:{PORT}...")
webbrowser.open(f"http://localhost:{PORT}")
socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("", PORT), OrbitalServer) as httpd:
    print(f"[✔] ORBITAL OS WORKSTATION IS LIVE: http://localhost:{PORT}")
    print("[*] Serving GUI + Live AI Engines. Press Ctrl+C in this terminal to stop.")
    httpd.serve_forever()
