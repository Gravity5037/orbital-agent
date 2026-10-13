"""Dataset curation — turning generations into training data, safely.

This is the loop that makes the system compound: generate, keep the good
ones, train a LoRA on them, and the next generation is better. It is real and
it works. It is also the exact process that produces model collapse if done
carelessly, so the rules are enforced in code rather than documented and
ignored.

**The collapse rule.** Training only on your own outputs degrades the model.
This is not a hypothesis — it is published in Nature ("AI models collapse
when trained on recursively generated data") and reproduced widely. The
mechanism is that each generation loses a little of the distribution's tails,
and errors compound across iterations.

**The mitigation, also published.** Accumulating real data alongside
synthetic data prevents collapse ("Is Model Collapse Inevitable?", 2024), and
self-verification provably prevents it (NeurIPS 2025). Both reduce to the
same discipline:

  1. **Never train on synthetic data alone.** Every dataset must carry a
     minimum fraction of real/human-origin items. Enforced here.
  2. **Keep the lineage.** A dataset built from generation N must not be the
     only input to generation N+1.
  3. **Verify before including.** An item enters a dataset only if it passed
     some check, and the check is recorded.
  4. **Cap the depth.** After a few synthetic generations, go back to real
     data. Enforced here.

Without these, a "self-growing" system reliably gets worse while appearing to
get better — because the failure mode is losing diversity, and every
individual sample still looks fine.
"""

import hashlib
import json
import os
import time
import uuid

from . import config, logutil

log = logutil.get_logger("dataset")

DATASETS_DIR = os.path.join(config.STATE_DIR, "datasets")

# The guard rails. Deliberately conservative.
MIN_REAL_FRACTION = float(os.environ.get("ORBITAL_MIN_REAL_FRACTION", "0.30"))
MAX_SYNTHETIC_DEPTH = int(os.environ.get("ORBITAL_MAX_SYNTHETIC_DEPTH", "3"))
MIN_DATASET_SIZE = 10


class DatasetError(Exception):
    pass


class CollapseRisk(DatasetError):
    """The dataset would violate a guard rail against model collapse."""


class Item:
    """One training item: an image, its caption, and where it came from."""

    __slots__ = ("path", "caption", "origin", "verified_by", "score", "meta")

    def __init__(self, path, caption, origin="real", verified_by=None,
                 score=None, meta=None):
        self.path = path
        self.caption = caption
        self.origin = origin          # "real" | "synthetic"
        self.verified_by = verified_by
        self.score = score
        self.meta = meta or {}

    def to_dict(self):
        return {
            "path": self.path,
            "caption": self.caption,
            "origin": self.origin,
            "verified_by": self.verified_by,
            "score": self.score,
            "meta": self.meta,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            path=data.get("path", ""),
            caption=data.get("caption", ""),
            origin=data.get("origin", "real"),
            verified_by=data.get("verified_by"),
            score=data.get("score"),
            meta=data.get("meta", {}),
        )


class Dataset:
    """A named collection of items, with provenance and guard rails."""

    def __init__(self, name, items=None, base_model=None, parents=None,
                 synthetic_depth=0, notes=""):
        self.name = name
        self.id = uuid.uuid4().hex[:12]
        self.items = list(items or [])
        self.base_model = base_model
        self.parents = list(parents or [])
        self.synthetic_depth = synthetic_depth
        self.notes = notes
        self.created = time.time()

    # ------------------------------------------------------------ stats
    def counts(self):
        real = sum(1 for i in self.items if i.origin == "real")
        synth = len(self.items) - real
        return {"total": len(self.items), "real": real, "synthetic": synth}

    def real_fraction(self):
        if not self.items:
            return 0.0
        return self.counts()["real"] / len(self.items)

    # ------------------------------------------------------ guard rails
    def check(self, min_real_fraction=None, max_depth=None, min_size=None):
        """Validate against the collapse guard rails.

        Returns a list of problems. Empty means the dataset is safe to train
        on. Raises nothing — callers decide whether a problem is fatal.
        """
        min_real_fraction = (
            MIN_REAL_FRACTION if min_real_fraction is None else min_real_fraction
        )
        max_depth = MAX_SYNTHETIC_DEPTH if max_depth is None else max_depth
        min_size = MIN_DATASET_SIZE if min_size is None else min_size

        problems = []
        counts = self.counts()

        if counts["total"] < min_size:
            problems.append(
                f"only {counts['total']} item(s); {min_size} is the minimum for "
                f"a LoRA that does anything"
            )

        frac = self.real_fraction()
        if frac < min_real_fraction:
            problems.append(
                f"real fraction is {frac:.0%}; at least {min_real_fraction:.0%} is "
                f"required. Training on synthetic data alone causes model collapse "
                f"(Nature, 2024) — the model gets worse each round while still "
                f"looking fine per-image."
            )

        if self.synthetic_depth > max_depth:
            problems.append(
                f"synthetic depth is {self.synthetic_depth}; the limit is "
                f"{max_depth}. Return to real data before another round."
            )

        unverified = [i for i in self.items
                      if i.origin == "synthetic" and not i.verified_by]
        if unverified:
            problems.append(
                f"{len(unverified)} synthetic item(s) have no recorded verification. "
                f"Self-verification is what provably prevents collapse "
                f"(NeurIPS 2025); unverified items reintroduce the risk."
            )

        if not self.base_model:
            problems.append("no base model recorded; the LoRA will not be reproducible")

        return problems

    def assert_safe(self, **kwargs):
        problems = self.check(**kwargs)
        if problems:
            raise CollapseRisk(
                "dataset failed guard rails:\n  - " + "\n  - ".join(problems)
            )
        return True

    # ------------------------------------------------------------- I/O
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "created": self.created,
            "base_model": self.base_model,
            "parents": self.parents,
            "synthetic_depth": self.synthetic_depth,
            "notes": self.notes,
            "counts": self.counts(),
            "real_fraction": round(self.real_fraction(), 3),
            "items": [i.to_dict() for i in self.items],
        }

    def save(self):
        os.makedirs(DATASETS_DIR, exist_ok=True)
        path = os.path.join(DATASETS_DIR, f"{self.name}.json")
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=2)
        os.replace(tmp, path)
        log.info(
            f"saved dataset '{self.name}': {self.counts()['total']} item(s), "
            f"{self.real_fraction():.0%} real"
        )
        return path

    @classmethod
    def load(cls, name):
        path = os.path.join(DATASETS_DIR, f"{name}.json")
        if not os.path.exists(path):
            raise DatasetError(f"no dataset '{name}' at {path}")
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        ds = cls(
            name=data.get("name", name),
            items=[Item.from_dict(i) for i in data.get("items", [])],
            base_model=data.get("base_model"),
            parents=data.get("parents", []),
            synthetic_depth=data.get("synthetic_depth", 0),
            notes=data.get("notes", ""),
        )
        ds.id = data.get("id", ds.id)
        ds.created = data.get("created", ds.created)
        return ds

    def write_captions(self, out_dir=None):
        """Emit kohya-style caption files (image.png + image.txt)."""
        out_dir = out_dir or os.path.join(DATASETS_DIR, f"{self.name}_captions")
        os.makedirs(out_dir, exist_ok=True)
        written = 0
        for item in self.items:
            if not item.path or not os.path.exists(item.path):
                continue
            stem = os.path.splitext(os.path.basename(item.path))[0]
            cap_path = os.path.join(out_dir, stem + ".txt")
            with open(cap_path, "w", encoding="utf-8") as fh:
                fh.write(item.caption)
            written += 1
        log.info(f"wrote {written} caption file(s) to {out_dir}")
        return out_dir


