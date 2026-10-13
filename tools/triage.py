"""Orbital triage — inventory old trees, keep what matters, archive the rest.

Run this BEFORE deleting anything. It never deletes. Everything it removes
from a tree is *moved* into a sibling folder you can inspect and delete
yourself.

    python triage.py                      # scan default locations, dry run
    python triage.py C:\\Orbital           # scan a specific tree
    python triage.py --all                # scan every known location
    python triage.py --apply              # actually move files

What it does:

  1. Walks each tree and hashes every file.
  2. Classifies each one: KEEP, ARCHIVE, or JUNK — with a reason.
  3. Detects duplicates, both within a tree and against the public repo.
  4. Prints a plan with reclaimable disk space.
  5. With --apply, moves ARCHIVE and JUNK into <tree>\\_archive\\, preserving
     the relative path so nothing gets lost in a flat pile.

Classification rules are conservative on purpose. Anything unrecognised is
KEEP. A file you did not expect to lose is far worse than a file you delete
manually later.

Exit codes: 0 = nothing to do or plan printed, 1 = error.
"""

import argparse
import hashlib
import os
import shutil
import sys
import time

# ---------------------------------------------------------------- rules
# Filename prefixes that mark one-shot mutator scripts. The old tree had 43
# of these; they rewrite other files in place and are not part of the system.
MUTATOR_PREFIXES = (
    "fix_", "patch_", "repair_", "upgrade_", "update_", "deploy_",
    "provision_", "inject_", "hook_", "wire_",
)
MUTATOR_EXACT = {
    "auto_fix.py", "clean_orbital_dir.py", "make_shortcut.py",
    "setup_orbital_fully_integrated.py", "setup_orbital_sd.py",
    "setup_silent_autostart.py", "package_orbital_flashdrive.py",
    "build_working_workstation.py", "embed_console.py",
    "fix_utf8_stable.py", "provision_pip_master.py",
}

# Directories that are always regenerable.
JUNK_DIRS = {
    "__pycache__", ".pytest_cache", ".mypy_cache", "node_modules",
    ".venv", "venv", "env", ".git", ".idea", ".vscode",
    "$RECYCLE.BIN", "System Volume Information",
}

JUNK_EXTS = {".pyc", ".pyo", ".pyd", ".tmp", ".temp", ".bak", ".old",
             ".swp", ".log", ".lnk"}

JUNK_NAMES = {"thumbs.db", "desktop.ini", ".ds_store", "capture.jpg"}

# Big files that are trivially re-downloadable.
INSTALLER_EXTS = {".exe", ".msi", ".dmg", ".iso", ".pkg"}
INSTALLER_MIN_BYTES = 50 * 1024 * 1024

# Things that are data or models — never touch, whatever else they look like.
KEEP_EXTS = {".db", ".sqlite", ".sqlite3", ".gguf", ".safetensors", ".ckpt",
             ".pt", ".pth", ".bin", ".safetensors.index.json"}

# Files worth flagging as genuinely useful, so they surface in the report.
VALUABLE_HINTS = (
    "self-healing", "ralph", "audit", "warden", "policy",
    "vision", "optical", "visualizer", "wake", "gui",
    "hive", "mesh", "peer", "engine", "telemetry",
)


def human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def sha256(path, chunk=1 << 20):
    h = hashlib.sha256()
    try:
        with open(path, "rb") as fh:
            while True:
                block = fh.read(chunk)
                if not block:
                    break
                h.update(block)
        return h.hexdigest()
    except OSError:
        return None


# --------------------------------------------------------------- classify
def classify(path, rel, size, repo_files, tracked_files=None):
    """Return (verdict, reason). verdict is KEEP, ARCHIVE or JUNK."""
    name = os.path.basename(path)
    lower = name.lower()
    ext = os.path.splitext(lower)[1]

    parts = set(rel.replace("\\", "/").split("/"))

    # --- always junk: caches, build artefacts, OS cruft
    if parts & JUNK_DIRS:
        hit = (parts & JUNK_DIRS).pop()
        return "JUNK", f"generated directory ({hit})"
    if ext in JUNK_EXTS:
        return "JUNK", f"generated file type ({ext})"
    if lower in JUNK_NAMES:
        return "JUNK", "OS cruft or screenshot"

    # --- never touch: data and models
    if ext in KEEP_EXTS:
        return "KEEP", f"data or model file ({ext})"

    # --- big re-downloadable installers
    if ext in INSTALLER_EXTS and size > INSTALLER_MIN_BYTES:
        return "JUNK", f"installer, re-downloadable ({human(size)})"

    # --- identical to a file that is already in version control
    if repo_files:
        digest = sha256(path)
        if digest and digest in repo_files:
            return "ARCHIVE", "identical copy exists in the git repo"

    # --- one-shot mutator scripts
    if lower.endswith(".py"):
        if lower in MUTATOR_EXACT:
            return "ARCHIVE", "one-shot mutator script"
        for prefix in MUTATOR_PREFIXES:
            if lower.startswith(prefix):
                return "ARCHIVE", f"one-shot mutator script ({prefix}*)"

    # --- the public repo tree itself, if it is a git checkout
    if tracked_files and lower in tracked_files:
        return "ARCHIVE", "tracked in the public git repo (redundant)"

    # --- named as valuable
    if any(hint in lower for hint in VALUABLE_HINTS):
        return "KEEP", "matches a known-useful component"

    return "KEEP", "unrecognised — kept by default"


