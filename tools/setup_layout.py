"""Relocate Orbital out of the user profile, onto the machine.

Why this matters:

  * **OneDrive.** Anything under %USERPROFILE%\\OneDrive syncs to Microsoft's
    cloud. Generated images and video would upload automatically.
  * **Portability.** A user-profile install dies with the account. A
    machine-level one survives profile resets and can be moved to another PC.
  * **Space.** Ollama models and Docker images are tens of gigabytes. Keeping
    them in the profile bloats roaming profiles and backups.

    python setup_layout.py                    # report only, change nothing
    python setup_layout.py --apply            # create dirs + set env vars
    python setup_layout.py --apply --move-ollama
    python setup_layout.py --apply --system   # machine-wide (needs admin)

Nothing is deleted. Ollama models are *moved*, and only with --move-ollama.
"""

import argparse
import os
import shutil
import subprocess
import sys

TARGET_ROOT = r"C:\Orbital"
TARGET_APP = os.path.join(TARGET_ROOT, "app")
TARGET_DATA = os.path.join(TARGET_ROOT, "data")
TARGET_MODELS = os.path.join(TARGET_ROOT, "models")

# Directories under the profile worth reporting on.
PROFILE_HOTSPOTS = [
    (".ollama", "Ollama models and config"),
    (".docker", "Docker Desktop data"),
    (".cache", "general cache"),
    ("AppData\\Local\\Temp", "temporary files"),
    ("OneDrive\\Desktop\\Orbital", "the old Desktop tree (syncs to cloud)"),
    ("Downloads", "downloads"),
]


