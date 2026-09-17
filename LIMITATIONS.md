# Known Limitations — ORBITAL CORE v0.1

Referenced from doc-comments in `warden.rs` and `identity.rs`. Consolidated
here rather than repeated inline.

## Decision opacity is in-process only

`WardenDecision` has no public constructor and cannot be serialized, which
prevents external *construction* or *cross-process replay* of a decision.
It is not a cryptographic guarantee (no signature, no MAC) — within the
same process, anything that could obtain unsafe/reflective access to
memory could still forge one. This is considered acceptable for v0.1's
threat model (a single local process with two trivial, side-effect-light
tools) and should be revisited before HOST v1.0 if the tool surface grows.

## Windows ACL enforcement is unverified

The `windows_acl` module in `identity.rs` was written without access to a
Windows machine, Windows toolchain, or any way to compile/run it in this
environment. It represents a genuine attempt using documented Win32 APIs
(`SetNamedSecurityInfoW`, `SetEntriesInAclW`, token/SID lookups), but:

- It has never compiled.
- `verify_dir`/`verify_dir` currently *re-applies* the restrictive DACL on
  every load rather than reading back and diffing the actual ACL — this is
  weaker than the POSIX path's strict "reject on mismatch, never silently
  repair" behavior, and is a known deviation from the letter of R2's
  verification requirement.
- SID buffer handling (`current_user_sid`) makes layout assumptions about
  `TOKEN_USER` that are correct per the Win32 documentation but untested.

**This code must be built and tested on a real Windows machine before it
is trusted.**

## Symlink rejection has a TOCTOU gap

`reject_symlink` is called before and after directory creation, but there
is a window between the check and subsequent file operations where a
symlink could theoretically be substituted by a co-resident attacker
process. A fully race-free implementation would need
`O_NOFOLLOW`-equivalent open flags plumbed through every file operation
rather than a separate metadata check. Deferred as future work; the
current check catches the common/non-adversarial-timing case (a symlink
already in place before ORBITAL starts).

## Sentinel model assumes an attacker cannot rewrite both files consistently

The sentinel-checkpoint scheme (see `audit.rs`) detects deletion,
truncation, replacement, or rollback of the SQLite database *as long as
the sentinel file itself survives untouched*. An attacker capable of
replacing both `audit.sqlite3` and `audit.sqlite3.sentinel` with a
mutually-consistent fabricated pair (i.e., a fabricated DB plus a sentinel
that correctly checkpoints against it) would not be detected by this
mechanism alone. Defending against that requires a root-of-trust outside
the local filesystem entirely (e.g., a remote/append-only log, TPM-backed
counter) and is explicitly out of scope for v0.1.