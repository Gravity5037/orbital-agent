# ORBITAL CORE v0.1

Single-machine HOST daemon implementing the frozen v0.1 specification,
including the R1–R4 security remediation pass.

## Build & run

```
cargo fmt
cargo check
cargo build --release
cargo test
ORBITAL_DATA_DIR=./orbital-data cargo run --release
```

Requires Rust (stable, edition 2021) and a C toolchain (bundled SQLite via
`rusqlite`'s `bundled` feature). On Windows, also requires the
`windows-sys` crate to compile the ACL enforcement path — see
`LIMITATIONS.md` before relying on that path.

**This crate has not been compiled in the authoring environment** (no Rust
toolchain, no network access to install one). Treat everything as
unverified until `cargo check`/`cargo test` actually run. See the
ORBITAL SIGN-OFF report delivered alongside this code for specifics.

## Module map

- `src/pipeline.rs` — **the only public entry point that can execute a
  tool.** Serializes schema -> warden -> durable audit -> decision
  consumption -> execution -> result audit under one lock. (R3, R4)
- `src/warden.rs` — deterministic, deny-by-default Policy Warden.
  `pub(crate)`-only constructor/evaluate; no `Default` impl (would be a
  public back door around that restriction).
- `src/tools.rs` — the exactly-two tools as a closed enum, plus the
  `ExecutionGuard` single-use ledger. `pub(crate)`-only, called solely by
  `pipeline.rs`.
- `src/schema.rs` — strict, `deny_unknown_fields` schema validation,
  hand-rolled duplicate-JSON-key detection, exact tool-name matching. The
  only path from raw bytes to a `ToolRequest`. (R1)
- `src/audit.rs` — SQLite (WAL, synchronous=FULL) hash-chained log plus a
  separate sentinel checkpoint file distinguishing genuine first-run from
  post-initialization deletion/replacement/rollback. Fail-closed
  `record()` — a sentinel-write failure after a successful SQLite commit
  is still a hard error. (R3)
- `src/identity.rs` — Ed25519 identity; POSIX 0600/0700 + symlink
  rejection; best-effort, **unverified** Windows DACL enforcement. (R2)
- `src/model_client.rs` — outbound-only HTTP client restricted to literal
  loopback IPs, no redirect-following, size-limited bodies.
- `src/main.rs` — thin wiring: load identity, open+verify audit, construct
  `Pipeline`, submit one demo request, wait for shutdown signal. Contains
  no security-relevant logic itself — deliberately cannot reach
  `warden`/`tools` internals directly, only `Pipeline::submit`.

See `LIMITATIONS.md` for consolidated known caveats (Windows ACL,
in-process decision opacity, symlink TOCTOU, sentinel threat model).

## Explicitly out of scope in this crate

Hive/networking, distributed execution, mobile/EDGE, BARE/UEFI,
self-evolution, autonomous code modification, semantic/vector memory,
network-facing tools, shell tool, arbitrary filesystem tool, Wasmtime,
OS-specific sandbox matrix. No inbound network listener exists in v0.1.