"""Orbital launcher.

One entrypoint that starts everything, and does nothing else. Notably it does
NOT run `git pull` — the old run_orbital.py fast-forwarded the working tree
on every launch with the output discarded, so a deployment step silently
rewrote the code you were running.

Usage:
    python start.py              # foreground, logs to console
    python start.py --check      # preflight only, then exit
    python start.py --background # detach on Windows (no console window)
"""

import argparse
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core import config, logutil  # noqa: E402

log = logutil.get_logger("startup")


def preflight():
    """Report what's present. Returns True if the engine can start."""
    config.ensure_dirs()
    problems = []

    log.info(f"Base directory : {config.BASE_DIR}")
    log.info(f"Python         : {sys.version.split()[0]} ({sys.executable})")
    log.info(f"Engine         : http://{config.ENGINE_HOST}:{config.ENGINE_PORT}")
    log.info(f"Mesh           : ws://{config.MESH_HOST}:{config.MESH_PORT}")

    try:
        import psutil  # noqa: F401

        log.info("psutil         : installed (real telemetry)")
    except ImportError:
        log.warn("psutil         : MISSING — telemetry will be partial")
        problems.append("pip install psutil")

    try:
        import websockets  # noqa: F401

        log.info("websockets     : installed (mesh enabled)")
    except ImportError:
        log.warn("websockets     : MISSING — mesh disabled")
        problems.append("pip install websockets")

    from core import auth, nucleus

    token = auth.get_token()
    log.info(f"API token      : {token}")
    log.info(f"Token file     : {config.TOKEN_FILE}")

    ok, detail = nucleus.health(timeout=3)
    if ok:
        log.info(f"Nucleus        : reachable at {config.OLLAMA_BASE}")
        log.info(f"Models         : {', '.join(detail) or 'none installed'}")
        if config.MODEL not in detail:
            log.warn(
                f"Model '{config.MODEL}' not found. Pull it with: ollama pull {config.MODEL}"
            )
    else:
        log.warn(f"Nucleus        : NOT reachable at {config.OLLAMA_BASE}")
        log.warn("                 Engine will run; chat will report this honestly.")
        log.warn("                 Fix: install Ollama and run `ollama serve`.")

    peers = config.peers()
    log.info(f"Peers          : {', '.join(peers) if peers else 'none configured'}")

    # --- GPU, so you know what will actually run before queueing a job
    from core import gpu

    gpus = gpu.detect()
    if not gpus:
        log.warn("GPU            : none detected")
    else:
        for g in gpus:
            vram = g.get("vram_total_gb")
            label = f"{g['name']}"
            if vram:
                label += f" — {vram} GB VRAM"
            if g.get("vram_note"):
                label += f" [{g['vram_note']}]"
            log.info(f"GPU            : {label}")

        best = max((g for g in gpus if g.get("vram_total_gb")),
                   key=lambda g: g["vram_total_gb"], default=None)
        if best:
            advice = gpu.advise(best["vram_total_gb"])
            log.info(f"Image gen      : {advice['verdict']}")
            if advice["cannot_run"]:
                log.warn(f"                 too large: {', '.join(advice['cannot_run'])}")

    if config.SHELL_ENABLED:
        log.warn("Shell bridge   : ENABLED (/ps and /cmd, token-gated)")
    else:
        log.info("Shell bridge   : disabled")

    if problems:
        log.info("To install missing pieces:  " + " && ".join(problems))

    return True


def main():
    ap = argparse.ArgumentParser(description="Start the Orbital node.")
    ap.add_argument("--check", action="store_true", help="preflight then exit")
    ap.add_argument(
        "--background", action="store_true", help="detach (Windows: no console)"
    )
    args = ap.parse_args()

    preflight()
    if args.check:
        return 0

    if args.background and os.name == "nt":
        creationflags = 0x08000000  # CREATE_NO_WINDOW
        log.info("Starting supervisor in the background")
        subprocess.Popen(
            [sys.executable, "-m", "core.supervisor"],
            cwd=config.BASE_DIR,
            creationflags=creationflags,
        )
        log.info(f"Follow logs: {config.LOG_DIR}")
        return 0

    log.info("Starting supervisor in the foreground (Ctrl-C to stop)")
    from core import supervisor

    return supervisor.main()


if __name__ == "__main__":
    raise SystemExit(main())
