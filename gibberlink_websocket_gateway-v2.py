import os
import sys
import json
import asyncio
import time

try:
    import websockets
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "websockets"], check=True)
    import websockets

CONNECTED_PEERS = set()

async def handler(websocket, path):
    CONNECTED_PEERS.add(websocket)
    try:
        async for message in websocket:
            data = json.loads(message)
            response = {
                "status": "ACK",
                "node_id": "Orbital-Host-01",
                "timestamp": time.time(),
                "crdt_lease": "GRANTED"
            }
            await websocket.send(json.dumps(response))
    except Exception:
        pass
    finally:
        CONNECTED_PEERS.remove(websocket)

async def main():
    async with websockets.serve(handler, "0.0.0.0", 8765):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
