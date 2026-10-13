"""Engine — the local HTTP API.

Replaces the old engine.py. Differences that matter:

  * binds 127.0.0.1 by default, not 0.0.0.0
  * every /api/* request requires the bearer token
  * CORS is an explicit origin list, not "*"
  * the PowerShell bridge is token-gated, loopback-only, and can be
    disabled entirely with ORBITAL_ENABLE_SHELL=0
  * /api/chat tries the real Nucleus backend and says so when it's down,
    instead of returning a canned string
  * real telemetry from psutil, no invented fallback numbers

Run:  python -m core.engine
"""

import json
import os
import platform
import subprocess
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import auth, config, logutil, nucleus

log = logutil.get_logger("engine")

# Origins allowed to call this API from a browser. Add your workstation's
# origin here if you serve the UI from somewhere else.
ALLOWED_ORIGINS = {
    "http://127.0.0.1:5000",
    "http://localhost:5000",
    "null",  # file:// pages send Origin: null
}

_MEMORY_LOCK = threading.Lock()
# State lives in the StateStore singleton below; see store().


# ---------------------------------------------------------------- telemetry
def telemetry():
    data = {
        "node": config.node_id(),
        "platform": platform.system(),
        "python": platform.python_version(),
        "time": time.time(),
    }
    try:
        import psutil

        vm = psutil.virtual_memory()
        data.update(
            {
                "cpu_pct": psutil.cpu_percent(interval=None),
                "ram_pct": vm.percent,
                "ram_used_gb": round(vm.used / (1024**3), 2),
                "ram_total_gb": round(vm.total / (1024**3), 2),
                "disk": {},
            }
        )
        for part in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(part.mountpoint)
                data["disk"][part.mountpoint] = {
                    "free_gb": round(usage.free / (1024**3), 2),
                    "pct": usage.percent,
                }
            except (PermissionError, OSError):
                continue
    except ImportError:
        data["psutil"] = "not installed"

    ok, detail = nucleus.health(timeout=1.5)
    data["nucleus"] = {
        "reachable": ok,
        "endpoint": config.OLLAMA_BASE,
        "models": detail if ok else [],
        "error": None if ok else detail,
    }

    try:
        from . import gpu

        data["gpu"] = gpu.summary()
    except Exception as exc:  # never let telemetry fail on a probe
        data["gpu"] = {"detected": False, "error": str(exc)}

    return data


# -------------------------------------------------------------- shell bridge
def run_shell(cmd):
    """PowerShell on Windows, /bin/sh elsewhere. Token-gated at the route."""
    if not config.SHELL_ENABLED:
        return {"error": "shell bridge disabled (ORBITAL_ENABLE_SHELL=0)"}

    if os.name == "nt":
        argv = ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd]
    else:
        argv = ["/bin/sh", "-c", cmd]

    try:
        res = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=config.SHELL_TIMEOUT,
            cwd=config.BASE_DIR,
        )
    except subprocess.TimeoutExpired:
        return {"error": f"timed out after {config.SHELL_TIMEOUT}s"}
    except FileNotFoundError as exc:
        return {"error": f"interpreter not found: {exc}"}

    return {
        "stdout": (res.stdout or "").strip(),
        "stderr": (res.stderr or "").strip(),
        "exit_code": res.returncode,
    }


# ------------------------------------------------------------------- state
# Conversation state lives in an OOSTATE.BIN image (see core/oostate.py).
# The old chat_memory.json was a flat list with no ids and no ordering, so
# two nodes that both talked offline could not be reconciled. The state store
# gives every message an id and a Lamport stamp, which is what makes merge
# commutative and idempotent.
_STORE = None


def store():
    """Lazy singleton for the live state."""
    global _STORE
    if _STORE is None:
        from . import statestore

        s = statestore.StateStore()
        loaded = s.load(missing_ok=True)
        if loaded:
            log.info(f"state loaded: {len(s.messages)} message(s) from {s.path}")
        else:
            log.info(f"no existing state at {s.path}; starting fresh")
        _STORE = s
    return _STORE


