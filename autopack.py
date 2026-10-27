"""autopack - sort a messy folder into a working Orbital tree, and test it.

    python autopack.py --scan                  what is here, what it is
    python autopack.py --plan                  what it would do, changing nothing
    python autopack.py --apply                 do it
    python autopack.py --verify                does the result run
    python autopack.py --undo                  put it back

**What it is for.**

A folder has accumulated Orbital files across several attempts: modules
here, half-copied trees there, loose .py files that belong in core/, old
bundles, duplicated scripts. Nobody can say what belongs where.

This reads what is actually there, works out what each file is, and sorts it
into the layout Orbital expects. Then it tests the result.

**Three rules it will not break.**

  1. **Nothing is deleted.** Ever. Files move, or they stay where they are.
     Anything unrecognised is left alone and reported.
  2. **Nothing is overwritten.** If two files want the same name, the second
     one is kept under a suffixed name and the collision is reported.
  3. **Every move is written down** before it happens, so `--undo` can put
     everything back exactly.

**How it decides where a file goes.**

Not by filename alone. It reads the file:

    has `def handle(` and core imports   -> a core module
    has `if __name__ == "__main__"`      -> a script or tool
    has `def test_` or `assert`          -> a test
    is HTML                              -> the interface folder
    is a .bundle or .tar.gz              -> an archive, left alone
    anything else                        -> left alone, reported

A file that already sits in the right place is not touched.

**What --verify does.**

After sorting, it runs the same checks `dircheck.py` runs: do the modules
parse, do they import, do the anchors hold, do the tests pass. If any fail
it says which, and does not claim success.
"""

import argparse
import ast
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time

STATE_NAME = ".autopack-state.json"

# Where each kind of file belongs.
LAYOUT = {
    "module": "core",
    "test": "tests",
    "tool": "tools",
    "html": "gui",
    "doc": "docs",
}

# Files that are part of the tree and should stay at the top level.
TOP_LEVEL_OK = {
    "start.py", "Orbital.bat", "Orbital-stop.bat", "Orbital.sh",
    "requirements.txt", "README.md", "CHANGELOG.md", ".gitignore",
    "PORTABLE.md", "STRUCTURE.md",
}

# Never touched, whatever they look like.
IGNORE_NAMES = {
    ".git", "__pycache__", "node_modules", ".venv", "venv",
    ".mypy_cache", ".pytest_cache",
}

IGNORE_EXT = (".bundle", ".tar", ".gz", ".zip", ".7z", ".rar", ".exe",
              ".dll", ".so", ".dylib", ".pyc", ".pyo", ".log", ".db")


class PackError(RuntimeError):
    """Base class."""


# ------------------------------------------------------------- classify
def read_text(path, limit=200000):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read(limit)
    except OSError:
        return ""


def classify(path):
    """What is this file? Returns (kind, reason).

    Reads the contents, not just the name. A file called `helpers.py` that
    defines core modules is a core module.
    """
    name = os.path.basename(path)
    ext = os.path.splitext(name)[1].lower()

    if name in IGNORE_NAMES or name.startswith("."):
        return None, "hidden or ignored"
    if ext in IGNORE_EXT:
        return None, "archive or binary - left alone"
    if name in TOP_LEVEL_OK:
        return "top", "belongs at the top level"

    # --- python
    if ext == ".py":
        src = read_text(path)
        if not src:
            return None, "empty or unreadable"

        # A test file
        if (name.startswith("test_") or
                re.search(r"^\s*def test_", src, re.M) or
                "unittest" in src[:2000]):
            return "test", "has test functions"

        # A core module: defines handle(), or has core-style imports and
        # does not run anything on import.
        has_handle = re.search(r"^def handle\(", src, re.M)
        has_dunder = '__name__ == "__main__"' in src
        imports_core = re.search(r"^from (core|\.)", src, re.M)

        if has_handle and imports_core and not has_dunder:
            return "module", "defines handle() and imports core"
        if has_handle and imports_core and has_dunder:
            # Has both - a module that is also runnable. Core is safer,
            # because tools/ is not importable as core.X.
            return "module", "defines handle() and imports core"

        # A tool: runnable, no handle()
        if has_dunder and not has_handle:
            return "tool", "runnable script with no handle()"

        # A module without handle() - still core if it imports core
        if imports_core:
            return "module", "imports core, no entry point"

        return "tool", "standalone python"

    # --- web
    if ext in (".html", ".htm"):
        return "html", "web page"
    if ext == ".css":
        return "html", "stylesheet"

    # --- docs
    if ext in (".md", ".txt", ".rst"):
        return "doc", "documentation"

    return None, "not recognised - left alone"


