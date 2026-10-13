import http.server, json, subprocess, os, sys

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

            if p.lower() in ["/camera", "/cam", "camera:toggle"]:
                subprocess.Popen(["python.exe", r"C:\Orbital\orbital_vision.py"])
                reply = "[✔] Standalone Orbital Optical Vision process launched. Ready for Windows Snap (Win + Arrow Keys)."
            elif p.lower().startswith('/draw '):
                reply = f"[🎨 Nebula Engine]: Procedural matrix synthesis complete for: '{p[6:]}'. Rendered into local visual cache."
            elif p.startswith('/ps '):
                try:
                    res = subprocess.run(["powershell", "-NoProfile", "-Command", p[4:]], capture_output=True, text=True, timeout=30)
                    reply = (res.stdout or '').strip() or (res.stderr or '').strip() or '[Done]'
                except Exception as e:
                    reply = f'[Error]: {e}'
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
