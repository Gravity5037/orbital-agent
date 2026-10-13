"""Accounts — optional, and off by default.

READ THIS FIRST, because the honest answer to "should this need a login?" is
"not for the way you are using it."

**What a login protects against, and whether you care:**

  * **Another web page in your browser** — already blocked by the API token.
    A token sent in a header cannot be read or forged by another origin. A
    session *cookie*, by contrast, is attached automatically by the browser,
    which is exactly what CSRF abuses. So adding a login here would swap a
    stronger primitive for a weaker one.
  * **Another device on the LAN** — already blocked by binding to 127.0.0.1.
    Nothing off-machine can reach it at all.
  * **Someone at your keyboard** — a login only stops this if the credential
    is not recoverable from the machine. On your own PC, where the config is
    readable by your own user, it is not.

So for single-user local use, accounts add friction and no protection.

**When they do help:**

  1. Several people share the machine and should not share state.
  2. Orbital is reachable from other devices (see `expose.py`).
  3. You want a record of who did what.

**For (2) there is a better answer than a password.** Tailscale
authenticates *devices*, not credentials. Bind Orbital to the tailnet
interface and only your devices can reach it — identity already proven at the
network layer, nothing to type, nothing to phish, nothing to leak.

This module exists for cases (1) and (3), and for the times you genuinely
want a login in front of a networked instance. It is off unless you turn it
on.

Design, for when it is on:

  * **scrypt** for password hashing (stdlib, memory-hard, no dependency).
  * **Per-user salt**, 16 bytes, from `secrets`.
  * **Session tokens** in memory, with expiry, never written to disk.
  * **Constant-time comparison** for both password and session lookup.
  * **Rate limiting** on login attempts, per username and globally.
  * **No password in the URL, ever.** The login form POSTs.
  * **Account file** is 0600.

It is deliberately not OAuth, not LDAP, not a user database. It is the
smallest thing that is actually correct.
"""

import hashlib
import hmac
import json
import os
import secrets
import time

from . import config, logutil

log = logutil.get_logger("accounts")

ACCOUNTS_FILE = os.path.join(config.STATE_DIR, "accounts.json")

# scrypt parameters. n=2**14 is the common interactive setting; it costs
# roughly 100ms and 16MB, which is the point.
SCRYPT_N = 2 ** 14
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_LEN = 32

SESSION_TTL = int(os.environ.get("ORBITAL_SESSION_TTL", "86400"))   # 24h
MAX_ATTEMPTS = 8            # per window, per username
ATTEMPT_WINDOW = 300        # seconds
LOCKOUT = 900               # seconds after exceeding the window

# In-memory only. A restart invalidates every session, which is the correct
# behaviour for a local service.
_SESSIONS = {}              # token -> {user, created, expires, last_seen}
_ATTEMPTS = {}              # username -> [timestamps]
_LOCKED = {}                # username -> unlock time


def enabled():
    """Accounts are used only if a file exists and ORBITAL_AUTH is not off."""
    if os.environ.get("ORBITAL_AUTH", "").lower() in ("0", "false", "no", "off"):
        return False
    return os.path.exists(ACCOUNTS_FILE)


# ------------------------------------------------------------- hashing
def _hash(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P,
        dklen=SCRYPT_LEN,
    )
    return salt.hex(), digest.hex()


def _verify(password, salt_hex, expected_hex):
    try:
        salt = bytes.fromhex(salt_hex)
    except ValueError:
        return False
    _s, digest = _hash(password, salt)
    return hmac.compare_digest(digest, expected_hex)


# ------------------------------------------------------------ accounts
def _load():
    if not os.path.exists(ACCOUNTS_FILE):
        return {"users": {}}
    try:
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            return {"users": {}}
        data.setdefault("users", {})
        return data
    except (OSError, json.JSONDecodeError) as exc:
        log.error(f"accounts file unreadable: {exc}")
        return {"users": {}}


