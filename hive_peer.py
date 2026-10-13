import http.server, json, urllib.request

PORT = 5000
HIVE_LOG = []
PEERS = ["http://10.0.0.129:5000", "http://192.168.1.105:5000"]

def broadcast_to_peers(entry):
    for peer in PEERS:
        if "127.0.0.1" in peer: continue
        try:
            data = json.dumps(entry).encode("utf-8")
            req = urllib.request.Request(f"{peer}/api/peer_sync", data=data, headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=1)
        except: pass

class PeerHandler(http.server.BaseHTTPRequestHandler):
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
    def do_POST(self):
        l = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(l).decode("utf-8")
        data = json.loads(body)
        if self.path == "/api/peer_sync":
            if data not in HIVE_LOG: HIVE_LOG.append(data)
            self.send_response(200); self.end_headers()
        elif self.path == "/api/chat":
            prompt = data.get("prompt", "")
            user_entry = {"sender": "user", "text": prompt}
            if user_entry not in HIVE_LOG: 
                HIVE_LOG.append(user_entry)
                broadcast_to_peers(user_entry)
            ai_entry = {"sender": "ai", "text": f"Synced Hive Node Processed: {prompt}"}
            HIVE_LOG.append(ai_entry)
            broadcast_to_peers(ai_entry)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"response": ai_entry["text"]}).encode("utf-8"))

if __name__ == "__main__":
    print(f"[✔] P2P Hive Node active on port {PORT}")
    http.server.HTTPServer(("0.0.0.0", PORT), PeerHandler).serve_forever()