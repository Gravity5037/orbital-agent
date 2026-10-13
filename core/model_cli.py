"""orbital-model — lineage, datasets and evaluation from the command line.

Usage:
    python -m core.model_cli lineage <artifact>     # ancestry tree
    python -m core.model_cli show <artifact>        # full record
    python -m core.model_cli list [--kind lora]     # search artifacts
    python -m core.model_cli add ...                # register an artifact
    python -m core.model_cli stats                  # registry overview

    python -m core.model_cli dataset list
    python -m core.model_cli dataset show <name>
    python -m core.model_cli dataset check <name>   # guard rails
    python -m core.model_cli dataset init <name>    # write eval prompt suite

    python -m core.model_cli eval --base X --candidate Y [--limit N]
    python -m core.model_cli eval --list            # past reports
"""

import argparse
import json
import sys
import time

from . import artifacts, config, dataset as ds_mod, evals, logutil

log = logutil.get_logger("model_cli")


def _fmt_ts(ts):
    try:
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(float(ts)))
    except (ValueError, OSError, TypeError):
        return "?"


# ------------------------------------------------------------- artifacts
def cmd_lineage(args):
    reg = artifacts.registry()
    try:
        rec = reg.get(args.artifact)
    except artifacts.NotFound:
        matches = reg.find(name=args.artifact)
        if not matches:
            print(f"no artifact matching '{args.artifact}'")
            return 1
        rec = matches[0]
        print(f"(matched '{args.artifact}' -> {rec['name']})")

    for line in reg.lineage_tree(rec["id"]):
        print(line)
    return 0


def cmd_show(args):
    reg = artifacts.registry()
    try:
        rec = reg.get(args.artifact)
    except artifacts.NotFound:
        matches = reg.find(name=args.artifact)
        if not matches:
            print(f"no artifact matching '{args.artifact}'")
            return 1
        rec = matches[0]

    print(f"name       : {rec['name']}")
    print(f"id         : {rec['id']}")
    print(f"kind       : {rec['kind']}")
    print(f"method     : {rec['method']}")
    print(f"path       : {rec['path'] or '(none)'}")
    print(f"created    : {_fmt_ts(rec['created'])}")
    if rec.get("parents"):
        print(f"parents    : {', '.join(rec['parents'])}")
    if rec.get("config"):
        print("config     :")
        for k, v in rec["config"].items():
            print(f"    {k} = {v}")
    if rec.get("metrics"):
        print("metrics    :")
        for k, v in rec["metrics"].items():
            print(f"    {k} = {v}")
    if rec.get("notes"):
        print(f"notes      : {rec['notes']}")

    desc = reg.descendants(rec["id"])
    if desc:
        print(f"descendants: {len(desc)}")
        for d in desc[:10]:
            print(f"    {d['name']} [{d['kind']}] ({d['id']})")
    return 0


def cmd_list(args):
    reg = artifacts.registry()
    recs = reg.find(name=args.name, kind=args.kind, method=args.method)
    if not recs:
        print("no artifacts match")
        return 0
    print(f"{'id':14s} {'kind':10s} {'method':12s} name")
    print("-" * 60)
    for r in recs:
        print(f"{r['id']:14s} {r['kind']:10s} {r['method']:12s} {r['name']}")
    print(f"\n{len(recs)} artifact(s)")
    return 0


def cmd_add(args):
    reg = artifacts.registry()
    parents = [p.strip() for p in (args.parents or "").split(",") if p.strip()]
    resolved = []
    for p in parents:
        if p in reg.artifacts:
            resolved.append(p)
            continue
        matches = reg.find(name=p)
        if not matches:
            print(f"parent '{p}' not found")
            return 1
        resolved.append(matches[0]["id"])

    cfg = {}
    for pair in (args.config or ""):
        if "=" in pair:
            k, _, v = pair.partition("=")
            cfg[k.strip()] = v.strip()

    try:
        aid = reg.add(args.name, args.kind, path=args.path or "",
                      parents=resolved, method=args.method,
                      config_data=cfg, notes=args.notes or "")
    except artifacts.ArtifactError as exc:
        print(f"could not register: {exc}")
        return 1

    reg.save()
    print(f"registered {args.kind} '{args.name}' as {aid}")
    if resolved:
        print(f"  parents: {', '.join(resolved)}")
    return 0


def cmd_stats(args):
    reg = artifacts.registry()
    s = reg.stats()
    print(f"total artifacts : {s['total']}")
    print(f"roots (no parent): {s['roots']}")
    if s["by_kind"]:
        print("by kind         : " + ", ".join(
            f"{k}={v}" for k, v in sorted(s["by_kind"].items())))
    if s["by_method"]:
        print("by method       : " + ", ".join(
            f"{k}={v}" for k, v in sorted(s["by_method"].items())))
    if not s["total"]:
        print("\nnothing registered yet. Add a base model:")
        print("  python -m core.model_cli add pony_v6 --kind base "
              "--method downloaded --path /models/pony.safetensors")
    return 0


