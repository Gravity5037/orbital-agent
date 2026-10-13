"""End-to-end test for the fixed Orbital core.

Starts a fake Nucleus backend and the real engine, then checks:

  1. /api/ping works without a token
  2. /api/telemetry rejects a missing token
  3. /api/telemetry accepts a valid token
  4. /api/chat returns a real LLM reply (from the fake backend)
  5. /api/chat does NOT expose the LLM when llm=false
  6. a foreign Origin is not granted CORS
  7. the shell bridge runs and returns output
  8. chat reports failure honestly when Nucleus is down
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

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BASE = "/tmp/orbtest"

sys.path.insert(0, ROOT)
os.environ["ORBITAL_BASE"] = BASE

results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print(f"{'PASS' if cond else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))


def req(path, method="GET", body=None, token=None, origin=None):
    url = f"http://127.0.0.1:5000{path}"
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method)
    if data:
        r.add_header("Content-Type", "application/json")
    if token:
        r.add_header("Authorization", f"Bearer {token}")
    if origin:
        r.add_header("Origin", origin)
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode()), dict(resp.headers)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}"), dict(e.headers)


def main():
    shutil.rmtree(BASE, ignore_errors=True)
    os.makedirs(BASE, exist_ok=True)

    procs = []
    try:
        procs.append(
            subprocess.Popen([sys.executable, os.path.join(HERE, "fake_ollama.py")])
        )
        time.sleep(1.0)

        env = dict(os.environ)
        procs.append(
            subprocess.Popen(
                [sys.executable, "-m", "core.engine"], cwd=ROOT, env=env
            )
        )

        # wait for the engine to bind
        for _ in range(40):
            time.sleep(0.25)
            try:
                req("/api/ping")
                break
            except Exception:
                continue

        sys.path.insert(0, ROOT)
        from core import auth

        token = auth.get_token()

        # 1
        st, body, _ = req("/api/ping")
        check("ping is reachable without a token", st == 200 and body.get("ok"))

        # 2
        st, body, _ = req("/api/telemetry")
        check("telemetry rejects a missing token", st == 401, f"got {st}")

        # 3
        st, body, _ = req("/api/telemetry", token=token)
        ok = st == 200 and "cpu_pct" in body
        check("telemetry accepts a valid token", ok, f"got {st}")
        check(
            "telemetry reports the real Nucleus state",
            body.get("nucleus", {}).get("reachable") is True,
            str(body.get("nucleus", {}).get("models")),
        )

        # 4
        st, body, _ = req("/api/chat", "POST", {"prompt": "hello there"}, token=token)
        check(
            "chat returns a real LLM reply",
            st == 200 and "FAKE-LLM" in body.get("response", ""),
            body.get("response", "")[:60],
        )
        check(
            "chat metadata marks it as an llm call",
            body.get("meta", {}).get("kind") == "llm",
            str(body.get("meta")),
        )

        # 5
        st, body, _ = req(
            "/api/chat", "POST", {"prompt": "hello", "llm": False}, token=token
        )
        check(
            "llm=false short-circuits the backend",
            body.get("meta", {}).get("kind") == "echo",
            str(body.get("meta")),
        )

        # 6
        st, body, headers = req(
            "/api/telemetry", token=token, origin="https://evil.example"
        )
        check(
            "foreign Origin is not granted CORS",
            "Access-Control-Allow-Origin" not in headers,
            str(headers.get("Access-Control-Allow-Origin")),
        )
        st, body, headers = req(
            "/api/telemetry", token=token, origin="http://127.0.0.1:5000"
        )
        check(
            "allowed Origin is granted CORS",
            headers.get("Access-Control-Allow-Origin") == "http://127.0.0.1:5000",
            str(headers.get("Access-Control-Allow-Origin")),
        )

        # 7
        st, body, _ = req("/api/shell", "POST", {"cmd": "echo orbital-ok"}, token=token)
        check(
            "shell bridge executes and returns output",
            "orbital-ok" in (body.get("stdout") or ""),
            str(body)[:80],
        )

        # 8 — kill the fake backend, chat must fail honestly
        procs[0].terminate()
        procs[0].wait(timeout=5)
        time.sleep(0.5)
        st, body, _ = req("/api/chat", "POST", {"prompt": "still there?"}, token=token)
        resp = body.get("response", "")
        check(
            "chat reports failure honestly when Nucleus is down",
            st == 200
            and body.get("meta", {}).get("kind") == "error"
            and "not reachable" in resp.lower(),
            resp[:70],
        )
        st, body, _ = req("/api/telemetry", token=token)
        check(
            "telemetry reflects Nucleus going down",
            body.get("nucleus", {}).get("reachable") is False,
        )

    finally:
        for p in procs:
            if p.poll() is None:
                try:
                    p.send_signal(signal.SIGTERM)
                    p.wait(timeout=5)
                except Exception:
                    p.kill()

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print(f"\n{passed}/{total} checks passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