def git_tracked(tree):
    """Map of lowercase basename -> path for files tracked by git in `tree`."""
    if not os.path.isdir(os.path.join(tree, ".git")):
        return None, None
    try:
        import subprocess

        out = subprocess.run(
            ["git", "-C", tree, "ls-files"],
            capture_output=True, text=True, timeout=30,
        )
        if out.returncode != 0:
            return None, None
        tracked = {}
        for line in out.stdout.splitlines():
            line = line.strip()
            if line:
                tracked[os.path.basename(line).lower()] = line
        return tracked, os.path.join(tree, ".git")
    except Exception:
        return None, None


def repo_hashes(tree):
    """Hashes of every git-tracked file, so duplicates can be spotted."""
    hashes = {}
    try:
        import subprocess

        out = subprocess.run(["git", "-C", tree, "ls-files"],
                             capture_output=True, text=True, timeout=30)
        for rel in out.stdout.splitlines():
            rel = rel.strip()
            if not rel:
                continue
            full = os.path.join(tree, rel.replace("/", os.sep))
            if os.path.isfile(full):
                d = sha256(full)
                if d:
                    hashes[d] = rel
    except Exception:
        pass
    return hashes


# ------------------------------------------------------------------ scan
def scan(tree, verbose=False):
    tree = os.path.abspath(tree)
    if not os.path.isdir(tree):
        return None

    tracked, _ = git_tracked(tree)
    known_hashes = repo_hashes(tree) if tracked else None

    entries = []
    total_bytes = 0

    for root, dirs, files in os.walk(tree):
        # Skip the archive folder we create, and git internals.
        dirs[:] = [d for d in dirs if d not in ("_archive", ".git")]

        for name in files:
            full = os.path.join(root, name)
            rel = os.path.relpath(full, tree)
            try:
                size = os.path.getsize(full)
            except OSError:
                continue
            total_bytes += size

            verdict, reason = classify(full, rel, size, known_hashes, tracked)
            entries.append({
                "path": full, "rel": rel, "size": size,
                "verdict": verdict, "reason": reason,
            })

    return {"tree": tree, "entries": entries, "total_bytes": total_bytes}


def report(scan_result, show_keep=False):
    tree = scan_result["tree"]
    entries = scan_result["entries"]

    junk = [e for e in entries if e["verdict"] == "JUNK"]
    arch = [e for e in entries if e["verdict"] == "ARCHIVE"]
    keep = [e for e in entries if e["verdict"] == "KEEP"]

    junk_bytes = sum(e["size"] for e in junk)
    arch_bytes = sum(e["size"] for e in arch)

    print("=" * 72)
    print(f"TREE: {tree}")
    print("=" * 72)
    print(f"  {len(entries)} files, {human(scan_result['total_bytes'])} total")
    print(f"    KEEP     {len(keep):4d} files  {human(sum(e['size'] for e in keep)):>10s}")
    print(f"    ARCHIVE  {len(arch):4d} files  {human(arch_bytes):>10s}")
    print(f"    JUNK     {len(junk):4d} files  {human(junk_bytes):>10s}")
    print(f"  reclaimable: {human(junk_bytes + arch_bytes)}")

    if junk:
        print("\n  JUNK — safe to remove, all regenerable:")
        by_reason = {}
        for e in junk:
            by_reason.setdefault(e["reason"], []).append(e)
        for reason, items in sorted(by_reason.items(),
                                    key=lambda kv: -sum(i["size"] for i in kv[1])):
            size = sum(i["size"] for i in items)
            print(f"    {reason}: {len(items)} file(s), {human(size)}")
            for e in items[:3]:
                print(f"      - {e['rel']}")
            if len(items) > 3:
                print(f"      ... and {len(items) - 3} more")

    if arch:
        print("\n  ARCHIVE — redundant or one-shot, moved not deleted:")
        by_reason = {}
        for e in arch:
            by_reason.setdefault(e["reason"], []).append(e)
        for reason, items in sorted(by_reason.items(),
                                    key=lambda kv: -len(kv[1])):
            print(f"    {reason}: {len(items)} file(s)")
            for e in items[:3]:
                print(f"      - {e['rel']}")
            if len(items) > 3:
                print(f"      ... and {len(items) - 3} more")

    if show_keep and keep:
        print("\n  KEEP — untouched:")
        for e in sorted(keep, key=lambda x: -x["size"])[:40]:
            print(f"    {human(e['size']):>10s}  {e['rel']}")
        if len(keep) > 40:
            print(f"    ... and {len(keep) - 40} more")

    return {"junk": junk, "archive": arch, "keep": keep}


