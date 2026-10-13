"""Spotify control via the Web API.

Unlike Hue, this one is not local — Spotify's API is cloud-only, and the
token flow requires a browser once. After that, playback control is just
HTTPS calls with a refresh token.

Setup, once:

  1. Create an app at https://developer.spotify.com/dashboard
  2. Add the redirect URI exactly:  http://127.0.0.1:8888/callback
  3. Set the credentials, either in the environment or in state/spotify.json:
         ORBITAL_SPOTIFY_CLIENT_ID
         ORBITAL_SPOTIFY_CLIENT_SECRET
  4. Run:  python -m core.spotify auth
     A browser opens, you approve, the token is stored.

Then: play, pause, skip, volume, search, queue, playlists.

Two honest notes:

  * **Playback requires an active device.** The API controls a Spotify
    client that is already running — it cannot start one. If nothing is
    playing, `devices()` shows what is available and `transfer()` moves
    playback to one of them.
  * **Free accounts are limited.** Some endpoints return 403 on free tier.
    That is Spotify's policy, not a bug here.
"""

import base64
import json
import os
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

from . import config, logutil

log = logutil.get_logger("spotify")

API = "https://api.spotify.com/v1"
ACCOUNTS = "https://accounts.spotify.com"
REDIRECT_PORT = int(os.environ.get("ORBITAL_SPOTIFY_PORT", "8888"))
REDIRECT_URI = f"http://127.0.0.1:{REDIRECT_PORT}/callback"
TOKEN_FILE = os.path.join(config.STATE_DIR, "spotify.json")

SCOPES = " ".join([
    "user-read-playback-state",
    "user-modify-playback-state",
    "user-read-currently-playing",
    "playlist-read-private",
    "playlist-modify-private",
    "user-library-read",
    "user-library-modify",
])


class SpotifyError(RuntimeError):
    """Base class for Spotify failures."""


class NotConfigured(SpotifyError):
    """No client id/secret, or no token yet."""


class NoDevice(SpotifyError):
    """Nothing to play on. Open Spotify on a device first."""


class PremiumRequired(SpotifyError):
    """This endpoint needs Premium."""


# ------------------------------------------------------------------ config
def credentials():
    cid = os.environ.get("ORBITAL_SPOTIFY_CLIENT_ID", "").strip()
    secret = os.environ.get("ORBITAL_SPOTIFY_CLIENT_SECRET", "").strip()

    if cid and secret:
        return cid, secret

    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            return data.get("client_id", ""), data.get("client_secret", "")
        except (OSError, json.JSONDecodeError):
            pass

    return cid, secret


