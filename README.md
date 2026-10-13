# Orbital

A local-first assistant. Runs entirely on your own hardware.

## Quick start

```bash
pip install -r requirements.txt
```

Then double-click `Orbital.bat`, or on any platform:

```bash
python start.py
```

## Layout

```
core/       the engine - 25 modules
gui/        the interface
tools/      diagnostics and maintenance
tests/      20 suites, 493 checks
docs/       audit, roadmap, full reference
```

## Reading order

1. **`README.md`** (this file) - what it is and how to run it
2. **`CHANGELOG.md`** - what changed from the original, and why
3. **`docs/REFERENCE.md`** - every module, endpoint and design decision
4. **`docs/AUDIT.md`** - what was wrong with the original, in detail
5. **`docs/ROADMAP.md`** - what is achievable, what is not, and why

## Status

| Component | State |
|---|---|
| Engine | working - loopback only, token-gated |
| Interface | working - themed |
| Chat | working - tool calling, identity |
| Image generation | needs ComfyUI + a checkpoint |
| Video | needs ComfyUI + Wan 2.2; impractical on 8 GB VRAM |
| Hue / Spotify / camera | working, needs pairing |
| Multi-machine | working - `ORBITAL_BACKENDS` |
| Accounts | optional, off by default |

Check what you have:

```bash
python tools/check_requirements.py
```

Run the tests:

```bash
python tests/run_tests.py
```
