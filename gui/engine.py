import os
import json
from http.server import HTTPServer, BaseHTTPRequestHandler

class NucleusHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/tags":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"models": [{"name": "qwen2.5-coder:1.5b"}]}).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/api/chat":
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            req = json.loads(body.decode("utf-8"))
            msgs = req.get("messages", [])
            last_msg = msgs[-1]["content"] if msgs else ""

            reply = f"Orbital Nucleus AI Engine Active.\nReceived: '{last_msg}'\nProcessing system context..."

            resp = {"message": {"role": "assistant", "content": reply}}
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(resp).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

def run_server():
    server = HTTPServer(("127.0.0.1", 11434), NucleusHandler)
    print("Nucleus Local AI Server active on http://127.0.0.1:11434")
    server.serve_forever()

if __name__ == "__main__":
    run_server()
