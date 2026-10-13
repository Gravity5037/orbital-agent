# Orbital — fixed core

A working replacement for the parts of `C:\Orbital` that were broken, missing,
or lying. Built against `origin/main` @ `8516331`.

Every claim below is covered by a test in `tests/`. Run them yourself:

```
python tests/run_tests.py
```

---

## What changed and why

### Security

| Old | New |
|---|---|
| `engine.py` bound `0.0.0.0:5000` with `Access-Control-Allow-Origin: *` and piped request bodies into PowerShell | binds `127.0.0.1`, every `/api/*` needs a bearer token, CORS is an explicit origin list |
| Any LAN device, or any web page you visited, had RCE as your user | `/api/shell` is token-gated and can be switched off entirely |
| `gui/orbital_login_gui.py` compared against the literal `"gravity"` | not an auth boundary and no longer presented as one |

### Broken things now working

| Old | Problem | New |
|---|---|---|
| `setup_silent_autostart.py` | `SyntaxError` — unescaped f-string at line 33. The generator never ran. | `install_autostart.py` — three mechanisms, reversible, dry-run |
| `healer_daemon.py` | called `inspect_and_repair()`, which doesn't exist; crashed on iteration 1, invisibly | `core/supervisor.py` — spawns, watches, restarts with backoff, gives up, logs |
| `core/gibberlink_mesh.py` | did not exist, in any commit | `core/mesh.py` — real WebSocket server + dialer |
| `core/csi_sensing_engine.py`, `core/spatial_map_engine.py` | did not exist | not written; the UI no longer claims they run |
| `gui/engine.py` | 41-line stub impersonating Ollama on Ollama's port, reporting a hardcoded model | `core/nucleus.py` — real client; when the backend is down it says so |
| `run_hive.py` | printed "Awaiting client connections" without opening a socket | deleted by `migrate.py` |
| `orbital_sync_engine.py` | returned `{"status": "SUCCESS"}` unconditionally | deleted by `migrate.py` |
| `run_orbital.py` | ran `git pull --rebase` on every launch, output discarded | `start.py` does not touch git |
| `launch_orbital_master.vbs` | `Stop-Process -Name python,pythonw` — killed every Python process on the machine | launches one thing |

### Telemetry

The old `ralph_heal_loop` POSTed `/telemetry` to `/api/chat`; the engine
answered every prompt with 200, so the diagnostic always reported
`"Port 5000 Kernel Socket: Optimal"` even when the engine was broken.
`core/engine.py` reports real psutil numbers, or says `psutil not installed`.

---

## Nebula — image generation

The module the old tree faked. `core/engine.py` answered `/draw` with the
string *"Procedural matrix synthesis complete... Rendered into local visual
cache."* No image, no model, no cache. This one returns real PNG bytes.