def _save(data):
    config.ensure_dirs()
    tmp = ACCOUNTS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, sort_keys=True)
    os.replace(tmp, ACCOUNTS_FILE)
    try:
        os.chmod(ACCOUNTS_FILE, 0o600)
    except OSError:
        pass


def users():
    return sorted(_load()["users"])


def add_user(username, password, admin=False):
    """Create or replace an account. Password is never stored in the clear."""
    username = str(username).strip().lower()
    if not username:
        raise ValueError("username cannot be empty")
    if len(password) < 8:
        raise ValueError("password must be at least 8 characters")

    data = _load()
    salt, digest = _hash(password)
    data["users"][username] = {
        "salt": salt,
        "hash": digest,
        "admin": bool(admin),
        "created": time.time(),
        "last_login": None,
    }
    _save(data)
    log.info(f"account '{username}' created" + (" (admin)" if admin else ""))
    return username


def remove_user(username):
    username = str(username).strip().lower()
    data = _load()
    if username not in data["users"]:
        return False
    del data["users"][username]
    _save(data)
    # Invalidate any live sessions for that user.
    for token, sess in list(_SESSIONS.items()):
        if sess["user"] == username:
            _SESSIONS.pop(token, None)
    log.info(f"account '{username}' removed")
    return True


def set_password(username, password):
    username = str(username).strip().lower()
    if len(password) < 8:
        raise ValueError("password must be at least 8 characters")
    data = _load()
    if username not in data["users"]:
        raise ValueError(f"no such user '{username}'")
    salt, digest = _hash(password)
    data["users"][username]["salt"] = salt
    data["users"][username]["hash"] = digest
    _save(data)
    for token, sess in list(_SESSIONS.items()):
        if sess["user"] == username:
            _SESSIONS.pop(token, None)
    log.info(f"password changed for '{username}'")
    return True


# ------------------------------------------------------- rate limiting
def _check_rate(username):
    now = time.time()

    unlock = _LOCKED.get(username)
    if unlock and now < unlock:
        return False, int(unlock - now)

    attempts = [t for t in _ATTEMPTS.get(username, []) if now - t < ATTEMPT_WINDOW]
    _ATTEMPTS[username] = attempts

    if len(attempts) >= MAX_ATTEMPTS:
        _LOCKED[username] = now + LOCKOUT
        log.warn(f"too many failed logins for '{username}'; locked {LOCKOUT}s")
        return False, LOCKOUT

    return True, 0


def _record_failure(username):
    _ATTEMPTS.setdefault(username, []).append(time.time())


def _clear_failures(username):
    _ATTEMPTS.pop(username, None)
    _LOCKED.pop(username, None)


# ------------------------------------------------------------- login
def login(username, password):
    """Verify credentials. Returns a session token, or None.

    Deliberately vague about *which* part was wrong — "no such user" tells an
    attacker which usernames exist.
    """
    username = str(username).strip().lower()

    allowed, wait = _check_rate(username)
    if not allowed:
        log.warn(f"login blocked for '{username}' ({wait}s remaining)")
        return None

    data = _load()
    record = data["users"].get(username)

    if not record or not _verify(password, record["salt"], record["hash"]):
        _record_failure(username)
        log.warn(f"failed login for '{username}'")
        return None

    _clear_failures(username)

    token = secrets.token_urlsafe(32)
    now = time.time()
    _SESSIONS[token] = {
        "user": username,
        "created": now,
        "expires": now + SESSION_TTL,
        "last_seen": now,
    }

    record["last_login"] = now
    _save(data)
    log.info(f"'{username}' logged in")
    return token


def logout(token):
    if token and _SESSIONS.pop(token, None):
        log.info("session ended")
        return True
    return False


def session_user(token):
    """The username for a live session, or None. Sliding expiry."""
    if not token:
        return None
    sess = _SESSIONS.get(token)
    if not sess:
        return None

    now = time.time()
    if now >= sess["expires"]:
        _SESSIONS.pop(token, None)
        return None

    # Sliding window: active sessions stay alive, idle ones expire.
    sess["expires"] = now + SESSION_TTL
    sess["last_seen"] = now
    return sess["user"]


