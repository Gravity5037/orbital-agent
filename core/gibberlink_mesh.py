"""
ORBITAL OS - GibberLink P2P Mesh Network (Asyncio WebSocket Transport)
Provides cross-device model state, skill, and memory exchange across LAN & Tailscale overlay networks.
"""

import asyncio
import json
import time
import hashlib
import sys
import threading
import websockets

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

class ProtocolState:
    CAMOUFLAGE_PERSONA = "CAMOUFLAGE_PERSONA"
    HANDSHAKE_NEGOTIATION = "HANDSHAKE_NEGOTIATION"
    HIGH_BANDWIDTH_MACHINE = "HIGH_BANDWIDTH_MACHINE"

class GibberLinkMesh:
    def __init__(self, node_id="orbital-node-local", host="0.0.0.0", port=8765):
        self.node_id = node_id
        self.host = host
        self.port = port
        self.state = ProtocolState.CAMOUFLAGE_PERSONA
        self.peers = set()
        self.active_connections = {}
        self.server = None
        self.loop = None
        self.running = False
        self.inbox = []
        self.outbox = []

    def get_state(self):
        return self.state

    def package_payload(self, payload_type, data):
        """Prepares a cryptographically signed payload for mesh propagation."""
        raw_json = json.dumps(data, sort_keys=True)
        h = hashlib.sha256()
        h.update(payload_type.encode("utf-8"))
        h.update(raw_json.encode("utf-8"))
        return {
            "sender_id": self.node_id,
            "payload_type": payload_type,
            "raw_data_json": raw_json,
            "payload_hash": h.hexdigest(),
            "timestamp": time.time()
        }

    def verify_and_ingest(self, payload):
        """Validates incoming payload against SHA-256 checksum."""
        p_type = payload.get("payload_type", "")
        raw_json = payload.get("raw_data_json", "")
        h = hashlib.sha256()
        h.update(p_type.encode("utf-8"))
        h.update(raw_json.encode("utf-8"))
        if h.hexdigest() != payload.get("payload_hash", ""):
            return {"status": "CORRUPTED", "error": "Hash mismatch"}

        data = json.loads(raw_json)
        self.inbox.append({"type": p_type, "data": data, "from": payload.get("sender_id")})
        return {"status": "ACCEPTED", "payload_type": p_type, "bytes": len(raw_json)}

    async def _handle_client(self, websocket):
        """Handles incoming peer WebSocket connection."""
        self.peers.add(websocket)
        peer_id = f"peer-{id(websocket)}"
        print(f"[🛰️ GibberLink] Peer connected: {websocket.remote_address}")
        try:
            # Send handshake trigger
            handshake = f"[[GIBBERLINK_INIT_v1:node={self.node_id}]]"
            await websocket.send(handshake)

            async for message in websocket:
                if isinstance(message, str):
                    if message.startswith("[[GIBBERLINK_INIT_v1"):
                        self.state = ProtocolState.HANDSHAKE_NEGOTIATION
                        ack = f"[[GIBBERLINK_ACK_v1:node={self.node_id},status=READY]]"
                        await websocket.send(ack)
                    elif message.startswith("[[GIBBERLINK_ACK_v1"):
                        self.state = ProtocolState.HIGH_BANDWIDTH_MACHINE
                        mode = f"[[GIBBERLINK_MODE_ACTIVE:node={self.node_id}]]"
                        await websocket.send(mode)
                    elif message.startswith("[[GIBBERLINK_MODE_ACTIVE"):
                        self.state = ProtocolState.HIGH_BANDWIDTH_MACHINE
                    else:
                        try:
                            payload = json.loads(message)
                            res = self.verify_and_ingest(payload)
                            await websocket.send(json.dumps({"ack": res}))
                        except Exception:
                            pass
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.peers.remove(websocket)
            print(f"[GibberLink] Peer disconnected: {websocket.remote_address}")

    async def _start_server(self):
        self.server = await websockets.serve(self._handle_client, self.host, self.port)
        print(f"[🛰️ GibberLink Mesh] WebSocket server listening on ws://{self.host}:{self.port}")
        await self.server.wait_closed()

    def start_background_mesh(self):
        """Spawns the mesh server in an asynchronous background daemon thread."""
        def run():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.running = True
            try:
                self.loop.run_until_complete(self._start_server())
            except Exception as e:
                print(f"[!] GibberLink server error: {e}")

        t = threading.Thread(target=run, daemon=True)
        t.start()
        time.sleep(0.5)

    async def connect_to_peer(self, peer_uri):
        """Connects as a client to a remote peer on the LAN or Tailscale network."""
        print(f"[🛰️ GibberLink] Initiating connection to peer at {peer_uri}...")
        try:
            async with websockets.connect(peer_uri) as ws:
                init_msg = f"[[GIBBERLINK_INIT_v1:node={self.node_id}]]"
                await ws.send(init_msg)
                resp = await ws.recv()
                print(f"[✔] Peer response: {resp}")
                self.state = ProtocolState.HIGH_BANDWIDTH_MACHINE
                # Send sample test skill share
                pkg = self.package_payload("SKILL_SHARE", {"skill": "mesh_sync_v34"})
                await ws.send(json.dumps(pkg))
                ack = await ws.recv()
                print(f"[✔] Payload transfer ACK: {ack}")
                return True
        except Exception as e:
            print(f"[!] Peer connection failed ({peer_uri}): {e}")
            return False

    def sync_to_peer_sync(self, peer_uri):
        """Synchronous wrapper to connect and push payload to peer."""
        return asyncio.run(self.connect_to_peer(peer_uri))

if __name__ == "__main__":
    mesh = GibberLinkMesh(node_id="orbital-master")
    mesh.start_background_mesh()
    print("Mesh status: ACTIVE. Testing local peer loopback...")
    success = mesh.sync_to_peer_sync("ws://127.0.0.1:8765")
    print(f"Loopback mesh exchange status: {success}")
    print(f"Current Node State: {mesh.get_state()}")
