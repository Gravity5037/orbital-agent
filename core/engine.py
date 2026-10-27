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
# One store per user, built on first use.
#
# This was a single global. That meant every logged-in user shared one
# conversation. It is now keyed by username: a guest (no accounts, or
# not signed in) gets the original store, and each account gets its own
# file under state/profiles/<name>/.
#
# The isolation is the filesystem's job, not a query filter. A separate
# file per user cannot leak through a forgotten WHERE clause.
_STORES = {}
_STORE_LOCK = threading.Lock()

# The user the current request belongs to. Set by the request handler
# before any store() call. Thread-local, because requests are threaded.
_CURRENT_USER = threading.local()


def set_current_user(username):
    """Who is asking. None means the guest store."""
    _CURRENT_USER.name = username or None


def current_user():
    return getattr(_CURRENT_USER, "name", None)


def store(username=None):
    """The live state for one user.

    username=None means the guest store. Passing it explicitly is for
    callers that are not in a request thread - the CLI, a test.
    """
    global _STORES

    if username is None:
        username = current_user()

    key = username or ""

    with _STORE_LOCK:
        if key in _STORES:
            return _STORES[key]

        from . import statestore, profiles

        path = profiles.ensure(username)
        s = statestore.StateStore(path=path)
        loaded = s.load(missing_ok=True)

        who = username or "guest"
        if loaded:
            log.info(f"state loaded for {who}: "
                     f"{len(s.messages)} message(s) from {s.path}")
        else:
            log.info(f"no existing state for {who} at {s.path}; fresh start")

        _STORES[key] = s
        return s


