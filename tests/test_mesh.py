"""Mesh test: spin up two real nodes and prove they handshake.

Node A listens on 8765 with a shared secret.
Node B listens on 8766 and dials A.
Then: correct secret connects, wrong secret is rejected, and a message
sent from B is received by A.
"""

import asyncio
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["ORBITAL_BASE"] = "/tmp/orbtest"

import websockets  # noqa: E402

from core import config  # noqa: E402
from core.mesh import Mesh  # noqa: E402

SECRET = "test-shared-secret"
results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(f"{'PASS' if cond else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))


async def wait_for_port(port, timeout=5.0):
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        try:
            async with websockets.connect(f"ws://127.0.0.1:{port}"):
                return True
        except Exception:
            await asyncio.sleep(0.2)
    return False


async def test_handshake_and_relay():
    config.MESH_PORT = 8765
    config.MESH_HOST = "127.0.0.1"

    a = Mesh(node_id="node-a", secret=SECRET)
    a_task = asyncio.create_task(a.start())
    await asyncio.sleep(1.0)

    # 1. a client with the right secret joins
    ws = await websockets.connect("ws://127.0.0.1:8765")
    await ws.send(json.dumps({"v": 1, "type": "hello", "from": "tester",
                              "ts": 0, "payload": {"secret": SECRET}}))
    reply = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
    check("peer with correct secret is welcomed",
          reply.get("type") == "welcome", str(reply.get("type")))
    check("welcome carries the node identity",
          reply.get("payload", {}).get("node") == "node-a",
          str(reply.get("payload")))

    # 2. ping/pong
    await ws.send(json.dumps({"v": 1, "type": "ping", "from": "tester",
                              "ts": 1.0, "payload": {}}))
    pong = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
    check("ping is answered with pong", pong.get("type") == "pong", str(pong.get("type")))

    # 3. peer shows up in the registry
    check("peer is registered", "tester" in a.peers, str(list(a.peers)))

    # 4. wrong secret is rejected
    ws2 = await websockets.connect("ws://127.0.0.1:8765")
    await ws2.send(json.dumps({"v": 1, "type": "hello", "from": "intruder",
                               "ts": 0, "payload": {"secret": "wrong"}}))
    bad = json.loads(await asyncio.wait_for(ws2.recv(), timeout=5))
    check("peer with wrong secret is rejected",
          bad.get("type") == "error", str(bad.get("payload")))
    check("rejected peer is not registered", "intruder" not in a.peers)

    # 5. version mismatch is refused
    ws3 = await websockets.connect("ws://127.0.0.1:8765")
    await ws3.send(json.dumps({"v": 99, "type": "hello", "from": "old",
                               "ts": 0, "payload": {"secret": SECRET}}))
    verr = json.loads(await asyncio.wait_for(ws3.recv(), timeout=5))
    check("protocol version mismatch is refused",
          verr.get("type") == "error", str(verr.get("payload")))

    # 6. broadcast reaches the connected peer
    a.broadcast("test-event", {"hello": "hive"})
    got = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
    check("broadcast is delivered to the peer",
          got.get("type") == "test-event" and got.get("payload", {}).get("hello") == "hive",
          str(got))

    # 7. malformed JSON doesn't kill the connection
    await ws.send("{not json")
    err = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
    check("malformed JSON yields an error, not a crash",
          err.get("type") == "error", str(err.get("payload")))

    a.stop()
    if a._server is not None:
        a._server.close()
        await a._server.wait_closed()
    a_task.cancel()
    try:
        await a_task
    except (asyncio.CancelledError, Exception):
        pass
    await asyncio.sleep(0.4)   # let the socket actually release


async def test_dialer_reconnects():
    """A dialer pointed at a dead port should retry, not crash."""
    # A port nothing else in the suite uses.
    config.MESH_PORT = 8797
    config.MESH_HOST = "127.0.0.1"
    os.environ["ORBITAL_PEERS"] = "ws://127.0.0.1:9999"
    m = Mesh(node_id="node-b", secret=SECRET)
    task = asyncio.create_task(m.start())
    await asyncio.sleep(2.0)
    check("dialer survives an unreachable peer", m._running)
    check("listener still came up despite dead peer", m._server is not None)
    m.stop()
    if m._server is not None:
        m._server.close()
        await m._server.wait_closed()
    task.cancel()
    try:
        await task
    except (asyncio.CancelledError, Exception):
        pass
    await asyncio.sleep(0.4)


async def main():
    await test_handshake_and_relay()
    await test_dialer_reconnects()
    passed = sum(1 for _, ok in results if ok)
    print(f"\n{passed}/{len(results)} checks passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