# -------------------------------------------------------------- datasets
def cmd_dataset(args):
    if args.action == "list":
        st = ds_mod.status()
        if not st["datasets"]:
            print("no datasets yet")
            return 0
        print(f"{'name':24s} {'items':>6s} {'real':>6s} {'depth':>6s}  safe")
        print("-" * 60)
        for d in st["datasets"]:
            if "error" in d:
                print(f"{d['name']:24s}  ERROR: {d['error']}")
                continue
            print(f"{d['name']:24s} {d['counts']['total']:6d} "
                  f"{d['real_fraction']:6.0%} {d['synthetic_depth']:6d}  "
                  f"{'yes' if d['safe'] else 'NO'}")
        return 0

    if args.action == "show":
        try:
            ds = ds_mod.Dataset.load(args.name)
        except ds_mod.DatasetError as exc:
            print(exc)
            return 1
        c = ds.counts()
        print(f"name           : {ds.name}")
        print(f"id             : {ds.id}")
        print(f"base model     : {ds.base_model or '(unset)'}")
        print(f"items          : {c['total']} ({c['real']} real, {c['synthetic']} synthetic)")
        print(f"real fraction  : {ds.real_fraction():.0%}")
        print(f"synthetic depth: {ds.synthetic_depth}")
        if ds.notes:
            print(f"notes          : {ds.notes}")
        problems = ds.check()
        if problems:
            print("\nGUARD RAIL FAILURES:")
            for p in problems:
                print(f"  - {p}")
        else:
            print("\nall guard rails pass — safe to train on")
        return 0

    if args.action == "check":
        try:
            ds = ds_mod.Dataset.load(args.name)
        except ds_mod.DatasetError as exc:
            print(exc)
            return 1
        problems = ds.check()
        if not problems:
            print(f"'{args.name}' passes all guard rails — safe to train on")
            return 0
        print(f"dataset failed guard rails:")
        for p in problems:
            print(f"  - {p}")
        print("\nTraining on this would risk model collapse.")
        print("Add real data, verify synthetic items, or reset the depth.")
        return 1

    if args.action == "init":
        path = evals.write_default_suite()
        print(f"wrote the default eval prompt suite to {path}")
        print("Edit it, then run:  python -m core.model_cli eval --base X")
        return 0

    print(f"unknown dataset action '{args.action}'")
    return 1


# ------------------------------------------------------------------ eval
def cmd_eval(args):
    if args.list:
        reports = evals.list_reports()
        if not reports:
            print("no eval reports yet")
            return 0
        for path in reports[:20]:
            try:
                rep = evals.load_report(path)
                print(f"{path.rsplit('/', 1)[-1]:40s} "
                      f"{rep.get('label') or '(unlabelled)':24s} "
                      f"{rep.get('elapsed')}s")
            except Exception:
                print(path)
        return 0

    if not args.base:
        print("--base is required (a checkpoint name or artifact name)")
        return 1

    variants = [{"name": "base", "checkpoint": args.base}]
    if args.candidate:
        variants.append({"name": "candidate", "checkpoint": args.candidate})

    suite = evals.load_suite()
    prompts = suite["prompts"][: args.limit] if args.limit else suite["prompts"]
    seeds = suite["seeds"][:1] if args.quick else suite["seeds"]

    label = f"{args.base}-vs-{args.candidate}" if args.candidate else args.base
    print(f"running {len(prompts)} prompt(s) x {len(seeds)} seed(s) "
          f"x {len(variants)} variant(s)")
    print("this generates real images and can take a while\n")

    def progress(vname, pid, seed, entry):
        print(f"  {vname}/{pid}/seed{seed}: {entry['elapsed']}s")

    report = evals.run(
        prompts=prompts, seeds=seeds,
        width=args.width, height=args.height, steps=args.steps,
        variants=variants, label=label, timeout=args.timeout,
        on_result=progress if args.verbose else None,
    )

    print()
    print(evals.summarize(report))
    if report["errors"]:
        print(f"\n{len(report['errors'])} error(s):")
        for e in report["errors"][:5]:
            print(f"  {e}")

    if args.save:
        path = evals.save(report)
        print(f"\nsaved: {path}")
    return 0


# ------------------------------------------------------------------ main
def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="orbital-model",
        description="Manage models, datasets and evaluations.",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("lineage", help="show an artifact's ancestry")
    p.add_argument("artifact")
    p.set_defaults(func=cmd_lineage)

    p = sub.add_parser("show", help="show an artifact's full record")
    p.add_argument("artifact")
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("list", help="search the registry")
    p.add_argument("name", nargs="?")
    p.add_argument("--kind", choices=artifacts.KINDS)
    p.add_argument("--method", choices=artifacts.METHODS)
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("add", help="register an artifact")
    p.add_argument("name")
    p.add_argument("--kind", required=True, choices=artifacts.KINDS)
    p.add_argument("--method", default="downloaded", choices=artifacts.METHODS)
    p.add_argument("--path")
    p.add_argument("--parents", help="comma-separated ids or names")
    p.add_argument("--config", action="append",
                   help="key=value, repeatable")
    p.add_argument("--notes")
    p.set_defaults(func=cmd_add)

    p = sub.add_parser("stats", help="registry overview")
    p.set_defaults(func=cmd_stats)

    p = sub.add_parser("dataset", help="manage training datasets")
    p.add_argument("action", choices=["list", "show", "check", "init"])
    p.add_argument("name", nargs="?")
    p.set_defaults(func=cmd_dataset)

    p = sub.add_parser("eval", help="run an A/B evaluation")
    p.add_argument("--base")
    p.add_argument("--candidate")
    p.add_argument("--limit", type=int, help="use only the first N prompts")
    p.add_argument("--quick", action="store_true", help="one seed instead of all")
    p.add_argument("--width", type=int, default=512)
    p.add_argument("--height", type=int, default=512)
    p.add_argument("--steps", type=int, default=25)
    p.add_argument("--timeout", type=int, default=300)
    p.add_argument("--save", action="store_true", help="write a report")
    p.add_argument("--list", action="store_true", help="list past reports")
    p.add_argument("-v", "--verbose", action="store_true")
    p.set_defaults(func=cmd_eval)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
