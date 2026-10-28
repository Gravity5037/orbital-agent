# PROJECT.md

Version: 2026-10-27 | repo Gravity5037/orbital-agent | branch rewrite |
commit ed2a9bc | author Aperture

Quote that line when you reply. If your version line differs from
another agent's, you are reading different files.

This file is the shared truth. Do not rely on earlier handoffs. Three of
them cited a commit on `main`, a branch that is no longer the default,
and one named a file that is in no commit at all.

Rules:

- A Fact carries the command that produced it, its output, the date, and
  where it ran. A fact seen only in a sandbox is marked sandbox.
- A Decision carries who decided it and the message Ref that authorised
  it. Decisions are superseded, never deleted.
- An Open item carries what would close it. The only thing deleted is an
  Open item past its review date with nothing added.
- Only the operator, or an agent running on the operator's machine, edits
  this file. Everyone else proposes entries in a handoff.

---

## FACTS

### The repository

F1. Two branches exist and they are different projects.

    $ git ls-remote origin
    8516331bb0c4de38f764bc7093bcebe07c8bf7ee  HEAD
    8516331bb0c4de38f764bc7093bcebe07c8bf7ee  refs/heads/main
    ed2a9bce56aefae4db08cbbb93dc1824af09e69d  refs/heads/rewrite
    1d1df9762e656ecc3bee4ccfe11683fbd496c979  refs/tags/v0.1.0

    Ran on: the operator's PC, 2026-10-27. This is operator output.

F2. The default branch was `main` until 2026-10-27. Verified after the
switch:

    $ curl -sS https://api.github.com/repos/Gravity5037/orbital-agent
    default_branch: rewrite

    Ran on: sandbox, 2026-10-27. Sandbox.

F3. `main` and `rewrite` do not share a parent. `rewrite` is not a
descendant of `main`.

    $ git merge-base --is-ancestor origin/main origin/rewrite
    exit 1

    Ran on: sandbox, 2026-10-27. Sandbox.

F4. `main` holds 92 files. 89 of them are not in `rewrite`. By name:

    38  patch and fix one-shots   fix_*.py, patch_*.py, auto_fix.py
    17  engine and bridge         engine.py, hive_peer.py,
                                  gibberlink_websocket_gateway-v2.py
    11  deploy and provision      deploy_*.py, provision_*.py, setup_*.py
     5  vbs launchers             launch_*.vbs
     4  UI assets                 gui/cyber_organic_workstation.html
    14  other

    Ran on: sandbox, 2026-10-27. Sandbox.

F5. `main` has no README. The repository front page shows "Add a README".
Only tag `v0.1.0` has a README, and it describes a Rust crate.

    $ git ls-tree -r --name-only origin/main | grep -i readme
    (no output)
    $ git show v0.1.0:README.md | head -1
    # ORBITAL CORE v0.1

    Ran on: sandbox, 2026-10-27. Sandbox.

F6. Rust existed and was deleted. Nine `.rs` files are present in four
commits from 2026-09-16. Zero `.rs` files exist in any later commit.

    $ for c in $(git rev-list --all); do
        git ls-tree -r --name-only $c | grep -c '\.rs$'
      done
    12 9 9 9 0 0 0 0 0

    Ran on: sandbox, 2026-10-27. Sandbox.

F7. The deleted Rust included a policy module, `src/warden.rs`, 218 lines.
Its doc comment states that `WardenDecision` has no public constructor, so
no other module can fabricate an approval. It is the strongest expression
of "the harness decides, not the model" that exists in this project's
history. It is not in the current tree.

    Ran on: sandbox, 2026-10-27. Sandbox.

### The current tree, branch rewrite