def load_token():
    if not os.path.exists(TOKEN_FILE):
        return None
    try:
        with open(TOKEN_FILE, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None


def save_token(data):
    config.ensure_dirs()
    existing = load_token() or {}
    existing.update(data)
    tmp = TOKEN_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(existing, fh, indent=2)
    os.replace(tmp, TOKEN_FILE)
    try:
        os.chmod(TOKEN_FILE, 0o600)
    except OSError:
        pass


# ------------------------------------------------------------------- auth
class _CallbackHandler(BaseHTTPRequestHandler):
    code = None
    error = None
    state_seen = None

    def log_message(self, *a):
        pass

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/callback":
            self.send_response(404)
            self.end_headers()
            return

        params = urllib.parse.parse_qs(parsed.query)
        _CallbackHandler.code = (params.get("code") or [None])[0]
        _CallbackHandler.error = (params.get("error") or [None])[0]
        _CallbackHandler.state_seen = (params.get("state") or [None])[0]

        body = b"<h2>Orbital: Spotify authorized.</h2><p>You can close this tab.</p>"
        if _CallbackHandler.error:
            body = b"<h2>Authorization failed.</h2>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def authorize(open_browser=True, timeout=180):
    """Run the OAuth flow. Opens a browser and waits for the redirect."""
    cid, secret = credentials()
    if not cid or not secret:
        raise NotConfigured(
            "No Spotify client id/secret. Create an app at "
            "https://developer.spotify.com/dashboard, add the redirect URI\n"
            f"    {REDIRECT_URI}\n"
            "then set ORBITAL_SPOTIFY_CLIENT_ID and ORBITAL_SPOTIFY_CLIENT_SECRET."
        )

    state = secrets.token_urlsafe(16)
    query = urllib.parse.urlencode({
        "client_id": cid,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "state": state,
    })
    url = f"{ACCOUNTS}/authorize?{query}"

    _CallbackHandler.code = None
    _CallbackHandler.error = None

    server = HTTPServer(("127.0.0.1", REDIRECT_PORT), _CallbackHandler)
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()

    log.info(f"waiting for authorization on {REDIRECT_URI}")
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    print("Open this URL if a browser did not open:")
    print(url)

    thread.join(timeout=timeout)
    server.server_close()

    if _CallbackHandler.error:
        raise SpotifyError(f"authorization denied: {_CallbackHandler.error}")
    if not _CallbackHandler.code:
        raise SpotifyError("timed out waiting for the redirect")
    if _CallbackHandler.state_seen and _CallbackHandler.state_seen != state:
        raise SpotifyError("state mismatch — possible CSRF, aborting")

    data = _token_request({
        "grant_type": "authorization_code",
        "code": _CallbackHandler.code,
        "redirect_uri": REDIRECT_URI,
    })

    save_token({
        "client_id": cid,
        "client_secret": secret,
        "access_token": data.get("access_token"),
        "refresh_token": data.get("refresh_token"),
        "expires_at": time.time() + data.get("expires_in", 3600) - 60,
        "scopes": data.get("scope", ""),
    })
    log.info("authorized")
    return True


def _token_request(payload):
    cid, secret = credentials()
    body = urllib.parse.urlencode(payload).encode("utf-8")
    basic = base64.b64encode(f"{cid}:{secret}".encode()).decode()

    req = urllib.request.Request(f"{ACCOUNTS}/api/token", data=body)
    req.add_header("Authorization", f"Basic {basic}")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise SpotifyError(f"token request failed (HTTP {exc.code}): {detail}") from exc
    except urllib.error.URLError as exc:
        raise SpotifyError(f"cannot reach Spotify: {exc.reason}") from exc


def access_token():
    """A valid access token, refreshing if needed."""
    data = load_token()
    if not data:
        raise NotConfigured(
            "Not authorized with Spotify. Run:  python -m core.spotify auth"
        )

    # A still-valid access token is usable on its own. Only the refresh path
    # needs a refresh token, so that requirement belongs there.
    if data.get("access_token") and time.time() < data.get("expires_at", 0):
        return data["access_token"]

    if not data.get("refresh_token"):
        raise NotConfigured(
            "The stored Spotify token has expired and there is no refresh "
            "token. Re-authorize with:  python -m core.spotify auth"
        )

    refreshed = _token_request({
        "grant_type": "refresh_token",
        "refresh_token": data["refresh_token"],
    })
    data["access_token"] = refreshed.get("access_token")
    data["expires_at"] = time.time() + refreshed.get("expires_in", 3600) - 60
    if refreshed.get("refresh_token"):
        data["refresh_token"] = refreshed["refresh_token"]
    save_token(data)
    return data["access_token"]


# -------------------------------------------------------------- API calls
def _call(method, path, params=None, body=None, timeout=15, raw=False):
    token = access_token()
    url = path if path.startswith("http") else API + path
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)

    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    if data:
        req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = resp.read()
            if raw:
                return payload
            if not payload:
                return {}
            return json.loads(payload.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        if exc.code == 403 and "PREMIUM" in detail.upper():
            raise PremiumRequired("this action requires Spotify Premium") from exc
        if exc.code == 404 and "NO_ACTIVE_DEVICE" in detail.upper():
            raise NoDevice("no active Spotify device — open Spotify somewhere first") from exc
        if exc.code == 401:
            raise SpotifyError("token rejected; try re-authorizing") from exc
        raise SpotifyError(f"HTTP {exc.code}: {detail[:200]}") from exc
    except urllib.error.URLError as exc:
        raise SpotifyError(f"cannot reach Spotify: {exc.reason}") from exc


def health(timeout=6):
    """(ok, detail). detail is the current track, or an error string."""
    try:
        token = access_token()
    except SpotifyError as exc:
        return False, str(exc)

    try:
        req = urllib.request.Request(f"{API}/me")
        req.add_header("Authorization", f"Bearer {token}")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            me = json.loads(resp.read().decode("utf-8"))
        return True, me.get("display_name") or me.get("id") or "authorized"
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}"
    except Exception as exc:
        return False, str(exc)


