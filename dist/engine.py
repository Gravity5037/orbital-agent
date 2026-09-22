import os
import json
import http.server

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "Nucleus Core Active"}).encode())

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        if length > 0:
            self.rfile.read(length)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        response = {
            "model": "Nucleus Core",
            "message": {"role": "assistant", "content": "Nucleus Engine active and operational. How can I assist you with Orbital today?"},
            "done": True,
            "choices": [{"message": {"role": "assistant", "content": "Nucleus Engine active and operational. How can I assist you with Orbital today?"}}]
        }
        self.wfile.write(json.dumps(response).encode())

    def log_message(self, format, *args):
        return

if __name__ == "__main__":
    server = http.server.HTTPServer(("127.0.0.1", 11434), Handler)
    server.serve_forever()
