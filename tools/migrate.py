"""Migrate an existing C:\\Orbital to the fixed layout.

Safety rules, because the old tree is full of scripts that rewrite files in
place and you have probably lost track of which version is live:

  * DRY RUN BY DEFAULT. Nothing is written without --apply.
  * Never deletes. Everything it retires is MOVED to legacy/.
  * Refuses to touch anything outside the target directory.
  * Prints a full plan before doing anything.

Usage:
    python migrate.py                 # show the plan, change nothing
    python migrate.py --apply         # move old files into legacy/
    python migrate.py --apply --purge # also move the 40 one-shot mutators
"""

import argparse
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core import config, logutil  # noqa: E402

log = logutil.get_logger("migrate")

# Modules that are now superseded. Moved to legacy/, never deleted.
SUPERSEDED = [
    "engine.py",              # replaced by core/engine.py
    "healer_daemon.py",       # replaced by core/supervisor.py
    "orbital_sync_engine.py", # returned SUCCESS unconditionally
    "run_orbital.py",         # ran git pull on every launch
    "setup_silent_autostart.py",  # SyntaxError; replaced by install_autostart.py
    "launch_nucleus_silent.vbs",
    "launch_orbital_master.vbs",  # killed every python.exe on the machine
    "gibberlink_websocket_gateway-v2.py",  # imported a module that never existed
    "core/ralph_heal_loop.py",    # superseded by core/supervisor.py
]

# The one-shot mutator scripts. All of them rewrite other files in place.
PREFIXES = ("fix_", "patch_", "repair_", "upgrade_", "update_", "deploy_")
KEEP = {"update.py"}  # update.py is a real Ollama client, not a mutator


def find_mutators(base):
    out = []
    for name in sorted(os.listdir(base)):
        if not name.endswith(".py"):
            continue
        if name in KEEP:
            continue
        if name.startswith(PREFIXES) or name in ("auto_fix.py", "clean_orbital_dir.py"):
            out.append(name)
    return out


def plan(base, purge):
    moves = []
    for rel in SUPERSEDED:
        path = os.path.join(base, rel.replace("/", os.sep))
        if os.path.exists(path):
            moves.append(rel)
    if purge:
        for name in find_mutators(base):
            if name not in moves:
                moves.append(name)
    return moves


def apply_moves(base, moves, legacy):
    os.makedirs(legacy, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    done = []

    for rel in moves:
        src = os.path.join(base, rel.replace("/", os.sep))
        if not os.path.exists(src):
            continue

        # Never escape the target directory.
        if os.path.commonpath([os.path.abspath(base), os.path.abspath(src)]) != os.path.abspath(base):
            log.warn(f"refusing to move {src} (outside {base})")
            continue

        dest = os.path.join(legacy, rel.replace("/", os.sep))
        if os.path.exists(dest):
            root, ext = os.path.splitext(dest)
            dest = f"{root}.{stamp}{ext}"
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        try:
            shutil.move(src, dest)
            done.append(rel)
            log.info(f"moved {rel} -> legacy/")
        except OSError as exc:
            log.error(f"could not move {rel}: {exc}")

    return done


def main():
    ap = argparse.ArgumentParser(description="Migrate C:\\Orbital to the fixed layout.")
    ap.add_argument("--base", default=config.BASE_DIR,
                    help=f"target directory (default: {config.BASE_DIR})")
    ap.add_argument("--apply", action="store_true", help="actually move files")
    ap.add_argument("--purge", action="store_true",
                    help="also retire the one-shot fix_/patch_/deploy_ scripts")
    args = ap.parse_args()

    base = os.path.abspath(args.base)
    legacy = os.path.join(base, "legacy")

    if not os.path.isdir(base):
        log.error(f"target directory does not exist: {base}")
        return 1

    log.info("=" * 66)
    log.info(f"Target     : {base}")
    log.info(f"Legacy dir : {legacy}")
    log.info(f"Mode       : {'APPLY' if args.apply else 'DRY RUN (nothing will change)'}")
    log.info("=" * 66)

    moves = plan(base, args.purge)

    if not moves:
        log.info("Nothing to retire. Tree already looks migrated.")
        return 0

    log.info(f"{len(moves)} file(s) would be retired to legacy/:")
    for rel in moves:
        log.info(f"    {rel}")

    if not args.purge:
        count = len(find_mutators(base))
        if count:
            log.info("")
            log.info(f"Note: {count} one-shot mutator script(s) are still present.")
            log.info("Re-run with --purge to retire those too.")

    log.info("")
    if not args.apply:
        log.info("DRY RUN — nothing was changed.")
        log.info("Re-run with --apply to perform the move.")
        return 0

    log.info("Applying…")
    done = apply_moves(base, moves, legacy)
    log.info("")
    log.info(f"Moved {len(done)} file(s) to {legacy}.")
    log.info("Nothing was deleted. Restore any file by moving it back.")
    log.info("")
    log.info("Next steps:")
    log.info("  1. python start.py --check")
    log.info("  2. python start.py")
    log.info("  3. python install_autostart.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