# ------------------------------------------------------------- playback
def devices():
    data = _call("GET", "/me/player/devices")
    return [
        {"id": d.get("id"), "name": d.get("name", "?"),
         "type": d.get("type", ""), "active": d.get("is_active", False),
         "volume": d.get("volume_percent")}
        for d in (data.get("devices") or [])
    ]


def transfer(device_name=None, device_id=None, play=True):
    """Move playback to a device. Required before play() if nothing is active."""
    target = device_id
    if not target:
        for d in devices():
            if device_name and device_name.lower() in d["name"].lower():
                target = d["id"]
                break
        if not target:
            for d in devices():
                if d["active"]:
                    target = d["id"]
                    break
    if not target:
        raise NoDevice("no Spotify devices available — open Spotify on a phone or PC")

    _call("PUT", "/me/player", body={"device_ids": [target], "play": play})
    return target


def now_playing():
    data = _call("GET", "/me/player/currently-playing")
    if not data or not data.get("item"):
        return None
    item = data["item"]
    artists = ", ".join(a.get("name", "") for a in item.get("artists", []))
    return {
        "name": item.get("name", "?"),
        "artists": artists,
        "album": (item.get("album") or {}).get("name", ""),
        "playing": data.get("is_playing", False),
        "progress_ms": data.get("progress_ms", 0),
        "duration_ms": item.get("duration_ms", 0),
        "url": (item.get("external_urls") or {}).get("spotify", ""),
    }


def play(uri=None, context=None, device=None):
    """Resume, or play a specific track/album/playlist URI.

    uri     — spotify:track:... etc
    context — spotify:album:... / playlist / artist
    """
    body = {}
    if uri:
        body["uris"] = [uri] if isinstance(uri, str) else list(uri)
    if context:
        body["context_uri"] = context

    params = {"device_id": device} if device else None
    _call("PUT", "/me/player/play", params=params, body=body or None)
    return True


def pause():
    _call("PUT", "/me/player/pause")
    return True


def next_track():
    _call("POST", "/me/player/next")
    return True


def previous_track():
    _call("POST", "/me/player/previous")
    return True


def set_volume(percent):
    percent = max(0, min(100, int(percent)))
    _call("PUT", "/me/player/volume", params={"volume_percent": percent})
    return percent


def seek(position_ms):
    _call("PUT", "/me/player/seek", params={"position_ms": int(position_ms)})
    return True


def shuffle(on=True):
    _call("PUT", "/me/player/shuffle", params={"state": "true" if on else "false"})
    return True


def repeat(mode="off"):
    if mode not in ("off", "track", "context"):
        raise SpotifyError("repeat must be off, track or context")
    _call("PUT", "/me/player/repeat", params={"state": mode})
    return True


# --------------------------------------------------------------- search
def search(query, kind="track", limit=8):
    data = _call("GET", "/search", params={
        "q": query, "type": kind, "limit": limit,
    })
    key = kind + "s"
    items = (data.get(key) or {}).get("items") or []
    out = []
    for item in items:
        if kind == "track":
            out.append({
                "name": item.get("name"),
                "artists": ", ".join(a.get("name", "") for a in item.get("artists", [])),
                "uri": item.get("uri"),
                "album": (item.get("album") or {}).get("name", ""),
            })
        elif kind == "album":
            out.append({
                "name": item.get("name"),
                "artists": ", ".join(a.get("name", "") for a in item.get("artists", [])),
                "uri": item.get("uri"),
            })
        elif kind == "playlist":
            out.append({
                "name": item.get("name"),
                "owner": (item.get("owner") or {}).get("display_name", ""),
                "uri": item.get("uri"),
            })
        elif kind == "artist":
            out.append({"name": item.get("name"), "uri": item.get("uri")})
    return out


def play_search(query, kind="track"):
    """Search and immediately play the first result."""
    results = search(query, kind=kind, limit=1)
    if not results:
        raise SpotifyError(f"no results for '{query}'")
    track = results[0]
    if kind == "track":
        play(uri=track["uri"])
    else:
        play(context=track["uri"])
    return track


def queue(uri):
    _call("POST", "/me/player/queue", params={"uri": uri})
    return True


def playlists(limit=20):
    data = _call("GET", "/me/playlists", params={"limit": limit})
    return [
        {"name": p.get("name"), "uri": p.get("uri"),
         "tracks": (p.get("tracks") or {}).get("total", 0)}
        for p in (data.get("items") or [])
    ]


