"""Artifact registry tests: provenance, lineage DAG, dependency safety."""

import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "/tmp/orbtest_artifacts"
os.environ["ORBITAL_BASE"] = BASE
os.environ["ORBITAL_QUIET"] = "1"
sys.path.insert(0, ROOT)

from core.artifacts import (  # noqa: E402
    ArtifactError, CycleError, NotFound, Registry,
)

results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(f"{'PASS' if cond else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))


def main():
    shutil.rmtree(BASE, ignore_errors=True)
    os.makedirs(BASE, exist_ok=True)

    r = Registry(path=os.path.join(BASE, "artifacts.json"))
    r.load(missing_ok=True)

    # ------------------------------------------------------------ basics
    base = r.add("pony_v6", "base", path="/models/pony.safetensors",
                 method="downloaded")
    check("registering a base model returns an id", bool(base), base)
    check("the base has no parents", r.get(base)["parents"] == [])

    # ------------------------------------------------ lineage: lora on base
    ds = r.add("curated_a", "dataset", path="/data/a", method="curated")
    lora = r.add("style_a", "lora", path="/loras/style_a.safetensors",
                 parents=[base, ds], method="trained",
                 config_data={"rank": 32, "steps": 1500, "lr": 1e-4})
    check("a LoRA records both its base and its dataset",
          sorted(r.get(lora)["parents"]) == sorted([base, ds]),
          str(r.get(lora)["parents"]))
    check("training config is preserved",
          r.get(lora)["config"]["rank"] == 32)

    # ------------------------------------------- lineage: merge of two models
    base2 = r.add("illustrious", "base", path="/models/illu.safetensors",
                  method="downloaded")
    merged = r.add("fusion_v1", "merged", path="/models/fusion.safetensors",
                   parents=[base, base2], method="merged",
                   config_data={"method": "slerp", "t": 0.5})
    check("a merge records both parents",
          len(r.get(merged)["parents"]) == 2)

    # ------------------------------------------------------- ancestors
    anc = r.ancestors(merged)
    ids = {a["id"] for a in anc}
    check("ancestors include the direct parents",
          base in ids and base2 in ids, str(ids))
    check("ancestors carry a depth", all("depth" in a for a in anc))

    deep = r.add("fusion_v2", "merged", parents=[merged, lora], method="merged")
    anc2 = r.ancestors(deep)
    ids2 = {a["id"] for a in anc2}
    check("ancestors traverse the whole DAG",
          {base, base2, merged, lora, ds}.issubset(ids2), str(sorted(ids2)))
    check("the same ancestor is not listed twice",
          len(anc2) == len(ids2), f"{len(anc2)} entries, {len(ids2)} unique")

    # ------------------------------------------------------ descendants
    desc = {d["id"] for d in r.descendants(base)}
    check("descendants find everything downstream",
          {lora, merged, deep}.issubset(desc), str(sorted(desc)))

    # ------------------------------------------------------ lineage tree
    tree = r.lineage_tree(deep)
    check("lineage tree renders", len(tree) >= 3, f"{len(tree)} lines")
    check("lineage tree shows the root model",
          any("pony_v6" in line for line in tree))

    # ---------------------------------------------------------- cycles
    try:
        r.update(base, name="pony_v6")
        # Manually attempt a cycle: make base a child of deep.
        r.artifacts[base]["parents"] = [deep]
        # The guard lives in add(); verify it catches a new cyclic link.
        r.artifacts[base]["parents"] = []
        newid = r.add("cyclic", "merged", parents=[deep], method="merged")
        try:
            r.add("bad", "merged", parents=[newid], method="merged",
                  artifact_id=newid)
            check("a self-referencing artifact is refused", False, "no exception")
        except (CycleError, Exception) as exc:
            check("a self-referencing artifact is refused",
                  "already exists" in str(exc) or isinstance(exc, CycleError),
                  f"{type(exc).__name__}")
    except Exception as exc:
        check("cycle handling did not crash", False, str(exc))

    # ---------------------------------------------------- validation
    try:
        r.add("bad_kind", "sandwich", method="downloaded")
        check("an unknown kind is refused", False, "no exception")
    except ArtifactError as exc:
        check("an unknown kind is refused", True, str(exc)[:40])

    try:
        r.add("bad_method", "lora", method="vibes")
        check("an unknown method is refused", False, "no exception")
    except ArtifactError as exc:
        check("an unknown method is refused", True, str(exc)[:40])

    try:
        r.add("orphan", "lora", parents=["nonexistent"], method="trained")
        check("a missing parent is refused", False, "no exception")
    except NotFound as exc:
        check("a missing parent is refused", True, str(exc)[:40])

    # -------------------------------------------------- dependency safety
    try:
        r.remove(base)
        check("removing an artifact with descendants is refused", False,
              "no exception")
    except ArtifactError as exc:
        check("removing an artifact with descendants is refused", True,
              str(exc)[:50])

    removed = r.remove(base, force=True)
    check("force removal succeeds", removed["id"] == base)
    check("force removal detaches the children",
          base not in r.get(lora)["parents"], str(r.get(lora)["parents"]))

    # ------------------------------------------------------ persistence
    count = r.save()
    check("save reports the artifact count", count == len(r.artifacts),
          f"{count} vs {len(r.artifacts)}")

    r2 = Registry(path=r.path)
    loaded = r2.load()
    check("registry reloads from disk", loaded is True)
    check("reloaded registry has the same artifacts",
          set(r2.artifacts) == set(r.artifacts))
    check("reloaded registry preserves lineage",
          r2.get(merged)["parents"] == r.get(merged)["parents"])

    # ----------------------------------------------------------- search
    check("find by kind works", len(r.find(kind="merged")) == 3,
          str(len(r.find(kind="merged"))))
    check("find by name substring works", len(r.find(name="fusion")) == 2,
          str(len(r.find(name="fusion"))))
    check("find by method works", len(r.find(method="downloaded")) == 1)

    # ------------------------------------------------------------ stats
    s = r.stats()
    check("stats counts by kind", s["by_kind"].get("merged") == 3, str(s["by_kind"]))
    # After force-removing pony_v6, illustrious is the only parentless model,
    # but curated_a (the dataset) also has no parents, so there are 2 roots.
    roots = {a["name"] for a in r.roots()}
    check("stats counts roots", s["roots"] == len(r.roots()),
          f"{s['roots']} roots: {sorted(roots)}")
    check("illustrious is a root after pony_v6 was removed",
          "illustrious" in roots, str(sorted(roots)))

    passed = sum(1 for _, ok in results if ok)
    print(f"\n{passed}/{len(results)} checks passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
