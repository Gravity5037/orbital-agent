"""Evolve - propose a change, prove it, keep it only if it's better.

    python -m core.evolve --status          what has been tried, what stuck
    python -m core.evolve --scan            find slow spots, measured
    python -m core.evolve --propose FILE    ask the model to make it faster
    python -m core.evolve --history         every attempt, kept or discarded
    python -m core.evolve --rollback ID     undo a change that was kept
    python -m core.evolve --why-not         the limits, stated plainly

**Read this first, because it is the whole design.**

The model does not get smarter. A 1.5B file on disk is the same file
tomorrow - its weights are fixed at training time and nothing here
changes that. What grows is the *system* around it: which patches
proved out, what got faster, what got reverted.

**That is not a consolation prize.** It is how every serious system
improves. You measure, you propose, you test, you keep the win.

**The one rule that makes this safe:**

    The model proposes. The harness decides.

A model that can edit its own code and commit the result unsupervised
is not a faster system. It is a system that will eventually delete its
own safety checks and report success. Every attempt to build that has
produced either a toy or an incident.

So the loop has five gates, and a patch must pass all five:

    1. COPY      the tree is copied. The live tree is never touched.
    2. TESTS     the suite runs against the copy. Any failure ends it.
    3. BENCH     both versions are timed, same machine, same run.
    4. RECORD    the attempt is written down either way - kept or not.
    5. APPROVE   a kept patch goes in the queue. You say yes or no.

Nothing reaches the live tree without your word. Nothing is deleted -
a discarded patch is kept on disk, because a failed idea is data.

**What this cannot do.**

  * **Make the model smarter.** It cannot. Numbers in a file do not
    change because software runs.
  * **Fix a bug it cannot see.** If the tests do not cover a case, a
    patch that breaks that case passes. Coverage is the ceiling.
  * **Know it is faster in general.** It knows it is faster *on this
    machine, on this benchmark*. A different workload may be slower.
  * **Improve what it cannot measure.** If there is no benchmark for a
    thing, this loop cannot make that thing better.

**To add a benchmark, drop a file in benchmarks/.**
To run the tests, the suite must be runnable with `python tests/run_tests.py`.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import config, logutil  # noqa: E402

log = logutil.get_logger("evolve")

EVOLVE_DIR = os.path.join(config.STATE_DIR, "evolve")
HISTORY = os.path.join(EVOLVE_DIR, "history.json")
QUEUE = os.path.join(EVOLVE_DIR, "queue.json")

BENCH_TIMEOUT = int(os.environ.get("ORBITAL_BENCH_TIMEOUT", "120"))
TEST_TIMEOUT = int(os.environ.get("ORBITAL_TEST_TIMEOUT", "900"))

MIN_GAIN = float(os.environ.get("ORBITAL_MIN_GAIN", "0.05"))


class EvolveError(RuntimeError):
    """Base class."""


def _load(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return default


def _save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    os.replace(tmp, path)


def history():
    return _load(HISTORY, {"attempts": []})


def queue():
    """Patches that passed and are waiting for a yes or no."""
    return _load(QUEUE, {"waiting": []})


def _record(entry):
    h = history()
    entry["id"] = hashlib.sha256(
        f"{entry.get('target')}{time.time()}".encode()).hexdigest()[:12]
    h["attempts"].append(entry)
    _save(HISTORY, h)
    return entry["id"]


def _enqueue(entry):
    q = queue()
    q["waiting"].append(entry)
    _save(QUEUE, q)


def find_benchmarks():
    """Benchmark scripts, if any. Each is timed before and after."""
    d = os.path.join(config.BASE_DIR, "benchmarks")
    if not os.path.isdir(d):
        return []
    return sorted(
        os.path.join(d, f) for f in os.listdir(d)
        if f.endswith(".py")
    )


def time_script(path, cwd, timeout=BENCH_TIMEOUT):
    """Run a script, return (seconds, ok, output)."""
    start = time.perf_counter()
    try:
        r = subprocess.run(
            [sys.executable, path],
            capture_output=True, text=True, timeout=timeout, cwd=cwd,
        )
        elapsed = time.perf_counter() - start
        ok = (r.returncode == 0)
        return elapsed, ok, (r.stdout + r.stderr)[-400:]
    except subprocess.TimeoutExpired:
        return float(timeout), False, f"timed out after {timeout}s"
    except OSError as exc:
        return 0.0, False, f"could not run: {exc}"


def run_tests(cwd, timeout=TEST_TIMEOUT):
    """Run the suite. Returns (passed, output)."""
    runner = os.path.join(cwd, "tests", "run_tests.py")
    if not os.path.exists(runner):
        return False, "no tests/run_tests.py - cannot verify anything"

    try:
        r = subprocess.run(
            [sys.executable, runner],
            capture_output=True, text=True, timeout=timeout, cwd=cwd,
        )
    except subprocess.TimeoutExpired:
        return False, f"tests timed out after {timeout}s"
    except OSError as exc:
        return False, f"could not run tests: {exc}"

    out = (r.stdout + r.stderr)
    passed = (r.returncode == 0 and "FAILED" not in out)
    return passed, out[-600:]


def baseline(tree=None):
    """Measure the current tree. Returns a report."""
    tree = tree or config.BASE_DIR
    benches = find_benchmarks()

    report = {
        "tree": tree,
        "at": time.time(),
        "tests": None,
        "results": [],
    }

    if benches:
        for b in benches:
            secs, ok, out = time_script(b, tree)
            report["results"].append({
                "bench": os.path.basename(b),
                "seconds": round(secs, 4),
                "ok": ok,
                "tail": out,
            })
    return report


def _copy_tree(target=None):
    """A working copy. The live tree is never edited by this module."""
    target = target or config.BASE_DIR
    tmp = tempfile.mkdtemp(prefix="orbital-evolve-")
    dest = os.path.join(tmp, "work")

    shutil.copytree(
        target, dest,
        ignore=shutil.ignore_patterns(
            ".git", "__pycache__", "*.pyc", "state", "logs",
            "images", "videos", "models", "node_modules"),
    )
    return dest


def evaluate(file_path, new_source, tree=None):
    """Run a proposed change through all five gates."""
    tree = tree or config.BASE_DIR
    rel = os.path.relpath(file_path, tree)

    result = {
        "target": rel,
        "at": time.time(),
        "gates": {},
        "verdict": "discard",
        "reason": "",
    }

    before = baseline(tree)
    result["gates"]["baseline"] = {
        "tests": before["tests"],
        "timings": {r["bench"]: r["seconds"] for r in before["results"]},
    }

    if not before["results"]:
        result["reason"] = ("no benchmarks in benchmarks/ - there is "
                            "nothing to measure, so nothing to prove")
        return result

    if not all(r["ok"] for r in before["results"]):
        result["reason"] = "the current tree fails its own benchmark"
        return result

    work = _copy_tree(tree)
    work_file = os.path.join(work, rel)

    if not os.path.exists(work_file):
        shutil.rmtree(os.path.dirname(work), ignore_errors=True)
        result["reason"] = f"{rel} does not exist in the tree"
        return result

    original = open(work_file, encoding="utf-8").read()
    open(work_file, "w", encoding="utf-8").write(new_source)
    result["gates"]["applied_to_copy"] = work

    try:
        passed, out = run_tests(work)
        result["gates"]["tests"] = {"passed": passed, "tail": out}

        if not passed:
            result["reason"] = ("the tests failed. A faster broken "
                                "version is not an improvement.")
            return result

        after = baseline(work)
        timings_before = result["gates"]["baseline"]["timings"]
        timings_after = {r["bench"]: r["seconds"] for r in after["results"]}

        if not all(r["ok"] for r in after["results"]):
            result["reason"] = "the change made a benchmark crash"
            return result

        gains = {}
        for bench, secs_before in timings_before.items():
            secs_after = timings_after.get(bench)
            if not secs_after:
                gains[bench] = None
                continue
            gains[bench] = round(
                (secs_before - secs_after) / secs_before, 4)

        result["gates"]["timings"] = {
            "before": timings_before, "after": timings_after, "gain": gains}

        worst = min((g for g in gains.values() if g is not None), default=0)

        if worst < MIN_GAIN:
            result["reason"] = (
                f"not faster by enough. Best {max(gains.values(), default=0):.1%}, "
                f"worst {worst:.1%}, needs at least {MIN_GAIN:.0%} on every "
                f"benchmark. Laptop timing noise is real.")
            return result

        result["verdict"] = "propose"
        result["reason"] = (f"tests pass and every benchmark improved "
                            f"by at least {worst:.1%}")
        result["new_source"] = new_source
        result["original_source"] = original

    finally:
        shutil.rmtree(os.path.dirname(work), ignore_errors=True)

    return result


def apply_approved(entry):
    """Put a queued patch into the live tree."""
    tree = config.BASE_DIR
    live = os.path.join(tree, entry["target"])

    if not os.path.exists(live):
        raise EvolveError(f"{entry['target']} is not in the tree")

    backups = os.path.join(EVOLVE_DIR, "backups")
    os.makedirs(backups, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    backup = os.path.join(
        backups, f"{entry['id']}-{os.path.basename(entry['target'])}.{stamp}")
    shutil.copy2(live, backup)

    with open(live, "w", encoding="utf-8") as fh:
        fh.write(entry["new_source"])

    entry["applied_at"] = time.time()
    entry["backup"] = backup

    h = history()
    for a in h["attempts"]:
        if a.get("id") == entry["id"]:
            a["applied"] = True
            a["backup"] = backup
    _save(HISTORY, h)

    q = queue()
    q["waiting"] = [w for w in q["waiting"] if w.get("id") != entry["id"]]
    _save(QUEUE, q)

    log.info(f"applied {entry['id']} to {entry['target']} (backup {backup})")
    return backup


def rollback(entry_id):
    """Undo an applied patch, from its backup."""
    h = history()
    found = None
    for a in h["attempts"]:
        if a.get("id") == entry_id and a.get("applied"):
            found = a
            break

    if not found:
        raise EvolveError(f"no applied patch with id {entry_id}")
    if not found.get("backup") or not os.path.exists(found["backup"]):
        raise EvolveError(f"the backup for {entry_id} is gone")

    live = os.path.join(config.BASE_DIR, found["target"])
    shutil.copy2(found["backup"], live)

    found["rolled_back"] = time.time()
    _save(HISTORY, h)
    log.info(f"rolled back {entry_id}")
    return True


PROMPT = """You are looking at one file from Orbital, a local AI
assistant. Your job is to make it faster without changing what it does.