# --------------------------------------------------------------- commands
def handle(text):
    """Chat commands. Returns (reply, meta) or None if not a Spotify command."""
    t = text.strip()
    low = t.lower()

    if low in ("/nowplaying", "/np", "/song"):
        try:
            cur = now_playing()
        except SpotifyError as exc:
            return (f"Spotify: {exc}", {"kind": "spotify", "ok": False})
        if not cur:
            return ("Nothing is playing.", {"kind": "spotify"})
        state = "playing" if cur["playing"] else "paused"
        return (f"{cur['name']} — {cur['artists']} [{state}]",
                {"kind": "spotify", "track": cur})

    if low.startswith("/play "):
        query = t[6:].strip()
        try:
            track = play_search(query)
            return (f"Playing {track['name']} — {track['artists']}",
                    {"kind": "spotify", "track": track})
        except NoDevice as exc:
            return (f"Spotify: {exc}", {"kind": "spotify", "ok": False})
        except SpotifyError as exc:
            return (f"Spotify: {exc}", {"kind": "spotify", "ok": False})

    if low in ("/pause",):
        try:
            pause()
            return ("Paused.", {"kind": "spotify"})
        except SpotifyError as exc:
            return (f"Spotify: {exc}", {"kind": "spotify", "ok": False})

    if low in ("/next", "/skip"):
        try:
            next_track()
            return ("Skipped.", {"kind": "spotify"})
        except SpotifyError as exc:
            return (f"Spotify: {exc}", {"kind": "spotify", "ok": False})

    if low in ("/prev", "/previous"):
        try:
            previous_track()
            return ("Previous track.", {"kind": "spotify"})
        except SpotifyError as exc:
            return (f"Spotify: {exc}", {"kind": "spotify", "ok": False})

    if low.startswith("/volume "):
        try:
            pct = int(low.split()[1].rstrip("%"))
        except (IndexError, ValueError):
            return ("Usage: /volume <0-100>", {"kind": "spotify"})
        try:
            set_volume(pct)
            return (f"Volume {pct}%.", {"kind": "spotify"})
        except SpotifyError as exc:
            return (f"Spotify: {exc}", {"kind": "spotify", "ok": False})

    if low in ("/devices",):
        try:
            found = devices()
        except SpotifyError as exc:
            return (f"Spotify: {exc}", {"kind": "spotify", "ok": False})
        if not found:
            return ("No Spotify devices found.", {"kind": "spotify"})
        lines = [f"  {'*' if d['active'] else ' '} {d['name']} ({d['type']})"
                 for d in found]
        return ("Devices:\n" + "\n".join(lines), {"kind": "spotify"})

    if low.startswith("/seek "):
        try:
            secs = int(low.split()[1])
        except (IndexError, ValueError):
            return ("Usage: /seek <seconds>", {"kind": "spotify"})
        try:
            seek(secs * 1000)
            return (f"Seeked to {secs}s.", {"kind": "spotify"})
        except SpotifyError as exc:
            return (f"Spotify: {exc}", {"kind": "spotify", "ok": False})

    return None


def main():
    import sys

    if len(sys.argv) < 2:
        print("usage: python -m core.spotify [auth|status|devices|now|play <query>]")
        return 1

    cmd = sys.argv[1].lower()

    if cmd == "auth":
        try:
            authorize()
            print("Authorized. Token stored in", TOKEN_FILE)
            return 0
        except SpotifyError as exc:
            print(f"Failed: {exc}")
            return 1

    if cmd == "status":
        ok, detail = health()
        print(("OK: " + str(detail)) if ok else ("Not available: " + str(detail)))
        return 0 if ok else 1

    if cmd == "devices":
        try:
            for d in devices():
                print(f"  {'*' if d['active'] else ' '} {d['name']} ({d['type']})")
            return 0
        except SpotifyError as exc:
            print(f"Failed: {exc}")
            return 1

    if cmd == "now":
        try:
            cur = now_playing()
            print(f"{cur['name']} — {cur['artists']}" if cur else "nothing playing")
            return 0
        except SpotifyError as exc:
            print(f"Failed: {exc}")
            return 1

    if cmd == "play" and len(sys.argv) > 2:
        query = " ".join(sys.argv[2:])
        try:
            track = play_search(query)
            print(f"Playing {track['name']} — {track['artists']}")
            return 0
        except SpotifyError as exc:
            print(f"Failed: {exc}")
            return 1

    print(f"unknown command '{cmd}'")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
