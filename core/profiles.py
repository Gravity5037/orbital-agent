"""Profiles - one private conversation store per account.

Before this, every user shared one conversation. You and a friend both
logged in and saw the same history. This gives each account its own.

    python -m core.profiles --list                 who has a profile
    python -m core.profiles --show gravity         what is in one
    python -m core.profiles --size                 how much space each uses
    python -m core.profiles --purge alice          delete one (asks first)

**How it works, in one sentence.**

The engine already had a lazy singleton store. That becomes a *per-user*
singleton: the first time a session touches the store, it is built for
that session's user and cached.

    guest (no accounts)   -> state/OOSTATE.BIN        (as before)
    logged in as gravity  -> state/profiles/gravity/OOSTATE.BIN
    logged in as alice    -> state/profiles/alice/OOSTATE.BIN

**Why a directory per user, not a field on the messages.**

Because it is the only version that is actually private. A `user` field
on each message means one file holds everyone's conversations, and any
bug that forgets to filter leaks everything. A separate file per user
means the isolation is the filesystem's job, not the query's.

**What the admin sees.**

Nothing, by default. Admin is a flag for managing *accounts*, not for
reading conversations. There is no code path that reads another user's
store. That is deliberate.

If you want an admin view later, it should be an explicit, logged action
- not a side effect of being an admin.

**What this does not do.**

  * **It does not encrypt the files.** They are on your disk, readable by
    anyone with file access - the same as before. Encrypting at rest is a
    separate piece of work.
  * **It does not migrate existing history.** A store that existed before
    accounts were enabled stays where it is, and becomes the *guest*
    store. Existing conversations are not handed to the first account
    created. That would be a surprise.
  * **It does not sync between machines.** Each machine has its own
    profiles. Merging them is what OOSTATE is for, and it is not wired
    up to profiles yet.
"""

import argparse
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import config, logutil  # noqa: E402

log = logutil.get_logger("profiles")

PROFILES_DIR = os.path.join(config.STATE_DIR, "profiles")

# Usernames come from accounts.py, which already restricts them to
# [a-z0-9_.-]. This is a second guard, because a profile path is built
# from a username and a path built from user input needs checking twice.
SAFE = set("abcdefghijklmnopqrstuvwxyz0123456789_.-")


class ProfileError(RuntimeError):
    """Base class."""


def _safe(username):
    """Is this username safe to use as a directory name?"""
    if not username:
        return False
    if len(username) > 64:
        return False
    if not all(c in SAFE for c in username):
        return False
    if username in (".", ".."):
        return False
    return True


def path_for(username=None):
    """Where this user's state lives.

    None or empty means the guest store - the original location. That
    keeps single-user installs working exactly as before.
    """
    if not username:
        return config.STATE_FILE

    username = str(username).strip().lower()
    if not _safe(username):
        raise ProfileError(
            f"'{username}' cannot be used as a profile name. "
            f"Allowed: letters, numbers, dot, dash, underscore.")

    return os.path.join(PROFILES_DIR, username, "OOSTATE.BIN")


def ensure(username):
    """Create the directory if it is missing. Returns the path."""
    path = path_for(username)
    if username:
        os.makedirs(os.path.dirname(path), exist_ok=True)
    return path


def exists(username):
    """Has this user ever stored anything?"""
    try:
        return os.path.exists(path_for(username))
    except ProfileError:
        return False


def listing():
    """Every profile on disk, with size and last activity."""
    out = []

    # The guest store, if it is there.
    if os.path.exists(config.STATE_FILE):
        st = os.stat(config.STATE_FILE)
        out.append({
            "user": None,
            "display": "(guest)",
            "path": config.STATE_FILE,
            "bytes": st.st_size,
            "modified": st.st_mtime,
        })

    if not os.path.isdir(PROFILES_DIR):
        return out

    for name in sorted(os.listdir(PROFILES_DIR)):
        d = os.path.join(PROFILES_DIR, name)
        if not os.path.isdir(d):
            continue
        f = os.path.join(d, "OOSTATE.BIN")
        if not os.path.exists(f):
            out.append({"user": name, "display": name, "path": d,
                        "bytes": 0, "modified": os.path.getmtime(d),
                        "empty": True})
            continue
        st = os.stat(f)
        out.append({
            "user": name,
            "display": name,
            "path": f,
            "bytes": st.st_size,
            "modified": st.st_mtime,
        })

    return out


def size_of(username):
    """Bytes used by one profile, including anything else in its folder."""
    try:
        path = path_for(username)
    except ProfileError:
        return 0
    if not username:
        return os.path.getsize(path) if os.path.exists(path) else 0

    d = os.path.dirname(path)
    if not os.path.isdir(d):
        return 0

    total = 0
    for root, _dirs, files in os.walk(d):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


def purge(username):
    """Delete a profile. Moves it to the trash rather than removing it.

    The conversation history of a person is not something to delete
    outright on a single command. It goes to the trash, where it can be
    restored - see core/eng/trash.py.
    """
    if not username:
        raise ProfileError(
            "refusing to purge the guest store. That is the original "
            "history, not a profile.")

    username = str(username).strip().lower()
    path = path_for(username)
    d = os.path.dirname(path)

    if not os.path.isdir(d):
        raise ProfileError(f"no profile for '{username}'")

    try:
        from core.eng import trash
    except ImportError:
        try:
            from core import trash
        except ImportError:
            raise ProfileError(
                "the trash module is not present, so this will not delete "
                "anything. Remove it by hand if you mean to: " + d)

    record = trash.put(d, reason=f"profile purge: {username}")
    log.info(f"profile '{username}' moved to the trash")
    return record


