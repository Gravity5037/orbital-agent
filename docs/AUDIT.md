# Orbital — Code Audit

**Repo:** `Gravity5037/orbital-agent` (public)
**Audited:** `origin/main` @ `8516331` ("Cleaned P2P Hive & UI sync node repository"), with `84885be` diffed
**Method:** static read of all 92 tracked files + full git history. No execution on the Windows host.
**Date:** 2026-10-13

> **Caveat up front:** I audited what is *committed*. Your local `C:\Orbital` may contain untracked files that are not in the repo. `.gitignore` only excludes `models/*.gguf`, `*.bin`, `*.pth`, `*.safetensors`, `__pycache__`, `.venv`, `build/`, `dist/`, `*.log`, `memory/chat_memory.json`, `OOSTATE.BIN` — so an untracked `core/gibberlink_mesh.py` would be visible as untracked on your machine. Nothing by that name exists in any commit ever. If it's on your disk, it is not in version control and nobody else can reproduce it.

---

## 0. Headline

The system described in the handoffs is not the system in the repository.

Three named subsystems — **Nucleus LLM (11434)**, **GibberLink Mesh (8765)**, **Wi-Fi CSI Radar (5555)** — are documented as "Active." None of them perform the function claimed. Two of the three have no implementation in the repo at all. The one that does bind a port is a 41-line stub that returns a hardcoded string while wearing Ollama's API shape.

Separately, there is a **live remote code execution path** that the architecture documents call "zero-trust."

Also: the handoffs cite `84885be`, but `origin/main` is now `8516331` — one commit ahead, and that newer commit *deletes* 409 lines including UI patches. The brief's own instruction (`git reset --hard origin/main`) lands on a different commit than the one it was written against.

---

## 1. P0 — Security

### 1.1 Unauthenticated RCE, LAN-exposed, CORS-wildcarded

`engine.py:63`

```python
http.server.HTTPServer(("0.0.0.0", ENGINE_PORT), Handler).serve_forever()
```

`engine.py:6-8`

```python
def run_shell(cmd):
    res = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], ...)
```

`engine.py:17-19`

```python
if p.startswith("/ps ") or p.startswith("ps: "):
    return run_shell(p.split(" ", 1)[1])
if p.startswith("/cmd ") or p.startswith("cmd: "):
    return run_shell(p.split(" ", 1)[1])
```

`engine.py` sets `Access-Control-Allow-Origin: *` on every response (`do_OPTIONS`, `do_GET`, `do_POST`).

Chain: **any device on your LAN** can `POST /api/chat` with `{"prompt": "/ps <anything>"}` and get arbitrary PowerShell executed as your user. No auth, no token, no origin check.

Worse, the wildcard CORS means **any web page you visit** in the same browser can issue that POST to `http://<your-lan-ip>:5000/api/chat` and read the response. You do not have to be on a hostile network for this to matter.

Note the inconsistency: `core/engine.py` correctly binds `127.0.0.1`. But the top-level `engine.py` is what `run_orbital.py` and every `.vbs` launcher actually start. The exposed one is the one that runs.

**Fix:** bind `127.0.0.1`, delete `run_shell` or gate it behind a token, and drop the wildcard CORS to an explicit origin.

### 1.2 The login gateway is not an auth boundary

`gui/orbital_login_gui.py`

- Admin key is a hardcoded plaintext literal: `if key == "gravity":` (line ~36).
- Second bypass: clicking the logo 20 times within 4 seconds opens the admin gateway (`_on_logo_click`).

Calling this a "Workstation Gateway" login overstates it — it's a themed launcher with a shared secret in the source of a public repo.

### 1.3 The launcher kills every Python process on the machine

`launch_orbital_master.vbs`

```vbs
WshShell.Run "powershell -NoProfile -Command ""Stop-Process -Name 'python','pythonw' -Force -ErrorAction SilentlyContinue""", 0, True
```

