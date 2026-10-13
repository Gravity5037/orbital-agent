"""Clean up the Orbital leftovers on this machine.

Tailored to the layout found here, not a generic tool. Run it in stages.

    python cleanup.py                 # report only — nothing changes
    python cleanup.py --stage 1       # the big safe wins
    python cleanup.py --stage 2       # the old repo tree
    python cleanup.py --stage 3       # the Desktop tree
    python cleanup.py --purge         # delete the trash folder for real

Nothing is deleted until you run --purge. Everything first moves to
C:\\Orbital-trash, so you can look at it before it goes.

What it will NOT touch, ever:
  * Ollama models and config
  * the working engine (C:\\Orbital2\\orbital-core)
  * orbital_audit.db — that is your hash-chained audit log
  * self-healing-loop.py — the best code in either old tree
  * anything outside the known Orbital paths
"""

import argparse
import os
import shutil
import sys
import time

TRASH = r"C:\Orbital-trash"
KEEP_DIR = r"C:\Orbital2"

# The old repo clone. Every file in it is superseded, and the two downloads
# that landed there have already been moved out.
OLD_REPO = r"C:\Orbital"

# The Desktop tree. Not a git checkout; hand-written files.
DESKTOP = os.path.join(os.path.expanduser("~"), "OneDrive", "Desktop", "Orbital")

# Files in the Desktop tree worth keeping no matter what.
DESKTOP_KEEP = {
    "self-healing-loop.py",   # the Ralph implementation, genuinely good
    "orbital_audit.db",       # the hash-chained audit log — real data
    "orbital_optical_vision.py",  # a real camera client
}

# Big re-downloadable installers. Safe to remove; both are already installed.
INSTALLERS = {
    "Docker Desktop Installer.exe": "629 MB — Docker is already installed",
    "OllamaSetup.exe": "1.56 GB — Ollama is already installed",
}

# Startup entries that point at files which no longer exist.
STARTUP_JUNK = {
    "Orbital.lnk": "points at C:\\Orbital\\launch.bat, which does not exist",
    "orbital-daemon.bat": "points at src\\daemon.py, which does not exist",
}


def human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def dir_size(path, limit=10):
    total = 0
    files = 0
    deadline = time.time() + limit
    for root, _dirs, names in os.walk(path):
        if time.time() > deadline:
            return total, files, True
        for name in names:
            try:
                total += os.path.getsize(os.path.join(root, name))
                files += 1
            except OSError:
                continue
    return total, files, False


def startup_dir():
    return os.path.join(
        os.environ.get("APPDATA", ""),
        "Microsoft", "Windows", "Start Menu", "Programs", "Startup",
    )


def move_to_trash(path, subfolder=""):
    """Move a file or directory into the trash folder. Returns (ok, detail)."""
    if not os.path.exists(path):
        return False, "does not exist"

    dest = os.path.join(TRASH, subfolder, os.path.basename(path.rstrip("\\/")))
    try:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        if os.path.exists(dest):
            dest += "." + time.strftime("%Y%m%d-%H%M%S")
        shutil.move(path, dest)
        return True, dest
    except OSError as exc:
        return False, str(exc)


# --------------------------------------------------------------- stages
def report():
    print("=" * 70)
    print("ORBITAL CLEANUP — what is on this machine")
    print("=" * 70)

    if os.path.isdir(OLD_REPO):
        size, files, truncated = dir_size(OLD_REPO)
        mark = "+" if truncated else ""
        print(f"\n  {OLD_REPO}")
        print(f"    {human(size)}{mark} across {files} files")
        print("    The old repo clone. Superseded by C:\\Orbital2\\orbital-core.")
        print("    Contains 43 one-shot mutator scripts and the vulnerable engine.py.")

    if os.path.isdir(DESKTOP):
        size, files, truncated = dir_size(DESKTOP)
        mark = "+" if truncated else ""
        print(f"\n  {DESKTOP}")
        print(f"    {human(size)}{mark} across {files} files")
        print("    Mostly two installers (2.1 GB) plus a few real files.")
        print("    Inside OneDrive, so it syncs to Microsoft's cloud.")

        for name, why in INSTALLERS.items():
            full = os.path.join(DESKTOP, name)
            if os.path.exists(full):
                print(f"      - {name}  ({why})")

    sd = startup_dir()
    if os.path.isdir(sd):
        stale = [n for n in STARTUP_JUNK if os.path.exists(os.path.join(sd, n))]
        if stale:
            print(f"\n  {sd}")
            for name in stale:
                print(f"    {name}  ({STARTUP_JUNK[name]})")

    if os.path.isdir(TRASH):
        size, files, _ = dir_size(TRASH)
        print(f"\n  {TRASH}")
        print(f"    {human(size)} across {files} files — already staged for deletion")
        print("    Run with --purge to delete it permanently.")

    print("\n" + "=" * 70)
    print("STAGES")
    print("=" * 70)
    print("  --stage 1   the 2.1 GB of installers, and the dead startup entries")
    print("  --stage 2   the old repo tree (C:\\Orbital)")
    print("  --stage 3   the rest of the Desktop tree")
    print("  --purge     delete the trash folder for real")
    print()
    print("  Everything moves to C:\\Orbital-trash first. Nothing is deleted")
    print("  until you run --purge.")