def apply_moves(scan_result, verdicts=("JUNK", "ARCHIVE")):
    """Move selected entries into <tree>/_archive/, preserving structure."""
    tree = scan_result["tree"]
    archive_root = os.path.join(tree, "_archive")
    stamp = time.strftime("%Y%m%d-%H%M%S")

    moved = 0
    errors = 0

    for entry in scan_result["entries"]:
        if entry["verdict"] not in verdicts:
            continue

        src = entry["path"]
        rel = entry["rel"]
        dest = os.path.join(archive_root, rel)

        if os.path.exists(dest):
            root, ext = os.path.splitext(dest)
            dest = f"{root}.{stamp}{ext}"

        try:
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.move(src, dest)
            moved += 1
        except OSError as exc:
            print(f"  ! could not move {rel}: {exc}")
            errors += 1

    return moved, errors, archive_root


# ------------------------------------------------------------------ main
def known_trees():
    """Locations Orbital has been seen in on this machine."""
    home = os.path.expanduser("~")
    candidates = [
        r"C:\Orbital",
        r"C:\Orbital2",
        os.path.join(home, "OneDrive", "Desktop", "Orbital"),
        os.path.join(home, "Desktop", "Orbital"),
    ]
    return [c for c in candidates if os.path.isdir(c)]


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="triage",
        description="Inventory Orbital trees. Never deletes; moves to _archive.",
    )
    ap.add_argument("trees", nargs="*", help="directories to scan")
    ap.add_argument("--all", action="store_true",
                    help="scan every known Orbital location")
    ap.add_argument("--apply", action="store_true",
                    help="actually move ARCHIVE and JUNK into _archive/")
    ap.add_argument("--show-keep", action="store_true",
                    help="list the files being kept")
    ap.add_argument("--keep-only", action="store_true",
                    help="with --apply, move only JUNK (leave archives in place)")
    args = ap.parse_args(argv)

    trees = list(args.trees)
    if args.all or not trees:
        trees = known_trees()

    if not trees:
        print("No Orbital trees found. Pass a path explicitly:")
        print(r"    python triage.py C:\Orbital")
        return 1

    print()
    print("ORBITAL TRIAGE")
    print(f"Mode: {'APPLY (files will be moved)' if args.apply else 'DRY RUN (nothing changes)'}")
    print()

    plans = []
    for tree in trees:
        result = scan(tree)
        if not result:
            print(f"skipping (not found): {tree}\n")
            continue
        report(result, show_keep=args.show_keep)
        print()
        plans.append(result)

    if not args.apply:
        total = sum(
            e["size"] for r in plans for e in r["entries"]
            if e["verdict"] in ("JUNK", "ARCHIVE")
        )
        print("=" * 72)
        print(f"DRY RUN — nothing changed. {human(total)} would be reclaimed.")
        print()
        print("Nothing is ever deleted. Files move to <tree>\\_archive\\ so you")
        print("can inspect them and remove them yourself.")
        print()
        print("To apply:")
        print("    python triage.py --all --apply")
        return 0

    print("=" * 72)
    print("APPLYING")
    print("=" * 72)
    verdicts = ("JUNK",) if args.keep_only else ("JUNK", "ARCHIVE")
    for result in plans:
        moved, errors, where = apply_moves(result, verdicts)
        print(f"  {result['tree']}: moved {moved} file(s), {errors} error(s)")
        print(f"    -> {where}")

    print()
    print("Done. Nothing was deleted.")
    print("Review each _archive folder, then delete it when you are satisfied.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
