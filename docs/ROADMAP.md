# Orbital — Feasibility Triage & Build Order

Maps the full vision against what is achievable, in what order, and at what cost.
Assessed 2026-10-13 against the fixed core in `orbital-fix/`.

**The core problem this document solves:** the vision is written as a spec for a
finished system. Every item reads as "has." That's why the audit found three
subsystems documented as "Active" with no implementation — the prose ran ahead
of the code and nobody could tell where the line was. This file draws the line.

---

## Tier 0 — Already built

Shipped in `orbital-fix/`. These are real and tested (37 checks).

| Vision item | Status |
|---|---|
| Decentralized P2P mesh | `core/mesh.py` — real WS server + dialer, secret handshake, backoff reconnect |
| Private multi-device network | Mesh + Tailscale for the encrypted transport layer |
| Hardware introspection | `core/engine.py` telemetry — CPU, RAM, disk via psutil |
| Self-healing runtime | `core/supervisor.py` — spawn, watch, restart, backoff, give up, log |
| Silent background operation | `launch_orbital_silent.vbs`, `install_autostart.py` |
| Glassmorphic UI (base) | `gui/cyber_organic_workstation.html` — obsidian/cyan, live telemetry |
| Master admin authority (local) | Token gate on every `/api/*` route |
| Self-optimizing for device | Partially — telemetry reports capability; nothing acts on it yet |

---

## Tier 1 — Real, achievable, high value

Weeks of work each. No exotic hardware. These are the ones to do next.

| Vision item | What it actually takes |
|---|---|
| **OOSTATE.BIN state continuity** | Serialize conversation + attention cache + logs to a portable file. Already 80% there: `state/chat_memory.json` exists. Real work is schema versioning and conflict resolution when two nodes diverge. **Highest value-per-effort item on this list.** |
| **Compute offloading** | A job protocol over the mesh: capability advertisement, dispatch, result return, timeout. The mesh transports it today; you need a scheduler on top. Start with one job type (chat) before generalizing. |
| **Camera / OCR / face / gesture** | All mature libraries: OpenCV, MediaPipe (pose + hands), Tesseract, `face_recognition`. Genuinely achievable. Note: `orbital_vision.py` in your repo is already a start. |
| **Smart home control** | Real public APIs: Hue (local bridge, no cloud needed), Spotify Web API, Nest (SDM API, OAuth required). Each is a contained project. |
| **3D Three.js nucleus orb** | Pure frontend. Fun, visible, low risk. Mesh states driven by real events from the engine rather than hardcoded. |
| **Global hotkeys / wake word** | Hotkeys are trivial (`keyboard` lib or Windows API). Wake word: openWakeWord or Porcupine. Local, no cloud. |
| **Capability advertisement** | Each node reports what it can do; the mesh registry carries it. Prerequisite for offloading. |

---

## Tier 2 — Real but substantial

Months. Legitimate engineering, no breakthroughs needed.

| Vision item | What it actually takes |
|---|---|
| **Sovereign boot** | See Tier 4 for why UEFI+Python isn't it. The realistic version: a bootable Linux live image (or Chromebook developer-mode image) that auto-launches Orbital. `core/adaptation_engine.py` already generates a shell recipe for this — it's the right instinct, just needs to actually work. |
| **Skill sharing** | Downloading and running code from peers is buildable *with* a sandbox: WASM for pure compute, or containers with dropped capabilities. **But see Tier 4 on "verify for security vulnerabilities."** |
| **Automated repair loop** | Detect failure (have it), reproduce in a sandbox, propose a patch, run tests, present for approval. Works well on narrow, well-tested problems. Works badly on anything ambiguous. |
| **Multi-node scheduling** | Which node runs what, based on capability + load + battery. This is a distributed-systems project. Start with manual pinning. |

---

## Tier 3 — Oversold as written

The capability is real; the marketing outruns it. Worth knowing before you spend months.

### Wi-Fi CSI through-wall respiration

CSI sensing is real research. But it requires **specific NIC hardware with CSI
extraction** — Intel 5300, Atheros AR9xxx, or a handful of Broadcom chips with
`nexmon` patched firmware. Standard consumer Wi-Fi cards do not expose CSI, and
**Windows does not expose it at all**, at any layer.

"Respiration through walls" appears in academic papers under controlled
conditions, with known room geometry, a still subject, and specialized capture.
It is not a feature you ship on a laptop's built-in radio.

What's actually achievable: presence and coarse motion detection, on supported
hardware, on Linux, with a patched driver. That's a research project, not a
subsystem.

### BLE RSSI spatial radar

RSSI gives you *proximity with high variance*, not position. "Spatial mapping"
from RSSI alone requires multiple fixed anchors and calibration, and even then
it's room-level at best. "Through wall" works at the level of "something is
roughly over there." Not a radar, and not a map.

