"""Orbital doctor — check this machine and say exactly what to do next.

Run this first, on the machine that will do the generating:

    python doctor.py

It checks everything the system needs, in dependency order, and ends with a
concrete next step rather than a wall of diagnostics. Nothing is modified
except creating the state/log directories if they don't exist.

Exit code is 0 if the engine can run, 1 if something essential is missing.
"""

import os
import socket
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

OK = "PASS"
WARN = "WARN"
FAIL = "FAIL"

_results = []


def report(status, label, detail=""):
    _results.append((status, label, detail))
    icon = {OK: "[ ok ]", WARN: "[warn]", FAIL: "[FAIL]"}[status]
    line = f"{icon} {label}"
    if detail:
        line += f"\n         {detail}"
    print(line)


def section(title):
    print(f"\n--- {title} " + "-" * max(0, 60 - len(title)))


# --------------------------------------------------------------- checks
def check_python():
    section("Python")
    v = sys.version_info
    if v >= (3, 9):
        report(OK, f"Python {v.major}.{v.minor}.{v.micro}")
    else:
        report(FAIL, f"Python {v.major}.{v.minor} is too old",
               "Orbital needs 3.9 or newer.")
    report(OK, f"interpreter: {sys.executable}")

    pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    if os.name == "nt":
        if os.path.exists(pyw):
            report(OK, "pythonw.exe present (silent background launch works)")
        else:
            report(WARN, "pythonw.exe not found",
                   "background autostart will flash a console window")


def check_dirs():
    section("Directories")
    from core import config

    report(OK, f"base directory: {config.BASE_DIR}")

    try:
        config.ensure_dirs()
        probe = os.path.join(config.STATE_DIR, ".doctor-probe")
        with open(probe, "w") as fh:
            fh.write("ok")
        os.remove(probe)
        report(OK, "base directory is writable")
    except OSError as exc:
        report(FAIL, "base directory is NOT writable", str(exc))
        return False

    for label, path in (("logs", config.LOG_DIR), ("state", config.STATE_DIR)):
        report(OK if os.path.isdir(path) else WARN, f"{label}: {path}")
    return True


def check_deps():
    section("Dependencies")
    missing = []

    try:
        import psutil

        report(OK, f"psutil {psutil.__version__} (telemetry)")
    except ImportError:
        report(WARN, "psutil missing — telemetry will be partial",
               "pip install psutil")
        missing.append("psutil")

    try:
        import websockets

        report(OK, f"websockets {websockets.__version__} (mesh)")
    except ImportError:
        report(WARN, "websockets missing — the mesh will be disabled",
               "pip install websockets")
        missing.append("websockets")

    if missing:
        report(WARN, "install missing packages with:",
               "pip install " + " ".join(missing))
    return True


def check_ports():
    section("Ports")

    from core import config

    for label, host, port in (
        ("engine API", config.ENGINE_HOST, config.ENGINE_PORT),
        ("mesh", config.MESH_HOST, config.MESH_PORT),
    ):
        s = socket.socket()
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, port))
            report(OK, f"{label} {host}:{port} is free")
        except OSError as exc:
            # Might be Orbital already running, which is fine.
            in_use = _probe_http(host, port)
            if in_use:
                report(WARN, f"{label} {host}:{port} already in use",
                       "if Orbital is already running, that is expected")
            else:
                report(WARN, f"{label} {host}:{port} is taken by something else",
                       str(exc))
        finally:
            s.close()