def save_state():
    with _MEMORY_LOCK:
        try:
            size = store().save()
            return size
        except Exception as exc:
            log.error(f"could not save state: {exc}")
            return None


def history():
    with _MEMORY_LOCK:
        return store().history()


def history_records(limit=None):
    with _MEMORY_LOCK:
        recs = store().ordered_messages()
    return recs[-limit:] if limit else recs


# --------------------------------------------------------------- dispatch
def handle_prompt(prompt, use_llm=True):
    """Route a prompt. Returns (text, meta)."""
    p = prompt.strip()

    if p.startswith("/ps ") or p.startswith("cmd: "):
        return _shell_reply(p, 4 if p.startswith("/ps ") else 5)
    if p.startswith("/cmd "):
        return _shell_reply(p, 5)
    if p.lower() in ("/whoami", "/identity", "/about"):
        from . import nucleus as nuc_mod

        ok, models = nuc_mod.health(timeout=2)
        lines = [
            "I am Orbital.",
            "",
            "A local-first assistant running entirely on your own hardware.",
            "Nothing you say leaves this machine.",
            "",
            "Components:",
            "  Nucleus  - the reasoning core (this conversation)",
            "  Nebula   - the image engine",
            "  Mesh     - links this instance to your other devices",
            "",
            f"Reasoning runs on: {config.MODEL}",
        ]
        if ok and models:
            lines.append(f"Models available: {', '.join(models[:6])}")
        else:
            lines.append("Text backend is not reachable right now.")
        lines.append("")
        lines.append(
            "The model underneath is not mine - I am the system around it."
        )
        return ("\n".join(lines), {"kind": "identity"})

    if p.lower() in ("/health", "/status"):
        t = telemetry()
        nuc = t["nucleus"]
        if nuc["reachable"]:
            detail = f"reachable, models: {', '.join(nuc['models']) or 'none'}"
        else:
            detail = f"UNREACHABLE — {nuc['error']}"
        return (
            f"Engine OK on {config.ENGINE_HOST}:{config.ENGINE_PORT}\n"
            f"Nucleus ({config.OLLAMA_BASE}): {detail}",
            {"kind": "status"},
        )

    # Device and service commands are handled locally, before the LLM.
    # Each module returns None when the text is not one of its commands.
    for module_name in ("hue", "spotify", "camera"):
        try:
            module = __import__(f"core.{module_name}", fromlist=["handle"])
            handled = module.handle(p)
            if handled is not None:
                return handled
        except Exception as exc:
            log.warn(f"{module_name} handler failed: {exc}")
            return (f"{module_name}: {exc}",
                    {"kind": module_name, "ok": False, "error": str(exc)})

    if not use_llm:
        return ("(LLM disabled for this request)", {"kind": "echo"})

    try:
        with _MEMORY_LOCK:
            convo = store().history(limit=20)
        convo.append({"role": "user", "content": p})

        # Tool-aware chat: the model can read the system, generate images,
        # control lights and so on. Falls back to plain chat automatically
        # for models that do not support tools.
        calls = []

        def _note(name, args, result, ok):
            calls.append({"name": name, "args": args, "ok": ok})

        reply, calls = nucleus.chat_with_tools(convo, on_tool=_note)

        meta = {"kind": "llm", "model": config.MODEL}
        if calls:
            meta["tools"] = calls
        return (reply, meta)
    except nucleus.NucleusError as exc:
        # Honest failure, not a fabricated success.
        return (
            f"Nucleus is not reachable, so this prompt was not processed.\n"
            f"Detail: {exc}\n"
            f"Start a backend on {config.OLLAMA_BASE} (ollama serve), or use "
            f"/ps, /cmd, /health, /telemetry.",
            {"kind": "error", "error": str(exc)},
        )


def _shell_reply(p, offset):
    result = run_shell(p[offset:])
    if "error" in result:
        return (f"[shell error] {result['error']}", {"kind": "shell", "ok": False})
    out = result["stdout"] or result["stderr"] or "(no output)"
    return (out, {"kind": "shell", "ok": result["exit_code"] == 0, **result})