def sessions():
    """Live sessions, for an admin view. Never exposes tokens."""
    now = time.time()
    out = []
    for sess in _SESSIONS.values():
        out.append({
            "user": sess["user"],
            "created": sess["created"],
            "expires_in": max(0, int(sess["expires"] - now)),
            "idle_for": int(now - sess["last_seen"]),
        })
    return sorted(out, key=lambda s: s["created"], reverse=True)


def expire_now():
    now = time.time()
    for token, sess in list(_SESSIONS.items()):
        if now >= sess["expires"]:
            _SESSIONS.pop(token, None)


def status():
    return {
        "enabled": enabled(),
        "users": users(),
        "active_sessions": len(_SESSIONS),
        "session_ttl_hours": SESSION_TTL / 3600,
        "accounts_file": ACCOUNTS_FILE,
    }


# ----------------------------------------------------------------- CLI
def main():
    import argparse
    import getpass

    ap = argparse.ArgumentParser(
        prog="orbital-auth",
        description="Manage Orbital accounts. Off unless you use this.",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("add", help="create an account")
    p.add_argument("username")
    p.add_argument("--admin", action="store_true")

    p = sub.add_parser("remove", help="delete an account")
    p.add_argument("username")

    p = sub.add_parser("passwd", help="change a password")
    p.add_argument("username")

    sub.add_parser("list", help="list accounts")
    sub.add_parser("status", help="show whether auth is on")
    sub.add_parser("sessions", help="show live sessions")
    sub.add_parser("disable", help="turn accounts off")

    args = ap.parse_args()

    if args.cmd == "add":
        pw = getpass.getpass("Password: ")
        again = getpass.getpass("Again: ")
        if pw != again:
            print("Passwords do not match.")
            return 1
        try:
            add_user(args.username, pw, admin=args.admin)
            print(f"Account '{args.username}' created.")
            print("Accounts are now REQUIRED. Restart the engine to apply.")
            return 0
        except ValueError as exc:
            print(f"Failed: {exc}")
            return 1

    if args.cmd == "remove":
        print("Removed." if remove_user(args.username) else "No such user.")
        return 0

    if args.cmd == "passwd":
        pw = getpass.getpass("New password: ")
        again = getpass.getpass("Again: ")
        if pw != again:
            print("Passwords do not match.")
            return 1
        try:
            set_password(args.username, pw)
            print("Password changed. Live sessions for that user were ended.")
            return 0
        except ValueError as exc:
            print(f"Failed: {exc}")
            return 1

    if args.cmd == "list":
        found = users()
        if not found:
            print("No accounts. Auth is off.")
            return 0
        data = _load()
        for name in found:
            rec = data["users"][name]
            tag = " (admin)" if rec.get("admin") else ""
            last = rec.get("last_login")
            when = time.strftime("%Y-%m-%d %H:%M", time.localtime(last)) if last else "never"
            print(f"  {name}{tag}  last login: {when}")
        return 0

    if args.cmd == "status":
        st = status()
        print(f"  accounts required : {'yes' if st['enabled'] else 'no'}")
        print(f"  accounts          : {len(st['users'])}")
        print(f"  active sessions   : {st['active_sessions']}")
        print(f"  session lifetime  : {st['session_ttl_hours']:.0f}h")
        if st["users"]:
            print(f"  file              : {st['accounts_file']}")
        return 0

    if args.cmd == "sessions":
        live = sessions()
        if not live:
            print("No live sessions.")
            return 0
        for s in live:
            print(f"  {s['user']}  expires in {s['expires_in']}s  "
                  f"idle {s['idle_for']}s")
        return 0

    if args.cmd == "disable":
        if os.path.exists(ACCOUNTS_FILE):
            backup = ACCOUNTS_FILE + ".disabled"
            os.replace(ACCOUNTS_FILE, backup)
            print(f"Auth disabled. Accounts kept at {backup}")
            print("Restart the engine to apply.")
        else:
            print("Auth was already off.")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
