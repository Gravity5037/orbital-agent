# What changed, and why

A summary of the work. The long version is in `docs/AUDIT.md`.

---

## The starting point

The original `C:\Orbital` tree had three subsystems documented as "Active"
that did not exist or did not work:

| Claimed | Reality |
|---|---|
| Nucleus LLM on 11434 | a 41-line stub returning a hardcoded string, wearing Ollama's API shape |
| GibberLink mesh on 8765 | `launch_hive_mesh.py` did not exist, in any commit |
| Wi-Fi CSI radar on 5555 | every reference was a browser `alert()` |
| Nebula image generation | `/draw` returned a formatted string claiming it had rendered an image |
| Ralph self-healing loop | called a method that did not exist; crashed silently on the first iteration |

And one live security problem: `engine.py` bound `0.0.0.0:5000` with wildcard
CORS and piped request bodies into PowerShell. On the machine this was
audited on, **27 copies** had accumulated and were listening.

---

## What was built

**Security**
- Binds `127.0.0.1` only
- Token on every route except `/api/ping`
- Explicit CORS origins, not `*`
- Shell bridge token-gated and disableable
- Refuses to start a second instance

**Honesty**
- Every backend reports failure instead of fabricating success
- `/draw` returns 503 with a reason when no image backend is running
- The self-healing loop actually restarts things, and logs when it gives up

**Capability**
- Real Ollama client, plus tool calling so the model can use the system
- Image generation via ComfyUI, with job queue and node routing
- Video via Wan 2.2, with an honest note that it is impractical on 8 GB
- Hue, Spotify and camera integrations
- State continuity (`OOSTATE.BIN`) with deterministic merge
- Model registry with provenance, plus anti-collapse guard rails
- A peer mesh that actually opens sockets

**Interface**
- A theme system: ferrofluid substrate, liquid glass surfaces, aurora light
- Radial menu, music player, action buttons — all vanilla CSS
- Served by the engine, so there is no token to paste

---

## Bugs found while building

Each of these was caught by a test, not by inspection:

1. `healer_daemon` called `inspect_and_repair()` — a method that never existed.
   It crashed on iteration one, invisibly, because output went to `DEVNULL`.
2. `setup_silent_autostart.py` had an unescaped f-string at line 33. It raised
   `SyntaxError` at compile time and never ran at all.
3. The job queue swept every `queued` job on startup, including ones submitted
   in the same process — killing legitimate work as "interrupted by a restart".
4. `hue.handle("/lights")` raised instead of returning a message, so an
   unpaired bridge produced silence rather than an explanation.
5. The session cookie authorised the UI but not API calls, so a successful
   login was followed by every request failing.
6. `_post` discarded the HTTP error body, so a model rejecting tools looked
   like a transport failure and the fallback never triggered.

---

## What is deliberately not built

- **UEFI bare-metal boot.** UEFI has no Python, no libc, no CUDA. The
  achievable version is a live boot image.
- **Through-wall Wi-Fi CSI sensing.** Needs specific NICs with CSI extraction.
  Windows does not expose CSI at all.
- **Autonomous self-improvement.** A model does not learn from being used.
  Artifacts accumulate; weights do not change.
- **Automatic security verification of downloaded code.** You can sandbox
  untrusted code; you cannot verify it is safe.
- **Splitting one image across machines.** Measured slower than local on any
  ordinary network. Jobs are routed whole instead.

Each of these is explained in `docs/ROADMAP.md`.