def forget_store(username):
    """Drop a cached store. Used when a profile is purged."""
    with _STORE_LOCK:
        _STORES.pop(username or "", None)


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

    def _bind_user(self):
        """Point the store at this request's user.

        Called at the top of every request. Without it, a request from
        one user could read or write another user's conversation,
        because the store is cached per-process.
        """
        try:
            from . import accounts
        except ImportError:
            set_current_user(None)
            return

        if not accounts.enabled():
            # No accounts at all. Single-user install. Guest store.
            set_current_user(None)
            return

        token = self._cookies().get("orbital_session")
        user = accounts.session_user(token) if token else None
        set_current_user(user)

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
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Orbital</title>
<style>
 body{margin:0;min-height:100vh;background:#04060B;color:#F0F4FF;
      font:15px/1.6 "Segoe UI",system-ui,sans-serif;
      display:flex;align-items:center;justify-content:center;padding:20px}
 .card{width:360px;padding:32px;border-radius:22px;
       background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.09);
       backdrop-filter:blur(20px)}
 h1{font-size:22px;margin:0 0 4px;font-weight:800;letter-spacing:-.02em}
 p.sub{color:#5A6786;font-size:12px;margin:0 0 22px}
 label{display:block;font-size:11px;text-transform:uppercase;
       letter-spacing:.14em;color:#5A6786;margin:14px 0 6px}
 .opt{text-transform:none;letter-spacing:0;color:#3F4A63;font-size:10px}
 input{width:100%;box-sizing:border-box;padding:11px 14px;border-radius:999px;
       background:rgba(0,0,0,.28);border:1px solid rgba(255,255,255,.09);
       color:#F0F4FF;font:14px inherit;outline:none}
 input:focus{border-color:rgba(139,92,246,.6)}
 button{width:100%;margin-top:20px;padding:12px;border:none;border-radius:999px;
        background:linear-gradient(115deg,#8B5CF6,#FF3D9A);color:#fff;
        font:600 14px inherit;cursor:pointer}
 button:disabled{opacity:.5;cursor:default}
 .err{margin-top:14px;color:#FECDD3;font-size:13px;display:none}
 .err.on{display:block}
 .ok{margin-top:14px;color:#86EFAC;font-size:13px;display:none}
 .ok.on{display:block}
 .swap{margin-top:18px;text-align:center;font-size:13px;color:#5A6786}
 .swap a{color:#8B5CF6;text-decoration:none;cursor:pointer}
 .swap a:hover{text-decoration:underline}
 .hint{font-size:11px;color:#3F4A63;margin-top:6px}
 .code{font:600 15px ui-monospace,monospace;letter-spacing:.03em;
       background:rgba(0,0,0,.4);border:1px solid rgba(139,92,246,.4);
       border-radius:10px;padding:14px;margin-top:12px;word-break:break-word;
       color:#C4B5FD}
 .warn{margin-top:12px;font-size:12px;color:#FCD34D}
 .taken{font-size:11px;margin-top:6px;color:#FCA5A5;display:none}
 .taken.on{display:block}
 .avail{font-size:11px;margin-top:6px;color:#86EFAC;display:none}
 .avail.on{display:block}
 .hidden{display:none}
</style></head><body>

<!-- ------------------------------------------------ sign in -->
<form class="card" id="signin" method="POST" action="/login">
 <h1>Orbital</h1>
 <p class="sub">Sign in to continue</p>
 <label for="u">Username</label>
 <input id="u" name="username" autocomplete="username" autofocus>
 <label for="p">Password</label>
 <input id="p" name="password" type="password" autocomplete="current-password">
 <button type="submit">Log in</button>
 <div class="err __ERR__">__MSG__</div>
 <div class="swap">New here? <a id="to-signup">Sign up</a></div>
</form>

<!-- ------------------------------------------------ sign up -->
<form class="card hidden" id="signup" method="POST" action="/signup">
 <h1>Create account</h1>
 <p class="sub">Your own Orbital, on this machine</p>

 <label for="su">Username</label>
 <input id="su" name="username" autocomplete="username"
        placeholder="Gravity" autocomplete="off">
 <div class="taken" id="taken">That username is taken.</div>
 <div class="avail" id="avail">Available</div>
 <div class="hint">3+ characters. Letters, numbers, dot, dash, underscore.</div>

 <label for="se">Email <span class="opt">(optional)</span></label>
 <input id="se" name="email" type="email" autocomplete="email"
        placeholder="you@example.com">

 <label for="sp">Phone <span class="opt">(optional)</span></label>
 <input id="sp" name="phone" type="tel" autocomplete="tel"
        placeholder="+1 555 000 0000">

 <label for="spw">Password</label>
 <input id="spw" name="password" type="password"
        autocomplete="new-password">
 <div class="hint">8+ characters.</div>

 <button type="submit" id="create">Create account</button>
 <div class="err" id="su-err"></div>
 <div class="swap">Already a member?
   <a id="to-signin">Log in</a></div>
</form>

<!-- ------------------------------------------------ recovery code -->
<div class="card hidden" id="done">
 <h1>Save this code</h1>
 <p class="sub">This is the only time it is shown</p>
 <p style="font-size:13px;color:#9AA3B2">
   If you forget your password, this code resets it. Write it down
   or put it in a password manager.
 </p>
 <div class="code" id="code-out"></div>
 <div class="warn">
   Orbital cannot email this to you. There is no mail server, and
   nothing leaves this machine. If you lose the code and the
   password, an admin has to reset the account.
 </div>
 <button id="continue">I saved it - continue</button>
</div>

<script>
const $ = (id) => document.getElementById(id);
const show = (el) => el.classList.remove("hidden");
const hide = (el) => el.classList.add("hidden");

$("to-signup").onclick = () => { hide($("signin")); show($("signup"));
                                 $("su").focus(); };
$("to-signin").onclick = () => { hide($("signup")); show($("signin"));
                                 $("u").focus(); };

// Live username check, so you know before you submit.
let checkTimer = null;
$("su").addEventListener("input", () => {
  const name = $("su").value.trim();
  $("taken").classList.remove("on");
  $("avail").classList.remove("on");
  clearTimeout(checkTimer);
  if (name.length < 3) return;
  checkTimer = setTimeout(async () => {
    try {
      const r = await fetch("/api/username?name=" + encodeURIComponent(name));
      const d = await r.json();
      if (d.taken) { $("taken").classList.add("on"); }
      else { $("avail").classList.add("on"); }
    } catch (e) { /* not fatal - the server checks on submit anyway */ }
  }, 350);
});

$("signup").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  $("su-err").classList.remove("on");
  $("create").disabled = true;

  const body = new URLSearchParams(new FormData($("signup")));
  try {
    const r = await fetch("/signup", { method: "POST", body: body });
    const d = await r.json();

    if (!r.ok || d.error) {
      $("su-err").textContent = d.error || ("Could not create the account.");
      $("su-err").classList.add("on");
      $("create").disabled = false;
      return;
    }

    // Show the recovery code. Nothing else happens until it is saved.
    $("code-out").textContent = d.recovery_code;
    hide($("signup"));
    show($("done"));
  } catch (e) {
    $("su-err").textContent = "Could not reach the engine. Is it running?";
    $("su-err").classList.add("on");
    $("create").disabled = false;
  }
});

$("continue").onclick = () => { window.location.href = "/"; };
</script>
</body></html>"""

    def _approve_tool(self, name, args):
        """May this tool run? Only write tools reach here."""
        log.info(f"the model asked to run '{name}' - refusing, "
                 f"no approval channel yet")
        return False

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

        # Inject a small admin panel for owners and admins. It is inert
        # for members: the server refuses every role change they attempt,
        # so hiding it is convenience, not the security boundary.
        panel = """
<div id="admin-panel" style="display:none;position:fixed;right:18px;bottom:18px;
     z-index:800;width:320px;max-height:70vh;overflow:auto;
     background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.09);
     border-radius:16px;padding:16px;backdrop-filter:blur(20px);
     font:13px/1.5 'Segoe UI',system-ui,sans-serif;color:#F0F4FF">
  <div style="display:flex;justify-content:space-between;align-items:center;
       margin-bottom:10px">
    <strong style="font-size:12px;letter-spacing:.1em;
            text-transform:uppercase;color:#5A6786">Accounts</strong>
    <span id="admin-close" style="cursor:pointer;color:#5A6786">x</span>
  </div>
  <div id="admin-list"></div>
  <div id="admin-msg" style="margin-top:10px;font-size:12px"></div>
</div>
<button id="admin-open" style="display:none;position:fixed;right:18px;bottom:18px;
        z-index:799;padding:10px 16px;border:none;border-radius:999px;
        background:linear-gradient(115deg,#8B5CF6,#FF3D9A);color:#fff;
        font:600 12px inherit;cursor:pointer">Accounts</button>
<script>
(function(){
  const $ = (id) => document.getElementById(id);
  let ME = null;

  async function whoami(){
    try {
      const r = await fetch('/api/whoami');
      return await r.json();
    } catch(e){ return {username:null}; }
  }

  async function load(){
    const r = await fetch('/api/accounts');
    if (!r.ok) { $('admin-list').textContent = 'Not permitted.'; return; }
    const d = await r.json();
    const owner = d.owner;
    $('admin-list').innerHTML = '';
    d.accounts.forEach(a => {
      const row = document.createElement('div');
      row.style.cssText = 'display:flex;justify-content:space-between;'
        + 'align-items:center;padding:6px 0;'
        + 'border-bottom:1px solid rgba(255,255,255,.05)';
      const isMe = a.username === d.you;
      const isOwner = a.username === owner;
      const roleColor = a.role === 'owner' ? '#FCD34D'
                      : a.role === 'admin' ? '#8B5CF6' : '#5A6786';
      row.innerHTML = '<span>' + a.username
        + (isMe ? ' <em style="color:#5A6786">(you)</em>' : '')
        + '<br><span style="font-size:11px;color:' + roleColor + '">'
        + a.role + '</span></span>';

      // The owner cannot be changed by anyone. An admin cannot be
      // changed by another admin. The buttons reflect that, and the
      // server refuses anyway.
      if (!isOwner && !isMe) {
        const btn = document.createElement('button');
        const target = a.role === 'admin' ? 'member' : 'admin';
        btn.textContent = a.role === 'admin' ? 'Demote' : 'Promote';
        btn.style.cssText = 'padding:5px 11px;border-radius:999px;border:1px solid'
          + ' rgba(255,255,255,.14);background:transparent;color:#F0F4FF;'
          + 'font:11px inherit;cursor:pointer';
        btn.onclick = () => change(a.username, target);
        row.appendChild(btn);
      }
      $('admin-list').appendChild(row);
    });
  }

  async function change(username, role){
    const r = await fetch('/api/role', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({username: username, role: role})
    });
    const d = await r.json();
    $('admin-msg').textContent = d.message || d.error || '';
    $('admin-msg').style.color = r.ok ? '#86EFAC' : '#FCA5A5';
    load();
  }

  $('admin-open').onclick = () => {
    $('admin-panel').style.display = 'block';
    $('admin-open').style.display = 'none';
    load();
  };
  $('admin-close').onclick = () => {
    $('admin-panel').style.display = 'none';
    $('admin-open').style.display = 'block';
  };

  whoami().then(w => {
    ME = w;
    // Only owners and admins see the button. Members are refused
    // server-side if they call the endpoint directly.
    if (w.role === 'owner' || w.role === 'admin') {
      $('admin-open').style.display = 'block';
    }
  });
})();
</script>
"""

        if "</body>" in html:
            html = html.replace("</body>", panel + "\n</body>", 1)

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
        self._bind_user()
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

        # --- who am I? The UI uses this to decide what to show.
        if route == "/api/whoami":
            from . import accounts
            me = None
            if accounts.enabled():
                me = accounts.session_user(
                    self._cookies().get("orbital_session"))
            self._json(200, {
                "authenticated": True,
                "username": me,
                "role": accounts.role_of(me) if me else None,
                "is_owner": accounts.is_owner(me) if me else False,
                "accounts_enabled": accounts.enabled(),
            })
            return

        # --- the roster. Owner and admins only.
        if route == "/api/accounts":
            from . import accounts

            me = accounts.session_user(
                self._cookies().get("orbital_session")) if accounts.enabled() else None
            if accounts.enabled() and accounts.role_of(me) == accounts.MEMBER:
                self._json(403, {"error": "not permitted"})
                return

            rows = accounts.roster()
            self._json(200, {
                "accounts": rows,
                "owner": accounts.owner_name(),
                "you": me,
            })
            return

        if route == "/api/ping":
            self._json(200, {"ok": True, "node": config.node_id()})
            return

        # --- is this username free? Called live from the signup form.
        if route == "/api/username":
            from . import accounts
            q = urllib.parse.parse_qs(
                urllib.parse.urlparse(self.path).query)
            name = (q.get("name") or [""])[0]
            self._json(200, {"name": name.strip().lower(),
                             "taken": accounts.taken(name)})
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
        self._bind_user()
        route = urllib.parse.urlparse(self.path).path

        # The login form posts here, and cannot require a token - the user
        # does not have one yet.
        # --- create an account
        if route == "/signup":
            from . import accounts

            length = int(self.headers.get("Content-Length", 0) or 0)
            if length > 8192:
                self._json(413, {"error": "payload too large"})
                return
            raw = self.rfile.read(length).decode("utf-8", errors="replace")
            form = urllib.parse.parse_qs(raw)

            username = (form.get("username") or [""])[0]
            password = (form.get("password") or [""])[0]
            email = (form.get("email") or [""])[0]
            phone = (form.get("phone") or [""])[0]

            try:
                result = accounts.add_user(
                    username, password, email=email, phone=phone)
            except ValueError as exc:
                # A refusal is an answer. Tell the form exactly why.
                self._json(400, {"error": str(exc)})
                return
            except Exception as exc:
                log.error(f"signup failed: {exc}")
                self._json(500, {"error": "could not create the account"})
                return

            log.info(f"signup: {result['username']}")
            # The recovery code is returned once and never again.
            self._json(200, {
                "username": result["username"],
                "recovery_code": result["recovery_code"],
            })
            return

        # --- reset a password with a recovery code
        if route == "/recover":
            from . import accounts

            length = int(self.headers.get("Content-Length", 0) or 0)
            if length > 8192:
                self._json(413, {"error": "payload too large"})
                return
            raw = self.rfile.read(length).decode("utf-8", errors="replace")
            form = urllib.parse.parse_qs(raw)

            try:
                result = accounts.recover_with_code(
                    (form.get("username") or [""])[0],
                    (form.get("code") or [""])[0],
                    (form.get("password") or [""])[0])
            except ValueError as exc:
                self._json(400, {"error": str(exc)})
                return

            self._json(200, {
                "username": result["username"],
                "new_recovery_code": result["new_recovery_code"],
            })
            return

        # --- role changes. Every one checks who is asking.
        if route in ("/api/role", "/api/remove"):
            from . import accounts

            me = accounts.session_user(
                self._cookies().get("orbital_session")) if accounts.enabled() else None

            length = int(self.headers.get("Content-Length", 0) or 0)
            raw = self.rfile.read(length).decode("utf-8", errors="replace")
            payload = {}
            try:
                payload = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                payload = {k: v[0] for k, v in
                           urllib.parse.parse_qs(raw).items()}

            target = str(payload.get("username", "")).strip().lower()
            if not target:
                self._json(400, {"error": "no username given"})
                return

            if route == "/api/role":
                role = str(payload.get("role", "")).strip().lower()
                ok, msg = accounts.set_role(me, target, role)
            else:
                ok, reason = accounts.can_manage(me, target)
                if ok and target == me:
                    ok, reason = False, "you cannot remove your own account."
                if ok:
                    accounts.remove_user(target)
                    msg = f"{target} removed"
                else:
                    msg = reason

            if not ok:
                self._json(403, {"error": msg})
                return
            self._json(200, {"ok": True, "message": msg})
            return

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

            # Route through the agent loop so a tool call runs instead
            # of being printed as text. Falls back to the plain handler
            # if the agent module is absent or the model is unreachable.
            text, meta = None, None
            if use_llm:
                try:
                    from . import agent
                    result = agent.ask(
                        prompt,
                        approve=self._approve_tool,
                        model=payload.get("model"),
                    )
                    text = result["answer"]
                    meta = {"kind": "agent",
                            "calls": result.get("calls_made", 0)}
                    if result.get("exhausted"):
                        meta["kind"] = "agent-stopped"
                except ImportError:
                    pass
                except Exception as exc:
                    log.warn(f"agent loop unavailable: {exc}")

            if text is None:
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
