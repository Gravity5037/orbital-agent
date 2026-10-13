"""The scenario this whole phase exists for.

Simulates: talk on a PC, export, carry the image to a phone, keep talking
there while the PC keeps talking too, then reconcile both sides when they
meet. Asserts nothing is lost, nothing duplicates, and both nodes agree.

Also covers the CLI surface and migration from the legacy chat_memory.json.
"""

import json
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

BASE = "/tmp/orbtest_continuity"
os.environ["ORBITAL_BASE"] = BASE

from core import oostate  # noqa: E402
from core.statestore import StateStore  # noqa: E402

results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(f"{'PASS' if cond else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))


def cli(*args, base=BASE):
    env = dict(os.environ)
    env["ORBITAL_BASE"] = base
    return subprocess.run(
        [sys.executable, "-m", "core.state_cli", *args],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=60,
    )


def main():
    shutil.rmtree(BASE, ignore_errors=True)
    os.makedirs(BASE, exist_ok=True)

    # ---------------------------------------------------------------- PC
    pc = StateStore(node_id="desktop")
    pc.add_message("user", "what is orbital?")
    pc.add_message("assistant", "a local-first assistant")
    pc.add_message("user", "remind me to check the mesh")
    pc.set_attention("current_topic", "mesh")
    pc.set_attention("last_device", "desktop")

    pc_path = os.path.join(BASE, "pc.bin")
    oostate.write(pc_path, pc.to_dict())
    check("PC state exports", os.path.exists(pc_path))

    # ------------------------------------------------- carry to the phone
    blob = open(pc_path, "rb").read()
    phone_state, _ = oostate.unpack(blob)
    phone = StateStore.from_dict(phone_state, node_id="phone")
    check("phone resumes from the PC image",
          len(phone.messages) == 3, f"{len(phone.messages)} messages")
    check("phone inherits the PC's attention",
          phone.attention_value("current_topic") == "mesh",
          str(phone.attention_value("current_topic")))

    # ------------------------------------------- both diverge while apart
    phone.add_message("user", "phone: add milk to the list")
    phone.add_message("assistant", "noted")
    phone.set_attention("last_device", "phone")

    pc.add_message("user", "pc: what's on the agenda?")
    pc.set_attention("current_topic", "agenda")

    check("phone has its own new messages", len(phone.messages) == 5)
    check("pc has its own new messages", len(pc.messages) == 4)

    # ------------------------------------------------------------ reconcile
    merged, report = phone.merge(pc)
    check("reconciliation loses nothing",
          len(merged.messages) == 6, f"{len(merged.messages)} messages")
    check("no duplicates after reconciliation",
          len(set(merged.messages)) == len(merged.messages))

    contents = {r["content"] for r in merged.messages.values()}
    check("phone's offline message survived",
          "phone: add milk to the list" in contents)
    check("pc's offline message survived",
          "pc: what's on the agenda?" in contents)
    check("the original three survived",
          "what is orbital?" in contents and "remind me to check the mesh" in contents)

    # reverse direction must agree
    merged_rev, _ = pc.merge(phone)
    check("reconciliation is order-independent",
          [r["id"] for r in merged.ordered_messages()] ==
          [r["id"] for r in merged_rev.ordered_messages()])

    # LWW on the contested attention key
    check("contested attention resolves deterministically",
          merged.attention_value("last_device") ==
          merged_rev.attention_value("last_device"),
          str(merged.attention_value("last_device")))

    # ------------------------------------------- write back and re-verify
    merged_path = os.path.join(BASE, "merged.bin")
    oostate.write(merged_path, merged.to_dict())
    reread, _ = oostate.read(merged_path)
    check("merged image round-trips",
          len(reread["messages"]) == 6, f"{len(reread['messages'])} messages")

    # A second merge of the same two sides is a no-op (convergence).
    again, _ = merged.merge(merged_rev)
    check("re-merging converged state changes nothing",
          len(again.messages) == 6, f"{len(again.messages)}")

    # ------------------------------------------------------------------ CLI
    r = cli("verify", merged_path)
    check("CLI verify passes on a good image", r.returncode == 0 and "OK" in r.stdout,
          r.stdout.strip().splitlines()[-1] if r.stdout else r.stderr[:60])

    # corrupt a copy and confirm the CLI refuses it
    bad_path = os.path.join(BASE, "corrupt.bin")
    raw = bytearray(open(merged_path, "rb").read())
    raw[-3] ^= 0xFF
    open(bad_path, "wb").write(bytes(raw))
    r = cli("verify", bad_path)
    check("CLI verify rejects a corrupted image",
          r.returncode == 1 and "FAIL" in r.stdout, r.stdout.strip()[:70])

    r = cli("inspect", merged_path)
    check("CLI inspect prints a header", r.returncode == 0 and "schema" in r.stdout,
          r.stdout.strip().splitlines()[1] if len(r.stdout.splitlines()) > 1 else "")

    r = cli("merge", pc_path, merged_path, "-o", os.path.join(BASE, "m2.bin"))
    check("CLI merge joins two images", r.returncode == 0 and "merged" in r.stdout,
          r.stdout.strip().splitlines()[0] if r.stdout else r.stderr[:60])

    # CLI export/import against a live base dir
    live_base = "/tmp/orbtest_continuity_live"
    shutil.rmtree(live_base, ignore_errors=True)
    os.makedirs(live_base, exist_ok=True)

    r = cli("export", os.path.join(BASE, "cli-export.bin"), base=live_base)
    check("CLI export writes an image", r.returncode == 0, r.stdout.strip()[:60])

    r = cli("import", merged_path, base=live_base)
    check("CLI import merges into the live state",
          r.returncode == 0 and "messages" in r.stdout, r.stdout.strip().splitlines()[1] if r.stdout else "")

    r = cli("show", "-v", "3", base=live_base)
    check("CLI show reports the imported messages",
          r.returncode == 0 and "messages   : 6" in r.stdout,
          [l for l in r.stdout.splitlines() if "messages" in l][:1])

    # ------------------------------------------------------------- legacy
    legacy = os.path.join(BASE, "chat_memory.json")
    with open(legacy, "w", encoding="utf-8") as fh:
        json.dump(
            [
                {"role": "user", "content": "old question", "ts": 1700000000.0},
                {"role": "assistant", "content": "old answer", "ts": 1700000001.0},
            ],
            fh,
        )
    r = cli("migrate-old", legacy, "-o", os.path.join(BASE, "legacy.bin"))
    check("CLI migrates the legacy chat_memory.json",
          r.returncode == 0 and "2 message" in r.stdout, r.stdout.strip().splitlines()[0])

    legacy_state, _ = oostate.read(os.path.join(BASE, "legacy.bin"))
    check("migrated state is at the current schema",
          legacy_state["schema"] == oostate.SCHEMA_VERSION,
          str(legacy_state["schema"]))
    check("migrated messages got ids",
          all(m.get("id") for m in legacy_state["messages"]))
    check("migrated messages preserve content",
          {m["content"] for m in legacy_state["messages"]} == {"old question", "old answer"})
    check("migration is recorded in meta",
          legacy_state.get("meta", {}).get("migrated_from_schema") == 1,
          str(legacy_state.get("meta")))

    passed = sum(1 for _, ok in results if ok)
    print(f"\n{passed}/{len(results)} checks passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
