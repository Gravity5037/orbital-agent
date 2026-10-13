"""Orbital requirements check.

Answers one question: what do I still need to install?

    python check_requirements.py

Checks each capability in dependency order and reports NEED / HAVE / OPTIONAL,
with the exact command to fix each gap. Nothing is installed and nothing is
modified — it only looks.

Exit code is 0 if everything essential is present, 1 otherwise, so it can
gate a script.
"""

import importlib
import os
import shutil
import socket
import subprocess
import sys
import urllib.error
import urllib.request

# ---------------------------------------------------------------- helpers
HAVE = "HAVE"
NEED = "NEED"
OPT = "OPTIONAL"
SKIP = "SKIP"

_rows = []


def row(state, name, detail="", fix=""):
    _rows.append((state, name, detail, fix))


def probe_http(url, timeout=3, path=None):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status, r.read()[:400]
    except urllib.error.HTTPError as e:
        return e.code, b""
    except Exception as e:
        return 0, str(e).encode()


def port_open(host, port, timeout=1.5):
    s = socket.socket()
    s.settimeout(timeout)
    try:
        s.connect((host, port))
        return True
    except Exception:
        return False
    finally:
        s.close()


def has_module(name):
    try:
        m = importlib.import_module(name)
        return getattr(m, "__version__", "installed")
    except ImportError:
        return None


def which(exe):
    return shutil.which(exe)


# ----------------------------------------------------------------- checks
def check_python():
    v = sys.version_info
    if v >= (3, 9):
        row(HAVE, "Python", f"{v.major}.{v.minor}.{v.micro}",
            "")
    else:
        row(NEED, "Python", f"{v.major}.{v.minor} is too old",
            "Install Python 3.9 or newer from python.org")


def check_core_deps():
    for mod, why, fix in (
        ("psutil", "CPU / RAM / disk telemetry", "pip install psutil"),
        ("websockets", "the peer mesh", "pip install websockets"),
    ):
        ver = has_module(mod)
        if ver:
            row(HAVE, f"python: {mod}", str(ver), "")
        else:
            row(NEED, f"python: {mod}", why, fix)


def check_optional_deps():
    for mod, why, fix in (
        ("cv2", "camera capture (webcam + phone streams)",
         "pip install opencv-python"),
        ("PIL", "image statistics in the eval harness", "pip install Pillow"),
        ("requests", "the legacy self-healing-loop.py", "pip install requests"),
    ):
        ver = has_module(mod)
        if ver:
            row(HAVE, f"python: {mod}", str(ver), "")
        else:
            row(OPT, f"python: {mod}", why, fix)


def check_engine():
    if port_open("127.0.0.1", 5000):
        status, body = probe_http("http://127.0.0.1:5000/api/ping")
        if status == 200:
            row(HAVE, "Orbital engine", "running on 127.0.0.1:5000", "")
            return True
        row(NEED, "Orbital engine", f"port 5000 answers but /api/ping gave {status}",
            "Something else may be using port 5000")
        return False
    row(NEED, "Orbital engine", "not running",
        r"C:\Orbital2\orbital-fix\START_ORBITAL.bat")
    return False


def check_engine_full():
    """Is this the full engine or the minimal bootstrap?"""
    if not port_open("127.0.0.1", 5000):
        return
    # The full engine has /api/nebula; the bootstrap returned 404.
    status, _ = probe_http("http://127.0.0.1:5000/api/nebula")
    if status in (200, 503):
        row(HAVE, "engine build", "full (Nebula, Hue, Spotify, mesh)", "")
    elif status == 404:
        row(NEED, "engine build", "this is the minimal bootstrap",
            "Extract orbital-fix.tar.gz and run START_ORBITAL.bat")
    elif status == 401:
        row(HAVE, "engine build", "responding (needs a token to inspect)", "")


def check_ollama():
    if not port_open("127.0.0.1", 11434):
        row(NEED, "Ollama", "not reachable on 127.0.0.1:11434",
            "Install from ollama.com, then run: ollama serve")
        return
    status, body = probe_http("http://127.0.0.1:11434/api/tags")
    if status != 200:
        row(NEED, "Ollama", f"reachable but /api/tags gave {status}", "")
        return
    try:
        import json
        models = [m.get("name") for m in json.loads(body).get("models", [])]
    except Exception:
        models = []
    if models:
        row(HAVE, "Ollama", f"{len(models)} model(s): {', '.join(models[:4])}", "")
    else:
        row(NEED, "Ollama", "running but no models installed",
            "ollama pull qwen2.5-coder:7b")


