"""Full-stack test: supervisor brings up engine + mesh, both answer.

This is the closest thing to "does Orbital actually boot" that can run
without a Windows host.
"""

import json
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "/tmp/orbtest_full"
results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(f"{'PASS' if cond else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))


def get(path, token=None):
    r = urllib.request.Request(f"http://127.0.0.1:5000{path}")
    if token:
        r.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(r, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, {}
    except Exception as e:
        return 0, {"_err": str(e)}


def main():
    shutil.rmtree(BASE, ignore_errors=True)
    os.makedirs(BASE, exist_ok=True)

    # The test process itself must use the same data root as the supervisor
    # it spawns, otherwise it reads a different token file and log dir.
    os.environ["ORBITAL_BASE"] = BASE

    env = dict(os.environ)
    env["ORBITAL_BASE"] = BASE
    env["ORBITAL_QUIET"] = "1"
    env["ORBITAL_PEERS"] = ""  # no peers; we just need the listener up

    fake = subprocess.Popen([sys.executable, os.path.join(ROOT, "tests", "fake_ollama.py")])
    time.sleep(0.8)
    sup = subprocess.Popen([sys.executable, "-m", "core.supervisor"], cwd=ROOT, env=env)

    try:
        # wait for the engine to answer
        up = False
        for _ in range(60):
            time.sleep(0.3)
            st, _b = get("/api/ping")
            if st == 200:
                up = True
                break
        check("supervisor brought the engine up", up)

        sys.path.insert(0, ROOT)
        from core import auth

        token = auth.get_token()
        st, body = get("/api/telemetry", token)
        check("telemetry answers through the supervisor",
              st == 200 and "cpu_pct" in body, f"status={st}")

        st, body = get("/api/logs?name=engine", token)
        check("log endpoint returns real lines",
              st == 200 and len(body.get("lines", [])) > 0,
              f"{len(body.get('lines', []))} lines")

        # mesh listener
        import socket

        s = socket.socket()
        s.settimeout(2)
        try:
            s.connect(("127.0.0.1", 8765))
            reachable = True
        except Exception as e:
            reachable = False
        finally:
            s.close()
        check("mesh listener is up on 8765", reachable)

        # engine bound to loopback only
        s = socket.socket()
        s.settimeout(2)
        try:
            s.connect(("127.0.0.1", 5000))
            loopback = True
        except Exception:
            loopback = False
        finally:
            s.close()
        check("engine is reachable on loopback", loopback)

    finally:
        for p in (sup, fake):
            if p.poll() is None:
                try:
                    p.send_signal(signal.SIGTERM)
                    p.wait(timeout=8)
                except Exception:
                    p.kill()

    passed = sum(1 for _, ok in results if ok)
    print(f"\n{passed}/{len(results)} checks passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
