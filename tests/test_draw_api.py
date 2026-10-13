"""HTTP-level test for the /api/draw surface.

Proves the endpoint is token-gated, returns a job handle instead of blocking,
and that the generated image is retrievable. Path traversal on /api/image is
checked explicitly.
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
BASE = "/tmp/orbtest_drawapi"
results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(f"{'PASS' if cond else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))


def req(path, method="GET", body=None, token=None, raw=False):
    url = f"http://127.0.0.1:5000{path}"
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method)
    if data:
        r.add_header("Content-Type", "application/json")
    if token:
        r.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(r, timeout=60) as resp:
            payload = resp.read()
            if raw:
                return resp.status, payload
            return resp.status, json.loads(payload.decode() or "{}")
    except urllib.error.HTTPError as e:
        raw_body = e.read()
        try:
            return e.code, json.loads(raw_body.decode() or "{}")
        except Exception:
            return e.code, {"_raw": raw_body[:100]}


def main():
    shutil.rmtree(BASE, ignore_errors=True)
    os.makedirs(BASE, exist_ok=True)
    os.environ["ORBITAL_BASE"] = BASE

    fake = subprocess.Popen([sys.executable, os.path.join(ROOT, "tests", "fake_comfy.py")])
    time.sleep(0.8)

    env = dict(os.environ)
    engine = subprocess.Popen([sys.executable, "-m", "core.engine"], cwd=ROOT, env=env)

    try:
        for _ in range(60):
            time.sleep(0.3)
            st, _b = req("/api/ping")
            if st == 200:
                break

        sys.path.insert(0, ROOT)
        from core import auth

        token = auth.get_token()

        # ---- auth on every draw route
        st, body = req("/api/draw", "POST", {"prompt": "x"})
        check("draw rejects a missing token", st == 401, f"got {st}")
        st, body = req("/api/draw/status")
        check("draw status rejects a missing token", st == 401, f"got {st}")
        st, body = req("/api/image?name=x.png")
        check("image route rejects a missing token", st == 401, f"got {st}")

        # ---- backend discovery
        st, body = req("/api/nebula", token=token)
        check("nebula endpoint reports the backend reachable",
              st == 200 and body.get("reachable") is True, str(body)[:80])
        check("nebula endpoint lists checkpoints",
              "sdxl_base.safetensors" in (body.get("checkpoints") or []),
              str(body.get("checkpoints")))

        # ---- submit returns immediately
        started = time.time()
        st, body = req("/api/draw", "POST", {"prompt": "a cat", "steps": 2,
                                             "width": 64, "height": 64}, token=token)
        elapsed = time.time() - started
        check("draw returns 202 Accepted", st == 202, f"got {st}")
        check("draw returns immediately, not after generation",
              elapsed < 5, f"{elapsed:.2f}s")
        job_id = body.get("job_id")
        check("draw returns a job id", bool(job_id), str(job_id))
        check("draw returns a poll path",
              body.get("poll") == f"/api/draw/{job_id}", str(body.get("poll")))

        # ---- poll to completion
        status = None
        deadline = time.time() + 40
        while time.time() < deadline:
            st, rec = req(f"/api/draw/{job_id}", token=token)
            status = rec.get("status")
            if status in ("done", "failed"):
                break
            time.sleep(0.3)
        check("the job reaches a terminal state", status == "done",
              f"{status}: {rec.get('error')}")
        check("the finished job reports an image path",
              bool(rec.get("result", {}).get("path")),
              str(rec.get("result", {}).get("path")))
        check("the finished job reports elapsed time",
              rec.get("result", {}).get("elapsed") is not None)

        # ---- fetch the image
        name = os.path.basename(rec["result"]["path"])
        st, data = req(f"/api/image?name={name}", token=token, raw=True)
        check("the image is retrievable over HTTP", st == 200, f"got {st}")
        check("the served bytes are a PNG",
              isinstance(data, bytes) and data[:8] == b"\x89PNG\r\n\x1a\n",
              repr(data[:8]) if isinstance(data, bytes) else str(data))

        # ---- path traversal must be refused
        st, body = req("/api/image?name=../../../../etc/passwd", token=token)
        check("path traversal on /api/image is refused",
              st == 400, f"got {st}: {str(body)[:60]}")
        st, body = req("/api/image?name=..%2F..%2Fetc%2Fpasswd", token=token)
        check("encoded path traversal is refused too",
              st in (400, 404), f"got {st}")

        st, body = req("/api/image?name=nonexistent.png", token=token)
        check("a missing image returns 404", st == 404, f"got {st}")

        # ---- job listing
        st, body = req("/api/draw/status", token=token)
        check("draw status lists jobs", st == 200 and len(body.get("jobs", [])) >= 1,
              f"{len(body.get('jobs', []))} job(s)")

        st, body = req("/api/draw/deadbeef", token=token)
        check("an unknown job id returns 404", st == 404, f"got {st}")

        st, body = req("/api/draw", "POST", {"prompt": "   "}, token=token)
        check("an empty prompt is rejected", st == 400, f"got {st}")

        st, body = req("/api/draw", "POST", {"prompt": "x", "width": "abc"}, token=token)
        check("a non-numeric width is rejected", st == 400, f"got {st}")

    finally:
        for p in (engine, fake):
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