# ---------------------------------------------------------------- HTTP
class Handler(BaseHTTPRequestHandler):
    server_version = "OrbitalEngine/2"

    def log_message(self, fmt, *args):
        log.info(f"{self.address_string()} {fmt % args}")

    # -- helpers
    def _origin(self):
        origin = self.headers.get("Origin")
        return origin if origin in ALLOWED_ORIGINS else None

    def _cors(self):
        origin = self._origin()
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def _authed(self):
        # Three ways in, in order of preference:
        #   1. a logged-in session cookie, when accounts are enabled
        #   2. a bearer token, for scripts and the file:// UI
        #   3. a ?token= query parameter, for convenience in a browser
        from . import accounts

        cookie_token = self._cookies().get("orbital_session")
        if cookie_token and accounts.session_user(cookie_token):
            return True

        header = self.headers.get("Authorization", "")
        token = header[7:] if header.startswith("Bearer ") else ""
        if not token:
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            token = q.get("token", [""])[0]

        if auth.check(token):
            return True

        self._json(401, {"error": "missing or invalid token"})
        return False

    def _json(self, code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    # -- verbs
    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    LOGIN_HTML = """<!DOCTYPE html><html><head><meta charset="utf-8">
<title>Orbital - sign in</title>
<style>
 body{margin:0;min-height:100vh;background:#04060B;color:#F0F4FF;
      font:15px/1.6 "Segoe UI",system-ui,sans-serif;
      display:flex;align-items:center;justify-content:center}
 .card{width:340px;padding:32px;border-radius:22px;
       background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.09);
       backdrop-filter:blur(20px)}
 h1{font-size:22px;margin:0 0 4px;font-weight:800;letter-spacing:-.02em}
 p.sub{color:#5A6786;font-size:12px;margin:0 0 22px}
 label{display:block;font-size:11px;text-transform:uppercase;
       letter-spacing:.14em;color:#5A6786;margin:14px 0 6px}
 input{width:100%;box-sizing:border-box;padding:11px 14px;border-radius:999px;
       background:rgba(0,0,0,.28);border:1px solid rgba(255,255,255,.09);
       color:#F0F4FF;font:14px inherit;outline:none}
 input:focus{border-color:rgba(139,92,246,.6)}
 button{width:100%;margin-top:20px;padding:12px;border:none;border-radius:999px;
        background:linear-gradient(115deg,#8B5CF6,#FF3D9A);color:#fff;
        font:600 14px inherit;cursor:pointer}
 .err{margin-top:14px;color:#FECDD3;font-size:13px;display:none}
 .err.on{display:block}
</style></head><body>
<form class="card" method="POST" action="/login">
 <h1>Orbital</h1>
 <p class="sub">Sign in to continue</p>
 <label for="u">Username</label>
 <input id="u" name="username" autocomplete="username" autofocus>
 <label for="p">Password</label>
 <input id="p" name="password" type="password" autocomplete="current-password">
 <button type="submit">Sign in</button>
 <div class="err __ERR__">__MSG__</div>
</form></body></html>"""

    def _login_page(self, message="", error=False):
        html = self.LOGIN_HTML.replace("__MSG__", message)
        if not error:
            html = html.replace('class="err __ERR__"', 'class="err"')
        else:
            html = html.replace("__ERR__", "on")
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _cookies(self):
        raw = self.headers.get("Cookie", "")
        out = {}
        for part in raw.split(";"):
            if "=" in part:
                k, _, v = part.partition("=")
                out[k.strip()] = v.strip()
        return out

    def _session_ok(self):
        """True if accounts are off, or a valid session cookie is present."""
        from . import accounts

        if not accounts.enabled():
            return True
        return accounts.session_user(self._cookies().get("orbital_session")) is not None

    def _serve_ui(self):
        """Serve the interface, with the token already in it.

        Why this exists: opening the UI as a file:// page means every request
        is cross-origin, which needs CORS, and the user has to copy a token by
        hand. Served from here it is same-origin, the token is injected, and
        there is nothing to paste.

        A page on a *different* origin still cannot read this response, so
        nothing about the token's protection changes.
        """
        import glob

        candidates = [
            os.path.join(config.GUI_DIR, "orbital.html"),
            os.path.join(config.GUI_DIR, "workstation.html"),
            os.path.join(config.BASE_DIR, "orbital.html"),
        ]
        # Fall back to whatever single-file UI is around.
        for pattern in ("orbital.html", "workstation.html"):
            candidates.extend(glob.glob(os.path.join(config.BASE_DIR, "**", pattern),
                                        recursive=True))

        path = next((c for c in candidates if os.path.exists(c)), None)
        if not path:
            self._json(404, {
                "error": "no interface file found",
                "looked_in": candidates[:4],
                "hint": "put orbital.html next to start.py, or in gui/",
            })
            return

        try:
            with open(path, "r", encoding="utf-8") as fh:
                html = fh.read()
        except OSError as exc:
            self._json(500, {"error": f"could not read {path}: {exc}"})
            return

        # Inject the token so the page needs no manual setup.
        token = auth.get_token()
        inject = (
            "<script>window.ORBITAL_TOKEN = %s; window.ORBITAL_SAME_ORIGIN = true;</script>"
            % json.dumps(token)
        )
        if "</head>" in html:
            html = html.replace("</head>", inject + "\n</head>", 1)
        else:
            html = inject + html

        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        route = urllib.parse.urlparse(self.path).path

        if route in ("/", "/ui", "/index.html"):
            if not self._session_ok():
                self._login_page()
                return
            self._serve_ui()
            return

        if route == "/logout":
            from . import accounts

            accounts.logout(self._cookies().get("orbital_session"))
            self.send_response(302)
            self.send_header("Set-Cookie",
                             "orbital_session=; Path=/; Max-Age=0; SameSite=Strict")
            self.send_header("Location", "/")
            self.end_headers()
            return

        if route == "/api/ping":
            self._json(200, {"ok": True, "node": config.node_id()})
            return
        if not self._authed():
            return

        if route == "/api/telemetry":
            self._json(200, telemetry())
        elif route == "/api/history":
            self._json(200, {"history": history()})
        elif route == "/api/image":
            from . import nebula

            name = urllib.parse.parse_qs(
                urllib.parse.urlparse(self.path).query
            ).get("name", [""])[0]
            # Path traversal guard: only a bare filename, no separators.
            if not name or name != os.path.basename(name) or ".." in name:
                self._json(400, {"error": "bad image name"})
                return
            path = os.path.join(nebula.OUTPUT_DIR, name)
            if not os.path.exists(path):
                self._json(404, {"error": "no such image"})
                return
            with open(path, "rb") as fh:
                data = fh.read()
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(data)))
            self._cors()
            self.end_headers()
            self.wfile.write(data)
        elif route == "/api/video/file":
            from . import video as video_mod

            name = urllib.parse.parse_qs(
                urllib.parse.urlparse(self.path).query
            ).get("name", [""])[0]
            if not name or name != os.path.basename(name) or ".." in name:
                self._json(400, {"error": "bad filename"})
                return
            path = os.path.join(video_mod.OUTPUT_DIR, name)
            if not os.path.exists(path):
                self._json(404, {"error": "no such video"})
                return
            with open(path, "rb") as fh:
                data = fh.read()
            ctype = "video/webm" if name.endswith(".webm") else "video/webm"
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self._cors()
            self.end_headers()
            self.wfile.write(data)

        elif route == "/api/draw/status":
            from . import jobs

            self._json(200, {"jobs": jobs.list_jobs(limit=50)})
        elif route.startswith("/api/draw/"):
            from . import jobs

            job_id = route.rsplit("/", 1)[-1]
            job = jobs.get(job_id)
            if not job:
                self._json(404, {"error": "no such job"})
                return
            self._json(200, job)
        elif route == "/api/spotify/now":
            from . import spotify

            try:
                self._json(200, spotify.now_playing() or {})
            except spotify.SpotifyError as exc:
                self._json(200, {"error": str(exc), "name": None})
        elif route == "/api/spotify/devices":
            from . import spotify

            try:
                self._json(200, {"devices": spotify.devices()})
            except spotify.SpotifyError as exc:
                self._json(503, {"error": str(exc), "devices": []})
        elif route == "/api/hue/lights":
            from . import hue

            try:
                self._json(200, {"lights": hue.lights()})
            except hue.HueError as exc:
                self._json(503, {"error": str(exc), "lights": []})
        elif route == "/api/tools":
            from . import tools

            self._json(200, {
                "tools": tools.names(),
                "count": len(tools.names()),
                "preamble": tools.capability_preamble(),
            })
        elif route == "/api/integrations":
            report = {}
            for name in ("hue", "spotify", "camera"):
                try:
                    module = __import__(f"core.{name}", fromlist=["health"])
                    ok, detail = module.health(timeout=4)
                    report[name] = {"available": ok, "detail": detail}
                except Exception as exc:
                    report[name] = {"available": False,
                                    "detail": f"{type(exc).__name__}: {exc}"}
            self._json(200, report)

        elif route == "/api/captures":
            from . import camera as camera_mod

            name = urllib.parse.parse_qs(
                urllib.parse.urlparse(self.path).query
            ).get("name", [""])[0]
            if not name or name != os.path.basename(name) or ".." in name:
                self._json(400, {"error": "bad filename"})
                return
            path = os.path.join(camera_mod.CAPTURE_DIR, name)
            if not os.path.exists(path):
                self._json(404, {"error": "no such capture"})
                return
            with open(path, "rb") as fh:
                data = fh.read()
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(data)))
            self._cors()
            self.end_headers()
            self.wfile.write(data)

        elif route == "/api/backends":
            from . import backends as backends_mod

            deep = urllib.parse.parse_qs(
                urllib.parse.urlparse(self.path).query
            ).get("deep", ["0"])[0] == "1"
            self._json(
                200,
                {"backends": backends_mod.status_report(deep=deep),
                 "totals": backends_mod.totals()},
            )
        elif route == "/api/nebula":
            from . import nebula

            ok, detail = nebula.health(timeout=3)
            self._json(
                200,
                {
                    "reachable": ok,
                    "endpoint": nebula.COMFY_BASE,
                    "checkpoints": detail if ok else [],
                    "error": None if ok else detail,
                    "output_dir": nebula.OUTPUT_DIR,
                },
            )
        elif route == "/api/logs":
            name = urllib.parse.parse_qs(
                urllib.parse.urlparse(self.path).query
            ).get("name", ["engine"])[0]
            if not name.replace("-", "").replace("_", "").isalnum():
                self._json(400, {"error": "bad log name"})
                return
            path = os.path.join(config.LOG_DIR, f"{name}.log")
            self._json(200, {"name": name, "lines": logutil.tail(path)})
        elif route == "/api/models":
            ok, detail = nucleus.health(timeout=3)
            self._json(200, {"reachable": ok, "models": detail if ok else [], "error": None if ok else detail})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        route = urllib.parse.urlparse(self.path).path

        # The login form posts here, and cannot require a token - the user
        # does not have one yet.
        if route == "/login":
            from . import accounts

            length = int(self.headers.get("Content-Length", 0) or 0)
            if length > 8192:
                self._json(413, {"error": "payload too large"})
                return
            raw = self.rfile.read(length).decode("utf-8", errors="replace")
            form = urllib.parse.parse_qs(raw)
            username = (form.get("username") or [""])[0]
            password = (form.get("password") or [""])[0]

            token = accounts.login(username, password)
            if not token:
                self._login_page(
                    "Incorrect username or password. "
                    "Too many attempts will lock the account temporarily.",
                    error=True,
                )
                return

            self.send_response(302)
            self.send_header(
                "Set-Cookie",
                f"orbital_session={token}; Path=/; HttpOnly; SameSite=Strict",
            )
            self.send_header("Location", "/")
            self.end_headers()
            return

        if not self._authed():
            return

        length = int(self.headers.get("Content-Length", 0) or 0)
        if length > 1_000_000:
            self._json(413, {"error": "payload too large"})
            return

        raw = self.rfile.read(length).decode("utf-8", errors="replace") if length else ""
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            self._json(400, {"error": "invalid JSON"})
            return

        if route == "/api/chat":
            prompt = str(payload.get("prompt", "")).strip()
            if not prompt:
                self._json(400, {"error": "empty prompt"})
                return
            use_llm = bool(payload.get("llm", True))
            text, meta = handle_prompt(prompt, use_llm=use_llm)
            with _MEMORY_LOCK:
                st = store()
                st.add_message("user", prompt)
                st.add_message("assistant", text)
            size = save_state()
            if size is None:
                meta["state_saved"] = False
            self._json(200, {"response": text, "meta": meta})

        elif route == "/api/draw":
            from . import jobs, nebula

            prompt = str(payload.get("prompt", "")).strip()
            if not prompt:
                self._json(400, {"error": "empty prompt"})
                return

            from . import backends as backends_mod

            target = None
            if payload.get("backend"):
                target = backends_mod.get(payload["backend"])
                if target is None:
                    self._json(400, {"error": f"unknown backend '{payload['backend']}'"})
                    return
                ok, detail = nebula.health(timeout=3, base=target.url)
            else:
                target = backends_mod.choose(kind="image")
                ok, detail = (target is not None), (
                    "no reachable image-capable backend" if target is None
                    else "ok"
                )

            if not ok:
                self._json(
                    503,
                    {
                        "error": "no image backend available",
                        "detail": detail,
                        "hint": (
                            "start ComfyUI, or add nodes with "
                            "ORBITAL_BACKENDS=name=http://host:8188,..."
                        ),
                        "backends": backends_mod.status_report(),
                    },
                )
                return

            params = {}
            for key in ("negative", "checkpoint", "sampler", "scheduler", "loras"):
                if key in payload:
                    params[key] = payload[key]
            for key in ("width", "height", "steps", "seed", "batch_size"):
                if key in payload:
                    try:
                        params[key] = int(payload[key])
                    except (TypeError, ValueError):
                        self._json(400, {"error": f"{key} must be an integer"})
                        return
            if "cfg" in payload:
                try:
                    params["cfg"] = float(payload["cfg"])
                except (TypeError, ValueError):
                    self._json(400, {"error": "cfg must be a number"})
                    return

            job = jobs.submit(prompt, backend=payload.get("backend"), **params)
            self._json(
                202,
                {
                    "job_id": job["id"],
                    "status": job["status"],
                    "poll": f"/api/draw/{job['id']}",
                    "backend": job.get("backend"),
                },
            )

        elif route == "/api/draw/status":
            from . import jobs

            self._json(200, {"jobs": jobs.list_jobs(limit=50)})

        elif route.startswith("/api/draw/"):
            from . import jobs

            job_id = route.rsplit("/", 1)[-1]
            job = jobs.get(job_id)
            if not job:
                self._json(404, {"error": "no such job"})
                return
            self._json(200, job)

        elif route == "/api/video":
            from . import jobs, video as video_mod

            prompt = str(payload.get("prompt", "")).strip()
            if not prompt:
                self._json(400, {"error": "empty prompt"})
                return

            from . import backends as backends_mod

            target = None
            if payload.get("backend"):
                target = backends_mod.get(payload["backend"])
                if target is None:
                    self._json(400, {"error": f"unknown backend '{payload['backend']}'"})
                    return
                ok, detail = video_mod.health(timeout=4, base=target.url)
            else:
                target = backends_mod.choose(kind="video")
                ok, detail = (target is not None), (
                    "no reachable video-capable backend" if target is None
                    else "ok"
                )

            if not ok:
                self._json(
                    503,
                    {
                        "error": "no video backend available",
                        "detail": detail,
                        "hint": (
                            "Wan 2.2 needs three files in ComfyUI: a diffusion model "
                            "in models/diffusion_models/, a text encoder (umt5_xxl) in "
                            "models/text_encoders/, and wan2.2_vae in models/vae/. "
                            "See the README."
                        ),
                        "backends": backends_mod.status_report(),
                    },
                )
                return

            mode = payload.get("mode", "t2v")
            if mode not in ("t2v", "i2v"):
                self._json(400, {"error": "mode must be t2v or i2v"})
                return

            params = {"mode": mode}
            for key in ("negative", "unet", "clip", "vae", "format"):
                if key in payload:
                    params[key] = payload[key]
            if mode == "i2v":
                if not payload.get("image_name"):
                    self._json(400, {"error": "i2v requires image_name"})
                    return
                params["image_name"] = payload["image_name"]
            for key in ("width", "height", "length", "fps", "steps", "seed"):
                if key in payload:
                    try:
                        params[key] = int(payload[key])
                    except (TypeError, ValueError):
                        self._json(400, {"error": f"{key} must be an integer"})
                        return
            if "cfg" in payload:
                try:
                    params["cfg"] = float(payload["cfg"])
                except (TypeError, ValueError):
                    self._json(400, {"error": "cfg must be a number"})
                    return
            if "loras" in payload:
                params["loras"] = payload["loras"]

            job = jobs.submit(prompt, kind="video",
                              backend=payload.get("backend"), **params)
            self._json(
                202,
                {
                    "job_id": job["id"],
                    "kind": "video",
                    "status": job["status"],
                    "poll": f"/api/draw/{job['id']}",
                    "backend": job.get("backend"),
                    "warning": (
                        "video generation is slow — expect minutes, not seconds. "
                        "A 5s 720p clip is roughly 9 minutes on an RTX 4090."
                    ),
                },
            )

        elif route == "/api/video/status":
            from . import video as video_mod

            ok, detail = video_mod.health(timeout=4)
            self._json(
                200,
                {
                    "reachable": ok,
                    "models": detail if ok else None,
                    "error": None if ok else detail,
                    "output_dir": video_mod.OUTPUT_DIR,
                    "defaults": {
                        "resolution": f"{video_mod.DEFAULT_WIDTH}x{video_mod.DEFAULT_HEIGHT}",
                        "frames": video_mod.DEFAULT_LENGTH,
                        "fps": video_mod.DEFAULT_FPS,
                        "steps": video_mod.DEFAULT_STEPS,
                    },
                },
            )

        elif route == "/api/state/export":

            blob = oostate.pack(store().to_dict())
            body = blob
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Disposition", 'attachment; filename="OOSTATE.BIN"')
            self.send_header("Content-Length", str(len(body)))
            self._cors()
            self.end_headers()
            self.wfile.write(body)

        elif route == "/api/state/import":
            from . import oostate

            blob = payload.get("blob")
            if not blob:
                self._json(400, {"error": "missing 'blob' (base64 OOSTATE.BIN)"})
                return
            try:
                import base64

                raw = base64.b64decode(blob, validate=True)
            except Exception as exc:
                self._json(400, {"error": f"blob is not valid base64: {exc}"})
                return

            strategy = payload.get("strategy", "merge")
            if strategy not in ("merge", "replace", "keep"):
                self._json(400, {"error": "strategy must be merge, replace or keep"})
                return

            before = len(store().messages)
            try:
                report = store().import_bytes(raw, strategy=strategy)
            except oostate.ChecksumError as exc:
                self._json(400, {"error": f"checksum mismatch: {exc}"})
                return
            except oostate.VersionError as exc:
                self._json(409, {"error": f"version conflict: {exc}"})
                return
            except oostate.FormatError as exc:
                self._json(400, {"error": f"malformed image: {exc}"})
                return

            save_state()
            after = len(store().messages)
            self._json(200, {"report": report, "before": before, "after": after})

        elif route.startswith("/api/spotify/"):
            from . import spotify

            action = route.rsplit("/", 1)[-1]
            try:
                if action == "play":
                    spotify.play(uri=payload.get("uri"),
                                 context=payload.get("context"))
                    result = {"ok": True, "action": "play"}
                elif action == "pause":
                    spotify.pause()
                    result = {"ok": True, "action": "pause"}
                elif action == "next":
                    spotify.next_track()
                    result = {"ok": True, "action": "next"}
                elif action == "previous":
                    spotify.previous_track()
                    result = {"ok": True, "action": "previous"}
                elif action == "shuffle":
                    spotify.shuffle(True)
                    result = {"ok": True, "action": "shuffle"}
                elif action == "repeat":
                    spotify.repeat("context")
                    result = {"ok": True, "action": "repeat"}
                elif action == "seek":
                    try:
                        pos = int(payload.get("position_ms", 0))
                    except (TypeError, ValueError):
                        self._json(400, {"error": "position_ms must be an integer"})
                        return
                    spotify.seek(pos)
                    result = {"ok": True, "action": "seek", "position_ms": pos}
                elif action == "volume":
                    try:
                        pct = int(payload.get("volume_percent", 50))
                    except (TypeError, ValueError):
                        self._json(400, {"error": "volume_percent must be an integer"})
                        return
                    spotify.set_volume(pct)
                    result = {"ok": True, "action": "volume", "volume_percent": pct}
                else:
                    self._json(404, {"error": f"unknown spotify action '{action}'"})
                    return
                self._json(200, result)
            except spotify.NoDevice as exc:
                self._json(409, {"error": str(exc), "hint": "open Spotify on a device"})
            except spotify.PremiumRequired as exc:
                self._json(403, {"error": str(exc)})
            except spotify.SpotifyError as exc:
                self._json(503, {"error": str(exc)})

        elif route.startswith("/api/hue/"):
            from . import hue

            action = route.rsplit("/", 1)[-1]
            try:
                if action == "set":
                    name = payload.get("name") or payload.get("id")
                    if not name:
                        self._json(400, {"error": "name or id is required"})
                        return
                    hue.set_light(
                        str(name),
                        on=payload.get("on"),
                        brightness_pct=payload.get("brightness_pct"),
                        hue=payload.get("hue"),
                        saturation=payload.get("saturation"),
                        color_temp=payload.get("color_temp"),
                    )
                    self._json(200, {"ok": True, "light": str(name)})
                elif action == "all":
                    changed = hue.all_lights(on=payload.get("on"),
                                             brightness_pct=payload.get("brightness_pct"))
                    self._json(200, {"ok": True, "changed": changed})
                else:
                    self._json(404, {"error": f"unknown hue action '{action}'"})
            except hue.HueError as exc:
                self._json(503, {"error": str(exc)})

        elif route == "/api/shell":
            if not config.SHELL_ENABLED:
                self._json(403, {"error": "shell bridge disabled"})
                return
            cmd = str(payload.get("cmd", "")).strip()
            if not cmd:
                self._json(400, {"error": "empty cmd"})
                return
            self._json(200, run_shell(cmd))
        else:
            self._json(404, {"error": "not found"})