Unscoped `Stop-Process -Name python,pythonw`. Anything else you're running in Python dies with it.

### 1.4 Deployment overwrites itself, silently, at every launch

`run_orbital.py`

```python
subprocess.run(["git", "-C", BASE, "pull", "--rebase", "origin", "main"],
               capture_output=True, timeout=10, creationflags=0x08000000)
```

Runs on every launch, output discarded, failures swallowed by `except Exception: pass`.

Combined with the brief's recommended `git reset --hard origin/main`, this discards local modifications — which is precisely where the repo's fixes live (see §4). The system cannot hold a known state.

### 1.5 Committed opaque Windows binary

`ttyd.exe` (1.4 MB) is tracked in a public repo with no provenance, checksum, or license. Nothing in the codebase launches it (see §2.4). Supply-chain smell regardless of intent.

---

## 2. P1 — Broken at runtime

### 2.1 The autostart generator cannot run — SyntaxError

`setup_silent_autostart.py:33`

```python
ps_script = f'''
...
$Shortcut.Arguments = "`"{C:\Orbital\launch_orbital_silent.vbs}`""
...
if (Test-Path "C:\Orbital\orbital_logo.ico") {
```

The f-string is not escaped. `{C:\Orbital\...}` is parsed as a format expression. Verified:

```
SyntaxError: f-string: expecting a valid expression after '{' (line 33)
```

The script that generates `run_orbital.py` and the silent VBS launcher **fails at compile time**, before writing anything. It also raises `SyntaxWarning: invalid escape sequence '\O'` at line 30.

So the committed `run_orbital.py` is not what this generator produces. Which version is live on your box is currently unknowable.

### 2.2 The self-healing loop crashes on its first iteration

`healer_daemon.py:10`

```python
healer.inspect_and_repair(t)
```

`core/ralph_heal_loop.py` defines exactly three methods:

```
def __init__(self, log_path=r"C:\Orbital\ralph_heal.log")
def log(self, msg)
def run_full_diagnostic_and_heal(self)
```

`inspect_and_repair` **does not exist**. `AttributeError` on the first target, before `time.sleep(5)` is ever reached. The daemon exits immediately.

Because `run_orbital.py` spawns it with `stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL`, **the crash produces no output anywhere.** This is the concrete cost of "silent": the self-healing system has been failing invisibly.

### 2.3 Autostart spawns three modules that do not exist

From `run_orbital.py` / `setup_silent_autostart.py`:

| Spawned path | Status |
|---|---|
| `core/healer_daemon.py` → `healer_daemon.py` | exists, crashes (§2.2) |
| `core/csi_sensing_engine.py` | **missing** — not in repo, not in any commit |
| `core/gibberlink_mesh.py` | **missing** — not in repo, not in any commit |
| `core/spatial_map_engine.py` | **missing** — not in repo, not in any commit |

`run_orbital.py` guards each with `if os.path.exists(svc):` and silently skips. The VBS launchers do not guard at all.

`gibberlink_websocket_gateway-v2.py` imports `from core.gibberlink_mesh import GibberLinkMesh` → `ImportError`. So the 8765 gateway has no working entrypoint either.

### 2.4 `launch_hive_mesh.py` does not exist

Both handoffs name it as a target module, the second calling it the 8765 WebSocket P2P gateway. Searched all history:

```
$ git log --all --pretty=format: --name-only | sort -u | grep -i "hive_mesh"
(none)
```

Never existed in this repo. The only mesh-adjacent files are `hive_peer.py` (55 lines) and `run_hive.py`, which is a 6-line script that prints three lines and exits:

```python
import socket
print("[*] Initializing Hive Link Node...")
hostname = socket.gethostname()
local_ip = socket.gethostbyname(hostname)
print(f"[PC Node active on host: {hostname} ({local_ip})]")
print("[Awaiting client connections on 0.0.0.0:5000...]")
```

It does not open a socket. It does not listen. It prints that it does.

### 2.5 No dependency manifest

No `requirements.txt`, `pyproject.toml`, `setup.py`, or `Pipfile` exists — yet `core/adaptation_engine.py` generates a deploy script containing:

```sh
python3 -m pip install -r requirements.txt || true
```

Installing from a file that is not in the repo, with `|| true` so failure is ignored.

---

## 3. P2 — Spec vs. reality

### 3.1 "Nucleus LLM Engine — llama-server.exe — 11434 — Active (Silent GGUF inference backend)"

There is no inference in this repository.

`gui/engine.py` is 41 lines. Its entire "chat" handler:

```python
reply = f"Orbital Nucleus AI Engine Active.\nReceived: '{last_msg}'\nProcessing system context..."
resp = {"message": {"role": "assistant", "content": reply}}
```

It binds `127.0.0.1:11434` and **impersonates Ollama's wire format** — `/api/chat` returning `{"message": {"role", "content"}}`, and `/api/tags` returning:

```python
json.dumps({"models": [{"name": "qwen2.5-coder:1.5b"}]})
```

That model name is hardcoded. No model is loaded. No weights are read. Any client that queries `/api/tags` will be told a model exists.

- `llama-server.exe` — not in the repo, not in `.gitignore` as ignored, simply absent.
- `Nucleus/model.gguf` — absent. `Nucleus/` contains one 0-byte file, `_engine.py`.
- `Nucleus/_engine.py` is **0 bytes**, committed empty at `84885be`.

`launch_nucleus.vbs` is the one place that genuinely tries to start an LLM:

```vbs
If FSO.FileExists(LlamaPath) Then
    WshShell.Run "... Start-Process -FilePath '" & LlamaPath & "' -ArgumentList '-m " & ModelPath & " --port 11434 -c 4096' ..."
ElseIf FSO.FileExists(EnginePy) Then
    WshShell.Run "pythonw.exe """ & EnginePy & """", 0, False
End If
```

If the GGUF is missing, it silently falls through to the stub — which then reports itself as the Nucleus LLM. **The stub is indistinguishable from the real thing at the API level**, which is why the dashboard shows "Active."

The actual working LLM client code lives elsewhere and targets Ollama, not this: `update.py:67` (`/api/generate`), `orbitalchat_gui.py:13`, `gui/orbital_navigator_gui.py:16`. If Ollama is installed, those work — and the stub on 11434 will collide with it, since both claim the port.

**Answering the port question from my earlier handoff:** the collision risk is real and already present. `update.py:123` runs `subprocess.Popen(["ollama", "serve"], ...)` while `gui/engine.py` binds the same port. Whichever starts first wins.

### 3.2 "Nebula Creative Engine — sub-second local visual generation via /draw"

`core/engine.py`:

```python
elif p.lower().startswith('/draw '):
    reply = f"[🎨 Nebula Engine]: Procedural matrix synthesis complete for: '{p[6:]}'. Rendered into local visual cache."
```

That is the whole implementation. A formatted string. No image library, no diffusion, no model, no cache directory, no file written. The phrase "Rendered into local visual cache" is text in a chat bubble.

### 3.3 "Wi-Fi CSI Sensing Radar — UDP 0.0.0.0:5555 — Listening (RF subcarrier variance)"

Every reference to `5555` in the codebase is UI copy:

```python
'<div class="nav-item" onclick="alert(\'CSI Radar: Listening UDP 5555\')">📡 Wi-Fi CSI Radar</div>'
```

```javascript
chat.innerHTML += '... UDP 5555 active. Sensing live human presence and respiration vectors.'
```

No socket. No `UDP`. No packet capture. No subcarrier anything. It is a sidebar button that opens a browser `alert()`.

`clean_orbital_dir.py:27` lists `"wifi_csi_sensing-v2.py"` among files to delete — suggesting an implementation once existed locally and was cleaned out.

### 3.4 "Embedded Web Console — ttyd.exe — 7681 — Active"

`ttyd.exe` is committed but **never launched by any script** (grepped `*.py`, `*.vbs`: no `Popen`/`Run` of it). `embed_console.py` injects an iframe pointing at `http://127.0.0.1:7681/` — which resolves to nothing. The workstation HTML renders a dead panel.

### 3.5 Things that report success unconditionally

`orbital_sync_engine.py` in full:

```python
import os

def execute_orbital_sync():
    return {"status": "SUCCESS", "message": "Orbital workspace synced."}
```

Returns `SUCCESS` without doing anything, ever.

`core/ralph_heal_loop.py` health check: POSTs `/telemetry` to `/api/chat`, and if HTTP 200 comes back, reports `"[✔] Port 5000 Kernel Socket: Optimal (Zero Latency)"`. But `/telemetry` isn't a real endpoint — it falls through `process_query` to the default branch, which returns a canned `"Orbital Engine active. Processed: '/telemetry'"`. **Any 200 counts as "Optimal."** The diagnostic cannot detect a broken engine, because the engine answers everything with 200.

Its "repair" action is also destructive:

```python
if "\\O" in code:
    code = code.replace("\\O", "\\\\O")
```

This rewrites `r"C:\Orbital"` into `r"C:\\Orbital"` — a literal double backslash in a raw string, i.e. a broken path. It scans `engine.py`, `run_orbital.py`, and `orbital_vision.py`, all of which contain `\Orbital` paths. If this branch ever fires, it corrupts the files it claims to heal.

Also note: `RalphHealLoop.run_full_diagnostic_and_heal()` is a **diagnostic reporter**, not a healer. It checks AST syntax, reads psutil telemetry, and formats a report. It never restarts a process, never writes a fix (except the corrupting one above). The restart logic lives in `healer_daemon.py` — which crashes (§2.2).

### 3.6 Commit drift

| | |
|---|---|
| Handoffs cite | `84885be` |
| Actual `origin/main` HEAD | `8516331` |

`8516331` ("Cleaned P2P Hive") changes 25 files, `+2905 / −409`, including `engine.py` (−132 lines), `gui/cyber_organic_workstation.html` (−341), and adds `hive_peer.py`, `run_hive.py`, `provision_pip_master.py`, `ttyd.exe`.

The operator was told to `git reset --hard origin/main`. That lands on `8516331`, not `84885be`. The handoff describes a tree that is one commit stale.

---

## 4. P3 — Structural

**41 of 71 top-level `.py` files are one-shot mutators.** `fix_*`, `patch_*`, `repair_*`, `upgrade_*`, `update_*`, `deploy_*`. They rewrite other files in place via string replacement:

- `fix_ui.py`, `patch_ui_final.py`, `repair_all_ui.py`, `fix_workstation_complete.py`, `wire_ui.py`, `inject_sync.py`, `hook_liquid_cam.py`, `enable_draggable_cam.py`, `patch_cam_draggable.py`, `patch_cam_dock_pip.py`, `patch_fancy_pip.py`, `patch_resizable_cam.py`, `patch_snap_assist.py`, `fix_scrollbars.py`, `fix_layout.py`, `fix_iframe.py`, `fix_frontend_chat.py` — **all edit the same `gui/cyber_organic_workstation.html`** with overlapping, order-dependent replacements.

They are non-idempotent (most guard with `if old in html`, some don't), order-dependent, and unversioned. The HTML in the repo is the residue of whichever sequence last ran. This is why no two machines agree on the file's contents — and why `git reset --hard` feels necessary.

`clean_orbital_dir.py` exists specifically to delete the artifacts the other scripts produce. That's the tell: the repo contains both a sediment layer and a script to scrape it off.

Also absent: `README`, `LICENSE`, any test, any CI.

---

## 5. What is actually real

To be fair — these are genuine and functional:

| Component | Reality |
|---|---|
| `engine.py` | A working HTTP server with a PowerShell bridge. It does exactly what it says. That's the §1.1 problem. |
| `gui/cyber_organic_workstation.html` | A real, styled workstation UI. |
| `gui/orbital_login_gui.py` | A real tkinter gateway (auth gate is decorative, §1.2). |
| `gui/orbital_navigator_gui.py` | 937 lines, the largest real module; has a working Ollama client at line 639. |
| `core/ralph_heal_loop.py` | Real AST scanning and psutil telemetry. Misnamed and miswired, but the bones are sound. |
| `core/adaptation_engine.py` | Real `platform` introspection; the deploy recipe is plausible. |
| `orbital_vision.py`, `orbitalchat_gui.py` | Real camera and chat clients. |

The architecture isn't absurd. The problem is that it's **unfinished work presented as a finished system**, with the gaps filled by strings that describe the missing behavior.

---

## 6. Recommended order of work

1. **Close the RCE.** `engine.py:63` → `127.0.0.1`. Remove `run_shell` or token-gate it. Replace `*` CORS with an explicit origin. Do this first; it's the only item with an active exposure.
2. **Stop the self-overwrite.** Remove the `git pull` from `run_orbital.py`. Deployment should not be a side effect of launching the UI. Pin a commit, tag releases.
3. **Make failures visible.** Drop `stdout=DEVNULL, stderr=DEVNULL`; log to a file. The §2.2 crash has been silent by construction — that's the single highest-leverage fix for debuggability.
4. **Fix the two hard crashes.** `setup_silent_autostart.py:33` f-string escaping; `healer_daemon.py:10` → call `run_full_diagnostic_and_heal()`.
5. **Decide what Nucleus is.** Either ship real GGUF inference or delete `gui/engine.py`. A stub wearing Ollama's API shape on Ollama's port is the worst of both — it will silently shadow a working install and make `/api/tags` lie.
6. **Delete the three missing-module spawns** or write the modules. 8765, 5555, and the spatial map currently do not exist.
7. **Remove `ttyd.exe`** or wire it up. Unused 1.4 MB binary in a public repo is pure liability.
8. **Consolidate the 41 mutators** into the files they modify, then delete them. `gui/cyber_organic_workstation.html` should be authored, not accreted.
9. **Add `requirements.txt`** — actually, since psutil is the only third-party import I found, that's a one-line file.

---

## 7. Direct answers to the open questions

| Question | Answer from source |
|---|---|
| Is 11434 Ollama or a wrapper? | Neither. It's a stub (`gui/engine.py`) that mimics Ollama's `/api/chat` and `/api/tags` shapes. Real Ollama is used by `update.py` / `orbitalchat_gui.py` / `orbital_navigator_gui.py`. |
| Model tags? | Hardcoded string `qwen2.5-coder:1.5b`. No model is loaded. |
| CPU or GPU? | N/A — no inference occurs. |
| Mesh wire format? | Unspecified, because `core/gibberlink_mesh.py` does not exist. |
| Mesh auth / bind scope? | Spec says `ws://0.0.0.0:8765`. No implementation to verify. |
| Autostart mechanism? | VBS (`launch_orbital_silent.vbs` etc.) via `WshShell.Run ..., 0, False` + a Desktop `.lnk` targeting `wscript.exe`. Not Task Scheduler, not registry, not a service. |
| Restart on crash? | No. Nothing supervises anything. The healer that was meant to crashes itself. |
| Where do logs go? | `ralph_heal.log` if the loop ran (it doesn't), plus `print()` to DEVNULL. Effectively nowhere. |
| "Zero-trust state isolation"? | Not implemented. Wildcard CORS + `0.0.0.0` bind + unauthenticated shell bridge is the opposite. |
| Node verification pass/fail? | No such check exists. `orbital_sync_engine.execute_orbital_sync()` returns `SUCCESS` unconditionally. |
| Python version? | Unspecified in repo. No manifest. |
| Deps installed how? | Unspecified. `requirements.txt` referenced but absent. |
