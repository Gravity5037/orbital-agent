"""orbital-state — inspect, export, import and merge OOSTATE.BIN images.

Usage:
    python -m core.state_cli show                       # live state summary
    python -m core.state_cli export out.bin             # write an image
    python -m core.state_cli inspect out.bin            # header only, no parse
    python -m core.state_cli verify out.bin             # full checksum check
    python -m core.state_cli import out.bin             # merge into live state
    python -m core.state_cli import out.bin --strategy replace
    python -m core.state_cli merge a.bin b.bin -o c.bin # join two images
    python -m core.state_cli migrate-old                 # import chat_memory.json
"""

import argparse
import json
import os
import sys

from . import config, logutil, oostate, statestore

log = logutil.get_logger("state_cli")


def _live():
    store = statestore.StateStore()
    store.load(missing_ok=True)
    return store


def _fmt_ts(ts):
    import datetime

    try:
        return datetime.datetime.fromtimestamp(float(ts)).strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, OSError, TypeError):
        return "?"


def cmd_show(args):
    store = _live()
    d = store.to_dict()
    print(f"node       : {store.node_id}")
    print(f"schema     : {d['schema']}")
    print(f"clock      : {store.clock}")
    print(f"created    : {_fmt_ts(store.created_at)}")
    print(f"updated    : {_fmt_ts(store.updated_at)}")
    print(f"messages   : {len(store.messages)}")
    print(f"attention  : {len(store.attention)} key(s)")
    print(f"logs       : {len(store.logs)}")
    print(f"path       : {store.path}")

    if store.messages and args.verbose:
        print("\nrecent messages:")
        for rec in store.ordered_messages()[-args.verbose:]:
            preview = rec["content"].replace("\n", " ")[:70]
            print(f"  [{rec['lamport']:>5}] {rec['role']:<9} {preview}")
    return 0


def cmd_export(args):
    store = _live()
    size = oostate.write(args.output, store.to_dict(), compress=not args.no_compress)
    ratio = ""
    raw = len(json.dumps(store.to_dict()).encode())
    if raw:
        ratio = f" ({100 * size / raw:.0f}% of raw)"
    print(f"wrote {args.output}: {size} bytes{ratio}")
    print(f"  {len(store.messages)} message(s), {len(store.attention)} attention key(s)")
    return 0


def cmd_inspect(args):
    with open(args.image, "rb") as fh:
        header = oostate.peek(fh.read())
    print(json.dumps(header, indent=2, sort_keys=True))
    return 0


def cmd_verify(args):
    try:
        state, header = oostate.read(args.image)
    except oostate.ChecksumError as exc:
        print(f"FAIL  checksum: {exc}")
        return 1
    except (oostate.FormatError, oostate.VersionError) as exc:
        print(f"FAIL  {type(exc).__name__}: {exc}")
        return 1

    print("OK    checksum matches")
    print(f"OK    format {header.get('format')} / schema {state.get('schema')}")
    print(f"      written by {header.get('generator')} on {_fmt_ts(header.get('written_at'))}")
    print(f"      {len(state.get('messages', []))} message(s)")
    return 0


def cmd_import(args):
    if not os.path.exists(args.image):
        print(f"no such file: {args.image}")
        return 1

    with open(args.image, "rb") as fh:
        blob = fh.read()

    store = _live()
    before = len(store.messages)

    try:
        report = store.import_bytes(blob, strategy=args.strategy)
    except oostate.ChecksumError as exc:
        print(f"refusing to import — checksum mismatch: {exc}")
        return 1
    except oostate.VersionError as exc:
        print(f"refusing to import — version: {exc}")
        return 1
    except oostate.FormatError as exc:
        print(f"refusing to import — malformed: {exc}")
        return 1

    if not args.dry_run:
        store.save()

    after = len(store.messages)
    print(f"strategy   : {report.get('strategy')}")
    print(f"messages   : {before} -> {after}  (+{after - before})")
    if report.get("conflicts"):
        print(f"conflicts  : {len(report['conflicts'])}")
        for c in report["conflicts"][:5]:
            print(f"  {c}")
    if args.dry_run:
        print("\ndry run — nothing written")
    return 0


def cmd_merge(args):
    try:
        a_state, _ = oostate.read(args.a)
        b_state, _ = oostate.read(args.b)
    except oostate.OostateError as exc:
        print(f"cannot read input: {exc}")
        return 1

    a = statestore.StateStore.from_dict(a_state)
    b = statestore.StateStore.from_dict(b_state)
    merged, report = a.merge(b)

    size = oostate.write(args.output, merged.to_dict(), compress=not args.no_compress)
    print(f"merged {len(a.messages)} + {len(b.messages)} -> {len(merged.messages)} message(s)")
    print(f"wrote {args.output}: {size} bytes")
    if report["conflicts"]:
        print(f"conflicts  : {len(report['conflicts'])}")
        for c in report["conflicts"][:5]:
            print(f"  {c}")
    return 0


def cmd_migrate_old(args):
    src = args.source or config.MEMORY_FILE
    if not os.path.exists(src):
        print(f"no such file: {src}")
        return 1

    store = statestore.from_chat_memory(src)
    print(f"parsed {len(store.messages)} message(s) from {src}")

    if args.output:
        size = oostate.write(args.output, store.to_dict())
        print(f"wrote {args.output}: {size} bytes")
    else:
        live = _live()
        merged, report = live.merge(store)
        if not args.dry_run:
            live.__dict__.update(merged.__dict__)
            live.save()
        print(f"merged into live state -> {len(live.messages)} message(s)")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="orbital-state", description="Inspect and move OOSTATE.BIN images."
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("show", help="summarize the live state")
    p.add_argument("-v", "--verbose", type=int, default=0, metavar="N",
                   help="also print the last N messages")
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("export", help="write an OOSTATE.BIN image")
    p.add_argument("output")
    p.add_argument("--no-compress", action="store_true")
    p.set_defaults(func=cmd_export)

    p = sub.add_parser("inspect", help="print the header without parsing the state")
    p.add_argument("image")
    p.set_defaults(func=cmd_inspect)

    p = sub.add_parser("verify", help="check integrity")
    p.add_argument("image")
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser("import", help="merge an image into the live state")
    p.add_argument("image")
    p.add_argument("--strategy", choices=["merge", "replace", "keep"], default="merge")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_import)

    p = sub.add_parser("merge", help="join two images into a third")
    p.add_argument("a")
    p.add_argument("b")
    p.add_argument("-o", "--output", required=True)
    p.add_argument("--no-compress", action="store_true")
    p.set_defaults(func=cmd_merge)

    p = sub.add_parser("migrate-old", help="import the legacy chat_memory.json")
    p.add_argument("source", nargs="?")
    p.add_argument("-o", "--output", help="write an image instead of merging")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_migrate_old)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
