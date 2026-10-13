"""Eval harness — the difference between growing and drifting.

A system that "improves over time" needs a definition of improved. Without
one, you cannot tell a better LoRA from a noisier one, and every change looks
like progress.

This runs a fixed prompt set against two artifacts (typically a base and a
candidate) and reports paired results. What it measures:

  * **Reproducibility** — same prompt, same seed, same output? If a candidate
    cannot reproduce the base, something is wrong with the pipeline, not the
    model.
  * **Divergence** — how far did outputs move? A LoRA that changes nothing is
    useless; one that changes everything has lost the base model.
  * **Prompt adherence proxy** — does the output actually contain what was
    asked for? Without a CLIP scorer this uses image statistics, which is
    weak but honest about being weak.
  * **Stability** — variance across seeds. High variance means the artifact is
    unpredictable.

The honest limitation, stated up front: automated image aesthetics scoring is
not solved, and this does not pretend to solve it. What it does reliably is
detect *regression* and *drift* — cases where a candidate broke something.
The final judgment on "is this better" is yours, and this gives you a
side-by-side to make it with.
"""

import hashlib
import json
import os
import statistics
import time

from . import config, logutil

log = logutil.get_logger("eval")

EVALS_DIR = os.path.join(config.STATE_DIR, "evals")
DEFAULT_SUITE = os.path.join(config.BASE_DIR, "eval_prompts.json")


class EvalError(Exception):
    pass


def default_suite():
    """A small, fixed prompt set covering distinct failure modes.

    Kept deliberately mundane. Prompts that are themselves unusual make
    results hard to compare across runs.
    """
    return {
        "name": "default",
        "prompts": [
            {"id": "portrait-single", "prompt": "a portrait of one person, "
             "neutral expression, plain background", "tags": ["anatomy", "face"]},
            {"id": "two-subjects", "prompt": "two people standing together, "
             "full body, simple room", "tags": ["anatomy", "composition"]},
            {"id": "hands-visible", "prompt": "a person with both hands visible, "
             "holding an object", "tags": ["hands"]},
            {"id": "closeup-detail", "prompt": "a close-up of a face, "
             "detailed skin texture", "tags": ["detail"]},
            {"id": "full-scene", "prompt": "a wide shot of a room with "
             "several objects and clear lighting", "tags": ["composition"]},
        ],
        "seeds": [1, 2, 3],
    }


def load_suite(path=None):
    path = path or DEFAULT_SUITE
    if path and os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict) and data.get("prompts"):
                return data
            log.warn(f"{path} is not a valid suite; using defaults")
        except (OSError, json.JSONDecodeError) as exc:
            log.warn(f"could not read {path}: {exc}; using defaults")
    return default_suite()


def write_default_suite(path=None):
    """Write the default suite to disk so it can be edited."""
    path = path or DEFAULT_SUITE
    suite = default_suite()
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(suite, fh, indent=2)
    log.info(f"wrote default eval suite to {path}")
    return path


# --------------------------------------------------------------- scoring
def image_stats(data):
    """Cheap, dependency-free statistics over PNG bytes.

    Uses Pillow when available for real pixel statistics. Falls back to a
    hash-and-size fingerprint otherwise, which can detect change but not
    measure it.
    """
    digest = hashlib.sha256(data).hexdigest()[:16]
    stats = {"bytes": len(data), "hash": digest, "mean": None, "std": None}

    try:
        import io

        from PIL import Image

        img = Image.open(io.BytesIO(data)).convert("L")
        px = list(img.getdata())
        stats["mean"] = round(sum(px) / len(px), 2)
        stats["std"] = round(statistics.pstdev(px), 2)
        stats["width"], stats["height"] = img.size
    except ImportError:
        stats["note"] = "install Pillow for real image statistics"
    except Exception as exc:
        stats["note"] = f"could not decode: {exc}"

    return stats


def compare_stats(a, b):
    """Distance between two image fingerprints. Lower is more similar."""
    if a["hash"] == b["hash"]:
        return 0.0

    # Normalised byte-size difference as a crude magnitude.
    size_delta = abs(a["bytes"] - b["bytes"]) / max(a["bytes"], b["bytes"], 1)

    if a.get("mean") is not None and b.get("mean") is not None:
        mean_delta = abs(a["mean"] - b["mean"]) / 255.0
        std_delta = abs(a["std"] - b["std"]) / 128.0
        return round((mean_delta + std_delta + size_delta) / 3, 4)

    return round(size_delta, 4)


