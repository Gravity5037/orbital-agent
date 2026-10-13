"""OOSTATE.BIN — the portable state image.

A self-describing binary container for Orbital's execution state, so a node
can export itself, move to another machine, and resume. Designed to be
inspectable, versioned, and corruption-detecting.

Layout (all integers big-endian):

    offset  size  field
    ------  ----  --------------------------------------------------
    0       8     magic, b"OOSTATE1"
    8       2     container format version (uint16)
    10      2     flags (uint16) — bit 0: payload is zlib-compressed
    12      4     header length (uint32)
    16      4     payload length (uint32)
    20      32    SHA-256 of the payload as stored (post-compression)
    52      H     header, UTF-8 JSON
    52+H    P     payload, UTF-8 JSON (optionally compressed)

Two independent version numbers, which matters:

  * ``FORMAT_VERSION`` is the *container*. Changes only if the byte layout
    changes. A reader that sees a higher value refuses the file outright,
    because it cannot trust its own parse.
  * ``schema`` lives inside the payload. Changes when the state model
    changes. A reader that sees a higher value refuses, but one that sees a
    lower value can attempt migration.

Conflating these is how formats become unreadable. Keeping them separate is
what lets a v3 payload travel in a v1 container.
"""

import hashlib
import json
import os
import struct
import time
import zlib

MAGIC = b"OOSTATE1"
FORMAT_VERSION = 1
SCHEMA_VERSION = 2

FLAG_COMPRESSED = 0x0001

_HEAD = struct.Struct(">8sHHII32s")
HEADER_SIZE = _HEAD.size  # 52 bytes


class OostateError(Exception):
    """Base for all state-image failures."""


class FormatError(OostateError):
    """Truncated, misaligned, or not an OOSTATE file at all."""


class ChecksumError(OostateError):
    """Payload does not match its digest — corrupted or tampered."""


class VersionError(OostateError):
    """Written by a newer version than this reader understands."""


def pack(state, compress=True, written_at=None):
    """Serialize a state dict into an OOSTATE.BIN byte string.

    ``written_at`` defaults to now. Pass a fixed value (or use
    :func:`content_hash`) when you need reproducible bytes — the payload is
    always canonical, but the header records when the image was made, so two
    images of the same state written at different times differ in exactly
    that field.
    """
    schema = state.get("schema", SCHEMA_VERSION)
    if schema > SCHEMA_VERSION:
        raise VersionError(
            f"refusing to write schema {schema}; this build writes {SCHEMA_VERSION}"
        )

    header = {
        "format": FORMAT_VERSION,
        "schema": schema,
        "node_id": state.get("node_id", ""),
        "created_at": state.get("created_at", time.time()),
        "written_at": time.time() if written_at is None else float(written_at),
        "generator": "orbital-core",
        "python": ".".join(str(p) for p in __import__("sys").version_info[:3]),
    }
    hdr_bytes = json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8")

    payload = canonical_payload(state)

    flags = 0
    if compress:
        payload = zlib.compress(payload, 9)
        flags |= FLAG_COMPRESSED

    digest = hashlib.sha256(payload).digest()

    return (
        _HEAD.pack(MAGIC, FORMAT_VERSION, flags, len(hdr_bytes), len(payload), digest)
        + hdr_bytes
        + payload
    )


def canonical_payload(state):
    """Canonical, uncompressed JSON bytes for a state dict.

    Sorted keys and no incidental whitespace, so the same logical state always
    produces the same bytes. This is what :func:`content_hash` digests.
    """
    return json.dumps(state, separators=(",", ":"), sort_keys=True).encode("utf-8")


def content_hash(state):
    """Hash of the state's *content*, ignoring when it was written.

    Two images with identical content hash to the same value regardless of
    header timestamps, which is what you want for comparing nodes.
    """
    return hashlib.sha256(canonical_payload(state)).hexdigest()


def unpack(blob):
    """Parse an OOSTATE.BIN byte string. Returns (state, header).

    Raises FormatError, ChecksumError, or VersionError.
    """
    if not isinstance(blob, (bytes, bytearray)):
        raise FormatError(f"expected bytes, got {type(blob).__name__}")
    if len(blob) < HEADER_SIZE:
        raise FormatError(
            f"too short: {len(blob)} bytes, need at least {HEADER_SIZE}"
        )

    magic, fmt, flags, hlen, plen, digest = _HEAD.unpack(blob[:HEADER_SIZE])

    if magic != MAGIC:
        raise FormatError(f"bad magic: {magic!r}, expected {MAGIC!r}")
    if fmt > FORMAT_VERSION:
        raise VersionError(
            f"container format {fmt} is newer than this build ({FORMAT_VERSION})"
        )

    end = HEADER_SIZE + hlen + plen
    if len(blob) < end:
        raise FormatError(
            f"truncated: header+payload need {end} bytes, file has {len(blob)}"
        )

    payload = bytes(blob[HEADER_SIZE + hlen : end])

    # Verify before decompressing — this is the point of storing the digest.
    if hashlib.sha256(payload).digest() != digest:
        raise ChecksumError("payload SHA-256 mismatch — file is corrupted")

    if flags & FLAG_COMPRESSED:
        try:
            payload = zlib.decompress(payload)
        except zlib.error as exc:
            raise FormatError(f"decompression failed: {exc}") from exc

    try:
        header = json.loads(blob[HEADER_SIZE : HEADER_SIZE + hlen].decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise FormatError(f"header is not valid JSON: {exc}") from exc

    try:
        state = json.loads(payload.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise FormatError(f"payload is not valid JSON: {exc}") from exc

    if not isinstance(state, dict):
        raise FormatError(f"payload is {type(state).__name__}, expected object")

    schema = state.get("schema", 0)
    if schema > SCHEMA_VERSION:
        raise VersionError(
            f"state schema {schema} is newer than this build ({SCHEMA_VERSION})"
        )

    return state, header


def peek(blob):
    """Read only the header. Useful for inspecting without parsing the state."""
    if len(blob) < HEADER_SIZE:
        raise FormatError("too short to contain a header")
    magic, fmt, flags, hlen, plen, _digest = _HEAD.unpack(blob[:HEADER_SIZE])
    if magic != MAGIC:
        raise FormatError(f"bad magic: {magic!r}")
    end = HEADER_SIZE + hlen
    if len(blob) < end:
        raise FormatError("truncated header")
    try:
        header = json.loads(blob[HEADER_SIZE:end].decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise FormatError(f"header is not valid JSON: {exc}") from exc
    header["_payload_bytes"] = plen
    header["_compressed"] = bool(flags & FLAG_COMPRESSED)
    header["_stored_digest"] = _digest.hex()
    return header


def write(path, state, compress=True, written_at=None):
    """Atomically write a state image. Never leaves a half-written file.

    Pass ``written_at`` for a byte-reproducible image.
    """
    blob = pack(state, compress=compress, written_at=written_at)
    tmp = str(path) + ".tmp"
    with open(tmp, "wb") as fh:
        fh.write(blob)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)
    return len(blob)


def read(path):
    """Read and verify a state image. Returns (state, header)."""
    with open(path, "rb") as fh:
        return unpack(fh.read())