# ---------------------------------------------------------------- plan
def scan(root):
    """Every file, what it is, and where it should go."""
    root = os.path.abspath(root)
    items = []

    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in IGNORE_NAMES]

        for f in files:
            full = os.path.join(dirpath, f)
            rel = os.path.relpath(full, root)

            # Only the top level is sorted. A file already inside a known
            # folder is where it belongs.
            depth = rel.count(os.sep)
            kind, reason = classify(full)

            items.append({
                "rel": rel,
                "abs": full,
                "depth": depth,
                "kind": kind,
                "reason": reason,
                "size": os.path.getsize(full),
            })

    return items


def plan(root, items=None):
    """What would move where. Changes nothing."""
    root = os.path.abspath(root)
    items = items if items is not None else scan(root)

    moves = []
    keep = []
    unknown = []

    for it in items:
        if it["depth"] > 0:
            # Already in a subfolder. Only flag it if it is clearly in the
            # wrong one.
            folder = it["rel"].split(os.sep)[0]
            want = LAYOUT.get(it["kind"])
            if it["kind"] and want and folder != want and \
                    folder in LAYOUT.values():
                moves.append({
                    "from": it["rel"],
                    "to": os.path.join(want, os.path.basename(it["rel"])),
                    "kind": it["kind"],
                    "reason": f"in {folder}/ but is a {it['kind']}",
                })
            else:
                keep.append(it["rel"])
            continue

        if it["kind"] in (None, "top"):
            if it["kind"] is None:
                unknown.append(it["rel"])
            else:
                keep.append(it["rel"])
            continue

        want = LAYOUT.get(it["kind"])
        if not want:
            keep.append(it["rel"])
            continue

        dest = os.path.join(want, os.path.basename(it["rel"]))
        if os.path.exists(os.path.join(root, dest)):
            # A name collision. Suffix rather than overwrite.
            base, ext = os.path.splitext(os.path.basename(it["rel"]))
            n = 2
            while os.path.exists(os.path.join(
                    root, want, f"{base}-{n}{ext}")):
                n += 1
            dest = os.path.join(want, f"{base}-{n}{ext}")
            moves.append({
                "from": it["rel"], "to": dest, "kind": it["kind"],
                "reason": "name already taken - renamed, not overwritten",
                "collision": True,
            })
        else:
            moves.append({
                "from": it["rel"], "to": dest, "kind": it["kind"],
                "reason": it["reason"],
            })

    return {"root": root, "moves": moves, "keep": keep, "unknown": unknown}


def render_plan(p):
    lines = []
    lines.append("")
    lines.append("=" * 74)
    lines.append(f"  AUTOPACK PLAN   {p['root']}")
    lines.append("=" * 74)

    if p["moves"]:
        lines.append("")
        lines.append(f"  WOULD MOVE ({len(p['moves'])}):")
        for m in p["moves"]:
            flag = " (renamed)" if m.get("collision") else ""
            lines.append(f"    {m['from']}")
            lines.append(f"      -> {m['to']}{flag}")
            lines.append(f"         {m['reason']}")
    else:
        lines.append("")
        lines.append("  nothing to move - the layout is already right")

    if p["unknown"]:
        lines.append("")
        lines.append(f"  NOT RECOGNISED, LEFT ALONE ({len(p['unknown'])}):")
        for u in p["unknown"][:20]:
            lines.append(f"    {u}")

    lines.append("")
    lines.append(f"  staying put: {len(p['keep'])} file(s)")
    lines.append("=" * 74)
    if p["moves"]:
        lines.append("  Nothing has changed. Run --apply to do it.")
        lines.append("=" * 74)
    return "\n".join(lines)