### Sub-second diffusion on a burner phone

Physically bounded. A phone that can't run the model can't run the model — that's
what offloading is for. "Sub-second" depends entirely on the target hardware and
model size. Achievable on a GPU desktop; not on a low-power device by definition.

### "Uncensored"

Local models without commercial guardrails are a real, available category —
that part is accurate. The caveat is that removing guardrails does not add
capability. It changes refusal behavior, not competence. Worth being precise
about what you're actually buying.

### "Omnipotent"

Not a property any system has. The concrete list underneath it (introspection,
vision, automation, governance) is mostly achievable. The word isn't.

---

## Tier 4 — Not achievable as stated

### UEFI bare-metal boot with a Python/LLM stack

UEFI applications are PE/COFF binaries. There is no Python interpreter in UEFI,
no libc, no PyTorch, no CUDA, no filesystem as you know it. Running an LLM
inference stack there means porting an entire runtime and a BLAS implementation
to a pre-boot environment with limited memory and no scheduler.

This is a multi-year effort for a funded team. And the payoff is negative:
you'd have no drivers, no GPU acceleration, no networking stack worth the name.

**The realistic version of "Sovereign Jump" is a live boot image.** Boot Linux
from USB, auto-launch Orbital, load `OOSTATE.BIN`, and you get every property
the vision actually describes — no Windows dependency, portable state, boots on
open hardware — without the impossible part. Do that instead.

### Automatic security verification of downloaded code

"Verify peer-supplied modules for security vulnerabilities" is not solvable in
the general case. You can *sandbox* untrusted code (containers, WASM, seccomp,
dropped privileges) — that's a real and good mitigation. You cannot *verify* it's
safe.

Sandbox and accept residual risk. Don't claim verification.

---

## Tier 5 — Will actively hurt you

Not "hard." These have negative expected value.

### Auto-committing self-patches to the live tree

An LLM loop that edits its own source and commits autonomously will eventually
commit something that breaks the system, and it will do so faster than you can
notice. Your own repo already shows the failure mode: 43 one-shot
`fix_*`/`patch_*` scripts that rewrite files in place, and
`core/ralph_heal_loop.py`'s "repair" rewrites `C:\Orbital` into `C:\\Orbital`.

Build the loop with a **human approval gate**. Sandbox, propose, test, show a
diff, wait for yes. The automation is in the detection and the patch generation —
not in the commit.

### Automated credential delegation to Instagram / Facebook

Two separate problems:

1. **It violates their terms of service**, and the enforcement is account
   bans — on accounts you presumably care about.
2. **It requires storing credentials** for third-party services in a system
   that, until this week, had an unauthenticated RCE endpoint reachable from any
   LAN device. A credential store in that system is a single point of total
   compromise for every account in it.

If you want account automation, the durable path is official APIs where they
exist, OAuth tokens scoped to the minimum, and OS-level credential storage
(Windows Credential Manager / DPAPI) rather than a file in the repo.

---

## Recommended build order

Ordered by value ÷ effort, with dependencies respected.

**Phase 1 — Make it real (done)**
Fixed core, tested, security closed, migration path. ← `orbital-fix/`

**Phase 2 — State continuity**
`OOSTATE.BIN` schema, versioned serialization, export/import, conflict rules.
Small, self-contained, unlocks everything cross-device. **Start here.**

**Phase 3 — Vision (the "eyes")**
Camera ingestion, OCR, face profiles, gesture. Mature libraries, visible payoff,
no exotic hardware. Also gives the UI something real to show.

**Phase 4 — Capability advertisement + offload**
Nodes report what they can do; mesh routes work. Begin with one job type.

**Phase 5 — The orb**
Three.js visualizer driven by real engine events. Frontend only, and it makes
the system legible at a glance.

**Phase 6 — Live boot image**
The achievable "Sovereign Jump." Boot Linux → auto-launch → load state.

**Phase 7 — Sandboxed skill sharing**
WASM or container sandbox. Peer-supplied modules run contained. No verification
claim.

**Phase 8 — Human-gated repair loop**
Detection and patch generation automated; the commit stays manual.

**Explicitly not planned:** UEFI-native Python, CSI through-wall sensing on
consumer hardware, automatic security verification, autonomous commits,
third-party credential automation.

---

## How to keep this honest

The failure mode that created the audit was documentation describing intent as
fact. Two rules prevent it:

1. **Every capability claim cites a test.** If `tests/` doesn't cover it, it
   goes in the "not built" section of the README.
2. **Three states, always distinct:** built, in progress, planned. The old tree
   had one state — "Active" — for all three.
