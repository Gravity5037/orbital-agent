"""
ORBITAL OS AUTO-LEARNED SKILL: Network Health Sentinel
"""
import socket
import time

NAME = "Network Health Sentinel"
DESCRIPTION = "Checks endpoint connectivity, DNS resolution, and socket latency."
KEYWORDS = ["ping", "network latency", "check host", "connection status"]

def run(prompt: str) -> str:
    host = "1.1.1.1"
    port = 53
    t0 = time.time()
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2.0)
        sock.connect((host, port))
        sock.close()
        latency_ms = (time.time() - t0) * 1000
        return f"[Network Sentinel]: DNS Gateway {host}:{port} reachable in {latency_ms:.1f}ms."
    except Exception as e:
        return f"[Network Sentinel]: Connection failed to {host}:{port}: {e}"

if __name__ == "__main__":
    print(run("check network"))
