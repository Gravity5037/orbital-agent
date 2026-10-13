"""Tests for the endpoints the new UI calls.

The two HTML components need these routes to exist and to fail gracefully
when Spotify or Hue are not configured — which is the normal state on a
fresh install, and the state the UI must handle without breaking.
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
BASE = "/tmp/orbtest_ui_endpoints"
results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(f"{'PASS' if cond else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))


def req(path, method="GET", body=None, token=None):
    url = f"http://127.0.0.1:5000{path}"
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method)
    if data:
        r.add_header("Content-Type", "application/json")
    if token:
        r.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(r, timeout=20) as resp:
            return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw.decode() or "{}")
        except Exception:
            return e.code, {"_raw": raw[:80]}
    except Exception as e:
        return 0, {"_err": str(e)}


def main():
    shutil.rmtree(BASE, ignore_errors=True)
    os.makedirs(BASE, exist_ok=True)
    os.environ["ORBITAL_BASE"] = BASE
    os.environ["ORBITAL_QUIET"] = "1"

    env = dict(os.environ)
    engine = subprocess.Popen([sys.executable, "-m", "core.engine"], cwd=ROOT, env=env)

    try:
        up = False
        for _ in range(50):
            time.sleep(0.3)
            st, _b = req("/api/ping")
            if st == 200:
                up = True
                break
        check("engine started", up)
        if not up:
            return 1

        sys.path.insert(0, ROOT)
        from core import auth

        token = auth.get_token()

        # ---------------------------------------------------- auth gate
        for path in ("/api/spotify/now", "/api/spotify/devices", "/api/hue/lights"):
            st, _b = req(path)
            check(f"{path} requires a token", st == 401, f"got {st}")

        # ------------------------------------------ GET routes, unconfigured
        # These are the states a fresh install is actually in. They must
        # return a usable payload rather than a 500.
        st, body = req("/api/spotify/now", token=token)
        check("spotify/now answers when unconfigured", st == 200, f"got {st}")
        check("spotify/now reports the problem in the body",
              "error" in body and body.get("name") is None,
              str(body)[:70])

        st, body = req("/api/spotify/devices", token=token)
        check("spotify/devices answers when unconfigured", st in (200, 503), f"got {st}")
        check("spotify/devices always returns a list",
              isinstance(body.get("devices"), list), str(body)[:60])

        st, body = req("/api/hue/lights", token=token)
        check("hue/lights answers when unpaired", st in (200, 503), f"got {st}")
        check("hue/lights always returns a list",
              isinstance(body.get("lights"), list), str(body)[:60])
        check("hue/lights explains that pairing is needed",
              "pair" in str(body.get("error", "")).lower(),
              str(body.get("error"))[:60])

        st, body = req("/api/integrations", token=token)
        check("integrations reports all three", st == 200
              and all(k in body for k in ("hue", "spotify", "camera")),
              str(list(body))[:70])
        check("integrations marks them unavailable",
              all(not body[k]["available"] for k in body),
              str({k: body[k]["available"] for k in body}))

        # ---------------------------------------- POST routes, unconfigured
        # A control action with nothing configured must fail cleanly, with a
        # status the UI can distinguish, not a 500.
        for action in ("play", "pause", "next", "previous", "shuffle", "repeat"):
            st, body = req(f"/api/spotify/{action}", "POST", {}, token=token)
            check(f"spotify/{action} fails cleanly when unconfigured",
                  st in (403, 409, 503), f"got {st}: {str(body)[:40]}")

        st, body = req("/api/spotify/seek", "POST", {"position_ms": 1000}, token=token)
        check("spotify/seek fails cleanly when unconfigured",
              st in (403, 409, 503), f"got {st}")

        st, body = req("/api/spotify/seek", "POST", {"position_ms": "abc"}, token=token)
        check("spotify/seek rejects a non-numeric position",
              st == 400, f"got {st}")

        st, body = req("/api/spotify/volume", "POST", {"volume_percent": "loud"},
                       token=token)
        check("spotify/volume rejects a non-numeric value", st == 400, f"got {st}")

        st, body = req("/api/spotify/nonsense", "POST", {}, token=token)
        check("an unknown spotify action returns 404", st == 404, f"got {st}")

        # ------------------------------------------------------- hue writes
        st, body = req("/api/hue/set", "POST", {}, token=token)
        check("hue/set requires a name", st == 400, f"got {st}")

        st, body = req("/api/hue/set", "POST", {"name": "Kitchen", "on": True},
                       token=token)
        check("hue/set fails cleanly when unpaired", st in (400, 503), f"got {st}")

        st, body = req("/api/hue/all", "POST", {"on": False}, token=token)
        check("hue/all fails cleanly when unpaired", st in (400, 503), f"got {st}")

        st, body = req("/api/hue/nonsense", "POST", {}, token=token)
        check("an unknown hue action returns 404", st == 404, f"got {st}")

        # --------------------------------------------- the player's own flow
        # What now-playing.html does on load: integrations, then now-playing.
        st, integ = req("/api/integrations", token=token)
        check("the player's boot sequence works", st == 200)

        st, np = req("/api/spotify/now", token=token)
        check("the player can read now-playing without crashing",
              st == 200 and "name" in np, str(np)[:60])

    finally:
        if engine.poll() is None:
            try:
                engine.send_signal(signal.SIGTERM)
                engine.wait(timeout=8)
            except Exception:
                engine.kill()

    passed = sum(1 for _, ok in results if ok)
    print(f"\n{passed}/{len(results)} checks passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