def human(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def dir_size(path, limit_seconds=12):
    """Total size, with a time limit so a huge tree cannot hang the tool."""
    import time

    total = 0
    files = 0
    deadline = time.time() + limit_seconds
    for root, dirs, names in os.walk(path):
        if time.time() > deadline:
            return total, files, True
        for name in names:
            try:
                total += os.path.getsize(os.path.join(root, name))
                files += 1
            except OSError:
                continue
    return total, files, False


def report_profile():
    home = os.path.expanduser("~")
    print("=" * 72)
    print(f"USER PROFILE: {home}")
    print("=" * 72)
    print("These are inside the profile. Sizes are approximate.\n")

    findings = []
    for rel, label in PROFILE_HOTSPOTS:
        path = os.path.join(home, rel)
        if not os.path.isdir(path):
            continue
        size, files, truncated = dir_size(path)
        findings.append((size, rel, label, files, truncated))

    if not findings:
        print("  nothing significant found")
        return []

    for size, rel, label, files, truncated in sorted(findings, reverse=True):
        mark = "+" if truncated else " "
        print(f"  {human(size):>10s}{mark}  {rel}")
        print(f"              {label} ({files} files)")

    print()
    print("  + means the scan hit its time limit; the real size is larger.")
    total = sum(f[0] for f in findings)
    print(f"\n  total scanned: {human(total)}")
    return findings


def plan_layout():
    print()
    print("=" * 72)
    print("TARGET LAYOUT")
    print("=" * 72)
    for path, what in (
        (TARGET_ROOT, "everything Orbital, outside the profile"),
        (TARGET_APP, "the code (core/, start.py)"),
        (TARGET_DATA, "state, logs, generated images and video"),
        (TARGET_MODELS, "model files (Ollama, checkpoints, LoRAs)"),
    ):
        exists = "exists" if os.path.isdir(path) else "will be created"
        print(f"  {path}")
        print(f"      {what}  [{exists}]")

    print()
    print("Environment variables to set:")
    print(f"  ORBITAL_BASE   = {TARGET_DATA}")
    print(f"  OLLAMA_MODELS  = {TARGET_MODELS}")
    print()
    print("ORBITAL_BASE moves state, logs and generated media out of the")
    print("profile. OLLAMA_MODELS moves the model blobs, which are the bulk.")
    print("Ollama must be restarted for OLLAMA_MODELS to take effect.")


def create_dirs(apply):
    made = []
    for path in (TARGET_ROOT, TARGET_APP, TARGET_DATA, TARGET_MODELS):
        if os.path.isdir(path):
            continue
        if apply:
            try:
                os.makedirs(path, exist_ok=True)
                made.append(path)
            except OSError as exc:
                print(f"  ! could not create {path}: {exc}")
        else:
            made.append(path)
    return made


def set_env(name, value, system, apply):
    """Set a persistent environment variable on Windows."""
    if os.name != "nt":
        return False, "not Windows"

    if not apply:
        return True, "(dry run)"

    argv = ["setx", name, value]
    if system:
        argv.append("/M")

    try:
        res = subprocess.run(argv, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as exc:
        return False, str(exc)

    if res.returncode == 0:
        return True, "set"
    err = (res.stderr or res.stdout or "").strip()
    if system and ("access" in err.lower() or "denied" in err.lower()):
        return False, "needs an Administrator prompt for --system"
    return False, err or f"exit code {res.returncode}"


def move_ollama(apply):
    """Move %USERPROFILE%\\.ollama\\models to the machine-level folder."""
    home = os.path.expanduser("~")
    src = os.path.join(home, ".ollama", "models")

    if not os.path.isdir(src):
        print("  no .ollama\\models found; nothing to move")
        return True

    size, files, _ = dir_size(src)
    dest = TARGET_MODELS

    print(f"  source: {src}")
    print(f"  dest  : {dest}")
    print(f"  size  : {human(size)} across {files} files")

    if not apply:
        print("  (dry run — not moved)")
        return True

    try:
        # Same volume: a rename is instant. Different volume: a copy.
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        if os.path.exists(dest):
            print(f"  ! {dest} already exists; merging would be ambiguous.")
            print(f"    Move it aside first, then re-run.")
            return False
        shutil.move(src, dest)
        print(f"  moved to {dest}")
        print(f"  set OLLAMA_MODELS={dest} and restart Ollama")
        return True
    except OSError as exc:
        print(f"  ! move failed: {exc}")
        print("    Ollama may still be running. Stop it first:")
        print("      taskkill /F /IM ollama.exe")
        print("      taskkill /F /IM 'ollama app.exe'")
        return False


def check_running():
    """Warn if Orbital or Ollama is running, since files may be locked."""
    if os.name != "nt":
        return []
    running = []
    for image in ("ollama.exe", "ollama app.exe", "python.exe", "pythonw.exe"):
        try:
            res = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {image}", "/NH"],
                capture_output=True, text=True, timeout=15,
            )
            if image.split(".")[0] in (res.stdout or "").lower():
                running.append(image)
        except (OSError, subprocess.SubprocessError):
            continue
    return running


def main(argv=None):
    global TARGET_ROOT, TARGET_APP, TARGET_DATA, TARGET_MODELS

    ap = argparse.ArgumentParser(
        prog="setup_layout",
        description="Move Orbital out of the user profile.",
    )
    ap.add_argument("--apply", action="store_true",
                    help="create directories and set env vars")
    ap.add_argument("--move-ollama", action="store_true",
                    help="move the Ollama model folder (large; stops nothing)")
    ap.add_argument("--system", action="store_true",
                    help="set machine-wide env vars instead of per-user")
    ap.add_argument("--root", default=TARGET_ROOT,
                    help=f"install root (default {TARGET_ROOT})")
    args = ap.parse_args(argv)

    TARGET_ROOT = args.root
    TARGET_APP = os.path.join(TARGET_ROOT, "app")
    TARGET_DATA = os.path.join(TARGET_ROOT, "data")
    TARGET_MODELS = os.path.join(TARGET_ROOT, "models")

    print()
    print("ORBITAL LAYOUT")
    print(f"Mode: {'APPLY' if args.apply else 'REPORT ONLY (nothing changes)'}")
    print()

    running = check_running()
    if running:
        print("! These are running and may lock files:")
        for name in running:
            print(f"    {name}")
        print("  Stop Ollama before moving its models:")
        print("    taskkill /F /IM ollama.exe")
        print()

    report_profile()
    plan_layout()

    print()
    print("=" * 72)
    print("ACTIONS")
    print("=" * 72)

    made = create_dirs(args.apply)
    if made:
        verb = "created" if args.apply else "would create"
        for path in made:
            print(f"  {verb}: {path}")
    else:
        print("  directories already present")

    print()
    for name, value in (("ORBITAL_BASE", TARGET_DATA),
                        ("OLLAMA_MODELS", TARGET_MODELS)):
        ok, detail = set_env(name, value, args.system, args.apply)
        scope = "machine" if args.system else "user"
        status = "set" if (ok and args.apply) else ("would set" if ok else "FAILED")
        print(f"  {name} = {value}  [{scope}] -> {status}"
              + (f" ({detail})" if not ok else ""))

    if args.move_ollama:
        print()
        print("  Moving Ollama models:")
        move_ollama(args.apply)

    print()
    print("=" * 72)
    if not args.apply:
        print("REPORT ONLY. Nothing was changed.")
        print()
        print("To apply:")
        print("    python setup_layout.py --apply")
        print()
        print("Add --move-ollama to relocate the model files too.")
        print("Add --system for machine-wide variables (needs Administrator).")
    else:
        print("DONE")
        print()
        print("Next steps:")
        print("  1. Restart Ollama so OLLAMA_MODELS takes effect")
        print("  2. Verify:  echo %ORBITAL_BASE%")
        print("  3. Start Orbital from the new location")
        print()
        print("Existing shells keep the old values. Open a new window.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
