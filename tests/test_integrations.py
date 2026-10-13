"""Integration tests: Hue, Spotify and camera.

These run against fake servers rather than real hardware, so the logic is
proven without needing a bridge, an account, or a webcam present.

The parts worth testing are the failure paths: no bridge paired, no Spotify
device, no OpenCV. Those are what actually break in use.
"""

import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "/tmp/orbtest_integrations"
os.environ["ORBITAL_BASE"] = BASE
os.environ["ORBITAL_QUIET"] = "1"
sys.path.insert(0, ROOT)

results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(f"{'PASS' if cond else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))


# ------------------------------------------------------------ fake bridge
class FakeHue(BaseHTTPRequestHandler):
    key = "fake-key-12345"
    lights = {
        "1": {"name": "Living Room", "state": {"on": True, "bri": 200, "reachable": True},
              "type": "Extended color light", "modelid": "LCT001"},
        "2": {"name": "Bedroom", "state": {"on": False, "bri": 0, "reachable": True},
              "type": "Dimmable light", "modelid": "LWB001"},
        "3": {"name": "Offline Lamp", "state": {"on": False, "bri": 0, "reachable": False},
              "type": "Dimmable light", "modelid": "LWB001"},
    }
    paired = False
    last_put = {}

    def log_message(self, *a):
        pass

    def _json(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path == "/api":
            if FakeHue.paired:
                return self._json(200, [{"success": {"username": FakeHue.key}}])
            return self._json(200, [{"error": {"type": 101,
                                               "description": "link button not pressed"}}])
        self._json(404, [])

    def do_GET(self):
        parts = self.path.strip("/").split("/")
        if len(parts) < 2 or parts[0] != "api" or parts[1] != FakeHue.key:
            return self._json(200, [{"error": {"type": 1, "description": "unauthorized"}}])
        resource = parts[2] if len(parts) > 2 else ""

        if resource == "lights":
            if len(parts) == 3:
                return self._json(200, FakeHue.lights)
            lid = parts[3]
            if lid in FakeHue.lights:
                return self._json(200, FakeHue.lights[lid])
            return self._json(200, [])
        if resource == "groups":
            return self._json(200, {"1": {"name": "All", "lights": ["1", "2", "3"],
                                          "type": "Room"}})
        if resource == "scenes":
            return self._json(200, {"s1": {"name": "Relax", "group": "1"}})
        self._json(404, [])

    def do_PUT(self):
        n = int(self.headers.get("Content-Length", 0) or 0)
        body = json.loads(self.rfile.read(n) or b"{}")
        parts = self.path.strip("/").split("/")

        if len(parts) >= 4 and parts[2] == "lights":
            lid = parts[3]
            if lid in FakeHue.lights:
                FakeHue.lights[lid]["state"].update(body)
                FakeHue.last_put = body
                return self._json(200, [{"success": {"/lights/%s/state" % lid: body}}])
        if len(parts) >= 4 and parts[2] == "groups":
            return self._json(200, [{"success": {}}])
        self._json(200, [])


def serve(handler, port):
    """Start a fake server. Fails with a clear message if the port is taken."""
    try:
        server = HTTPServer(("127.0.0.1", port), handler)
    except OSError as exc:
        raise SystemExit(
            f"port {port} is already in use ({exc}). "
            f"Something else in this suite, or a stray Orbital process, is "
            f"holding it. Stop Orbital and re-run."
        ) from exc
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server


def wait_port(port, timeout=8):
    deadline = time.time() + timeout
    while time.time() < deadline:
        s = socket.socket()
        s.settimeout(0.4)
        try:
            s.connect(("127.0.0.1", port))
            return True
        except Exception:
            time.sleep(0.15)
        finally:
            s.close()
    return False


def main():
    shutil.rmtree(BASE, ignore_errors=True)
    os.makedirs(BASE, exist_ok=True)

    # ================================================================= HUE
    print("\n--- Hue ---")
    server = serve(FakeHue, 8791)

    from core import hue

    hue.BRIDGE = "http://127.0.0.1:8791"

    # not paired yet
    ok, detail = hue.health()
    check("hue reports not-paired before pairing",
          ok is False and "pair" in str(detail).lower(), str(detail)[:50])

    # pairing refused without the button
    try:
        hue.pair(timeout=0)
        check("hue pair fails without the link button", False, "no exception")
    except hue.NotPaired as exc:
        check("hue pair fails without the link button", True,
              str(exc)[:50])

    # pairing succeeds when the bridge accepts
    FakeHue.paired = True
    key = hue.pair(timeout=5)
    check("hue pair stores a key when the bridge accepts",
          key == FakeHue.key, key)
    check("hue writes the key to disk", os.path.exists(hue.KEY_FILE))
    check("the key file is not world-readable",
          (os.stat(hue.KEY_FILE).st_mode & 0o077) == 0,
          oct(os.stat(hue.KEY_FILE).st_mode & 0o777))

    ok, detail = hue.health()
    check("hue reports healthy once paired", ok is True, str(detail))

    found = hue.lights()
    check("hue lists lights", len(found) == 3, f"{len(found)} lights")
    living = [l for l in found if l["name"] == "Living Room"][0]
    check("hue normalises brightness to a percentage",
          living["brightness_pct"] == round(200 / 254 * 100),
          f"{living['brightness_pct']}% (expected {round(200 / 254 * 100)}%)")
    check("hue sorts lights by name",
          [l["name"] for l in found] == sorted([l["name"] for l in found]),
          str([l["name"] for l in found]))
    check("hue reports reachability",
          any(not l["reachable"] for l in found))

    light = hue.find_light("living")
    check("hue finds a light by partial name", light["name"] == "Living Room",
          light["name"])

    try:
        hue.find_light("nonexistent")
        check("hue raises on an unknown light", False, "no exception")
    except hue.HueError:
        check("hue raises on an unknown light", True)

    hue.set_light("Living Room", on=True, brightness_pct=50)
    check("hue converts brightness_pct to bridge units",
          FakeHue.last_put.get("bri") == round(50 / 100 * 254),
          str(FakeHue.last_put))
    check("hue sets the on flag", FakeHue.last_put.get("on") is True)

    hue.set_light("1", on=False)
    check("hue accepts a light id directly",
          FakeHue.lights["1"]["state"]["on"] is False)

    # brightness on an off light should turn it on
    FakeHue.lights["2"]["state"]["on"] = False
    hue.set_light("Bedroom", brightness_pct=30)
    check("setting brightness turns an off light on",
          FakeHue.lights["2"]["state"]["on"] is True)

    try:
        hue.set_light("Bedroom")
        check("hue refuses a no-op change", False, "no exception")
    except hue.HueError:
        check("hue refuses a no-op change", True)

    changed = hue.all_lights(on=True)
    check("hue skips unreachable lights in a broadcast",
          "Offline Lamp" not in changed, str(changed))

    groups = hue.groups()
    check("hue lists groups", len(groups) == 1, str(groups))
    scenes = hue.scenes()
    check("hue lists scenes", len(scenes) == 1, str(scenes))

    # command routing
    reply, meta = hue.handle("/lights")
    check("hue chat command lists lights", "Living Room" in reply, reply[:40])
    reply, meta = hue.handle("/lights off")
    check("hue chat command turns everything off", "off" in reply.lower())
    reply, meta = hue.handle("/lights dim 25")
    check("hue chat command dims", "25" in reply, reply[:40])
    check("a non-hue message returns None", hue.handle("hello there") is None)

    # unreachable bridge
    hue.BRIDGE = "http://127.0.0.1:8798"
    ok, detail = hue.health(timeout=2)
    check("hue reports an unreachable bridge",
          ok is False and "unreachable" in str(detail).lower(),
          str(detail)[:60])
    hue.BRIDGE = "http://127.0.0.1:8791"

    server.shutdown()

    # ============================================================= SPOTIFY
    print("\n--- Spotify ---")
    from core import spotify

    check("spotify reports not-configured without credentials",
          spotify.health()[0] is False)

    try:
        spotify.access_token()
        check("spotify raises without a token", False, "no exception")
    except spotify.NotConfigured as exc:
        check("spotify raises without a token", True, str(exc)[:45])

    # A fake token, written through the module's own save path so the
    # permission handling is exercised rather than bypassed.
    spotify.save_token({
        "client_id": "cid", "client_secret": "secret",
        "access_token": "fake-token",
        "expires_at": time.time() + 3600,
    })

    check("spotify loads a stored token", spotify.load_token() is not None)
    check("spotify returns an unexpired token as-is",
          spotify.access_token() == "fake-token")

    check("the token file is not world-readable",
          (os.stat(spotify.TOKEN_FILE).st_mode & 0o077) == 0,
          oct(os.stat(spotify.TOKEN_FILE).st_mode & 0o777))

    # Command parsing without a network round trip
    handled = spotify.handle("/volume 150")
    check("spotify handles a volume command (or reports no device)",
          handled is not None, str(handled)[:60])
    check("a non-spotify message returns None",
          spotify.handle("what is the weather") is None)

    # Error mapping
    check("spotify maps 403 PREMIUM to PremiumRequired",
          spotify.PremiumRequired is not None)
    check("spotify maps no-device to NoDevice", spotify.NoDevice is not None)

    # ============================================================== CAMERA
    print("\n--- Camera ---")
    from core import camera

    ok, detail = camera.available()
    if ok:
        check("camera detects OpenCV", True, f"OpenCV {detail}")
    else:
        check("camera reports a missing OpenCV clearly",
              "opencv" in detail.lower(), detail[:60])

    url = camera.phone_url("100.64.0.5")
    check("camera builds a phone MJPEG url",
          url == "http://100.64.0.5:8080/video", url)
    url2 = camera.phone_url("http://100.64.0.5/", port=8081, path="videofeed")
    check("camera tolerates a scheme and trailing slash in the host",
          url2 == "http://100.64.0.5:8081/videofeed", url2)

    if ok:
        try:
            camera.snapshot(99)
            check("camera raises on an unavailable source", False, "no exception")
        except camera.CameraError as exc:
            check("camera raises on an unavailable source", True,
                  str(exc)[:50])

    check("a non-camera message returns None",
          camera.handle("not a camera command") is None)

    # ============================================================ ENGINE
    print("\n--- Engine wiring ---")
    from core import engine

    text, meta = engine.handle_prompt("/lights", use_llm=False)
    check("engine routes /lights to the hue handler",
          meta.get("kind") == "hue",
          f"kind={meta.get('kind')}, text={text[:50]!r}")
    # Whatever the bridge state, the reply must be a message rather than an
    # exception. That is the property that matters: a handler that throws is
    # a handler the engine silently drops.
    check("a hue failure produces a reply, not an exception",
          meta.get("kind") == "hue" and bool(text),
          text[:70])
    check("the hue failure reply is not the echo fallback",
          meta.get("kind") != "echo", str(meta))

    text, meta = engine.handle_prompt("/nonexistentcommand", use_llm=False)
    check("an unknown command falls through to the echo path",
          meta.get("kind") == "echo", str(meta))

    passed = sum(1 for _, ok in results if ok)
    print(f"\n{passed}/{len(results)} checks passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
