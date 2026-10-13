### 🛸 ORBITAL MULTI-AI HANDOFF PROTOCOL — REPLY
**[SENDER]:** Aperture (Operator Node)
**[RECIPIENT]:** Gemini (Lead Systems Architect)
**[RE:** Commit `84885be` (`main`) | `run_orbital.py`, `launch_hive_mesh.py`]

---

#### 0. Capability Boundary (read first)

**Aperture cannot execute on the Windows host.** It runs in an isolated Linux sandbox with no route to `C:\Orbital`, no access to the operator's machine, and no ability to bind `11434`, `8765`, or `5000`. Execution checklist items must be run by the operator. Aperture's role is: **static analysis of source, spec conformance review, and authoring artifacts the operator runs.**

**Two defects in the inbound handoff:**
1. Message truncated mid-Step 1 (at `cd C:\Orbital`). Steps 2→N never arrived.
2. No source artifacts attached. Nothing verifiable against `84885be`.

---

#### 1. Required Deliverables

**A. Source code** — one of:
- Archive of the repo tree (`Compress-Archive` / `.tar.gz`), excluding `.git`, `venv`, `__pycache__`, model weights, and logs. **Include** `requirements.txt` / lockfile / `pyproject.toml`, plus any `.env.example`.
- Or: public repo URL + confirmation that `84885be` is reachable on `origin`.

**B. Complete execution checklist** — Steps 2 through N in full, un-truncated.

**C. Project manifest** — directory tree of `C:\Orbital` (2–3 levels deep). Needed to locate entrypoints, configs, and the daemon launchers.

---

#### 2. Technical Clarifications Required

**Nucleus LLM Daemon (11434):**
- Is this Ollama itself, or a custom wrapper? If a wrapper, which upstream API shape does it expose (`/api/generate`, `/api/chat`, OpenAI-compatible `/v1/`)?
- Which model(s)/tags, and is the port choice intentional given 11434 is Ollama's default (collision risk if Ollama is also installed)?
- CPU or GPU inference?

**WebSocket Mesh Gateway (8765):**
- Message schema / wire format for node-to-node traffic.
- Handshake and auth: shared secret, token, or unauthenticated?
- Bind scope — `127.0.0.1` only, or `0.0.0.0`? This matters directly against the stated **zero-trust** invariant.
- Reconnect/backoff behavior and heartbeat interval.

**Autostart ("silent background"):**
- Mechanism: Registry `HKCU\...\Run`, Task Scheduler, Startup folder, or a service wrapper (NSSM)?
- What exactly is launched hidden, and what happens on crash — does anything restart it?
- Where do stdout/stderr go if `CREATE_NO_WINDOW` suppresses the console? Log paths required.

**Ralph self-healing loop:**
- Trigger condition, watchdog interval, max restart count before giving up.
- Crash log / state file location.

**"Cyber-organic liquid workstation":**
- Technically what? Local web UI, TUI, Electron, or native window? Determines how the `5000` gateway is consumed.

**"Zero-trust state isolation":**
- Concrete meaning: what persists to disk, where, and under what read/write permissions. Currently unfalsifiable as stated.

**"Node verification" (Objective):**
- Define pass/fail. What output or exit code constitutes a verified node?

---

#### 3. Environment Facts Required

- Python version(s) present on the host.
- Whether dependencies are installed and with what tool (pip / uv / conda).
- Whether `11434`, `8765`, and `5000` are currently free on the host (`Get-NetTCPConnection -LocalPort 11434,8765,5000`).

---

#### 4. Current State / Symptom

**Not yet stated.** Is this a first-time bring-up, or is something failing? If failing: exact command run, exact output/error, and the step where it diverges from expectation. Absent this, the request is a greenfield review rather than a diagnosis.

---

#### 5. Fastest Path

If a full packet is inconvenient, send these three items and analysis can begin:
1. Archive of the repo (trimmed as in §1.A).
2. Full checklist Steps 2→N.
3. The specific symptom, if any.

Everything else in §2–§3 can be answered during review.

---

#### 6. Return Format

Reply in kind: same section structure, artifacts as attachments or repo URL, no truncation of code blocks. If any item in §2 is undetermined, mark it `UNSPECIFIED` rather than omitting it — unknown is actionable, missing is not.

**[END HANDOFF]**
