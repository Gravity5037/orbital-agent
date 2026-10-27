"""dircheck - what is actually in this Orbital tree, and what is wrong with it.

    python dircheck.py                    check the current folder
    python dircheck.py --path C:\\Orbital2
    python dircheck.py --json             machine readable
    python dircheck.py --expect 53        check against a known count
    python dircheck.py --dupes            find duplicate trees on this machine

**What it answers.**

Six questions, in the order that matters:

  1. Is this an Orbital tree at all?
  2. What modules does it have, and which are missing?
  3. Does every module import?
  4. Do the tests pass?
  5. Are there stray files that should not be here?
  6. Are there OTHER copies of Orbital on this machine?

**Why this exists.**

The tree has been rebuilt, lost, re-cloned and confused so many times that
nobody can say what is on any given machine. This produces one answer, from
the files themselves, and says which checks it could not run rather than
guessing.

**It does not change anything.** It reads and reports. Fixing is a separate
command, on purpose.
"""

import argparse
import ast
import importlib
import json
import os
import subprocess
import sys
import time

EXPECTED_MODULES = [
    # the original core
    "accounts", "artifacts", "auth", "backends", "camera", "config",
    "dataset", "engine", "evals", "gpu", "hue", "jobs", "logutil", "mesh",
    "model_cli", "nebula", "nucleus", "oostate", "spotify", "state_cli",
    "statestore", "supervisor", "tools", "video",
    # the governance layer
    "anchor", "approve", "denials", "dossier",
    # still to build
    "halt", "engines", "court", "commune", "conference", "memory",
    "capability", "cloud", "birth", "merge", "vision", "distill", "duo",
    "evolve", "research", "intake", "android", "sensors", "servo", "notice",
    "wish", "snapshot", "vault", "absorb",
]

# Files that should not be in a clean tree.
STRAY_PATTERNS = [
    "patch_*.py", "fix_*.py", "temp*.py", "test_me.py", "scratch*.py",
    "*.bak", "*.old", "*.orig", "*.pyc", "__pycache__",
]

CORE_ONLY = {"__init__.py"}


def find_trees(start, max_depth=3):
    """Find folders that look like an Orbital tree."""
    found = []
    start = os.path.abspath(start)

    for root, dirs, files in os.walk(start):
        depth = root[len(start):].count(os.sep)
        if depth > max_depth:
            dirs[:] = []
            continue

        # Skip things that cannot contain a tree.
        dirs[:] = [d for d in dirs
                   if d not in (".git", "node_modules", "__pycache__",
                                ".venv", "venv", "site-packages")]

        if "core" in dirs and any(f in files for f in
                                  ("start.py", "Orbital.bat",
                                   "requirements.txt")):
            core = os.path.join(root, "core")
            modules = [f[:-3] for f in os.listdir(core)
                       if f.endswith(".py")]
            found.append({
                "path": root,
                "modules": len(modules),
                "has_start": "start.py" in files,
                "has_bat": "Orbital.bat" in files,
                "has_git": ".git" in os.listdir(root),
                "modified": os.path.getmtime(root),
            })

    return sorted(found, key=lambda t: -t["modified"])


