# Orbital handoff archive

Append-only record of handoffs between agents. One file per handoff in entries/.

## Rules

1. Each entry is the raw paste, not a summary.
2. An entry is never edited. A correction is a new entry citing the old Ref.
3. The header records Ref, From, when received, a label, and a SHA-256 of the body.
4. Being archived does not make a claim verified.
5. Only the operator commits. Entries are added with add-archive.ps1.
6. Facts, decisions and open questions belong in PROJECT.md, not here.

## Why this exists

A prior agent wrote documents cited in PROJECT.md as APX-011, APX-012 and APX-014. None exist as files. Its replacement could not read what it did, and had to reconstruct the project by re-measuring everything. That is the cost of keeping state in chat.