def summary():
    """One line per profile, for the chat command."""
    rows = listing()
    if not rows:
        return "no profiles yet"

    lines = []
    for r in rows:
        kb = r["bytes"] / 1024
        age = (time.time() - r["modified"]) / 86400
        when = "today" if age < 1 else f"{age:.0f}d ago"
        size = f"{kb:.0f} KB" if kb >= 1 else f"{r['bytes']} B"
        lines.append(f"  {r['display']:<16} {size:>8}   {when}")
    return "\n".join(lines)


# ---------------------------------------------------------------- chat
def handle(text):
    """Chat commands. Returns (reply, meta) or None."""
    t = text.strip().lower()

    if t in ("/profiles", "/who"):
        return (summary(), {"kind": "profiles",
                            "count": len(listing())})

    if t in ("/mystore", "/myinfo"):
        try:
            from core import accounts
        except ImportError:
            return ("accounts are not present",
                    {"kind": "profiles", "ok": False})

        me = getattr(handle, "_current_user", None)
        if not me:
            return ("You are not signed in, so you are using the shared "
                    "guest store.",
                    {"kind": "profiles", "user": None})

        b = size_of(me)
        return (f"Your store: {path_for(me)}\n"
                f"  size: {b} bytes\n"
                f"  only you can read it",
                {"kind": "profiles", "user": me})

    return None


# ------------------------------------------------------------------ CLI
def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="orbital-profiles",
        description="One private conversation store per account.",
    )
    ap.add_argument("--list", action="store_true", help="every profile")
    ap.add_argument("--show", metavar="USER", help="details for one")
    ap.add_argument("--size", action="store_true", help="space used")
    ap.add_argument("--purge", metavar="USER",
                    help="delete a profile (moves it to the trash)")
    ap.add_argument("--why-not", action="store_true")
    args = ap.parse_args(argv)

    if args.why_not:
        print("""
======================================================================
  PROFILES: WHAT THIS DOES AND DOES NOT DO
======================================================================

  HOW IT WORKS

    Each account gets its own OOSTATE.BIN:

      guest (no accounts)   -> state/OOSTATE.BIN
      logged in as gravity  -> state/profiles/gravity/OOSTATE.BIN
      logged in as alice    -> state/profiles/alice/OOSTATE.BIN

  WHY A FILE PER USER, NOT A FIELD ON MESSAGES

    A 'user' field means one file holds everyone's conversations, and
    any bug that forgets to filter leaks everything. A separate file
    per user makes isolation the filesystem's job.

  WHAT THE ADMIN SEES

    Nothing. Admin is a flag for managing accounts, not for reading
    conversations. No code path reads another user's store.

  WHAT THIS DOES NOT DO

    - It does not encrypt the files. They are readable by anyone with
      file access to this machine.

    - It does not migrate existing history. A store that existed
      before accounts were enabled stays as the guest store.

    - It does not sync between machines. Each machine keeps its own.

  TO PURGE

    --purge moves a profile to the trash, not delete. Conversation
    history is not something to remove on one command.
======================================================================
""")
        return 0

    if args.purge:
        try:
            rec = purge(args.purge)
        except ProfileError as exc:
            print(f"\n  {exc}\n")
            return 1
        print()
        print(f"  profile '{args.purge}' moved to the trash")
        if isinstance(rec, dict) and rec.get("id"):
            print(f"  restore it with: python -m core.trash restore "
                  f"{rec['id']}")
        print()
        return 0

    if args.show:
        name = args.show.strip().lower()
        try:
            path = path_for(name)
        except ProfileError as exc:
            print(f"\n  {exc}\n")
            return 1
        print()
        print(f"  user    : {name}")
        print(f"  path    : {path}")
        print(f"  exists  : {os.path.exists(path)}")
        print(f"  size    : {size_of(name)} bytes")
        print()
        return 0

    if args.size:
        rows = listing()
        print()
        if not rows:
            print("  no profiles yet\n")
            return 0
        total = 0
        for r in rows:
            b = size_of(r["user"])
            total += b
            print(f"  {r['display']:<16} {b:>10,} bytes")
        print(f"  {'TOTAL':<16} {total:>10,} bytes")
        print()
        return 0

    if args.list or True:
        rows = listing()
        print()
        print("=" * 60)
        print("  PROFILES")
        print("=" * 60)
        if not rows:
            print()
            print("  none yet. Each account gets one on first use.")
            print()
            print("=" * 60)
            return 0
        print()
        for r in rows:
            age = (time.time() - r["modified"]) / 86400
            when = "today" if age < 1 else f"{age:.0f} days ago"
            print(f"  {r['display']}")
            print(f"    {r['path']}")
            print(f"    {r['bytes']:,} bytes  ·  {when}")
        print()
        print("=" * 60)
        print(f"  {len(rows)} profile(s). Each is private to its account.")
        print("=" * 60)
        return 0


if __name__ == "__main__":
    sys.exit(main())
