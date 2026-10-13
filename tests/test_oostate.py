"""OOSTATE.BIN container tests: round-trip, corruption, versioning."""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["ORBITAL_BASE"] = "/tmp/orbtest_state"

from core import oostate  # noqa: E402
from core.statestore import StateStore  # noqa: E402

results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(f"{'PASS' if cond else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))


def sample_state():
    s = StateStore(node_id="node-a")
    s.add_message("user", "hello")
    s.add_message("assistant", "hi there")
    s.set_attention("current_topic", "orbital")
    s.add_log("INFO", "test log line")
    return s.to_dict()


def main():
    state = sample_state()

    # 1. round trip
    blob = oostate.pack(state)
    back, header = oostate.unpack(blob)
    check("round-trips without loss", back == state)
    check("header records the writer", header.get("generator") == "orbital-core",
          str(header.get("generator")))
    check("header records the schema", header.get("schema") == oostate.SCHEMA_VERSION)

    # 2. compression actually compresses
    uncompressed = oostate.pack(state, compress=False)
    check("compression shrinks the payload", len(blob) < len(uncompressed),
          f"{len(blob)} < {len(uncompressed)}")

    # 3. uncompressed round trip
    back2, _ = oostate.unpack(uncompressed)
    check("uncompressed round-trips too", back2 == state)

    # 4. corruption is detected — flip one byte in the payload
    corrupt = bytearray(blob)
    corrupt[-5] ^= 0xFF
    try:
        oostate.unpack(bytes(corrupt))
        check("corrupted payload is rejected", False, "no exception raised")
    except oostate.ChecksumError:
        check("corrupted payload is rejected", True, "ChecksumError")
    except oostate.FormatError as exc:
        check("corrupted payload is rejected", True, f"FormatError: {exc}")

    # 5. truncation is detected
    try:
        oostate.unpack(blob[: len(blob) // 2])
        check("truncated file is rejected", False, "no exception raised")
    except (oostate.FormatError, oostate.ChecksumError):
        check("truncated file is rejected", True)

    # 6. wrong magic
    try:
        oostate.unpack(b"NOTOSTATE" + blob[9:])
        check("wrong magic is rejected", False, "no exception raised")
    except oostate.FormatError:
        check("wrong magic is rejected", True)

    # 7. too short
    try:
        oostate.unpack(b"OOSTATE1")
        check("undersized file is rejected", False, "no exception raised")
    except oostate.FormatError:
        check("undersized file is rejected", True)

    # 8. not bytes
    try:
        oostate.unpack("a string")
        check("non-bytes input is rejected", False, "no exception raised")
    except oostate.FormatError:
        check("non-bytes input is rejected", True)

    # 9. a newer container format is refused, not guessed at
    newer = bytearray(blob)
    newer[9] = oostate.FORMAT_VERSION + 1  # low byte of uint16 at offset 8
    try:
        oostate.unpack(bytes(newer))
        check("newer container format is refused", False, "no exception raised")
    except oostate.VersionError:
        check("newer container format is refused", True, "VersionError")

    # 10. peek reads the header without needing a valid payload
    header_only = oostate.peek(blob)
    check("peek works on a full image", header_only.get("schema") == oostate.SCHEMA_VERSION)

    # 11. atomic write + read from disk
    path = "/tmp/orbtest_state/test.bin"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    written = oostate.write(path, state, written_at=1.0)
    check("write reports the file size", written == os.path.getsize(path),
          f"{written} == {os.path.getsize(path)}")
    check("a fixed timestamp makes the write byte-reproducible",
          open(path, "rb").read() == oostate.pack(state, written_at=1.0))
    disk_state, _ = oostate.read(path)
    check("reads back identically from disk", disk_state == state)
    check("no .tmp file left behind", not os.path.exists(path + ".tmp"))

    # 12. determinism. Bytes include a written_at timestamp, so identical
    # content written at two different moments differs only there. The
    # content hash is what must be stable.
    check("content hash is stable across writes",
          oostate.content_hash(state) == oostate.content_hash(state))
    check("packing is deterministic when the timestamp is fixed",
          oostate.pack(state, written_at=1.0) == oostate.pack(state, written_at=1.0))
    h1 = oostate.peek(oostate.pack(state, written_at=1.0))
    h2 = oostate.peek(oostate.pack(state, written_at=2.0))
    check("only the timestamp differs between two writes of the same state",
          {k: v for k, v in h1.items() if k != "written_at"} ==
          {k: v for k, v in h2.items() if k != "written_at"},
          "all other header fields match")
    check("same content produces the same payload digest",
          h1["_stored_digest"] == h2["_stored_digest"])

    passed = sum(1 for _, ok in results if ok)
    print(f"\n{passed}/{len(results)} checks passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