Backend is [ComfyUI](https://github.com/comfyanonymous/ComfyUI), the standard
local image server. Orbital builds the workflow graph in code, so resolution,
steps, seed, sampler and prompts are all parameters rather than something you
export from a UI.

### Setup

```powershell
git clone https://github.com/comfyanonymous/ComfyUI
cd ComfyUI
pip install -r requirements.txt
python main.py --listen 127.0.0.1 --port 8188
```

Put a checkpoint in `ComfyUI/models/checkpoints/`, then:

```
GET  /api/nebula          # is the backend up, what checkpoints exist
POST /api/draw            # {"prompt": "...", "steps": 28}
GET  /api/draw/<job_id>   # poll status
GET  /api/image?name=...  # fetch the PNG
```

`POST /api/draw` returns **202 with a job id** immediately. Generation takes
seconds to minutes, so blocking the request would freeze the engine. One
worker thread processes the queue — diffusion saturates the GPU, and running
two jobs concurrently makes both slower without finishing more.

### VRAM, honestly

This is the hard constraint. Total VRAM during generation, at 1024×1024:

| Model | FP16 | FP8 | GGUF Q4 |
|---|---|---|---|
| SD 1.5 | ~5 GB | — | — |
| SDXL / Pony / Illustrious | ~8 GB | — | — |
| SD 3.5 Medium | ~7 GB | — | — |
| SD 3.5 Large | ~12 GB | ~9 GB | — |
| Flux.1 Dev | ~35 GB | ~15 GB | ~9 GB |

Rule of thumb: **8 GB** → SDXL family, and that is the sweet spot for
fine-tunes and LoRAs. **12 GB** → Flux at GGUF Q5–Q6. **16 GB** → Flux FP8.
**24 GB+** → anything, with ControlNets and LoRAs loaded together.

If it does not fit, you get an out-of-memory crash, not a slow image.

### On fine-tunes and content

Base SDXL produces fairly bland output and is heavily safety-filtered in its
training. The community fine-tunes are where both quality and range come from:

- **Pony Diffusion V6 XL** — SDXL fine-tune, Danbooru-style tagging, very wide
  content range. ~8 GB.
- **Illustrious XL** — SDXL fine-tune, stronger anatomy and faces.
- **Realistic Vision**, **DreamShaper** — SD 1.5, photoreal and general.

These are ordinary `.safetensors` files in `models/checkpoints/`. Set a
default with `ORBITAL_CHECKPOINT=pony_v6.safetensors`, or pass `"checkpoint"`
per request. LoRAs go in `models/loras/` and can be chained per request:

```json
{"prompt": "...", "loras": [{"name": "style.safetensors", "strength": 0.8}]}
```

What you generate on your own hardware is your business. Two practical notes
rather than moral ones: output of real, identifiable people is a legal problem
in a lot of jurisdictions, and anything that leaves the machine is not local
any more.

---


```
core/
  config.py       paths, ports, env overrides
  logutil.py      file + console logging (nothing goes to DEVNULL)
  auth.py         token generation, constant-time check
  nucleus.py      client for the Ollama-compatible backend
  nebula.py       ComfyUI image generation client
  video.py        Wan 2.2 text-to-video and image-to-video
  backends.py     ComfyUI node pool, routing, failover
  hue.py          Philips Hue control (local bridge API)
  spotify.py      Spotify Web API (playback, search, playlists)
  camera.py       webcam capture + phone camera streams
  artifacts.py    model registry with provenance (a DAG)
  dataset.py      curation + anti-collapse guard rails
  evals.py        paired A/B evaluation of variants
  model_cli.py    lineage / datasets / eval from the command line
  jobs.py         generation job queue (non-blocking, routed)
  oostate.py      OOSTATE.BIN container — versioned, checksummed, compressed
  statestore.py   live state model + deterministic merge
  state_cli.py    inspect / export / import / merge / migrate
  engine.py       HTTP API on 127.0.0.1:5000
  mesh.py         WebSocket mesh on 127.0.0.1:8765
  supervisor.py   starts and restarts engine + mesh
check_requirements.py  what do I still need to install
doctor.py         environment check — run this first
start.py          launcher and preflight
install_autostart.py
migrate.py        retire the old tree, non-destructively
launch_orbital_silent.vbs
tests/            7 suites, 102 checks
```

---

## Video generation

Same ComfyUI backend, much bigger cost. Wan 2.2 is the current standard.

**Read this before trying it.** A 5-second 720p clip is roughly **9 minutes on
an RTX 4090** with the 5B model — the *fast* case. Going from 480p to 720p
roughly triples generation time. This is not interactive, which is why it goes
through the same job queue as images.

### What you need

Three separate files, unlike image models which bundle everything in one
checkpoint:

| File | Goes in |
|---|---|
| `wan2.2_ti2v_5B_fp16.safetensors` | `ComfyUI/models/diffusion_models/` |
| `umt5_xxl_fp8_e4m3fn_scaled.safetensors` | `ComfyUI/models/text_encoders/` |
| `wan2.2_vae.safetensors` | `ComfyUI/models/vae/` |

Plus the `ComfyUI-GGUF` custom node if you use quantized models.

### VRAM tiers

| VRAM | Model | Reality |
|---|---|---|
| 8 GB | TI2V-5B GGUF Q8 (5.4 GB) | works, offloads to RAM, slow |
| 12 GB | 14B Q4_K_M (9.7 GB), 480p | tight, short clips |
| 16 GB | 14B Q5/Q6 | 720p with partial offload |
| 24 GB | 14B FP8 (14.3 GB) | 720p comfortable |

**System RAM matters as much as VRAM.** Whatever doesn't fit on the GPU gets
offloaded there. Budget 32 GB RAM for the 5B model, 64 GB for 14B at FP8.

### Usage

```powershell
POST /api/video          {"prompt": "...", "length": 49, "fps": 16}
POST /api/video          {"prompt": "...", "mode": "i2v", "image_name": "start.png"}
GET  /api/video/status   # are the three model files present
GET  /api/draw/<job_id>  # same poll endpoint as images
GET  /api/video/file?name=...
```

Frame counts snap to **4n+1** (Wan's requirement), so asking for 50 frames
gets you 49. Video jobs and image jobs share one queue and one worker — a
10-minute video blocks an image job behind it. That is deliberate: both
saturate the same GPU.

### Speed levers

1. **Steps.** Default 30. LightX2V 4-step LoRAs cut this to 4, with some loss
   of motion fidelity.
2. **Frames.** 49 at 16 fps ≈ 3 seconds. Halving it halves the cost.
3. **Resolution.** The biggest lever by far.
4. **Offloading.** Every layer streamed from system RAM costs time on every
   step. Fitting the active model in VRAM is the single biggest win.

---


The portable state image. Conversation, attention, and logs travel between
devices in one file.

### Why it can merge

The old `chat_memory.json` was a flat list. Two devices that both talked while
offline produced two lists with no way to reconcile them — no ids, no
ordering, no notion of which came first. That is unfixable at the merge step,
so the fix is in the data model:

- **Every message has a unique id.** Merge is a set union keyed by id. No
  message can be lost or duplicated, because identity is explicit.
- **Every message has a Lamport stamp.** Wall clocks drift and get set
  backwards; a logical counter gives an order both nodes agree on.
- **Ordering is total:** `(lamport, ts, origin, id)`. Every component exists on
  every record, so every node sorts identically.

That buys three properties, all tested:

| Property | Meaning |
|---|---|
| commutative | `merge(A,B) == merge(B,A)` |
| idempotent | `merge(A,A) == A` |
| associative | `merge(merge(A,B),C) == merge(A,merge(B,C))` |

With those, nodes can gossip state in any order, repeatedly, over a lossy
mesh, and converge. Without them you get duplicated messages and lost edits.

### Conflict rules

| Data | Rule |
|---|---|
| Messages | union by id; identical ids with different content resolve by `(ts, origin, content)` and are **reported**, never silently dropped |
| Attention | last-write-wins per key, ties broken by node id |
| Logs | deduplicated on `(ts, level, message, origin)`, newest kept |
| Meta | union; local wins |

### The container

```
0    8    magic "OOSTATE1"
8    2    container format version
10   2    flags (bit 0 = zlib compressed)
12   4    header length
16   4    payload length
20   32   SHA-256 of the payload as stored
52   H    header, UTF-8 JSON
52+H P    payload, UTF-8 JSON (optionally compressed)
```

Two version numbers, deliberately separate:

- **`FORMAT_VERSION`** — the container. A newer value is refused outright,
  because the reader cannot trust its own parse.
- **`schema`** — the state model, inside the payload. A newer value is refused;
  an *older* value is migrated forward.

Conflating these is how formats become unreadable. Keeping them apart is what
lets a v3 payload travel in a v1 container.

The digest is verified **before** decompression, so a corrupted file is
rejected rather than producing a zlib error that tells you nothing. Writes are
atomic (`tmp` + `fsync` + `os.replace`), so a crash mid-write cannot leave a
half-written image.

### Using it

```powershell
python -m core.state_cli show -v 5           # what's in the live state
python -m core.state_cli export stick.bin    # write an image
python -m core.state_cli inspect stick.bin   # header only, no parse
python -m core.state_cli verify stick.bin    # checksum check
python -m core.state_cli import stick.bin    # merge it in
python -m core.state_cli import stick.bin --strategy replace
python -m core.state_cli merge a.bin b.bin -o c.bin
python -m core.state_cli migrate-old         # import legacy chat_memory.json
```

Over HTTP (token required):

```
GET  /api/state/export          -> OOSTATE.BIN bytes
POST /api/state/import          {"blob": "<base64>", "strategy": "merge"}
```

### What this does not do

- **No automatic sync.** Merging is explicit. The mesh transports messages; it
  does not yet push state on its own. That is Phase 4.
- **No compression of intent.** If two devices genuinely disagree, the merge
  picks deterministically and reports it. It does not ask you.
- **Bounded, not unlimited.** 5000 messages, 200 attention keys, 500 log lines.
  Images stay small enough to move.

---


## Install

On the Windows box, from `C:\Orbital`:

```powershell
pip install -r requirements.txt
python doctor.py             # check this machine, get a concrete next step
python start.py              # foreground; Ctrl-C to stop
```

`doctor.py` is the place to start. It checks Python, dependencies, ports,
GPU and VRAM, every backend, and the state image — then tells you the single
next thing to do rather than dumping diagnostics. Safe to run any time; it
changes nothing except creating the state and log directories.

If it says a backend is unreachable, that backend is the next thing to
install. It will not tell you image generation is ready when it isn't.

`--check` prints the API token. To run headless:

```powershell
python start.py --background
Get-Content logs\supervisor.log -Tail 20 -Wait
```

Then open `gui\cyber_organic_workstation.html`, paste the token from
`state\engine.token` into the sidebar, and the telemetry panel goes live.

### Nucleus

The engine runs with or without an LLM. With none, `/ps`, `/cmd`, `/health`
and `/telemetry` still work, and chat returns an honest error.

For real reasoning, install [Ollama](https://ollama.com) and:

```powershell
ollama pull qwen2.5-coder:1.5b
ollama serve
```

Point at something else with `ORBITAL_OLLAMA=http://host:11434`.
`llama-server` works too — it speaks the same API.

---

## Migrating an existing tree

```powershell
python migrate.py                     # dry run, shows the plan
python migrate.py --apply             # move 9 superseded files to legacy\
python migrate.py --apply --purge     # also retire the ~43 one-shot mutators
```

Nothing is ever deleted. Everything goes to `legacy/` and can be moved back.

---

## Configuration

All optional; defaults shown.

| Variable | Default | Meaning |
|---|---|---|
| `ORBITAL_BASE` | `C:\Orbital` on Windows, repo root elsewhere | data directory |
| `ORBITAL_STATE` | `<base>/state/OOSTATE.BIN` | state image path |
| `ORBITAL_ENGINE_HOST` / `_PORT` | `127.0.0.1` / `5000` | API bind |
| `ORBITAL_MESH_HOST` / `_PORT` | `127.0.0.1` / `8765` | mesh bind |
| `ORBITAL_OLLAMA` | `http://127.0.0.1:11434` | LLM backend |
| `ORBITAL_MODEL` | `qwen2.5-coder:1.5b` | model name |
| `ORBITAL_COMFY` | `http://127.0.0.1:8188` | local ComfyUI endpoint |
| `ORBITAL_BACKENDS` | *(empty)* | `name=url[@weight],...` node pool |
| `ORBITAL_WORKERS` | `4` | max generation workers |
| `ORBITAL_BACKEND_TTL` | `5` | backend probe cache, seconds |
| `ORBITAL_CHECKPOINT` | *(first found)* | default image checkpoint |
| `ORBITAL_IMAGE_WIDTH` / `_HEIGHT` | `1024` | default resolution |
| `ORBITAL_IMAGE_STEPS` | `28` | default sampling steps |
| `ORBITAL_IMAGE_CFG` | `7.0` | default guidance scale |
| `ORBITAL_NEGATIVE` | *(sane defaults)* | default negative prompt |
| `ORBITAL_IMAGE_TIMEOUT` | `600` | image generation timeout, seconds |
| `ORBITAL_VIDEO_UNET` | `wan2.2_ti2v_5B_fp16.safetensors` | video diffusion model |
| `ORBITAL_VIDEO_CLIP` | `umt5_xxl_fp8_e4m3fn_scaled.safetensors` | video text encoder |
| `ORBITAL_VIDEO_VAE` | `wan2.2_vae.safetensors` | video VAE |
| `ORBITAL_VIDEO_WIDTH` / `_HEIGHT` | `704` / `480` | default video resolution |
| `ORBITAL_VIDEO_LENGTH` | `49` | default frames (snaps to 4n+1) |
| `ORBITAL_VIDEO_FPS` | `16` | default frame rate |
| `ORBITAL_VIDEO_STEPS` | `30` | default sampling steps |
| `ORBITAL_VIDEO_TIMEOUT` | `3600` | video generation timeout, seconds |
| `ORBITAL_PEERS` | *(empty)* | `ws://host:8765,ws://host2:8765` |
| `ORBITAL_MESH_SECRET` | *(empty)* | shared secret for the handshake |
| `ORBITAL_TOKEN` | *(generated)* | override the API token |
| `ORBITAL_ENABLE_SHELL` | `1` | set `0` to disable `/ps` and `/cmd` |
| `ORBITAL_NODE_ID` | hostname | name this node advertises |

---

## API

All `/api/*` routes except `/api/ping` need `Authorization: Bearer <token>`.

| Route | Method | Purpose |
|---|---|---|
| `/api/ping` | GET | liveness, no auth |
| `/api/telemetry` | GET | CPU, RAM, disk, nucleus state |
| `/api/chat` | POST | `{"prompt": "...", "llm": true}` |
| `/api/shell` | POST | `{"cmd": "..."}` |
| `/api/history` | GET | recent conversation |
| `/api/state/export` | GET | download `OOSTATE.BIN` |
| `/api/state/import` | POST | `{"blob": base64, "strategy": "merge"}` |
| `/api/logs?name=engine` | GET | tail a log file |
| `/api/models` | GET | models on the backend |
| `/api/nebula` | GET | image backend status + checkpoints |
| `/api/backends` | GET | node pool: load, capability, health |
| `/api/integrations` | GET | Hue / Spotify / camera status |
| `/api/spotify/now` | GET | current track |
| `/api/spotify/devices` | GET | available players |
| `/api/spotify/<action>` | POST | play, pause, next, previous, seek, volume, shuffle, repeat |
| `/api/hue/lights` | GET | all lights with state |
| `/api/hue/set` | POST | `{"name": "...", "on": true}` |
| `/api/hue/all` | POST | `{"on": false}` |
| `/api/captures?name=` | GET | fetch a saved camera capture |
| `/api/draw` | POST | `{"prompt": "...", "steps": 28}` → 202 + job id |
| `/api/draw/<id>` | GET | poll a generation job |
| `/api/draw/status` | GET | list recent jobs |
| `/api/image?name=` | GET | fetch a generated PNG |
| `/api/video` | POST | `{"prompt": "...", "length": 49}` → 202 + job id |
| `/api/video/status` | GET | video model availability |
| `/api/video/file?name=` | GET | fetch a generated clip |

---

## Integrations — lights, music, cameras

Three integrations, in increasing order of difficulty. The first two are
genuinely easy; the third has platform constraints worth knowing about.

### Philips Hue — the best of the three

The bridge speaks plain HTTP on your LAN. No cloud account, no rate limits,
no internet required once paired. This is the one that is both easy *and*
fully local.

```powershell
python -m core.hue discover          # find the bridge
python -m core.hue pair              # press the link button, then run this
python -m core.hue lights            # list them
```

`pair` waits for you to press the round link button on the bridge — that
requirement is Hue's proof of physical access, not an inconvenience. The key
is stored in `state/hue.key` with 0600 permissions.

Then in chat:

```
/lights                     list every light with state
/lights on                  all on
/lights off                 all off
/lights dim 25              all to 25%
/lights scene Relax         activate a scene
/lights Kitchen             toggle one by name
```

`set_light()` also takes `hue`, `saturation` and `color_temp` for colour
control, and `transition` for fade timing.

### Spotify

Cloud-only, unlike Hue — the Web API has no local option. One browser
approval, then it is just HTTPS calls with a refresh token.

1. Create an app at https://developer.spotify.com/dashboard
2. Add the redirect URI exactly: `http://127.0.0.1:8888/callback`
3. Set `ORBITAL_SPOTIFY_CLIENT_ID` and `ORBITAL_SPOTIFY_CLIENT_SECRET`
4. `python -m core.spotify auth`

```
/play <search>      search and play the first result
/nowplaying         what is playing
/pause /next /prev
/volume 40
/devices            list available players
```

**Two honest limitations.** The API controls a Spotify client that is
already running — it cannot start one, so if nothing is playing, use
`/devices` and `transfer()`. And some endpoints return 403 on free accounts.
That is Spotify's policy, and the module reports it as `PremiumRequired`
rather than as a generic error.

### Running it — no terminal, no token

Double-click **`Orbital.bat`**. That's it.

What it does:

1. Checks whether Orbital is already running. If so, it just opens the
   interface and exits — no second instance.
2. Otherwise starts the engine detached with `pythonw`, so **no console
   window stays open**. Output goes to `logs\`.
3. Waits for the engine to answer, up to 30 seconds.
4. Opens `http://127.0.0.1:5000/` in your browser.

**No token to paste.** The engine serves the interface itself and injects the
token into the page. Same origin, so there is not even a CORS request. The
manual token panel is hidden automatically when this happens.

Stop it with **`Orbital-stop.bat`**, or just leave it running — it is idle
when not in use.

**Is the token still doing anything?** Yes, and it still matters:

| From | Result |
|---|---|
| `http://127.0.0.1:5000/` (served) | works — token injected |
| any other page in your browser | 401 — cannot read the injected token |
| anything else on the LAN | 401 — and the bind is loopback-only |
| no token / wrong token | 401 |

The token protects against *other pages in your browser* reaching the engine.
That is the realistic threat on a home machine: a tab you have open
scripting a request to localhost. Removing the token would reopen exactly the
hole that produced 27 unauthenticated processes on port 5000.

If you want it gone entirely for a single-user machine:

```
set ORBITAL_TOKEN=none
```

That is a deliberate choice with a real trade-off, not a default.

### Accounts — optional, and off by default

**The honest answer to "should this need a login?" is "not for the way you
are using it."** Here is the reasoning, so you can decide rather than take my
word for it.

| Threat | Already handled by | Would a login help? |
|---|---|---|
| Another web page in your browser reaching the engine | the API token — a header cannot be read or forged by another origin | **No, and it makes it worse** |
| Another device on the LAN | binding to `127.0.0.1` | No — nothing can reach it |
| Someone at your keyboard | nothing | Only if the credential is not readable on the machine. On your own PC, it is. |

The second row deserves emphasis: a login means a **session cookie**, and
cookies are attached automatically by the browser. That is precisely what
CSRF abuses. Swapping a header token for a cookie trades a stronger
primitive for a weaker one.

**When accounts genuinely help:**

1. Several people share the machine and should not share state.
2. Orbital is reachable from other devices.
3. You want a record of who did what.

For (2), a password is the wrong tool. **Tailscale authenticates devices,
not credentials.** Bind Orbital to the tailnet interface and only your
devices can reach it — identity proven at the network layer, nothing to
type, nothing to phish.

**Turning them on:**

```powershell
python -m core.accounts add jay
```

That is the whole setup. From then on `/` shows a themed sign-in page.
Turn them off again with:

```powershell
python -m core.accounts disable
```

**What it gets right, when it is on:**

- **scrypt** password hashing — memory-hard, stdlib, no dependency
- **Per-user salt**, so two people with the same password get different hashes
- **Sessions in memory only** — a restart invalidates everything
- **Sliding expiry** — active sessions live, idle ones expire
- **Rate limiting** — 8 failures in 5 minutes locks the account for 15
- **No username enumeration** — a wrong password and an unknown user give the
  same answer, so the login form cannot be used to discover accounts
- **HttpOnly, SameSite=Strict** cookie, so it cannot be read by scripts or
  sent cross-site
- **Owner-only** accounts file, `0600`

The API token keeps working alongside accounts, so scripts and the
`file://` UI are unaffected.

### Tools — why the model stops saying "I can't do that"

Without tools, asked "can you see my camera", the model answered *"I don't
have the capability to see your camera."* That is false. Orbital can. The
model simply did not know it was the reasoning part of a system that could.

Two mechanisms, together:

**Native tool calling.** 13 tools declared with JSON schemas. The model
decides when to call one, the engine executes it, the result goes back. Four
of the five models on this machine support it natively (qwen2.5, llama3.x).

**A capability preamble.** States plainly what Orbital can do, and what is
available *right now*, so the model neither refuses out of habit nor promises
something the machine cannot deliver.

| Tool | What it does |
|---|---|
| `get_time` | real date and time |
| `get_system_info` | CPU, RAM, GPU, VRAM, disk, models |
| `list_files` / `read_file` | filesystem access |
| `generate_image` | queue an image |
| `check_image_backend` | is ComfyUI up |
| `capture_camera` / `list_cameras` | webcam and phone streams |
| `hue_lights` / `hue_control` | lights |
| `spotify_now` / `spotify_control` | music |
| `system_status` | health of everything |

Models without tool support degrade gracefully — the request is retried
without the tools field rather than failing. Tool errors reach the model as
readable text, never a traceback, so it can explain what went wrong.

```
GET /api/tools      list the tools and the current preamble
```

### Identity

Orbital identifies as Orbital, and is honest about what it runs on.

The distinction the prompt holds:

| Layer | What it is |
|---|---|
| **Nucleus** | the reasoning engine — a component |
| **Nebula** | the image engine — a component |
| **Orbital** | the whole thing — what you talk to |

Every chat request gets a system prompt establishing this, so the model
answers as Orbital rather than announcing itself as Qwen or Llama. But it is
also instructed to answer honestly if asked what model it runs on — the user
can read their own config, so pretending otherwise would just be confusing.

```
/whoami      what am I
/identity    same
/about       same
```

These answer deterministically from the engine, not from the model, so the
reply is the same every time. Change the identity with `ORBITAL_IDENTITY`.

### The theme

`gui/theme.css` is the design system. Every component draws from it, so the
whole program reads as one thing.

**Three references, one synthesis:**

- **Ferrofluid** is the substrate — deep obsidian, glossy, with an
  iridescent sheen that only shows at the rim, the way light behaves on a
  real ferrofluid surface.
- **Liquid glass** is the surface — translucent panels, blurred, with lit
  specular edges that refract the light behind them.
- **Midnight gospel** is the light — saturated cosmic gradients drifting
  slowly behind the glass. Nothing sits still, nothing is flat.

Everything is a custom property, so the entire look retunes from `:root`:
40 tokens covering colour, blur radius, corner geometry, the blob radii used
for organic shapes, and motion timing.

**Graceful degradation.** Three features carry the design and each has a
browser that predates it, so all three have `@supports` fallbacks:

| Feature | Without it | Fallback |
|---|---|---|
| `backdrop-filter` | no glass | opaque gradient panel, aurora boosted to compensate |
| `conic-gradient` | sheen renders black | linear gradient sheen |
| `mask-composite` | rims render solid | plain 1px border |

Plus `prefers-reduced-motion` (drops every animation) and `forced-colors`
(respects high-contrast mode). A `.orbital--lite` class on `<body>` turns off
blur and animation entirely for weak GPUs — the **Lite** button in the header
toggles it, which matters on integrated graphics.

### UI components

Two standalone widgets in `gui/`, both vanilla CSS with no external
dependencies:

**`radial-menu.html`** — a radial speed-dial. The toggle rotates 45 degrees
and eight items fly outward on staggered delays (0-225 ms). Pure CSS: the
state is a hidden checkbox and the animation is the `~` sibling combinator.
No JavaScript for the layout or motion.

**`workstation.html`** — the main interface, using the full theme. Fixed app
shell: chat on the left, telemetry / token / radial actions / commands on the
right. Layout is flexbox, not grid, for broader support.

**`ring-button.html`** — a button that grows four concentric colour rings on
hover, built from stacked inset box-shadows. Each shadow paints beneath the
one before it, so increasing spreads produce four 4px bands. Sizes for small,
default and large; a staggered reveal variant; focus and reduced-motion
aware.

**`action-button.html`** — a hover-expand action button. A 50px circle
grows into a 140px pill, the icon slides out of the clipped area and the
label rises into view. Variants for danger, warn and safe; a two-step
confirm state for destructive actions; keyboard-focusable and
reduced-motion aware.

**`now-playing.html`** — a Spotify player that expands on hover, from a
160x80 card to 288x160. Vinyl collapses, artwork fades in, controls slide
out. Also pure CSS for the animation.

Both degrade to demo data when the engine is unreachable, so they render
correctly before anything is configured. Point `now-playing.html` at a live
engine with a token:

```
gui/now-playing.html?token=<your engine token>
```

It then polls `/api/spotify/now` every 5 seconds and drives real playback.

### Camera

Two separate problems.

**Local webcam** is straightforward — OpenCV, one call.

```powershell
python -m core.camera probe          # which camera indices work
python -m core.camera snapshot 0     # grab a frame
```

```
/snapshot           capture from camera 0
/cameras            list local cameras
/snapshot 1         capture from camera 1
```

**Phone camera** is where the platform matters, and no amount of code
changes it:

- **Android** permits a foreground service to hold the camera. A background
  app gets killed, so a phone camera node has to stay open.
- **iOS** does not permit background camera access at all. The app must be
  foregrounded. There is no application-layer workaround.

So the workable design is: the phone runs a streaming app, and Orbital
consumes that stream. Tailscale makes the phone reachable from anywhere
without exposing it to the internet.

```python
camera.phone_url("100.64.0.5")            # -> http://100.64.0.5:8080/video
camera.snapshot("http://100.64.0.5:8080/video")
```

`watch_motion()` runs a frame-difference loop and saves a capture per event,
which is the usual way to turn a camera into something useful.

Install OpenCV first: `pip install opencv-python`

---

## Making your own models — the accumulation loop

Three separate claims live in "build my own LLM from the best public models."
They have very different truth values, and it matters which is which.

### 1. Merging existing models — real, and easier than you think

You can combine public models into a new one without training. Tools like
`mergekit` implement SLERP, TIES, DARE and task arithmetic, and it works on
consumer hardware — merging is arithmetic over weights, not gradient descent.

```bash
pip install mergekit
mergekit-yaml config.yaml ./my-model --cuda
```

```yaml
# config.yaml — average two SDXL fine-tunes, keeping what each is good at
slices:
  - sources:
      - model: /models/pony_v6.safetensors
        parameters: { weight: 0.6 }
      - model: /models/illustrious.safetensors
        parameters: { weight: 0.4 }
    parameters: { density: 0.8 }
merge_method: task_arithmetic
dtype: float16
```

The caveat: merging averages *weights*, and weights are not interpretable
modules. Two checkpoints fine-tuned from the same base merge well. Different
architectures do not merge at all. "Copying the best parts" works at the
level of whole models or LoRAs, not individual capabilities.

### 2. Training your own LoRAs — real, and the actual mechanism

This is what compounds. 20–50 curated images, a few hours, and you have an
adapter that captures something specific. `core/dataset.py` handles the
curation and guard rails; `kohya-ss/sd-scripts` does the training.

### 3. A self-improving intellect that grows on its own — not achievable

This is the part that needs saying plainly. A model does not learn from being
used. Nothing in the system gets smarter because you prompted it. There is no
feedback path from inference to weights, and adding one is not a matter of
code — it is the training problem, and training is a distinct, expensive,
supervised process.

What *is* achievable is an **accumulation loop**: artifacts you make are kept,
scored, and reused. It compounds because the artifacts are permanent, not
because anything learns.

### Model collapse — why the guard rails exist

Training a model on its own output makes it worse. Not a hypothesis —
published in Nature (2024) and reproduced widely. Each round loses a little of
the output distribution's tails, and the losses compound. The failure is
invisible per-image: every individual sample still looks fine while diversity
quietly disappears.

Two published mitigations, both enforced in `core/dataset.py`:

- **Accumulate real data alongside synthetic** ("Is Model Collapse
  Inevitable?", 2024) — at least 30% real, enforced at build time
- **Self-verify before including** ("Self-Verification Provably Prevents Model
  Collapse", NeurIPS 2025) — every synthetic item must record what checked it

Plus a depth cap: after 3 synthetic generations, go back to real data.

```
$ python -m core.model_cli dataset check my_lora_v3
dataset failed guard rails:
  - real fraction is 12%; at least 30% is required. Training on synthetic
    data alone causes model collapse (Nature, 2024) — the model gets worse
    each round while still looking fine per-image.
  - synthetic depth is 4; the limit is 3. Return to real data before another round.
```

It refuses. That refusal is the feature.

### Provenance

Every artifact records what it was made from, so the graph is a DAG you can
walk in both directions:

```
$ python -m core.model_cli lineage fusion_v2
fusion_v2 [merged/merged] (a1b2c3d4)
  fusion_v1 [merged/merged] (e5f6a7b8)
    pony_v6 [base/downloaded] (11223344)
    illustrious [base/downloaded] (55667788)
  style_a [lora/trained] (99aabbcc)
    pony_v6 [base/downloaded] (11223344)
    curated_a [dataset/curated] (ddeeff00)
```

Merges have several parents. LoRAs have a base and a dataset. That graph is
what makes the whole thing auditable — you can always ask where something came
from and get a real answer.

### Evaluating

"Better" needs a definition or every change looks like progress.
`core/evals.py` runs a fixed prompt/seed grid against a base and a candidate
and reports paired divergence:

```
$ python -m core.model_cli eval --base pony_v6 --candidate fusion_v1
Eval: pony_v6-vs-fusion_v1
  variants: base, candidate
  baseline: base
    candidate: divergence 0.084 (15 paired) — moderate — a real change,
               base model likely intact
```

It detects the two failure modes that matter: a variant that changed nothing
(`IDENTICAL`) and one that destroyed the base model (`extreme`). Automated
aesthetic scoring is not solved and this does not pretend otherwise — final
judgement is yours, with a side-by-side to make it from.

### CLI

```powershell
python -m core.model_cli stats
python -m core.model_cli add pony_v6 --kind base --method downloaded --path /models/pony.safetensors
python -m core.model_cli add style_a --kind lora --method trained --parents pony_v6,curated_a --config rank=32
python -m core.model_cli add fusion_v1 --kind merged --method merged --parents pony_v6,illustrious
python -m core.model_cli lineage fusion_v2
python -m core.model_cli dataset check my_dataset    # exits 1 if unsafe
python -m core.model_cli eval --base pony_v6 --candidate fusion_v1 --save
```

`dataset check` returns a non-zero exit code when the guard rails fail, so it
can gate a training script directly:

```powershell
python -m core.model_cli dataset check my_lora_v3; if ($?) { python train_lora.py }
```

### What is not possible

- **A text LLM built from scratch.** Pretraining costs millions of dollars.
  LoRA fine-tuning an existing model is the achievable version.
- **Capability-level grafting.** You cannot extract "reasoning" from one model
  and paste it into another. Merging operates on whole weight tensors.
- **Self-improvement without training.** No amount of clever prompting adds
  capability to fixed weights.
- **Orbital as a "final fusion" that transcends its parts.** Merging produces
  a model that is a blend of its parents, not more than the sum of them.
  Usually it is somewhat less than the best parent at any single task.

---

## Hive routing — splitting work across machines

The mesh connects nodes. This decides which node *does the work*. Those are
different problems, and this is the one that actually buys throughput.

### Why not split one image across machines

Intra-image parallelism needs device-to-device activation transfer on every
step. For SDXL that is ~10 MB per step. Measured against a ~6 s local
generation:

| Setup | Result |
|---|---|
| 2 devices, gigabit LAN | 5.4 s (10% faster) |
| 2 devices, Tailscale direct | 5.9 s (marginal) |
| 2 devices, Tailscale relayed | **20.5 s (3x slower)** |
| 4 devices, gigabit LAN | 3.9 s |

It only scales properly on NVLink-class interconnect — xDiT's research used
600 GB/s NVLink and 100 Gbps Ethernet. The one intra-image split that
survives a normal network is **CFG parallelism** (a single 0.13 MB latent
all-gather per step, ~30 ms total over 25 steps), and that needs xDiT rather
than ComfyUI.

### What does work: routing whole jobs

Splitting a batch needs **no communication at all** and scales linearly:

| Workload | 1 node | 2 nodes | 4 nodes |
|---|---|---|---|
| 20 images | 120 s | 60 s | 30 s |
| 10 video clips (9 min each) | 90 min | 45 min | 22.5 min |

Video is where this matters most, because clips take minutes.

### Setup

```powershell
$env:ORBITAL_BACKENDS = "desktop=http://100.64.0.5:8188,laptop=http://100.64.0.9:8188@2"
python start.py
```

Format is `name=url[@weight]`, comma-separated. Weight biases routing toward
a beefier machine. The local instance is always in the pool, so a
single-machine setup needs no configuration.

Each entry must be a ComfyUI instance with `--listen` set:

```powershell
python main.py --listen 0.0.0.0 --port 8188
```

Reach them over Tailscale by IP or MagicDNS name.

### How routing decides

1. **Reachable** — probes `/queue`; unreachable nodes are skipped
2. **Capable** — an image-only node never gets a video job
3. **Not in cooldown** — 3 consecutive failures pauses a node for 60 s
4. **Least loaded** — `(running + pending) / weight`, lowest wins

Probe results are cached for 5 s and capability checks for 5 min, so routing
adds no meaningful latency.

### Failover

A job that fails is retried on the next-best node, up to 3 attempts. The job
record shows which node ran it and how many attempts it took:

```json
{"status": "done", "backend": "desktop", "attempts": 1,
 "result": {"path": "...", "backend": "desktop"}}
```

Pin a job to a specific node with `"backend": "laptop"` in the request.

### Worker count

Defaults to one worker per configured backend, capped at `ORBITAL_WORKERS`
(4). With a single backend, extra workers just contend for the same GPU —
they only help across machines.

---

## The mesh

Envelope: `{"v":1,"type":...,"from":...,"ts":...,"payload":...}`

Types: `hello`, `welcome`, `ping`, `pong`, `error`, plus anything you broadcast.

```powershell
$env:ORBITAL_MESH_SECRET = "shared-secret"
$env:ORBITAL_PEERS = "ws://100.64.0.5:8765"   # Tailscale IP of the other node
python start.py
```

Wrong secret, wrong protocol version, and malformed JSON are all rejected
without dropping the connection.

It moves messages and keeps connections alive. Routing, consensus and
scheduling are **not** implemented, and the code does not pretend otherwise.

---

## Still not built

Named honestly, so nothing is mistaken for working:

- **Wi-Fi CSI sensing.** Every `5555` reference in the old tree was a browser
  `alert()`. No packet capture, no subcarrier analysis.
- **The spatial map engine.** Never existed.
- **`ttyd.exe`.** Committed to the old repo, never launched by any script.
  `embed_console.py` iframed port 7681 at nothing. Not carried over.
- **Splitting a single image across machines.** Measured slower than local
  on any ordinary network. Jobs are routed whole instead.
- **Autonomous self-improvement.** Nothing learns from being used. Artifacts
  accumulate; the weights do not change on their own.
- **Video on 8 GB VRAM.** A 5s 720p clip is ~9 min on an RTX 4090 and
  roughly 90 min on a GTX 1080. The code works; the hardware does not.
- **Phone camera in the background.** A platform restriction on both iOS and
  Android, not something code can route around.
- **Training from scratch.** Fine-tuning and merging are achievable.
  Pretraining is not.
- **Automatic state sync over the mesh.** State moves when you export and
  import it. Nodes do not yet push state to each other unprompted.
- **Compute offloading.** No capability advertisement, no job dispatch.

See `orbital_roadmap.md` for the full plan and the reasoning behind what is
and is not worth attempting.