def _probe_http(host, port, path="/api/ping", timeout=2):
    import urllib.error
    import urllib.request

    try:
        with urllib.request.urlopen(f"http://{host}:{port}{path}", timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def check_gpu():
    section("GPU")
    from core import gpu

    devices = gpu.detect()
    if not devices:
        report(WARN, "no GPU detected",
               "image and video generation will be extremely slow or fail.\n"
               "         On Windows check Task Manager > Performance > GPU.")
        return None

    best = None
    for d in devices:
        vram = d.get("vram_total_gb")
        note = f" [{d['vram_note']}]" if d.get("vram_note") else ""
        if vram:
            report(OK, f"{d['name']} — {vram} GB VRAM{note}")
            if best is None or vram > best.get("vram_total_gb", 0):
                best = d
        else:
            report(WARN, f"{d['name']} — VRAM unknown",
                   "run `nvidia-smi` for an exact figure")

    if best:
        advice = gpu.advise(best["vram_total_gb"])
        report(OK, f"image generation: {advice['verdict']}")
        if advice.get("can_run"):
            can = ", ".join(f"{c['model']} ({c['precision']})" for c in advice["can_run"])
            report(OK, f"can run: {can}")
        if advice.get("cannot_run"):
            report(WARN, f"too large: {', '.join(advice['cannot_run'])}")

        vram = best["vram_total_gb"]
        if vram >= 12:
            report(OK, "LoRA training is feasible on this card")
        elif vram >= 8:
            report(WARN, "LoRA training: SD 1.5 yes, SDXL painful",
                   "consider a rented GPU for SDXL LoRA training")
        else:
            report(WARN, "LoRA training not practical on this card")

    return best


def check_comfy():
    section("Image backend (ComfyUI)")
    from core import nebula

    ok, detail = nebula.health(timeout=3)
    if not ok:
        report(WARN, f"ComfyUI not reachable at {nebula.COMFY_BASE}",
               "image generation needs it. Install:\n"
               "         git clone https://github.com/comfyanonymous/ComfyUI\n"
               "         cd ComfyUI && pip install -r requirements.txt\n"
               "         python main.py --listen 127.0.0.1 --port 8188")
        return False

    report(OK, f"ComfyUI reachable at {nebula.COMFY_BASE}")
    if detail:
        report(OK, f"{len(detail)} checkpoint(s): {', '.join(detail[:5])}")
        if len(detail) > 5:
            report(OK, f"...and {len(detail) - 5} more")
        report(OK, "image generation is ready")
    else:
        report(WARN, "no checkpoints installed",
               "put a .safetensors file in ComfyUI/models/checkpoints/.\n"
               "         SDXL fine-tunes are the usual choice — Pony V6 XL or\n"
               "         Illustrious XL, ~8 GB VRAM.")
    return True


_VIDEO_READY = None


def check_video():
    global _VIDEO_READY
    section("Video backend (Wan 2.2)")
    from core import video

    ok, detail = video.health(timeout=4)
    _VIDEO_READY = ok
    if ok:
        report(OK, "video stack is complete")
        return True

    report(WARN, "video not ready", str(detail))
    report(WARN, "video needs three files in ComfyUI:", 
           "models/diffusion_models/  <- wan2.2_ti2v_5B_fp16.safetensors\n"
           "         models/text_encoders/     <- umt5_xxl_fp8_e4m3fn_scaled.safetensors\n"
           "         models/vae/               <- wan2.2_vae.safetensors")
    report(WARN, "expect it to be slow",
           "a 5s 720p clip is ~9 minutes on an RTX 4090")
    return False


def check_ollama():
    section("Text backend (Ollama)")
    from core import config, nucleus

    ok, detail = nucleus.health(timeout=3)
    if ok:
        report(OK, f"Ollama reachable at {config.OLLAMA_BASE}")
        if detail:
            report(OK, f"models: {', '.join(detail[:6])}")
            if config.MODEL in detail:
                report(OK, f"configured model '{config.MODEL}' is present")
            else:
                report(WARN, f"configured model '{config.MODEL}' not installed",
                       f"ollama pull {config.MODEL}")
        else:
            report(WARN, "no models installed", f"ollama pull {config.MODEL}")
        return True

    report(WARN, f"Ollama not reachable at {config.OLLAMA_BASE}",
           "optional. Chat will report this honestly instead of faking a reply.\n"
           "         Install from https://ollama.com then: ollama serve")
    return False


def check_backends():
    section("Hive")
    from core import backends as backends_mod

    pool = backends_mod.registry()
    if len(pool) == 1:
        report(OK, "single node (local only)")
        report(OK, "add machines with:",
               'ORBITAL_BACKENDS="desktop=http://100.64.0.5:8188"')
        return

    report(OK, f"{len(pool)} nodes configured")
    for b in pool:
        st = b.probe(force=True)
        if st["reachable"]:
            cap = b.capability(force=True)
            kinds = ", ".join(
                k for k, v in (("image", cap["image"]), ("video", cap["video"])) if v
            ) or "nothing"
            report(OK, f"{b.name} ({b.url}) — load {st['load']}, can do: {kinds}")
        else:
            report(WARN, f"{b.name} ({b.url}) unreachable", str(st.get("error")))


def check_state():
    section("State")
    from core import auth, config, statestore

    try:
        token = auth.get_token()
        report(OK, f"API token ready ({len(token)} chars)")
        report(OK, f"token file: {config.TOKEN_FILE}")
    except OSError as exc:
        report(FAIL, "could not create the API token", str(exc))

    try:
        s = statestore.StateStore()
        if s.load(missing_ok=True):
            report(OK, f"state image found: {len(s.messages)} message(s)")
        else:
            report(OK, "no state image yet (a fresh one will be created)")
    except Exception as exc:
        report(WARN, "state image could not be read", f"{type(exc).__name__}: {exc}")


# --------------------------------------------------------------- summary
def summary(gpu_info, comfy_ready=False):
    section("Summary")
    fails = [r for r in _results if r[0] == FAIL]
    warns = [r for r in _results if r[0] == WARN]

    if fails:
        print(f"\n{len(fails)} blocking problem(s):")
        for _s, label, detail in fails:
            print(f"  - {label}")
        print("\nFix those first.")
        return 1

    print(f"\n{len([r for r in _results if r[0] == OK])} checks passed, "
          f"{len(warns)} warning(s).")

    print("\nNEXT STEPS")
    print("-" * 60)

    if not comfy_ready:
        print("1. Install ComfyUI and start it, then re-run doctor.py")
        print("2. Put a checkpoint in ComfyUI/models/checkpoints/")
        print("   For SDXL: Pony V6 XL or Illustrious XL (~8 GB VRAM)")
        print("3. Re-run: python doctor.py")
    else:
        print("1. Start Orbital:      python start.py")
        print("2. Note the API token it prints")
        print("3. Open gui/cyber_organic_workstation.html in a browser")
        print("4. Paste the token into the sidebar")
        print("5. Type /draw <prompt> and watch the gallery")

    if not _VIDEO_READY:
        print()
        print("Video is optional and can wait. Add the Wan 2.2 files")
        print("(see README) once images are working.")

    print()
    print("Verify the install any time with:  python tests/run_tests.py")
    return 0


def main():
    print("=" * 62)
    print("ORBITAL DOCTOR")
    print("=" * 62)

    check_python()
    if not check_dirs():
        return 1
    check_deps()
    check_ports()
    gpu_info = check_gpu()
    check_state()
    check_backends()
    comfy_ready = check_comfy()
    check_video()
    check_ollama()

    return summary(gpu_info, comfy_ready)


if __name__ == "__main__":
    sys.exit(main())