def check_tree(path):
    """Everything about one tree."""
    path = os.path.abspath(path)
    result = {
        "path": path,
        "checked_at": time.time(),
        "is_orbital": False,
        "problems": [],
        "notes": [],
    }

    if not os.path.isdir(path):
        result["problems"].append(f"no such folder: {path}")
        return result

    core = os.path.join(path, "core")
    if not os.path.isdir(core):
        result["problems"].append("no core/ folder - this is not a tree")
        return result

    result["is_orbital"] = True

    # --- modules
    present = sorted(f[:-3] for f in os.listdir(core)
                     if f.endswith(".py") and f not in CORE_ONLY)
    result["modules_present"] = present
    result["module_count"] = len(present)

    missing = [m for m in EXPECTED_MODULES if m not in present]
    extra = [m for m in present if m not in EXPECTED_MODULES]
    result["modules_missing"] = missing
    result["modules_extra"] = extra

    if missing:
        result["notes"].append(
            f"{len(missing)} expected module(s) not present")
    if extra:
        result["notes"].append(
            f"{len(extra)} module(s) present that are not on the expected "
            f"list - not necessarily wrong, just unaccounted for")

    # --- do they parse
    broken = []
    for m in present:
        p = os.path.join(core, f"{m}.py")
        try:
            with open(p, encoding="utf-8") as fh:
                ast.parse(fh.read())
        except SyntaxError as exc:
            broken.append(f"{m}.py line {exc.lineno}: {exc.msg}")
        except OSError as exc:
            broken.append(f"{m}.py unreadable: {exc}")
    result["syntax_errors"] = broken
    if broken:
        result["problems"].append(
            f"{len(broken)} module(s) have syntax errors")

    # --- top level
    files = os.listdir(path)
    result["has_start"] = "start.py" in files
    result["has_requirements"] = "requirements.txt" in files
    result["has_git"] = ".git" in files
    result["has_tests"] = os.path.isdir(os.path.join(path, "tests"))

    if not result["has_start"]:
        result["notes"].append("no start.py - you cannot launch this tree")

    # --- stray files
    strays = []
    for f in files:
        for pat in STRAY_PATTERNS:
            if pat.startswith("*"):
                if f.endswith(pat[1:]):
                    strays.append(f)
            elif "*" in pat:
                pre, _, post = pat.partition("*")
                if f.startswith(pre) and f.endswith(post):
                    strays.append(f)
            elif f == pat:
                strays.append(f)
    result["stray_files"] = sorted(set(strays))
    if strays:
        result["notes"].append(
            f"{len(set(strays))} stray file(s) - see the list")

    # --- imports (in a subprocess, so a bad module cannot kill us)
    if present and not broken:
        code = (
            "import sys, os, importlib, json\n"
            f"sys.path.insert(0, {path!r})\n"
            "os.environ.setdefault('ORBITAL_BASE', %r)\n" % path +
            "bad = {}\n"
            "for m in %r:\n" % present +
            "    try:\n"
            "        importlib.import_module('core.' + m)\n"
            "    except Exception as e:\n"
            "        bad[m] = type(e).__name__ + ': ' + str(e)[:80]\n"
            "print(json.dumps(bad))\n"
        )
        try:
            r = subprocess.run([sys.executable, "-c", code],
                               capture_output=True, text=True, timeout=180,
                               cwd=path)
            bad = json.loads((r.stdout or "{}").strip().splitlines()[-1]
                             if r.stdout.strip() else "{}")
            result["import_failures"] = bad
            if bad:
                result["problems"].append(
                    f"{len(bad)} module(s) fail to import")
        except Exception as exc:
            result["import_failures"] = {}
            result["notes"].append(f"could not run the import check: {exc}")
    else:
        result["import_failures"] = {}

    # --- anchors, if present
    if "anchor" in present:
        try:
            r = subprocess.run(
                [sys.executable, "-m", "core.anchor", "--verify"],
                capture_output=True, text=True, timeout=120, cwd=path)
            held = (r.stdout or "").count("[held ]")
            broken_a = (r.stdout or "").count("[BROKEN]")
            result["anchors_held"] = held
            result["anchors_broken"] = broken_a
            if broken_a:
                result["problems"].append(
                    f"{broken_a} anchor(s) broken")
        except Exception as exc:
            result["notes"].append(f"could not run the anchor check: {exc}")

    # --- tests
    if result["has_tests"]:
        try:
            r = subprocess.run(
                [sys.executable, "tests/run_tests.py"],
                capture_output=True, text=True, timeout=900, cwd=path)
            out = (r.stdout or "") + (r.stderr or "")
            result["tests_passed"] = "All" in out and "passed" in out
            result["tests_output"] = out.strip().splitlines()[-1][:120] \
                if out.strip() else "(no output)"
            if not result["tests_passed"]:
                result["problems"].append("the test suite did not pass")
        except Exception as exc:
            result["notes"].append(f"could not run the tests: {exc}")

    return result