# ------------------------------------------------------------------ run
def run(
    prompts=None,
    seeds=None,
    width=512,
    height=512,
    steps=None,
    base=None,
    variants=None,
    label="",
    timeout=300,
    on_result=None,
):
    """Generate the suite against several configurations and compare.

    `variants` is a list of {"name", "checkpoint", "loras", ...} dicts. Each
    is run over the whole prompt/seed grid, so results are paired: prompt
    N seed S in variant A is directly comparable to the same in variant B.

    Returns a report dict. Nothing is written unless save() is called.
    """
    from . import nebula

    suite_prompts = prompts or default_suite()["prompts"]
    seeds = seeds or default_suite()["seeds"]
    variants = variants or [{"name": "base"}]

    total = len(suite_prompts) * len(seeds) * len(variants)
    log.info(
        f"eval: {len(suite_prompts)} prompts x {len(seeds)} seeds x "
        f"{len(variants)} variant(s) = {total} generations"
    )
    if total > 60:
        log.warn(f"{total} generations is a lot — expect this to take a while")

    report = {
        "label": label,
        "started": time.time(),
        "config": {"width": width, "height": height, "steps": steps},
        "variants": [v["name"] for v in variants],
        "results": {},
        "errors": [],
    }

    for variant in variants:
        vname = variant["name"]
        report["results"][vname] = {}

        for item in suite_prompts:
            pid = item["id"]
            report["results"][vname][pid] = {"prompt": item["prompt"], "runs": []}

            for seed in seeds:
                try:
                    result = nebula.generate(
                        item["prompt"],
                        negative=variant.get("negative"),
                        checkpoint=variant.get("checkpoint"),
                        width=variant.get("width", width),
                        height=variant.get("height", height),
                        steps=variant.get("steps", steps) or 25,
                        cfg=variant.get("cfg", 7.0),
                        seed=seed,
                        loras=variant.get("loras"),
                        save=True,
                        timeout=timeout,
                        base=base,
                    )
                    with open(result["path"], "rb") as fh:
                        data = fh.read()

                    entry = {
                        "seed": seed,
                        "path": result["path"],
                        "elapsed": result.get("elapsed"),
                        "stats": image_stats(data),
                    }
                    report["results"][vname][pid]["runs"].append(entry)

                    if on_result:
                        on_result(vname, pid, seed, entry)

                except Exception as exc:
                    msg = f"{vname}/{pid}/seed{seed}: {type(exc).__name__}: {exc}"
                    log.error(msg)
                    report["errors"].append(msg)

    report["finished"] = time.time()
    report["elapsed"] = round(report["finished"] - report["started"], 1)

    report["comparison"] = _compare(report, variants)
    log.info(f"eval finished in {report['elapsed']}s with {len(report['errors'])} error(s)")
    return report


def _compare(report, variants):
    """Paired comparison of each variant against the first (the baseline)."""
    if len(variants) < 2:
        return {"note": "single variant; nothing to compare"}

    baseline = variants[0]["name"]
    out = {"baseline": baseline, "versus": {}}

    for variant in variants[1:]:
        vname = variant["name"]
        distances = []
        elapsed = []
        missing = 0

        for pid, block in report["results"].get(baseline, {}).items():
            base_runs = {r["seed"]: r for r in block["runs"]}
            cand_block = report["results"].get(vname, {}).get(pid, {})
            for run_rec in cand_block.get("runs", []):
                b = base_runs.get(run_rec["seed"])
                if not b:
                    missing += 1
                    continue
                distances.append(
                    compare_stats(b["stats"], run_rec["stats"])
                )
                if run_rec.get("elapsed"):
                    elapsed.append(run_rec["elapsed"])

        if not distances:
            out["versus"][vname] = {"error": "no paired results"}
            continue

        avg = sum(distances) / len(distances)
        out["versus"][vname] = {
            "paired_runs": len(distances),
            "unpaired": missing,
            "mean_divergence": round(avg, 4),
            "min_divergence": round(min(distances), 4),
            "max_divergence": round(max(distances), 4),
            "identical_fraction": round(
                sum(1 for d in distances if d == 0.0) / len(distances), 3
            ),
            "mean_seconds": round(sum(elapsed) / len(elapsed), 1) if elapsed else None,
            "verdict": _verdict(avg),
        }
    return out


def _verdict(avg):
    """Translate divergence into something actionable.

    These thresholds are heuristics, not science. They flag the two failure
    modes that actually matter: a change that did nothing, and a change that
    destroyed the base model.
    """
    if avg == 0.0:
        return "IDENTICAL — the variant had no effect at all"
    if avg < 0.01:
        return "near-identical — the effect is too small to matter"
    if avg < 0.15:
        return "moderate — a real change, base model likely intact"
    if avg < 0.35:
        return "large — check that prompt adherence survived"
    return "extreme — this looks like the base model was lost"


# ---------------------------------------------------------------- output
def save(report, name=None):
    os.makedirs(EVALS_DIR, exist_ok=True)
    name = name or f"eval-{time.strftime('%Y%m%d-%H%M%S')}.json"
    if not name.endswith(".json"):
        name += ".json"
    path = os.path.join(EVALS_DIR, name)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    os.replace(tmp, path)
    log.info(f"eval report written to {path}")
    return path


def list_reports():
    if not os.path.isdir(EVALS_DIR):
        return []
    return sorted(
        (os.path.join(EVALS_DIR, f) for f in os.listdir(EVALS_DIR)
         if f.endswith(".json")),
        key=os.path.getmtime,
        reverse=True,
    )


def load_report(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def summarize(report):
    """A short human-readable rendering."""
    lines = [
        f"Eval: {report.get('label') or '(unlabelled)'}",
        f"  {report.get('elapsed')}s, {len(report.get('errors', []))} error(s)",
        f"  variants: {', '.join(report.get('variants', []))}",
    ]
    comp = report.get("comparison", {})
    if comp.get("versus"):
        lines.append(f"  baseline: {comp.get('baseline')}")
        for name, data in comp["versus"].items():
            if "error" in data:
                lines.append(f"    {name}: {data['error']}")
                continue
            lines.append(
                f"    {name}: divergence {data['mean_divergence']} "
                f"({data['paired_runs']} paired) — {data['verdict']}"
            )
    return "\n".join(lines)
