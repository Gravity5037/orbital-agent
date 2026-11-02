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

        # Wait for the engine to bind.
        #
        # The old loop accepted a 200 from ANY process on 5000. If the child
        # died at bind -- which it does whenever something else holds the
        # port -- a stale engine from an earlier run answered the ping, and
        # the test then ran against a process that had never seen its token.
        # Every token-bearing call returned 401 and the cause looked like an
        # auth bug. Check the child is alive before trusting the response.
        engine = procs[-1]

        # Give the child a moment to fail. A child that cannot bind dies in
        # well under a second; a healthy one needs longer than that to come
        # up. Checking before the ping means a dead child is caught on its
        # first iteration instead of being masked by a stale responder.
        time.sleep(1.0)

        ready = False
        for _ in range(40):
            if engine.poll() is not None:
                raise SystemExit(
                    "the engine child exited during startup with code "
                    f"{engine.returncode}. Something else is on port 5000.\n"
                    "Find it with:  netstat -ano | findstr :5000"
                )
            try:
                req("/api/ping")
                ready = True
                break
            except Exception:
                time.sleep(0.25)
                continue
        if not ready:
            raise SystemExit("the engine never answered /api/ping")
        if engine.poll() is not None:
            raise SystemExit(
                "the engine child died just after answering /api/ping - "
                "the response came from another process"
            )

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
        # Chat routes through core/agent.py so a tool call runs instead
        # of being printed as text. The agent path sets kind to "agent",
        # and to "agent-stopped" only when the step budget ran out. This
        # asserts the specific value rather than accepting a set, so a
        # reply that silently fell back to the plain handler is caught
        # instead of tolerated.
        meta = body.get("meta", {})
        check(
            "chat is handled by the agent loop",
            meta.get("kind") == "agent",
            str(meta),
        )
        check(
            "the agent path reports a tool count",
            "calls" in meta,
            str(meta),
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
