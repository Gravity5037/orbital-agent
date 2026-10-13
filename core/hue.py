"""Philips Hue control over the local bridge API.

The best of the integrations, because it is genuinely local: the Hue Bridge
speaks plain HTTP on your LAN, no cloud account, no rate limits, no internet
required once paired.

Three steps to set up:

  1. Find the bridge     — discovery, or set ORBITAL_HUE_BRIDGE
  2. Pair                — press the physical button, then call pair()
  3. Control             — on/off, brightness, colour, scenes

The pairing step exists because Hue requires proof of physical access: you
press the link button on the bridge and it accepts a key request for the next
30 seconds. That is a real security property, not an inconvenience.

API shape (v1, which is what every bridge speaks):
    GET  /api/<key>/lights          list lights
    GET  /api/<key>/lights/<id>     one light's state
    PUT  /api/<key>/lights/<id>/state   set state
    GET  /api/<key>/groups          rooms and zones
    GET  /api/<key>/scenes          scenes
"""

import json
import os
import socket
import time
import urllib.error
import urllib.request

from . import config, logutil

log = logutil.get_logger("hue")

BRIDGE = os.environ.get("ORBITAL_HUE_BRIDGE", "").strip()
KEY_FILE = os.path.join(config.STATE_DIR, "hue.key")

# Hue's own discovery service. Only used to find the bridge's LAN address;
# no control traffic leaves the network.
DISCOVERY_URL = "https://discovery.meethue.com"

APP_NAME = "orbital#desktop"

# Hue is strict about value ranges.
MAX_BRI = 254
MAX_HUE = 65535
MAX_SAT = 254
MIN_CT = 153      # ~6500K
MAX_CT = 500      # ~2000K


class HueError(RuntimeError):
    """Base class for Hue failures."""


class NotPaired(HueError):
    """No application key. Call pair() with the link button pressed."""


class BridgeUnreachable(HueError):
    """The bridge did not answer."""


