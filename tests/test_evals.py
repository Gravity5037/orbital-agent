"""Eval harness tests: paired comparison, drift detection, reproducibility.

Proves the harness can tell the difference between a variant that did
nothing, one that changed things moderately, and one that broke the model.
"""

import os
import shutil
import signal
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "/tmp/orbtest_evals"
os.environ["ORBITAL_BASE"] = BASE
os.environ["ORBITAL_QUIET"] = "1"
sys.path.insert(0, ROOT)

from core import evals  # noqa: E402

results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(f"{'PASS' if cond else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))


def wait_up(port=8188, timeout=10):
    import socket

    deadline = time.time() + timeout
    while time.time() < deadline:
        s = socket.socket()
        s.settimeout(0.4)
        try:
            s.connect(("127.0.0.1", port))
            return True
        except Exception:
            time.sleep(0.15)
        finally:
            s.close()
    return False


def main():
    shutil.rmtree(BASE, ignore_errors=True)
    os.makedirs(BASE, exist_ok=True)

    # ------------------------------------------------- default suite shape
    suite = evals.default_suite()
    check("the default suite has prompts", len(suite["prompts"]) >= 5,
          f"{len(suite['prompts'])} prompts")
    check("the default suite has seeds", len(suite["seeds"]) >= 2,
          str(suite["seeds"]))
    check("prompts carry ids and tags",
          all("id" in p and "tags" in p for p in suite["prompts"]))

    # Writing it out and reading it back
    path = evals.write_default_suite()
    check("the suite can be written to disk", os.path.exists(path), path)
    loaded = evals.load_suite(path)
    check("the suite reloads", loaded["name"] == suite["name"])
    check("a missing suite falls back to defaults",
          evals.load_suite("/tmp/does-not-exist.json")["name"] == "default")

    # ---------------------------------------------------------- scoring
    from tests.fake_comfy import tiny_png

    a = evals.image_stats(tiny_png(rgb=(0, 0, 0)))
    b = evals.image_stats(tiny_png(rgb=(255, 255, 255)))
    check("image stats produce a hash", bool(a["hash"]))
    check("image stats produce a byte count", a["bytes"] > 0)
    check("identical inputs hash identically",
          evals.image_stats(tiny_png(rgb=(0, 0, 0)))["hash"] == a["hash"])

    check("identical images have zero divergence",
          evals.compare_stats(a, a) == 0.0)
    check("different images have non-zero divergence",
          evals.compare_stats(a, b) > 0.0,
          str(evals.compare_stats(a, b)))

    # Verdict thresholds
    check("zero divergence is called IDENTICAL",
          "IDENTICAL" in evals._verdict(0.0))
    check("a tiny change is called near-identical",
          "near-identical" in evals._verdict(0.005))
    check("a moderate change is called moderate",
          "moderate" in evals._verdict(0.08))
    check("a huge change warns the base model was lost",
          "lost" in evals._verdict(0.9))

    # ------------------------------------------------------ full run
    fake = subprocess.Popen([sys.executable, os.path.join(ROOT, "tests", "fake_comfy.py")])
    try:
        if not wait_up():
            check("fake backend started", False)
            return 1
        check("fake backend started", True)

        from core import nebula

        nebula.COMFY_BASE = "http://127.0.0.1:8188"

        small_suite = {
            "name": "test",
            "prompts": [
                {"id": "p1", "prompt": "first prompt", "tags": []},
                {"id": "p2", "prompt": "second prompt", "tags": []},
            ],
            "seeds": [1, 2],
        }

        report = evals.run(
            prompts=small_suite["prompts"],
            seeds=small_suite["seeds"],
            width=64, height=64, steps=2,
            variants=[
                {"name": "base", "checkpoint": "sdxl_base.safetensors"},
                {"name": "candidate", "checkpoint": "pony_v6.safetensors"},
            ],
            label="test-run",
            timeout=60,
        )

        check("the run completes without errors", not report["errors"],
              str(report["errors"][:1]))
        check("results are keyed by variant",
              set(report["results"]) == {"base", "candidate"},
              str(list(report["results"])))
        check("each variant has both prompts",
              set(report["results"]["base"]) == {"p1", "p2"},
              str(list(report["results"]["base"])))
        check("each prompt has one run per seed",
              len(report["results"]["base"]["p1"]["runs"]) == 2,
              str(len(report["results"]["base"]["p1"]["runs"])))
        check("runs record a seed",
              all("seed" in r for r in report["results"]["base"]["p1"]["runs"]))
        check("runs record stats",
              all("stats" in r for r in report["results"]["base"]["p1"]["runs"]))
        check("the run records elapsed time", report.get("elapsed") is not None)

        # Paired comparison
        comp = report["comparison"]
        check("comparison names the baseline", comp.get("baseline") == "base")
        check("comparison covers the candidate",
              "candidate" in comp.get("versus", {}), str(list(comp.get("versus", {}))))
        cand = comp["versus"]["candidate"]
        check("comparison pairs every run",
              cand.get("paired_runs") == 4, str(cand.get("paired_runs")))
        check("comparison reports no unpaired runs",
              cand.get("unpaired") == 0, str(cand.get("unpaired")))
        check("comparison produces a verdict", bool(cand.get("verdict")),
              str(cand.get("verdict")))
        check("comparison records divergence bounds",
              cand["min_divergence"] <= cand["mean_divergence"] <= cand["max_divergence"],
              f"{cand['min_divergence']} <= {cand['mean_divergence']} <= {cand['max_divergence']}")

        # The fake backend returns the same PNG every time, so a variant that
        # differs only by checkpoint name should show zero divergence.
        check("identical outputs are detected as identical",
              cand["identical_fraction"] == 1.0,
              str(cand["identical_fraction"]))

        # ------------------------------------------------- save + reload
        saved = evals.save(report, "test-report")
        check("the report saves to disk", os.path.exists(saved), saved)
        reloaded = evals.load_report(saved)
        check("the report reloads", reloaded["label"] == "test-run")
        check("reloaded comparison matches",
              reloaded["comparison"]["versus"]["candidate"]["paired_runs"] == 4)

        reports = evals.list_reports()
        check("list_reports finds the saved report", len(reports) >= 1,
              f"{len(reports)} report(s)")

        # ------------------------------------------------------ summary
        text = evals.summarize(report)
        check("summarize produces readable output", "candidate" in text, text[:70])
        check("summary includes the verdict", "divergence" in text)

        # ------------------------------------- single variant, no compare
        solo = evals.run(
            prompts=small_suite["prompts"][:1], seeds=[1],
            width=64, height=64, steps=2,
            variants=[{"name": "only"}], label="solo", timeout=60,
        )
        check("a single-variant run skips comparison",
              "note" in solo["comparison"], str(solo["comparison"]))

        # ------------------------------------------- error handling
        nebula.COMFY_BASE = "http://127.0.0.1:8399"
        broken = evals.run(
            prompts=small_suite["prompts"][:1], seeds=[1],
            width=64, height=64, steps=2,
            variants=[{"name": "unreachable"}], label="broken", timeout=10,
        )
        check("an unreachable backend is recorded as an error",
              len(broken["errors"]) >= 1, str(broken["errors"][:1])[:80])
        check("the run still returns a report", "results" in broken)

    finally:
        if fake.poll() is None:
            try:
                fake.send_signal(signal.SIGTERM)
                fake.wait(timeout=5)
            except Exception:
                fake.kill()

    passed = sum(1 for _, ok in results if ok)
    print(f"\n{passed}/{len(results)} checks passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