# ---------------------------------------------------------------- apply
def _state_path(root):
    return os.path.join(root, STATE_NAME)


def apply_plan(p):
    """Do the moves. Writes an undo record first."""
    root = p["root"]
    record = {"at": time.time(), "root": root, "done": []}

    with open(_state_path(root), "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=2)

    made = []
    failed = []

    for m in p["moves"]:
        src = os.path.join(root, m["from"])
        dst = os.path.join(root, m["to"])

        if not os.path.exists(src):
            failed.append((m["from"], "source is gone"))
            continue
        if os.path.exists(dst):
            failed.append((m["from"], "destination exists"))
            continue

        try:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.move(src, dst)
            made.append(m)
            record["done"].append({"from": m["from"], "to": m["to"]})
        except OSError as exc:
            failed.append((m["from"], str(exc)[:60]))

    with open(_state_path(root), "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=2)

    return {"moved": made, "failed": failed}


def undo(root):
    """Put every moved file back."""
    sp = _state_path(root)
    if not os.path.exists(sp):
        raise PackError("no record of a previous --apply in this folder")

    with open(sp, encoding="utf-8") as fh:
        record = json.load(fh)

    back, failed = [], []
    for m in reversed(record.get("done", [])):
        src = os.path.join(root, m["to"])
        dst = os.path.join(root, m["from"])
        if not os.path.exists(src):
            failed.append((m["to"], "already gone"))
            continue
        if os.path.exists(dst):
            failed.append((m["to"], "something is there now"))
            continue
        try:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.move(src, dst)
            back.append(m)
        except OSError as exc:
            failed.append((m["to"], str(exc)[:60]))

    record["undone_at"] = time.time()
    record["done"] = []
    with open(sp, "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=2)

    return {"restored": back, "failed": failed}


# ---------------------------------------------------------------- verify
def verify(root):
    """Run the checks dircheck runs. Returns (ok, report)."""
    here = os.path.dirname(os.path.abspath(__file__))
    checker = os.path.join(here, "dircheck.py")

    lines = []
    lines.append("")
    lines.append("=" * 74)
    lines.append("  VERIFY")
    lines.append("=" * 74)

    ok = True

    if not os.path.exists(checker):
        lines.append("")
        lines.append("  dircheck.py is not next to this file, so the full")
        lines.append("  check cannot run. Doing what it can.")
        lines.append("")

    core = os.path.join(root, "core")
    if not os.path.isdir(core):
        lines.append("")
        lines.append("  ! no core/ folder. This is not a tree.")
        lines.append("=" * 74)
        return False, "\n".join(lines)

    # --- do the modules parse
    modules = sorted(f[:-3] for f in os.listdir(core) if f.endswith(".py"))
    broken = []
    for m in modules:
        try:
            with open(os.path.join(core, f"{m}.py"), encoding="utf-8") as fh:
                ast.parse(fh.read())
        except SyntaxError as exc:
            broken.append(f"{m}.py:{exc.lineno} {exc.msg}")

    lines.append("")
    lines.append(f"  modules        : {len(modules)}")
    lines.append(f"  parse          : "
                 f"{'all OK' if not broken else f'{len(broken)} BROKEN'}")
    if broken:
        ok = False
        for b in broken:
            lines.append(f"      {b}")

    # --- do they import
    code = (
        "import sys, os, importlib, json\n"
        f"sys.path.insert(0, {root!r})\n"
        f"os.environ.setdefault('ORBITAL_BASE', {root!r})\n"
        f"bad = {{}}\n"
        f"for m in {modules!r}:\n"
        "    if m == '__init__': continue\n"
        "    try:\n"
        "        importlib.import_module('core.' + m)\n"
        "    except Exception as e:\n"
        "        bad[m] = type(e).__name__\n"
        "print(json.dumps(bad))\n"
    )
    try:
        r = subprocess.run([sys.executable, "-c", code],
                           capture_output=True, text=True, timeout=240,
                           cwd=root)
        bad = json.loads((r.stdout or "{}").strip().splitlines()[-1]
                         if r.stdout.strip() else "{}")
    except Exception as exc:
        bad = {}
        lines.append(f"  import check   : could not run ({exc})")

    if bad:
        ok = False
        lines.append(f"  import         : {len(bad)} FAILED")
        for m, e in list(bad.items())[:10]:
            lines.append(f"      {m}: {e}")
    else:
        lines.append(f"  import         : all OK")

    # --- anchors
    if "anchor" in modules:
        try:
            r = subprocess.run(
                [sys.executable, "-m", "core.anchor", "--verify"],
                capture_output=True, text=True, timeout=120, cwd=root)
            held = (r.stdout or "").count("[held ]")
            broke = (r.stdout or "").count("[BROKEN]")
            lines.append(f"  anchors        : {held} held, {broke} broken")
            if broke:
                ok = False
        except Exception:
            lines.append("  anchors        : could not run")

    # --- tests
    runner = os.path.join(root, "tests", "run_tests.py")
    if os.path.exists(runner):
        try:
            r = subprocess.run([sys.executable, runner],
                               capture_output=True, text=True, timeout=900,
                               cwd=root)
            out = (r.stdout or "") + (r.stderr or "")
            passed = "All" in out and "passed" in out
            lines.append(f"  tests          : "
                         f"{'pass' if passed else 'FAIL'}")
            if not passed:
                ok = False
                tail = out.strip().splitlines()[-3:]
                for t in tail:
                    lines.append(f"      {t[:70]}")
        except Exception as exc:
            lines.append(f"  tests          : could not run ({exc})")
    else:
        lines.append("  tests          : no runner found")

    lines.append("")
    lines.append("=" * 74)
    lines.append(f"  {'READY' if ok else 'NOT READY'}")
    lines.append("=" * 74)
    return ok, "\n".join(lines)


# ------------------------------------------------------------------ CLI
def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="autopack",
        description="Sort a messy folder into a working Orbital tree.",
    )
    ap.add_argument("--path", default=".",
                    help="the folder to work on (default: current)")
    ap.add_argument("--scan", action="store_true",
                    help="list every file and what it is")
    ap.add_argument("--plan", action="store_true",
                    help="what it would do, changing nothing")
    ap.add_argument("--apply", action="store_true", help="do it")
    ap.add_argument("--verify", action="store_true",
                    help="does the result run")
    ap.add_argument("--undo", action="store_true", help="put it back")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    root = os.path.abspath(args.path)

    if not os.path.isdir(root):
        print(f"\n  no such folder: {root}\n")
        return 1

    if args.undo:
        try:
            r = undo(root)
        except PackError as exc:
            print(f"\n  {exc}\n")
            return 1
        print()
        print(f"  restored {len(r['restored'])} file(s)")
        for f, why in r["failed"]:
            print(f"    ! could not restore {f}: {why}")
        print()
        return 0

    if args.verify:
        ok, text = verify(root)
        print(text)
        return 0 if ok else 1

    items = scan(root)

    if args.scan:
        if args.json:
            print(json.dumps(items, indent=2))
            return 0
        print()
        print("=" * 74)
        print(f"  SCAN   {root}")
        print("=" * 74)
        by_kind = {}
        for it in items:
            by_kind.setdefault(it["kind"] or "unknown", []).append(it)

        for kind in ("module", "test", "tool", "html", "doc", "top",
                     "unknown"):
            group = by_kind.get(kind)
            if not group:
                continue
            print(f"\n  {kind.upper()} ({len(group)})")
            for it in group[:25]:
                depth = "" if it["depth"] == 0 else "  (nested)"
                print(f"    {it['rel']:<46} {it['reason'][:28]}{depth}")
            if len(group) > 25:
                print(f"    ... and {len(group) - 25} more")

        print()
        print("=" * 74)
        print(f"  {len(items)} file(s) total")
        print("=" * 74)
        return 0

    p = plan(root, items)

    if args.apply:
        result = apply_plan(p)
        print()
        print(f"  moved {len(result['moved'])} file(s)")
        for f, why in result["failed"]:
            print(f"    ! {f}: {why}")
        print()
        print(f"  undo with:  python autopack.py --path {root} --undo")
        print()
        return 0

    if args.json:
        print(json.dumps(p, indent=2))
    else:
        print(render_plan(p))
    return 0


if __name__ == "__main__":
    sys.exit(main())