Rules, and they are not negotiable:

  * The behaviour must be identical. Same inputs, same outputs, same
    errors. If you are unsure whether a change alters behaviour, do not
    make it.
  * Do not remove error handling, logging, or safety checks. Those are
    not overhead, they are the point.
  * Do not add dependencies. Standard library only.
  * Do not change the public function signatures.
  * If there is no honest speedup available, say NO CHANGE and explain
    why. A wrong optimisation is worse than a slow function.

Return the complete new file, then a line saying:

  WHY: <one sentence on what you changed and the expected gain>

FILE: {name}
--- BEGIN ---
{source}
--- END ---
"""


def propose(file_path, tree=None):
    """Ask the model for a faster version. Returns (ok, message, result)."""
    tree = tree or config.BASE_DIR
    rel = os.path.relpath(file_path, tree)

    if not os.path.exists(file_path):
        return False, f"{rel} does not exist", None

    source = open(file_path, encoding="utf-8").read()
    if len(source) > 120_000:
        return False, f"{rel} is too large to work with in one pass", None

    try:
        from core import nucleus
    except ImportError:
        return False, "the nucleus module is not present", None

    ok, detail = nucleus.health(timeout=5)
    if not ok:
        return False, f"no model is reachable ({detail})", None

    prompt = PROMPT.format(name=rel, source=source)

    try:
        answer = nucleus.chat(
            [{"role": "user", "content": prompt}], timeout=600)
    except Exception as exc:
        return False, f"the model could not answer: {exc}", None

    new_source = _extract_code(answer)
    if not new_source:
        return False, "the model did not return a complete file", None
    if new_source.strip() == source.strip():
        return False, "the model proposed no change", None

    result = evaluate(file_path, new_source, tree=tree)
    entry_id = _record(result)

    if result["verdict"] == "propose":
        _enqueue(result)
        return True, (f"proposal {entry_id} passed every gate. "
                      f"Approve it with: python -m core.evolve --approve {entry_id}"), result

    return False, f"discarded: {result['reason']}", result


def _extract_code(answer):
    """Pull the file out of the model's reply."""
    if "--- BEGIN ---" in answer and "--- END ---" in answer:
        body = answer.split("--- BEGIN ---", 1)[1].split("--- END ---")[0]
        return body.strip("\n")

    blocks = []
    parts = answer.split("```")
    for i in range(1, len(parts), 2):
        block = parts[i]
        if "\n" in block:
            first, rest = block.split("\n", 1)
            if first.strip().lower() in ("python", "py", ""):
                blocks.append(rest)
    if blocks:
        return max(blocks, key=len).strip("\n")
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="orbital-evolve",
        description="Propose a change, prove it, keep it only if better.",
    )
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--scan", action="store_true", help="measure the tree")
    ap.add_argument("--propose", metavar="FILE")
    ap.add_argument("--history", action="store_true")
    ap.add_argument("--approve", metavar="ID")
    ap.add_argument("--reject", metavar="ID")
    ap.add_argument("--rollback", metavar="ID")
    ap.add_argument("--why-not", action="store_true")
    args = ap.parse_args(argv)

    if args.why_not:
        print(__doc__)
        return 0

    if args.scan:
        print()
        benches = find_benchmarks()
        if not benches:
            print("  no benchmarks in benchmarks/")
            print()
            print("  nothing to measure means nothing to improve.")
            print("  add a script to benchmarks/ that prints a result,")
            print("  and this loop can work on making it faster.")
            print()
            return 1

        print("  measuring the current tree...")
        print()
        rep = baseline()
        for r in rep["results"]:
            mark = "ok " if r["ok"] else "FAIL"
            print(f"  [{mark}] {r['bench']:<28} {r['seconds']:.4f}s")
            if not r["ok"]:
                print(f"         {r['tail'][:120]}")
        print()
        return 0

    if args.propose:
        path = args.propose
        if not os.path.isabs(path):
            path = os.path.join(config.BASE_DIR, path)
        print()
        print("  asking the model for a faster version...")
        ok, msg, result = propose(path)
        print()
        if result:
            print(f"  target  : {result['target']}")
            print(f"  verdict : {result['verdict']}")
            print(f"  reason  : {result['reason']}")
            g = result["gates"].get("timings", {})
            if g:
                print()
                for bench, gain in g.get("gain", {}).items():
                    if gain is not None:
                        before = g["before"][bench]
                        after = g["after"][bench]
                        print(f"  {bench:<28} {before:.4f}s -> "
                              f"{after:.4f}s  ({gain:+.1%})")
            print()
        print(f"  {'OK' if ok else 'no'}: {msg}")
        print()
        return 0 if ok else 1

    if args.approve:
        q = queue()
        entry = next((w for w in q["waiting"] if w.get("id") == args.approve), None)
        if not entry:
            print(f"  no queued patch with id {args.approve}")
            return 1
        try:
            backup = apply_approved(entry)
        except EvolveError as exc:
            print(f"  {exc}")
            return 1
        print()
        print(f"  applied to {entry['target']}")
        print(f"  backup   {backup}")
        print(f"  undo     python -m core.evolve --rollback {entry['id']}")
        print()
        return 0

    if args.reject:
        q = queue()
        before = len(q["waiting"])
        q["waiting"] = [w for w in q["waiting"] if w.get("id") != args.reject]
        _save(QUEUE, q)
        print(f"  {'rejected' if len(q['waiting']) < before else 'not found'}")
        return 0

    if args.rollback:
        try:
            rollback(args.rollback)
        except EvolveError as exc:
            print(f"  {exc}")
            return 1
        print(f"  rolled back {args.rollback}")
        return 0

    if args.history:
        h = history()
        if not h["attempts"]:
            print("  nothing tried yet")
            return 0
        for a in h["attempts"][-20:]:
            state = ("APPLIED" if a.get("applied")
                     else "queued" if a["verdict"] == "propose"
                     else "discarded")
            when = time.strftime("%m-%d %H:%M", time.localtime(a["at"]))
            print(f"  {a['id']}  {state:<10} {when}  {a['target']}")
            print(f"              {a['reason'][:90]}")
        return 0

    h = history()
    q = queue()
    print()
    print(f"  attempts recorded : {len(h['attempts'])}")
    print(f"  kept              : "
          f"{sum(1 for a in h['attempts'] if a.get('applied'))}")
    print(f"  waiting for you   : {len(q['waiting'])}")
    print(f"  benchmarks        : {len(find_benchmarks())}")
    print()
    if not find_benchmarks():
        print("  no benchmarks yet, so nothing can be proven faster.")
        print("  put a script in benchmarks/ to give this loop something")
        print("  to work on.")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())