def stage1():
    """Installers and dead startup entries. Zero risk."""
    print("\nSTAGE 1 — installers and dead startup entries")
    print("-" * 70)

    if os.path.isdir(DESKTOP):
        for name in INSTALLERS:
            full = os.path.join(DESKTOP, name)
            if os.path.exists(full):
                size = os.path.getsize(full)
                ok, detail = move_to_trash(full, "installers")
                if ok:
                    print(f"  moved {name}  ({human(size)})")
                else:
                    print(f"  ! could not move {name}: {detail}")
            else:
                print(f"  (not present) {name}")

    sd = startup_dir()
    for name in STARTUP_JUNK:
        full = os.path.join(sd, name)
        if os.path.exists(full):
            ok, detail = move_to_trash(full, "startup")
            print(f"  {'moved' if ok else '! could not move'} {name}"
                  + ("" if ok else f": {detail}"))
        else:
            print(f"  (not present) {name}")


def stage2():
    """The old repo tree."""
    print("\nSTAGE 2 — the old repo tree")
    print("-" * 70)

    if not os.path.isdir(OLD_REPO):
        print(f"  {OLD_REPO} not found")
        return

    size, files, _ = dir_size(OLD_REPO)
    print(f"  {OLD_REPO}: {human(size)} across {files} files")

    # Refuse if the working install is inside it.
    if os.path.abspath(KEEP_DIR).startswith(os.path.abspath(OLD_REPO)):
        print("  ! C:\\Orbital2 is inside this tree; refusing to move it")
        return

    ok, detail = move_to_trash(OLD_REPO, "old-repo")
    if ok:
        print(f"  moved the whole tree to {detail}")
    else:
        print(f"  ! could not move: {detail}")


def stage3():
    """The rest of the Desktop tree, keeping the files worth keeping."""
    print("\nSTAGE 3 — the rest of the Desktop tree")
    print("-" * 70)

    if not os.path.isdir(DESKTOP):
        print(f"  {DESKTOP} not found")
        return

    kept = []
    moved = 0

    for name in sorted(os.listdir(DESKTOP)):
        full = os.path.join(DESKTOP, name)

        if name in DESKTOP_KEEP:
            kept.append(name)
            continue

        # Keep anything that is clearly data rather than code.
        if name.lower().endswith((".db", ".sqlite", ".gguf", ".safetensors")):
            kept.append(name)
            continue

        ok, _detail = move_to_trash(full, "desktop-tree")
        if ok:
            moved += 1

    print(f"  moved {moved} item(s) to trash")
    if kept:
        print("  kept:")
        for name in kept:
            print(f"    {name}")


def purge():
    """Delete the trash folder for real."""
    print("\nPURGE")
    print("-" * 70)

    if not os.path.isdir(TRASH):
        print(f"  {TRASH} does not exist; nothing to purge")
        return

    size, files, _ = dir_size(TRASH)
    print(f"  {TRASH}: {human(size)} across {files} files")
    print()
    print("  This is permanent. There is no undo.")
    print("  Look inside the folder first if you have not already.")
    print()

    answer = input("  Type DELETE to confirm: ").strip()
    if answer != "DELETE":
        print("  cancelled — nothing was deleted")
        return

    try:
        shutil.rmtree(TRASH)
        print(f"  deleted {TRASH}  ({human(size)} reclaimed)")
    except OSError as exc:
        print(f"  ! could not delete: {exc}")
        print("    Close any Explorer windows showing the folder, then retry.")


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="cleanup",
        description="Remove Orbital leftovers. Moves to trash; never deletes directly.",
    )
    ap.add_argument("--stage", type=int, choices=[1, 2, 3],
                    help="run one stage")
    ap.add_argument("--purge", action="store_true",
                    help="delete the trash folder permanently")
    ap.add_argument("--all", action="store_true",
                    help="run all three stages in order")
    args = ap.parse_args(argv)

    if args.purge:
        purge()
        return 0

    if args.all:
        print("Running all stages. Everything goes to", TRASH)
        stage1()
        stage2()
        stage3()
        print()
        print("=" * 70)
        print(f"Done. Inspect {TRASH}, then run --purge to delete it.")
        print("=" * 70)
        return 0

    if args.stage == 1:
        stage1()
        return 0
    if args.stage == 2:
        stage2()
        return 0
    if args.stage == 3:
        stage3()
        return 0

    report()
    return 0


if __name__ == "__main__":
    sys.exit(main())