def _request(path, method="GET", body=None, timeout=5, bridge=None):
    base = (bridge or BRIDGE).rstrip("/")
    if not base:
        raise HueError("no bridge configured; run discover() or set ORBITAL_HUE_BRIDGE")
    if not base.startswith("http"):
        base = "http://" + base

    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method)
    if data:
        req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise BridgeUnreachable(
            f"bridge unreachable at {base}: {exc.reason}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise HueError(f"bridge returned non-JSON: {exc}") from exc


def discover(timeout=5):
    """Find bridges on the network. Returns a list of {id, internalipaddress}."""
    found = []

    # Hue's discovery endpoint returns LAN addresses of bridges on this
    # network. Cheap and reliable when the machine has internet.
    try:
        req = urllib.request.Request(DISCOVERY_URL)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        for entry in data or []:
            ip = entry.get("internalipaddress")
            if ip:
                found.append({"id": entry.get("id", ""), "ip": ip,
                              "source": "cloud-discovery"})
    except Exception as exc:
        log.info(f"cloud discovery unavailable ({exc}); trying the local network")

    # mDNS name, which most bridges answer to on a home LAN.
    for host in ("philips-hue.local", "hue.local"):
        try:
            ip = socket.gethostbyname(host)
            if ip and not any(f["ip"] == ip for f in found):
                found.append({"id": "", "ip": ip, "source": "mdns"})
        except OSError:
            continue

    # Whatever is already configured, so it shows up even if discovery fails.
    if BRIDGE:
        ip = BRIDGE.replace("http://", "").replace("https://", "").split(":")[0]
        if not any(f["ip"] == ip for f in found):
            found.append({"id": "", "ip": ip, "source": "configured"})

    return found


def load_key():
    """The stored application key, or None."""
    if os.path.exists(KEY_FILE):
        try:
            with open(KEY_FILE, "r", encoding="utf-8") as fh:
                return fh.read().strip() or None
        except OSError:
            return None
    return None


def save_key(key):
    config.ensure_dirs()
    with open(KEY_FILE, "w", encoding="utf-8") as fh:
        fh.write(key)
    try:
        os.chmod(KEY_FILE, 0o600)
    except OSError:
        pass
    log.info(f"paired; key stored in {KEY_FILE}")


def pair(bridge=None, wait=False, timeout=30):
    """Request an application key.

    Press the link button on the bridge FIRST, then call this. Without the
    button press the bridge returns error type 101.

    With wait=True it retries for `timeout` seconds, which is easier than
    trying to press a physical button and run a command simultaneously.
    """
    deadline = time.time() + (timeout if wait else 0)
    attempt = 0

    while True:
        attempt += 1
        try:
            result = _request("/api", method="POST",
                              body={"devicetype": APP_NAME}, bridge=bridge)
        except BridgeUnreachable:
            raise

        if isinstance(result, list) and result:
            entry = result[0]
            if "success" in entry:
                key = entry["success"].get("username")
                if key:
                    save_key(key)
                    return key
            err = entry.get("error", {})
            if err.get("type") == 101:
                if time.time() < deadline:
                    if attempt == 1:
                        log.info("waiting for the link button — press it now")
                    time.sleep(2)
                    continue
                raise NotPaired(
                    "the bridge is not accepting new keys. Press the round "
                    "link button on the bridge, then run pair() within 30 seconds."
                )
            raise HueError(f"pairing failed: {err}")

        raise HueError(f"unexpected pairing response: {result}")


def _key(bridge=None):
    key = load_key()
    if not key:
        raise NotPaired(
            "not paired with the Hue bridge. Press the link button, then run: "
            "python -m core.hue pair"
        )
    return key


def bridge_ip():
    """Best guess at the bridge address."""
    if BRIDGE:
        return BRIDGE
    found = discover(timeout=3)
    return found[0]["ip"] if found else ""


def health(timeout=4):
    """(ok, detail). detail is the light count or an error string."""
    try:
        key = _key()
    except NotPaired as exc:
        return False, str(exc)
    try:
        lights = _request(f"/api/{key}/lights", timeout=timeout)
    except HueError as exc:
        return False, str(exc)
    if isinstance(lights, dict):
        return True, len(lights)
    return False, f"unexpected response: {str(lights)[:80]}"


# ------------------------------------------------------------------ state
def lights():
    """All lights as a list of dicts with a normalised shape."""
    key = _key()
    raw = _request(f"/api/{key}/lights")
    out = []
    for lid, data in (raw or {}).items():
        state = data.get("state", {})
        out.append({
            "id": lid,
            "name": data.get("name", f"light {lid}"),
            "on": bool(state.get("on")),
            "brightness": state.get("bri", 0),
            "brightness_pct": round(state.get("bri", 0) / MAX_BRI * 100),
            "reachable": state.get("reachable", True),
            "type": data.get("type", ""),
            "model": data.get("modelid", ""),
        })
    return sorted(out, key=lambda x: x["name"].lower())


def find_light(name):
    """Resolve a light by name (case-insensitive substring) or by id."""
    for light in lights():
        if light["id"] == str(name):
            return light
    matches = [l for l in lights() if name.lower() in l["name"].lower()]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise HueError(f"no light matching '{name}'")
    names = ", ".join(m["name"] for m in matches)
    raise HueError(f"'{name}' is ambiguous: {names}")


def set_light(name, on=None, brightness=None, brightness_pct=None,
              hue=None, saturation=None, color_temp=None, transition=None,
              bridge=None):
    """Change one light. Returns the bridge's response.

    Only the parameters you pass are changed. brightness is 0-254;
    brightness_pct is 0-100 for convenience.
    """
    light = find_light(name)
    key = _key(bridge)

    payload = {}

    if brightness_pct is not None:
        brightness = round(max(0, min(100, brightness_pct)) / 100 * MAX_BRI)
    if brightness is not None:
        payload["bri"] = max(1, min(MAX_BRI, int(brightness)))
    if on is not None:
        payload["on"] = bool(on)
    elif brightness is not None:
        # Setting brightness on a light that is off should turn it on.
        payload["on"] = True

    if hue is not None:
        payload["hue"] = max(0, min(MAX_HUE, int(hue)))
    if saturation is not None:
        payload["sat"] = max(0, min(MAX_SAT, int(saturation)))
    if color_temp is not None:
        payload["ct"] = max(MIN_CT, min(MAX_CT, int(color_temp)))
    if transition is not None:
        payload["transitiontime"] = max(0, int(transition * 10))  # ms -> 100ms units

    if not payload:
        raise HueError("nothing to change; pass on, brightness, hue or color_temp")

    result = _request(f"/api/{key}/lights/{light['id']}/state",
                      method="PUT", body=payload, bridge=bridge)

    for entry in result or []:
        if "error" in entry:
            raise HueError(entry["error"].get("description", str(entry["error"])))
    return result


def all_lights(on=None, brightness_pct=None, **kwargs):
    """Apply the same change to every light."""
    changed = []
    for light in lights():
        if not light["reachable"]:
            continue
        try:
            set_light(light["id"], on=on, brightness_pct=brightness_pct, **kwargs)
            changed.append(light["name"])
        except HueError as exc:
            log.warn(f"could not set {light['name']}: {exc}")
    return changed


def groups():
    """Rooms and zones."""
    key = _key()
    raw = _request(f"/api/{key}/groups")
    out = []
    for gid, data in (raw or {}).items():
        out.append({
            "id": gid,
            "name": data.get("name", f"group {gid}"),
            "lights": data.get("lights", []),
            "type": data.get("type", ""),
        })
    return sorted(out, key=lambda x: x["name"].lower())


def scenes():
    """Scenes, which are how you actually want to set mood."""
    key = _key()
    raw = _request(f"/api/{key}/scenes")
    out = []
    for sid, data in (raw or {}).items():
        out.append({
            "id": sid,
            "name": data.get("name", f"scene {sid}"),
            "group": data.get("group"),
        })
    return sorted(out, key=lambda x: x["name"].lower())


def set_group(name, on=None, brightness_pct=None, scene=None, **kwargs):
    """Control a room. If `scene` is given, activate it on the group."""
    key = _key()
    target = None
    for group in groups():
        if group["id"] == str(name) or name.lower() in group["name"].lower():
            target = group
            break
    if not target:
        raise HueError(f"no group matching '{name}'")

    if scene:
        for s in scenes():
            if s["name"].lower() == scene.lower() and str(s.get("group")) == target["id"]:
                return _request(f"/api/{key}/groups/{target['id']}/action",
                                method="PUT", body={"scene": s["id"]})
        raise HueError(f"no scene '{scene}' in group '{target['name']}'")

    payload = {}
    if on is not None:
        payload["on"] = bool(on)
    if brightness_pct is not None:
        payload["bri"] = max(1, min(MAX_BRI,
                                    round(max(0, min(100, brightness_pct)) / 100 * MAX_BRI)))
        payload["on"] = True
    payload.update(kwargs)
    if not payload:
        raise HueError("nothing to change")
    return _request(f"/api/{key}/groups/{target['id']}/action",
                    method="PUT", body=payload)


# --------------------------------------------------------------- commands
def handle(text):
    """Natural-ish commands for the chat interface.

    Returns (reply, meta) or None if this is not a Hue command.
    """
    t = text.strip().lower()

    if t in ("/lights", "/hue", "lights"):
        try:
            found = lights()
        except HueError as exc:
            return (f"Hue: {exc}", {"kind": "hue", "ok": False})
        if not found:
            return ("No lights found on the bridge.", {"kind": "hue"})
        lines = [f"  {'on ' if l['on'] else 'off'}  {l['brightness_pct']:>3}%  {l['name']}"
                 for l in found]
        return ("Lights:\n" + "\n".join(lines), {"kind": "hue", "count": len(found)})

    if t.startswith("/lights "):
        arg = text.strip()[8:].strip()
        low = arg.lower()

        if low in ("on", "off"):
            try:
                changed = all_lights(on=(low == "on"))
            except HueError as exc:
                return (f"Hue: {exc}", {"kind": "hue", "ok": False})
            return (f"Turned {low}: {', '.join(changed) or 'nothing'}",
                    {"kind": "hue"})

        if low.startswith("dim "):
            try:
                pct = int(low.split()[1].rstrip("%"))
            except (IndexError, ValueError):
                return ("Usage: /lights dim <0-100>", {"kind": "hue"})
            try:
                changed = all_lights(brightness_pct=pct)
            except HueError as exc:
                return (f"Hue: {exc}", {"kind": "hue", "ok": False})
            return (f"Dimmed to {pct}%: {', '.join(changed) or 'nothing'}",
                    {"kind": "hue"})

        if low.startswith("scene "):
            scene = arg[6:].strip()
            try:
                set_group("all", scene=scene)
                return (f"Activated scene '{scene}'", {"kind": "hue"})
            except HueError as exc:
                return (f"Could not activate '{scene}': {exc}", {"kind": "hue"})

        try:
            set_light(arg, on=True)
            return (f"Turned on {arg}", {"kind": "hue"})
        except HueError as exc:
            return (f"Could not control '{arg}': {exc}", {"kind": "hue"})

    return None


def main():
    import sys

    if len(sys.argv) < 2:
        print("usage: python -m core.hue [discover|pair|lights|on <name>|off <name>]")
        return 1

    cmd = sys.argv[1].lower()

    if cmd == "discover":
        found = discover()
        if not found:
            print("No bridges found. Set ORBITAL_HUE_BRIDGE to the bridge IP.")
            return 1
        for f in found:
            print(f"  {f['ip']}  ({f['source']})")
        return 0

    if cmd == "pair":
        print("Press the link button on the bridge now.")
        try:
            key = pair(wait=True, timeout=40)
            print(f"Paired. Key stored in {KEY_FILE}")
            return 0
        except HueError as exc:
            print(f"Pairing failed: {exc}")
            return 1

    if cmd == "lights":
        ok, detail = health()
        if not ok:
            print(f"Not available: {detail}")
            return 1
        for light in lights():
            state = "on " if light["on"] else "off"
            print(f"  {state}  {light['brightness_pct']:>3}%  {light['name']}")
        return 0

    if cmd in ("on", "off") and len(sys.argv) > 2:
        name = " ".join(sys.argv[2:])
        try:
            set_light(name, on=(cmd == "on"))
            print(f"{cmd}: {name}")
            return 0
        except HueError as exc:
            print(f"Failed: {exc}")
            return 1

    print(f"unknown command '{cmd}'")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
