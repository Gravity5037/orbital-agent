"""Dataset guard rail tests — the anti-collapse machinery.

These are the most important checks in the whole project. A system that
trains on its own output without these constraints gets worse over time while
every individual image still looks fine. The failure is invisible without a
test like this one.

Grounded in:
  * "AI models collapse when trained on recursively generated data" (Nature, 2024)
  * "Is Model Collapse Inevitable?" (2024) — accumulating real data prevents it
  * "Self-Verification Provably Prevents Model Collapse" (NeurIPS 2025)
"""

import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "/tmp/orbtest_dataset"
os.environ["ORBITAL_BASE"] = BASE
os.environ["ORBITAL_QUIET"] = "1"
sys.path.insert(0, ROOT)

from core import dataset as ds_mod  # noqa: E402
from core.dataset import (  # noqa: E402
    CollapseRisk, Dataset, Item,
)

results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(f"{'PASS' if cond else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))


def fake_items(n, origin, verified=True, prefix="x"):
    return [
        Item(path=f"/tmp/{prefix}{i}.png", caption=f"{prefix} {i}",
             origin=origin,
             verified_by="test" if (origin == "synthetic" and verified) else None)
        for i in range(n)
    ]


def main():
    shutil.rmtree(BASE, ignore_errors=True)
    os.makedirs(BASE, exist_ok=True)

    # ------------------------------------------- synthetic-only is refused
    bad = Dataset(name="all_synthetic", base_model="pony_v6")
    bad.items = fake_items(20, "synthetic")
    problems = bad.check()
    check("an all-synthetic dataset is flagged",
          any("real fraction" in p for p in problems), str(problems)[:90])
    try:
        bad.assert_safe()
        check("assert_safe refuses an all-synthetic dataset", False,
              "no exception raised")
    except CollapseRisk as exc:
        check("assert_safe refuses an all-synthetic dataset", True,
              "CollapseRisk raised")

    # The message must actually explain the risk, not just fail.
    msg = " ".join(problems)
    check("the failure explains model collapse",
          "collapse" in msg.lower(), msg[:80])
    check("the failure cites the mechanism",
          "synthetic" in msg.lower())

    # --------------------------------------------- sufficient real data
    good = Dataset(name="balanced", base_model="pony_v6")
    good.items = fake_items(7, "real", prefix="r") + fake_items(13, "synthetic")
    problems = good.check()
    check("a dataset with 35% real passes the real-fraction rule",
          not any("real fraction" in p for p in problems), str(problems))
    check("a balanced dataset passes assert_safe",
          good.assert_safe() is True)
    check("real fraction is computed correctly",
          abs(good.real_fraction() - 0.35) < 0.001,
          f"{good.real_fraction():.3f}")

    # ---------------------------------------- boundary of the real rule
    edge = Dataset(name="edge", base_model="pony_v6")
    edge.items = fake_items(3, "real", prefix="r") + fake_items(7, "synthetic")
    check("exactly at the threshold passes",
          edge.real_fraction() == 0.30, f"{edge.real_fraction():.2f}")
    check("30% real is accepted",
          not any("real fraction" in p for p in edge.check()),
          str(edge.check()))

    below = Dataset(name="below", base_model="pony_v6")
    below.items = fake_items(2, "real", prefix="r") + fake_items(8, "synthetic")
    check("just below the threshold is refused",
          any("real fraction" in p for p in below.check()),
          f"{below.real_fraction():.2f}")

    # ------------------------------------------------ depth guard rail
    deep = Dataset(name="deep", base_model="pony_v6", synthetic_depth=4)
    deep.items = fake_items(10, "real", prefix="r")
    check("exceeding the synthetic depth limit is flagged",
          any("synthetic depth" in p for p in deep.check()), str(deep.check()))
    try:
        deep.assert_safe()
        check("assert_safe refuses an over-deep dataset", False, "no exception")
    except CollapseRisk:
        check("assert_safe refuses an over-deep dataset", True)

    ok_depth = Dataset(name="ok_depth", base_model="pony_v6", synthetic_depth=2)
    ok_depth.items = fake_items(10, "real", prefix="r")
    check("depth within the limit is accepted",
          not any("synthetic depth" in p for p in ok_depth.check()))

    # -------------------------------------- unverified synthetic items
    unverified = Dataset(name="unverified", base_model="pony_v6")
    unverified.items = fake_items(5, "real", prefix="r") + fake_items(5, "synthetic", verified=False)
    check("unverified synthetic items are flagged",
          any("verification" in p for p in unverified.check()),
          str(unverified.check())[:90])

    # ------------------------------------------------ size guard rail
    tiny = Dataset(name="tiny", base_model="pony_v6")
    tiny.items = fake_items(2, "real", prefix="r")
    check("an undersized dataset is flagged",
          any("minimum" in p for p in tiny.check()), str(tiny.check()))

    # ------------------------------------------------- base model needed
    nobase = Dataset(name="nobase")
    nobase.items = fake_items(10, "real", prefix="r")
    check("a missing base model is flagged",
          any("base model" in p for p in nobase.check()), str(nobase.check()))

    # ------------------------------------------------------ persistence
    path = good.save()
    check("a dataset saves to disk", os.path.exists(path), path)
    reloaded = Dataset.load("balanced")
    check("a dataset reloads", reloaded.name == "balanced")
    check("item counts survive the round trip",
          reloaded.counts() == good.counts(), str(reloaded.counts()))
    check("origins survive the round trip",
          reloaded.real_fraction() == good.real_fraction())

    # ------------------------------------------------- caption export
    real_files = []
    for i in range(3):
        p = os.path.join(BASE, f"img{i}.png")
        with open(p, "wb") as fh:
            fh.write(b"not really a png")
        real_files.append(p)
    captioned = Dataset(name="captions", base_model="pony_v6")
    captioned.items = [
        Item(path=p, caption=f"caption number {i}", origin="real")
        for i, p in enumerate(real_files)
    ] + fake_items(7, "real", prefix="r")
    out = captioned.write_captions()
    check("caption files are written", os.path.isdir(out), out)
    written = [f for f in os.listdir(out) if f.endswith(".txt")]
    check("one caption per existing image", len(written) == 3, str(len(written)))
    sample = os.path.join(out, "img0.txt")
    check("caption content is correct",
          open(sample).read() == "caption number 0")

    # ------------------------------------- building from an eval report
    report = {
        "label": "test-eval",
        "results": {
            "base": {
                "p1": {"prompt": "a prompt", "runs": [
                    {"seed": 1, "path": real_files[0],
                     "stats": {"std": 40.0, "bytes": 100}},
                    {"seed": 2, "path": real_files[1],
                     "stats": {"std": 10.0, "bytes": 100}},
                ]},
            }
        },
    }

    built = ds_mod.build_from_generations(
        "from_eval", report, "base", "pony_v6",
        real_items=[Item(path=real_files[2], caption="real one", origin="real")],
    )
    check("building from a report produces items", built.counts()["total"] == 3,
          str(built.counts()))
    check("generated items are marked synthetic",
          built.counts()["synthetic"] == 2, str(built.counts()))
    check("generated items record their verification",
          all(i.verified_by for i in built.items if i.origin == "synthetic"))
    check("the dataset's depth increments from its parents",
          built.synthetic_depth == 0, str(built.synthetic_depth))

    # Filtering by score
    filtered = ds_mod.build_from_generations(
        "filtered", report, "base", "pony_v6", min_score=20.0,
        real_items=[Item(path=real_files[2], caption="real", origin="real")],
    )
    check("min_score filters out low-scoring generations",
          filtered.counts()["synthetic"] == 1, str(filtered.counts()))

    # Depth increments when built on top of a synthetic-derived parent
    parent = Dataset(name="parent", base_model="pony_v6", synthetic_depth=2)
    child = ds_mod.build_from_generations(
        "child", report, "base", "pony_v6",
        real_items=[Item(path=real_files[2], caption="r", origin="real")],
        parent_datasets=[parent],
    )
    check("depth increments when the parent was synthetic-derived",
          child.synthetic_depth == 3, str(child.synthetic_depth))

    # ------------------------------------------------------------ status
    # status() reads from disk, so save an unsafe one to prove it is flagged.
    bad.save()
    st = ds_mod.status()
    check("status lists saved datasets", len(st["datasets"]) >= 2,
          str([d["name"] for d in st["datasets"]]))
    check("status reports the guard rails",
          st["guard_rails"]["min_real_fraction"] == ds_mod.MIN_REAL_FRACTION,
          str(st["guard_rails"]))
    check("status marks unsafe datasets",
          any(not d.get("safe", True) for d in st["datasets"] if "safe" in d))

    passed = sum(1 for _, ok in results if ok)
    print(f"\n{passed}/{len(results)} checks passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
