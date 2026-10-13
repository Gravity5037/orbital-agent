"""
ORBITAL OS - GibberLink WebSocket Gateway v2
Launches the background asyncio WebSocket mesh listener.
"""

import sys
from core.gibberlink_mesh import GibberLinkMesh

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

def main():
    print("[🛰️ GibberLink Mesh] Initializing gateway on ws://0.0.0.0:8765...")
    mesh = GibberLinkMesh(node_id="orbital-gateway-v2")
    mesh.start_background_mesh()
    import time
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[🛰️ GibberLink Mesh] Gateway shutting down.")

if __name__ == "__main__":
    main()