def serve():
    config.ensure_dirs()
    store()  # load state from OOSTATE.BIN at startup
    token = auth.get_token()
    ok, detail = nucleus.health(timeout=2)

    log.info(f"Engine listening on http://{config.ENGINE_HOST}:{config.ENGINE_PORT}")
    log.info(f"Token file: {config.TOKEN_FILE}")
    if ok:
        log.info(f"Nucleus reachable at {config.OLLAMA_BASE} — models: {detail or 'none'}")
    else:
        log.warn(f"Nucleus NOT reachable at {config.OLLAMA_BASE} ({detail}); chat will report this")

    from . import jobs, nebula

    from . import backends as backends_mod

    pool = backends_mod.registry()
    if len(pool) > 1:
        log.info(f"Backend pool: {len(pool)} node(s)")
    for b in pool:
        status = b.probe(force=True)
        if status["reachable"]:
            cap = b.capability(force=True)
            kinds = ", ".join(
                k for k, v in (("image", cap["image"]), ("video", cap["video"])) if v
            ) or "nothing"
            log.info(
                f"  {b.name:14s} {b.url:34s} up — load {status['load']}, "
                f"can do: {kinds}"
            )
        else:
            log.warn(f"  {b.name:14s} {b.url:34s} DOWN — {status['error']}")

    jobs.start_worker()

    if not any(b.probe()["reachable"] for b in pool):
        log.warn("No ComfyUI backend reachable; /api/draw and /api/video will 503")

    httpd = ThreadingHTTPServer((config.ENGINE_HOST, config.ENGINE_PORT), Handler)
    httpd.daemon_threads = True
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        log.info("shutting down")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    serve()