def check_gpu():
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from core import gpu
        devices = gpu.detect()
    except Exception as e:
        row(OPT, "GPU detection", f"could not probe: {e}", "")
        return

    if not devices:
        row(NEED, "GPU", "none detected",
            "Image generation will be extremely slow without one")
        return

    for d in devices:
        vram = d.get("vram_total_gb")
        note = f" [{d['vram_note']}]" if d.get("vram_note") else ""
        row(HAVE, "GPU", f"{d['name']}" + (f" - {vram} GB VRAM" if vram else "") + note, "")


def check_nvidia_driver():
    """Pascal cards need 570+ for Ollama's CUDA build."""
    if not which("nvidia-smi"):
        return
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,compute_cap,driver_version",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip()
    except Exception:
        return
    if not out:
        return

    for line in out.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 3:
            continue
        name, cap, driver = parts[0], parts[1], parts[2]
        try:
            cap_f = float(cap)
            drv_f = float(driver.split(".")[0])
        except ValueError:
            continue

        # Cards at compute capability 5.0-6.2 (Maxwell through Pascal) need
        # driver 570 or newer, or Ollama's CUDA kernel will not load.
        if 5.0 <= cap_f <= 6.2:
            if drv_f >= 570:
                row(HAVE, "NVIDIA driver", f"{driver} (OK for compute {cap})", "")
            else:
                row(NEED, "NVIDIA driver",
                    f"{driver} - too old for compute {cap}",
                    "Ollama needs 570+. Get it from Windows Update > Optional "
                    "updates, or nvidia.com/drivers")
        else:
            if drv_f >= 550:
                row(HAVE, "NVIDIA driver", f"{driver} (compute {cap})", "")
            else:
                row(OPT, "NVIDIA driver", f"{driver} - consider updating", "")


def check_comfy():
    if not port_open("127.0.0.1", 8188):
        row(NEED, "ComfyUI (images)", "not running on 127.0.0.1:8188",
            "git clone https://github.com/comfyanonymous/ComfyUI\n"
            "         cd ComfyUI && pip install -r requirements.txt\n"
            "         python main.py --listen 127.0.0.1 --port 8188")
        return
    status, _ = probe_http(
        "http://127.0.0.1:8188/object_info/CheckpointLoaderSimple")
    if status == 200:
        row(HAVE, "ComfyUI (images)", "running", "")
    else:
        row(OPT, "ComfyUI (images)", f"running, probe gave {status}", "")


def check_ffmpeg():
    if which("ffmpeg"):
        row(HAVE, "ffmpeg", "on PATH", "")
    else:
        row(OPT, "ffmpeg", "not found - only needed for video post-processing",
            "winget install ffmpeg")


def check_paths():
    base = os.environ.get("ORBITAL_BASE") or (
        r"C:\Orbital2" if os.name == "nt" else os.path.dirname(os.path.abspath(__file__))
    )
    row(HAVE, "ORBITAL_BASE", base, "")
    token = os.path.join(base, "state", "engine.token")
    if os.path.exists(token):
        row(HAVE, "API token", token, "")
    else:
        row(NEED, "API token", f"not found at {token}",
            "It is created on first start")


# ----------------------------------------------------------------- output
def render():
    width = max((len(r[1]) for r in _rows), default=20) + 2
    icon = {HAVE: "[ ok ]", NEED: "[NEED]", OPT: "[opt ]", SKIP: "[skip]"}

    print()
    print("=" * 74)
    print("ORBITAL REQUIREMENTS")
    print("=" * 74)
    print()

    for state, name, detail, fix in _rows:
        print(f"{icon[state]} {name:<{width}} {detail}")
        if fix and state in (NEED, OPT):
            for line in fix.splitlines():
                print(f"{'':>6} {'':<{width}} -> {line.strip()}")

    needs = [r for r in _rows if r[0] == NEED]
    haves = [r for r in _rows if r[0] == HAVE]
    opts = [r for r in _rows if r[0] == OPT]

    print()
    print("=" * 74)
    print(f"  {len(haves)} ready, {len(needs)} missing, {len(opts)} optional")
    print("=" * 74)

    if not needs:
        print("\nEverything essential is present.")
        print("Start with:  C:\\Orbital2\\orbital-fix\\START_ORBITAL.bat")
        return 0

    print(f"\n{len(needs)} thing(s) to fix, in the order that unblocks the most:")
    print()
    for i, (_s, name, _d, fix) in enumerate(needs, 1):
        print(f"  {i}. {name}")
        if fix:
            for line in fix.splitlines():
                print(f"     {line.strip()}")
    return 1


def main():
    check_python()
    check_paths()
    check_core_deps()
    check_gpu()
    check_nvidia_driver()
    check_engine()
    check_engine_full()
    check_ollama()
    check_comfy()
    check_optional_deps()
    check_ffmpeg()
    return render()


if __name__ == "__main__":
    sys.exit(main())
