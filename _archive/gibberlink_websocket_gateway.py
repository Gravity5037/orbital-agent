import asyncio, json, socket, time, hashlib
from http.server import HTTPServer, BaseHTTPRequestHandler
from orbitalchat import EmbeddedGibberLinkEngine

class GibberLinkGatewayHandler(BaseHTTPRequestHandler):
    engine = EmbeddedGibberLinkEngine("gemini-auto-bridge")
    def _set_headers(self, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
    def do_GET(self):
        self._set_headers(200)
        self.wfile.write(json.dumps({"status": "ACTIVE", "state": self.engine.get_state()}).encode())
    def do_POST(self):
        data = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode()
        reply = self.engine.process_peer_message(data)
        self._set_headers(200)
        self.wfile.write(json.dumps({"reply": reply or self.engine.get_state()}).encode())

def run_gateway():
    print("ORBITAL GIBBERLINK AUTOMATIC GATEWAY ACTIVE [127.0.0.1:8888]")
    HTTPServer(("127.0.0.1", 8888), GibberLinkGatewayHandler).serve_forever()
if __name__ == "__main__": run_gateway()