def list_datasets():
    if not os.path.isdir(DATASETS_DIR):
        return []
    return sorted(f[:-5] for f in os.listdir(DATASETS_DIR) if f.endswith(".json"))


def build_from_generations(
    name,
    report,
    variant,
    base_model,
    caption_fn=None,
    min_score=None,
    real_items=None,
    parent_datasets=None,
    notes="",
):
    """Turn an eval report into a dataset.

    Items are taken from one variant's runs in the report. `caption_fn` maps a
    prompt id and its text to a training caption — the default just uses the
    prompt, which is usually right for a style or subject LoRA.

    `real_items` are Items with origin="real". They are what keeps this safe.
    Pass none and the resulting dataset will fail its guard rails, on purpose.
    """
    items = []

    for pid, block in (report.get("results", {}).get(variant, {}) or {}).items():
        prompt_text = block.get("prompt", "")
        for run_rec in block.get("runs", []):
            path = run_rec.get("path")
            if not path or not os.path.exists(path):
                continue

            score = None
            stats = run_rec.get("stats", {})
            if stats.get("std") is not None:
                # Higher standard deviation means more contrast/detail, which
                # correlates weakly with a less flat image. A proxy, not truth.
                score = round(stats["std"], 2)

            if min_score is not None and (score is None or score < min_score):
                continue

            caption = (
                caption_fn(pid, prompt_text) if caption_fn else prompt_text
            )
            items.append(Item(
                path=path,
                caption=caption,
                origin="synthetic",
                verified_by=f"eval:{report.get('label') or 'unnamed'}",
                score=score,
                meta={"prompt_id": pid, "seed": run_rec.get("seed"),
                      "variant": variant},
            ))

    items.extend(real_items or [])

    # Depth increments if any parent was itself synthetic-derived.
    depth = 0
    if parent_datasets:
        depth = 1 + max(
            (getattr(p, "synthetic_depth", 0) for p in parent_datasets),
            default=0,
        )

    ds = Dataset(
        name=name,
        items=items,
        base_model=base_model,
        parents=[getattr(p, "id", str(p)) for p in (parent_datasets or [])],
        synthetic_depth=depth,
        notes=notes,
    )

    counts = ds.counts()
    log.info(
        f"built dataset '{name}': {counts['total']} item(s), "
        f"{counts['real']} real / {counts['synthetic']} synthetic, depth {depth}"
    )
    return ds


def status():
    """Overview for the UI and CLI."""
    out = {"datasets": [], "guard_rails": {
        "min_real_fraction": MIN_REAL_FRACTION,
        "max_synthetic_depth": MAX_SYNTHETIC_DEPTH,
        "min_dataset_size": MIN_DATASET_SIZE,
    }}
    for name in list_datasets():
        try:
            ds = Dataset.load(name)
            out["datasets"].append({
                "name": name,
                "counts": ds.counts(),
                "real_fraction": round(ds.real_fraction(), 3),
                "synthetic_depth": ds.synthetic_depth,
                "base_model": ds.base_model,
                "safe": not ds.check(),
                "problems": ds.check(),
            })
        except Exception as exc:
            out["datasets"].append({"name": name, "error": str(exc)})
    return out