def render(r):
    lines = []
    lines.append("")
    lines.append("=" * 74)
    lines.append(f"  DIRCHECK   {r['path']}")
    lines.append("=" * 74)

    if not r["is_orbital"]:
        lines.append("")
        for p in r["problems"]:
            lines.append(f"  ! {p}")
        lines.append("")
        return "\n".join(lines)

    lines.append("")
    lines.append(f"  modules present : {r['module_count']}")
    lines.append(f"  expected        : {len(EXPECTED_MODULES)}")
    lines.append(f"  missing         : {len(r['modules_missing'])}")
    if r.get("has_start"):
        lines.append(f"  start.py        : yes")
    if r.get("has_git"):
        lines.append(f"  git             : yes")
    if "anchors_held" in r:
        lines.append(f"  anchors         : {r['anchors_held']} held, "
                     f"{r.get('anchors_broken', 0)} broken")
    if "tests_passed" in r:
        lines.append(f"  tests           : "
                     f"{'pass' if r['tests_passed'] else 'FAIL'}"
                     f"  ({r.get('tests_output', '')})")

    if r["modules_missing"]:
        lines.append("")
        lines.append(f"  MISSING MODULES ({len(r['modules_missing'])})")
        for m in r["modules_missing"]:
            lines.append(f"    {m}")

    if r.get("modules_extra"):
        lines.append("")
        lines.append(f"  UNEXPECTED MODULES ({len(r['modules_extra'])})")
        for m in r["modules_extra"]:
            lines.append(f"    {m}")

    if r.get("syntax_errors"):
        lines.append("")
        lines.append(f"  SYNTAX ERRORS ({len(r['syntax_errors'])})")
        for e in r["syntax_errors"]:
            lines.append(f"    {e}")

    if r.get("import_failures"):
        lines.append("")
        lines.append(f"  IMPORT FAILURES ({len(r['import_failures'])})")
        for m, e in list(r["import_failures"].items())[:12]:
            lines.append(f"    {m}: {e}")

    if r.get("stray_files"):
        lines.append("")
        lines.append(f"  STRAY FILES ({len(r['stray_files'])})")
        for f in r["stray_files"][:15]:
            lines.append(f"    {f}")

    lines.append("")
    lines.append("  " + "-" * 70)
    if r["problems"]:
        lines.append(f"  {len(r['problems'])} PROBLEM(S):")
        for p in r["problems"]:
            lines.append(f"    ! {p}")
    else:
        lines.append("  no problems found")
    for n in r.get("notes", []):
        lines.append(f"    note: {n}")
    lines.append("=" * 74)
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="dircheck",
        description="What is in this Orbital tree, and what is wrong with it.",
    )
    ap.add_argument("--path", default=".",
                    help="the tree to check (default: the current folder)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--dupes", action="store_true",
                    help="find every Orbital tree on this machine")
    ap.add_argument("--search", default=None,
                    help="where to look for trees (default: home folder)")
    ap.add_argument("--expect", type=int, default=None,
                    help="fail if the module count is not this")
    args = ap.parse_args(argv)

    if args.dupes:
        start = args.search or os.path.expanduser("~")
        trees = find_trees(start)
        if args.json:
            print(json.dumps(trees, indent=2))
            return 0
        print()
        print("=" * 74)
        print(f"  ORBITAL TREES under {start}")
        print("=" * 74)
        if not trees:
            print("\n  none found")
            print("  (searched 3 levels deep for a folder with core/ and "
                  "start.py)")
            print()
            return 0
        for t in trees:
            age = (time.time() - t["modified"]) / 86400
            when = f"{age:.0f}d ago" if age >= 1 else "today"
            print(f"\n  {t['path']}")
            print(f"    {t['modules']} modules  ·  "
                  f"{'git ' if t['has_git'] else ''}"
                  f"{'start.py ' if t['has_start'] else ''}"
                  f"· modified {when}")
        print()
        print("=" * 74)
        print(f"  {len(trees)} tree(s). The newest is at the top.")
        print("  Pick one, then:  python dircheck.py --path <that path>")
        print("=" * 74)
        return 0

    r = check_tree(args.path)

    if args.json:
        print(json.dumps(r, indent=2))
    else:
        print(render(r))

    if args.expect is not None:
        if r.get("module_count") != args.expect:
            print(f"\n  expected {args.expect} modules, found "
                  f"{r.get('module_count')}\n")
            return 1

    return 0 if r["is_orbital"] and not r["problems"] else 1


if __name__ == "__main__":
    sys.exit(main())