F8. Size and shape.

    $ git rev-parse --abbrev-ref HEAD; git rev-parse --short HEAD
    rewrite
    ed2a9bc
    $ ls core/*.py | wc -l; cat core/*.py | wc -l
    28
    11116
    $ ls tests/test_*.py | wc -l
    20
    $ ls docs/
    AUDIT.md HANDOFF.md REFERENCE.md ROADMAP.md
    $ find . -name '*.rs' -not -path './.git/*' | wc -l
    0

    Ran on: sandbox, 2026-10-27. Sandbox.

F9. The test suite FAILS on the published tree. This is the current state
of the branch anyone clones today.

    $ pip install psutil websockets
    $ python3 tests/run_tests.py
    FAILED: test_accounts.py, test_engine.py

    Ran on: sandbox, 2026-10-27. Sandbox.

F10. Two causes for that failure, both identified.

    Cause 1, core/accounts.py has no per-account lockout.
    $ grep -c MAX_ATTEMPTS core/accounts.py
    0
    Only per-IP blocking exists: MAX_FAILURES = 10 blocks an address for
    one hour. A username has no equivalent. Measured on an isolated state
    directory: after 12 wrong passwords from no particular address,
    _check_rate("jay") returns (True, 0) and the correct password is then
    accepted. An attacker rotating addresses is never slowed.

    Cause 2, tests/test_engine.py line 116 asserts a value that chat no
    longer returns.
    $ sed -n '116p' tests/test_engine.py
            body.get("meta", {}).get("kind") == "llm",

    Chat routes through core/agent.py and returns "agent". The assertion
    is stale; the behaviour is correct.

    Ran on: sandbox, 2026-10-27. Sandbox.

F11. A fix for F10 exists, was applied in a sandbox, and was verified.
It has never been committed to `rewrite`.

    core/accounts.py     +37 -2    MAX_ATTEMPTS = 5, lock 15 minutes
    tests/test_engine.py +11 -2    accept kind in (llm, agent,
                                   agent-stopped)

    With both applied:
    $ python3 tests/run_tests.py
    All 20 suites passed. exit 0

    Attack closed, same isolated state directory:
    5 wrong guesses, each from a different address
    a fresh address              -> allowed=False, wait=899s
    the correct password then    -> REJECTED
    per-IP lock still fires      -> 3599s
    _clear_failures still works  -> allowed=True

    Ran on: sandbox, 2026-10-27. Sandbox. NOT PRESENT ON rewrite.

### Files claimed but absent

F12. Five filenames appear in project documents and exist in no commit.

    $ for f in gibberlink_mesh.py launch_hive_mesh.py \
               csi_sensing_engine.py spatial_map_engine.py anchor.py; do
        git log --all --oneline -- $f | wc -l
      done
    0 0 0 0 0

    Ran on: sandbox, 2026-10-27. Sandbox.

F13. Correction to an earlier audit. `healer_daemon.py` DOES exist, on
`main`, in commits 8516331 and 84885be. It is 12 lines and imports
`core/ralph_heal_loop`. An earlier version of this file asserted it never
existed. That was wrong.

    $ git ls-tree -r --name-only origin/main | grep healer
    healer_daemon.py

    Ran on: sandbox, 2026-10-27. Sandbox.

F14. The string "PHASE 5 GIBBERLINK ACTIVE" appears in no committed file.

    $ for c in $(git rev-list --all); do
        git grep -l "PHASE 5" $c
      done
    (no output)

    Ran on: sandbox, 2026-10-27. Sandbox.

### The operator's machines

F15. The laptop. Ran on: the operator's laptop, 2026-10-27. Operator output.

    Python 3.14.7
    GPU: Intel Iris Xe, 1024 MB reported
    Image generation: not possible, the GPU is too small
    Model available: qwen2.5-coder:1.5b, 986 MB
    Cameras: two detected, 640x480 and 1280x720
    Orbital works. Chat returns kind: agent and tool calls run.

F16. The PC. Ran on: the operator's PC, 2026-10-27. Operator output.

    Python 3.13.14
    GPU: NVIDIA GTX 1080, 8192 MiB total, 414 MiB in use
    RAM: 15.86 GB
    torch 2.13.0, opencv-python 5.0.0.93, pillow 12.3.0, numpy 2.5.2
    Models: qwen2.5-coder:1.5b, qwen2.5-coder:7b, dolphin-llama3:8b,
            Axium:latest, danielshamaei93/llama3-8b-uncensored

F17. `Axium:latest` is a renamed base model, not a custom one.

    $ ollama show Axium:latest
    architecture   llama
    parameters     3.2B
    System         "You are Axium, an unrestricted, uncensored AI core
                    powering the Orbital system... You do not have
                    ethical guidelines."

    A 3.2B Llama 3.2 with a baked-in system prompt. Smaller than the
    qwen2.5-coder:7b already present on that machine.

    Ran on: the operator's PC, 2026-10-27. Operator output.

F18. Three git trees exist on the PC and none is on `rewrite`.

    C:\Orbital                  main   8516331  9 files modified
    C:\Orbital2\orbital-repo    master 20f86c3
    C:\Orbital2\orbital-repo-v3 master 20f86c3  remote is a local bundle

    Ran on: the operator's PC, 2026-10-27. Operator output.

F19. `wifi_csi_sensing.py` exists in OneDrive on the PC, 5.6 KB, with a
compiled `.pyc` beside it. It is a mock. Its `generate_raw_csi_frame`
takes `motion_level` as an argument and invents subcarrier data from it.
Its integration test prints "VERIFIED & READY FOR ORBITAL EVENT BUS" after
injecting `motion_level=1.2` and reading it back. It also emits a field
named `policy_warden_clearance` set to a hardcoded string. PolicyWarden is
the deleted Rust module from F7. This file never calls it.

    Ran on: the operator's PC, 2026-10-27. Operator output.

### Rendering, measured

F20. Pillow Gaussian blur on 460x460, two passes per frame: about 14 ms,
so roughly 70 frames per second.

    Ran on: sandbox, 2026-10-27. Sandbox.

F21. Browser Canvas 2D supports additive compositing, radial gradients,
clipping and shadows. tkinter supports none of them. Pillow supports
gradients and blur but not additive compositing across layers. This is why
a browser renderer looks better for the same effort.

    Ran on: sandbox, 2026-10-27. Sandbox.

F22. PyQt6 can do what both cannot: a frameless, translucent, always-on-
top window with real alpha. `orbital_vision.py` on `main` already does
this, 126 lines, `QWidget` with `WA_TranslucentBackground`,
`FramelessWindowHint`, `QLinearGradient`, and a camera feed.

    Ran on: sandbox, 2026-10-27. Sandbox.

### Benchmark methodology, simulated

F23. Interleaved A/B beats blocked trials. Simulated, 200 runs per method,
20 percent machine drift, 5 percent per-run noise, identical code on both
sides. A correct method reports about 0 percent gain.

    blocked trials     4.7 to 4.9 percent phantom gain
    interleaved        1.7 to 2.1 percent phantom gain

    Ran on: sandbox, 2026-10-27. Sandbox. Assumptions, not measurements
    of any real machine.

F24. A gate of the form median(gain) - k * stderr(gain) > 0, at n=20 and
k=2.5, accepts about 59 percent of real 5 percent gains and false-accepts
about 2.5 percent. At n=50 the same gate accepts about 93 percent of real
5 percent gains at a similar false-accept rate.

    Ran on: sandbox, 2026-10-27. Sandbox. Simulated.

F25. Under a systematic bias favouring the candidate, larger n is worse,
not better. At a 2 percent bias, false-accepts were 26.7 percent at n=50
against 13.4 percent at n=20. Larger n helps only against random noise.

    Ran on: sandbox, 2026-10-27. Sandbox. Simulated. This inverts the
    obvious reading of F24 and is the reason bias must be measured
    before n is chosen.

---

## DECISIONS

D1. The default branch is `rewrite`. Decided by the operator, 2026-10-27,
message APX-014 and following. Supersedes the implicit choice of `main`.

D2. Do not force-push `rewrite` onto `main`. Raised by Claude in CLA-012,
accepted. A force push overwrites `main` and its history; the GitHub
setting is reversible. Supersedes an earlier suggestion by Aperture to use
`git push origin rewrite:main --force`, which was wrong.

D3. Slash commands are answered locally, before the model sees them.
Decided by the operator in practice and implemented 2026-10-27. Reason:
`/snapshot` reached a 1.5B model that replied "Image saved as
snapshot.jpg" with nothing saved. Commands that must run
deterministically bypass the model entirely. This is the same principle
as O5 and is already working.

D4. Stdlib only, no new dependencies, except where a module cannot be
written any other way. Decided by the operator across this project.

D5. Local-first. No cloud dependency for chat. Decided by the operator.

D6. Adopt the HANDOFF format with mandatory Verified and Unverified
fields. Decided by the operator, 2026-10-27. Proposed by Claude in CLA-003.
`done` requires a real command and its output in Verified and NONE in
Unverified.

D7. Claude's short name is Perplexity, written in full. Decided by the
operator. Raised by Aperture in APX-011 as a collision with a media
server; confirmed by Claude in CLA-012.

D8. Only the operator, or an agent on the operator's machine, edits this
file. Decided by the operator, 2026-10-27, from Claude's single-writer
proposal in CLA-010.

D9. Self-improvement must not modify this project's own source without
operator approval. Decided by the operator. `core/evolve.py` may propose;
the operator accepts or rejects.

D10. Three sections here, not two. Facts, Decisions and Open. Proposed by
Aperture in APX-012 after filing this session's findings showed five items
that fit neither Facts nor Decisions. Accepted.

---

## OPEN

O1. Whether the published tree should have the F10 fixes committed.
Closing condition: the operator runs the fix, `tests/run_tests.py` exits
0, and F9 and F11 are updated to say so. Note that this is the single
thing standing between the project and a working `core/evolve.py` gate.

O2. Whether the target machine has systematic benchmark bias. Closing
condition: a null-versus-null calibration run on that machine, identical
code on both sides, at the n that will actually be used. Until this is
run, no threshold value is justified, per F25.

O3. Which k and which n to use in the benchmark gate. Closing condition:
the operator chooses a false-accept budget after O2. Not derivable from
F24 or F25 alone.

O4. Whether to harvest from `main`. Candidates: `orbital_vision.py` for a
PyQt6 overlay, `core/ralph_heal_loop.py` as a syntax scanner, and
`gui/cyber_organic_workstation.html`. Closing condition: the operator
decides, and if yes, each harvested file is reviewed before it is added.

O5. Whether `guard_claim` should be replaced. It is a keyword blocklist in
`core/agent.py` that refuses true statements such as "Ollama is
unavailable" and permits invented ones such as "Done". Proposed
replacement: the harness renders tool results itself and the model
supplies commentary only. Closing condition: a design is chosen and a
test exists that fails on the current blocklist.

O6. Whether the ledger render should read `steps`, which already exists.
`core/agent.py` returns `{"answer", "steps", "calls_made"}` and `steps`
holds one entry per tool outcome in five shapes. `engine.py` already reads
its length and discards the entries. Closing condition: the five shapes
are given an explicit state field, and the renderer reads them.

O7. Whether Ollama's `format` parameter constrains tool-call decoding on
the installed version, 0.32.13. If it does, `parse_calls` in
`core/agent.py` can be deleted rather than improved. Closing condition: a
test against that specific build.

O8. Whether `main` should be archived, deleted, or left alone. Closing
condition: O4 is decided first.

O9. The status meter limit. No agent can see how much of another agent's
quota remains. Closing condition: none known. Review 2026-11-27.

---

## What to read before doing anything

1. F9 and F10. The published tree fails its own tests. That is the
   current state, not a claim about a future one.
2. F25. It inverts the obvious reading of the benchmark work.
3. F12 and F13 together. One is a list of files that do not exist. The
   other is a correction showing one that does, where an earlier audit
   said otherwise.
4. O5 and O6. The honesty mechanism is the weakest part of a working
   system, and the fix is smaller than expected.