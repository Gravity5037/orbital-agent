"""GibberLink — the peer mesh.

This is the module that never existed. It is a real WebSocket server plus a
dialer for configured peers, with:

  * a JSON envelope: {"v":1,"type":...,"from":...,"ts":...,"payload":...}
  * optional shared-secret handshake (ORBITAL_MESH_SECRET)
  * heartbeat + exponential-backoff reconnect
  * bounded in-memory peer registry

Deliberately minimal: it moves messages between nodes and keeps connections
alive. Routing, consensus and scheduling are not solved here and are not
pretended to be.
"""

import asyncio
import json
import time

from . import config, logutil

try:
    import websockets
except ImportError:  # pragma: no cover
    websockets = None

log = logutil.get_logger("mesh")

PROTOCOL_VERSION = 1
HEARTBEAT_INTERVAL = 15
BACKOFF_MIN = 1.0
BACKOFF_MAX = 30.0


class Mesh:
    def __init__(self, node_id=None, secret=None):
        self.node_id = node_id or config.node_id()
        self.secret = secret if secret is not None else __import__("os").environ.get(
            "ORBITAL_MESH_SECRET", ""
        )
        self.peers = {}  # peer_id -> websocket
        self._server = None
        self._tasks = []
        self._running = False

    # ------------------------------------------------------------ envelope
    def envelope(self, mtype, payload):
        return {
            "v": PROTOCOL_VERSION,
            "type": mtype,
            "from": self.node_id,
            "ts": time.time(),
            "payload": payload,
        }

    async def _send(self, ws, mtype, payload):
        try:
            await ws.send(json.dumps(self.envelope(mtype, payload)))
            return True
        except Exception as exc:
            log.warn(f"send failed ({mtype}): {exc}")
            return False

    def broadcast(self, mtype, payload):
        """Fire-and-forget broadcast from sync code."""
        if not self._running:
            return 0
        sent = 0
        for ws in list(self.peers.values()):
            try:
                asyncio.run_coroutine_threadsafe(self._send(ws, mtype, payload), self._loop)
                sent += 1
            except Exception:
                continue
        return sent

    # ------------------------------------------------------------ server
    async def _handler(self, ws):
        path = getattr(getattr(ws, "request", None), "path", "") or ""
        peer_id = None
        try:
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    await self._send(ws, "error", {"error": "malformed JSON"})
                    continue

                if msg.get("v") != PROTOCOL_VERSION:
                    await self._send(ws, "error", {"error": "version mismatch"})
                    await ws.close()
                    return

                mtype = msg.get("type")
                if mtype == "hello":
                    if self.secret and msg.get("payload", {}).get("secret") != self.secret:
                        log.warn(f"rejected {ws.remote_address}: bad secret")
                        await self._send(ws, "error", {"error": "unauthorized"})
                        await ws.close()
                        return
                    peer_id = msg.get("from") or str(ws.remote_address)
                    self.peers[peer_id] = ws
                    log.info(f"peer joined: {peer_id} ({ws.remote_address})")
                    await self._send(
                        ws,
                        "welcome",
                        {"node": self.node_id, "peers": list(self.peers)},
                    )
                elif mtype == "ping":
                    await self._send(ws, "pong", {"t": msg.get("ts")})
                elif mtype == "pong":
                    pass
                else:
                    log.info(f"{peer_id or 'anon'} -> {mtype}")
        except Exception as exc:
            log.warn(f"peer connection error: {exc}")
        finally:
            if peer_id and self.peers.get(peer_id) is ws:
                del self.peers[peer_id]
                log.info(f"peer left: {peer_id}")

    # ------------------------------------------------------------- dialer
    async def _dial_forever(self, url):
        backoff = BACKOFF_MIN
        while self._running:
            try:
                async with websockets.connect(url, open_timeout=5) as ws:
                    await self._send(ws, "hello", {"secret": self.secret, "node": self.node_id})
                    raw = await asyncio.wait_for(ws.recv(), timeout=5)
                    reply = json.loads(raw)
                    if reply.get("type") == "error":
                        log.warn(f"{url} rejected us: {reply.get('payload')}")
                        await asyncio.sleep(BACKOFF_MAX)
                        continue
                    log.info(f"connected to peer at {url}")
                    backoff = BACKOFF_MIN
                    while self._running:
                        await asyncio.sleep(HEARTBEAT_INTERVAL)
                        if not await self._send(ws, "ping", {}):
                            break
            except Exception as exc:
                log.info(f"{url} unavailable ({type(exc).__name__}); retry in {backoff:.0f}s")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, BACKOFF_MAX)

    # -------------------------------------------------------------- life
    async def _serve(self):
        self._server = await websockets.serve(
            self._handler, config.MESH_HOST, config.MESH_PORT
        )
        log.info(f"mesh listening on ws://{config.MESH_HOST}:{config.MESH_PORT} as '{self.node_id}'")
        if self.secret:
            log.info("shared-secret handshake is ON")
        else:
            log.warn("no ORBITAL_MESH_SECRET set — any local client can join")
        await asyncio.Future()

    async def start(self):
        if websockets is None:
            log.error("websockets not installed; mesh disabled")
            return
        self._running = True
        self._loop = asyncio.get_running_loop()
        for url in config.peers():
            self._tasks.append(asyncio.create_task(self._dial_forever(url)))
            log.info(f"dialing configured peer {url}")
        if not config.peers():
            log.info("no peers configured (set ORBITAL_PEERS=ws://host:8765,...)")
        await self._serve()

    def stop(self):
        self._running = False


def main():
    if websockets is None:
        print("Install websockets first:  pip install websockets")
        return 1
    mesh = Mesh()
    try:
        asyncio.run(mesh.start())
    except KeyboardInterrupt:
        mesh.stop()
        log.info("mesh stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
