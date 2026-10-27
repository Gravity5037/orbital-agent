"""Accounts - identity, roles, recovery, lockouts.

Sign in with username, email, or phone. Three roles, one owner.
scrypt passwords. 5 failures alerts, 10 blocks the IP for an hour.
Deletion has a 7-day backout. Cannot send email or SMS - see notify.py.
"""

import argparse
import getpass
import hashlib
import hmac
import json
import os
import re
import secrets
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import config, logutil  # noqa: E402

log = logutil.get_logger("accounts")

ACCOUNTS_FILE = os.path.join(config.STATE_DIR, "accounts.json")

SESSION_TTL = 60 * 60 * 12          # 12 hours
MAX_FAILURES = 10                   # before the IP block
ALERT_AT = 5                        # notify at this many failures
FAIL_WINDOW = 60 * 60               # failures older than this are forgotten
IP_BLOCK_SECONDS = 60 * 60          # one hour
DELETE_GRACE_DAYS = 7

OWNER = "owner"
ADMIN = "admin"
MEMBER = "member"

_LOCK = threading.RLock()
_SESSIONS = {}      # token -> record
_FAILURES = {}      # username -> [timestamps]
_IP_FAILURES = {}   # ip -> [timestamps]
_IP_BLOCKED = {}    # ip -> unblock time

def enabled():
    """Accounts are used only if the file exists and ORBITAL_AUTH is not off."""
    if os.environ.get("ORBITAL_AUTH", "").lower() in ("0", "false", "no", "off"):
        return False
    return os.path.exists(ACCOUNTS_FILE)

def _load():
    if not os.path.exists(ACCOUNTS_FILE):
        return {"users": {}}
    try:
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict) or "users" not in data:
            return {"users": {}}
        return data
    except (OSError, json.JSONDecodeError) as exc:
        log.warn(f"could not read accounts: {exc}")
        return {"users": {}}

def _save(data):
    os.makedirs(os.path.dirname(ACCOUNTS_FILE), exist_ok=True)
    tmp = ACCOUNTS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, ACCOUNTS_FILE)
    try:
        os.chmod(ACCOUNTS_FILE, 0o600)
    except OSError:
        pass

def _hash(secret, salt=None):
    """scrypt. Returns (salt_hex, digest_hex)."""
    salt = salt or secrets.token_bytes(16)
    if isinstance(salt, str):
        salt = bytes.fromhex(salt)
    digest = hashlib.scrypt(
        secret.encode("utf-8"), salt=salt,
        n=2 ** 14, r=8, p=1, dklen=32,
    )
    return salt.hex(), digest.hex()

def _verify(secret, salt_hex, expected_hex):
    try:
        _s, digest = _hash(secret, salt_hex)
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(digest, expected_hex)

def _digits(value):
    return re.sub(r"[^0-9]", "", str(value or ""))

def users():
    return sorted(_load()["users"].keys())

def owner_name():
    for name, rec in _load()["users"].items():
        if rec.get("role") == OWNER:
            return name
    return ""

def role_of(username):
    username = str(username or "").strip().lower()
    rec = _load()["users"].get(username)
    if not rec:
        return MEMBER
    return rec.get("role") or (ADMIN if rec.get("admin") else MEMBER)

def is_owner(username):
    return bool(username) and str(username).strip().lower() == owner_name()

def phones_of(username):
    """Every number on an account, labelled. The first is the primary."""
    rec = _load()["users"].get(str(username or "").strip().lower())
    if not rec:
        return []
    out = list(rec.get("phones") or [])
    primary = rec.get("phone")
    if primary and not any(_digits(p.get("number")) == _digits(primary)
                           for p in out):
        out.insert(0, {"label": "primary", "number": primary})
    return out

def set_phones(username, entries):
    """Replace the number list. Each entry is {label, number}."""
    username = str(username or "").strip().lower()

    clean = []
    seen = set()
    for e in entries or []:
        if isinstance(e, str):
            e = {"label": "", "number": e}
        number = str(e.get("number") or "").strip()
        if not number:
            continue
        digits = _digits(number)
        if len(digits) < 7:
            raise ValueError(f"'{number}' does not look like a phone number")
        if digits in seen:
            continue
        seen.add(digits)
        clean.append({
            "label": str(e.get("label") or "").strip()[:24],
            "number": number,
            "verified": False,
        })

    with _LOCK:
        data = _load()
        rec = data["users"].get(username)
        if not rec:
            raise ValueError("no such user")

        for other_name, other in data["users"].items():
            if other_name == username:
                continue
            theirs = {_digits(other.get("phone"))}
            theirs |= {_digits(p.get("number"))
                       for p in (other.get("phones") or [])}
            for entry in clean:
                if _digits(entry["number"]) in theirs:
                    raise ValueError(
                        f"That number is already on another account.")

        rec["phones"] = clean
        rec["phone"] = clean[0]["number"] if clean else ""
        _save(data)

    log.info(f"{username} now has {len(clean)} phone number(s)")
    return clean

def taken(username):
    username = str(username or "").strip().lower()
    return bool(username) and username in _load()["users"]

def find_user(identifier):
    """Resolve a username, email, or phone to a username. None if unknown."""
    if not identifier:
        return None
    ident = str(identifier).strip()
    if not ident:
        return None

    low = ident.lower()
    data = _load()

    if low in data["users"]:
        return low

    if "@" in ident:
        for name, rec in data["users"].items():
            if (rec.get("email") or "").lower() == low:
                return name

    digits = _digits(ident)
    if len(digits) >= 7:
        for name, rec in data["users"].items():
            if _digits(rec.get("phone")) == digits:
                return name
            for entry in rec.get("phones") or []:
                if _digits(entry.get("number")) == digits:
                    return name

    return None

RECOVERY_WORDS = (
    "anchor", "amber", "arrow", "atlas", "baker", "beacon", "birch", "bishop",
    "bison", "blade", "bloom", "border", "bottle", "bramble", "bronze", "brook",
    "cabin", "cactus", "candle", "canyon", "cedar", "cello", "cherry", "cinder",
    "citrus", "clover", "cobalt", "comet", "copper", "coral", "cotton", "crater",
    "cricket", "crystal", "daisy", "dawn", "delta", "denim", "diesel", "dolphin",
    "domino", "dragon", "ember", "engine", "fable", "falcon", "feather", "fern",
    "flint", "forest", "fossil", "fountain", "garden", "ginger", "glacier", "granite",
    "harbor", "hazel", "heron", "hickory", "hollow", "honey", "indigo", "ivory",
    "jade", "jasmine", "jungle", "juniper", "kestrel", "lantern", "larch", "lattice",
    "lavender", "lemon", "linen", "lobster", "lotus", "magnet", "maple", "marble",
)

def new_recovery_code(words=5):
    """Five words, ~60 bits. Easy to read off paper and type back."""
    return "-".join(secrets.choice(RECOVERY_WORDS) for _ in range(words))

def recover_with_code(username, code, new_password):
    """Reset a password with the code from signup. Single use."""
    username = str(username or "").strip().lower()
    code = str(code or "").strip().lower()
    if len(new_password) < 8:
        raise ValueError("password must be at least 8 characters")

    with _LOCK:
        data = _load()
        rec = data["users"].get(username)
        if not rec:
            raise ValueError("That username and recovery code do not match.")
        if rec.get("recovery_used"):
            raise ValueError(
                "That recovery code has already been used. Ask an admin to "
                "reset the account.")
        if not _verify(code, rec.get("recovery_salt"),
                       rec.get("recovery_hash")):
            _record_failure(username)
            raise ValueError("That username and recovery code do not match.")

        salt, digest = _hash(new_password)
        rec["salt"] = salt
        rec["hash"] = digest

        fresh = new_recovery_code()
        csalt, cdigest = _hash(fresh)
        rec["recovery_salt"] = csalt
        rec["recovery_hash"] = cdigest
        rec["recovery_used"] = True
        _save(data)

    _clear_failures(username)
    expire_now()
    log.info(f"'{username}' recovered with their code")
    return {"username": username, "new_recovery_code": fresh}

def new_code_for(username):
    username = str(username or "").strip().lower()
    with _LOCK:
        data = _load()
        rec = data["users"].get(username)
        if not rec:
            raise ValueError("no such user")
        fresh = new_recovery_code()
        csalt, cdigest = _hash(fresh)
        rec["recovery_salt"] = csalt
        rec["recovery_hash"] = cdigest
        rec["recovery_used"] = False
        _save(data)
    return fresh

def add_user(username, password, admin=False, email="", phone="",
             display=None, recovery=None, replace=False):
    """Create an account. Refuses a username that is taken."""
    original = str(username or "").strip()
    username = original.lower()

    if not username:
        raise ValueError("username cannot be empty")
    if len(username) < 3:
        raise ValueError("username must be at least 3 characters")
    if not re.match(r"^[a-z0-9_.-]+$", username):
        raise ValueError(
            "username can use letters, numbers, dot, dash and underscore")
    if len(password) < 8:
        raise ValueError("password must be at least 8 characters")

    with _LOCK:
        data = _load()

        if username in data["users"] and not replace:
            raise ValueError("That username is taken. Try another.")

        email = str(email or "").strip()
        if email:
            if "@" not in email or "." not in email.split("@")[-1]:
                raise ValueError("that does not look like an email address")
            for name, rec in data["users"].items():
                if name != username and \
                        (rec.get("email") or "").lower() == email.lower():
                    raise ValueError("That email is already registered.")

        if isinstance(phone, (list, tuple)):
            entries = [e if isinstance(e, dict) else {"number": e}
                       for e in phone]
        else:
            entries = ([{"label": "", "number": phone}] if str(phone or "").strip()
                       else [])

        clean_phones = []
        seen = set()
        for e in entries:
            number = str(e.get("number") or "").strip()
            if not number:
                continue
            digits = _digits(number)
            if len(digits) < 7:
                raise ValueError("that does not look like a phone number")
            if digits in seen:
                continue
            seen.add(digits)
            clean_phones.append({
                "label": str(e.get("label") or "").strip()[:24],
                "number": number,
                "verified": False,
            })

        for name, rec in data["users"].items():
            if name == username:
                continue
            theirs = {_digits(rec.get("phone"))}
            theirs |= {_digits(p.get("number"))
                       for p in (rec.get("phones") or [])}
            for entry in clean_phones:
                if _digits(entry["number"]) in theirs:
                    raise ValueError(
                        "That phone number is already registered.")

        first = not data["users"]
        if first:
            role = OWNER
        elif admin:
            role = ADMIN
        else:
            role = MEMBER

        salt, digest = _hash(password)
        code = recovery or new_recovery_code()
        csalt, cdigest = _hash(code)

        data["users"][username] = {
            "salt": salt,
            "hash": digest,
            "role": role,
            "admin": role in (ADMIN, OWNER),
            "created": time.time(),
            "last_login": None,
            "display": (display or original)[:32],
            "email": email,
            "phone": clean_phones[0]["number"] if clean_phones else "",
            "phones": clean_phones,
            "recovery_salt": csalt,
            "recovery_hash": cdigest,
            "recovery_used": False,
            "active": True,
            "deleted_at": None,
            "theme": "",
        }
        _save(data)

    log.info(f"account '{username}' created ({role})")
    return {"username": username, "role": role, "recovery_code": code}

def set_password(username, password, actor=None):
    username = str(username or "").strip().lower()
    if len(password) < 8:
        raise ValueError("password must be at least 8 characters")
    if actor and actor != username:
        ok, why = can_manage(actor, username)
        if not ok:
            raise ValueError(why)

    with _LOCK:
        data = _load()
        rec = data["users"].get(username)
        if not rec:
            raise ValueError("no such user")
        rec["salt"], rec["hash"] = _hash(password)
        _save(data)

    expire_now(username)
    log.info(f"password changed for '{username}'")
    return True

def set_contact(username, email=None, phone=None):
    """Change the email or phone on an account. Pass None to leave alone."""
    username = str(username or "").strip().lower()
    with _LOCK:
        data = _load()
        rec = data["users"].get(username)
        if not rec:
            raise ValueError("no such user")

        if email is not None:
            email = str(email).strip()
            if email:
                if "@" not in email or "." not in email.split("@")[-1]:
                    raise ValueError("that does not look like an email address")
                for name, other in data["users"].items():
                    if name != username and \
                            (other.get("email") or "").lower() == email.lower():
                        raise ValueError("That email is already registered.")
            rec["email"] = email

        if phone is not None:
            phone = str(phone).strip()
            if phone:
                if len(_digits(phone)) < 7:
                    raise ValueError("that does not look like a phone number")
                for name, other in data["users"].items():
                    if name != username and \
                            _digits(other.get("phone")) == _digits(phone):
                        raise ValueError("That phone number is already in use.")
            rec["phone"] = phone

        _save(data)

    log.info(f"contact details updated for '{username}'")
    return True

def rename(old, new, actor=None):
    """Change a username. The old one becomes free for anyone to take."""
    old = str(old or "").strip().lower()
    new_original = str(new or "").strip()
    new = new_original.lower()

    if actor and actor != old:
        ok, why = can_manage(actor, old)
        if not ok:
            raise ValueError(why)
    if not new:
        raise ValueError("username cannot be empty")
    if len(new) < 3:
        raise ValueError("username must be at least 3 characters")
    if not re.match(r"^[a-z0-9_.-]+$", new):
        raise ValueError("username can use letters, numbers, dot, dash, underscore")
    if new == old:
        raise ValueError("that is already your username")

    with _LOCK:
        data = _load()
        if old not in data["users"]:
            raise ValueError("no such user")
        if new in data["users"]:
            raise ValueError("That username is taken. Try another.")
        if data["users"][old].get("role") == OWNER:
            raise ValueError("the owner account cannot be renamed")

        rec = data["users"].pop(old)
        rec["display"] = new_original[:32]
        data["users"][new] = rec
        _save(data)

    with _LOCK:
        for token, sess in _SESSIONS.items():
            if sess["user"] == old:
                sess["user"] = new

    log.info(f"'{old}' renamed to '{new}'")
    return {"username": new, "released": old}

def set_theme(username, theme):
    """Store a colour choice. An empty string means the default."""
    username = str(username or "").strip().lower()
    with _LOCK:
        data = _load()
        rec = data["users"].get(username)
        if not rec:
            raise ValueError("no such user")
        rec["theme"] = str(theme or "")[:64]
        _save(data)
    return rec["theme"]

def theme_of(username):
    username = str(username or "").strip().lower()
    rec = _load()["users"].get(username)
    return (rec or {}).get("theme", "")

def deactivate(username, actor=None):
    """Refuse future logins. Fully reversible."""
    username = str(username or "").strip().lower()
    if actor and actor != username:
        ok, why = can_manage(actor, username)
        if not ok:
            raise ValueError(why)
    with _LOCK:
        data = _load()
        rec = data["users"].get(username)
        if not rec:
            raise ValueError("no such user")
        if rec.get("role") == OWNER:
            raise ValueError("the owner account cannot be deactivated")
        rec["active"] = False
        _save(data)
    expire_now(username)
    log.info(f"'{username}' deactivated")
    return True

def reactivate(username, actor=None):
    username = str(username or "").strip().lower()
    if actor and actor != username:
        ok, why = can_manage(actor, username)
        if not ok:
            raise ValueError(why)
    with _LOCK:
        data = _load()
        rec = data["users"].get(username)
        if not rec:
            raise ValueError("no such user")
        rec["active"] = True
        _save(data)
    log.info(f"'{username}' reactivated")
    return True

def request_delete(username):
    """Start the 7-day backout window. Login is refused immediately."""
    username = str(username or "").strip().lower()
    with _LOCK:
        data = _load()
        rec = data["users"].get(username)
        if not rec:
            raise ValueError("no such user")
        if rec.get("role") == OWNER:
            raise ValueError("the owner account cannot be deleted")
        rec["deleted_at"] = time.time()
        rec["active"] = False
        _save(data)
    expire_now(username)
    log.info(f"'{username}' scheduled for deletion")
    return days_left(username)

def cancel_delete(username):
    username = str(username or "").strip().lower()
    with _LOCK:
        data = _load()
        rec = data["users"].get(username)
        if not rec:
            raise ValueError("no such user")
        if not rec.get("deleted_at"):
            raise ValueError("that account is not scheduled for deletion")
        rec["deleted_at"] = None
        rec["active"] = True
        _save(data)
    log.info(f"'{username}' deletion cancelled")
    return True

def days_left(username):
    """Days remaining in the backout window, or None."""
    rec = _load()["users"].get(str(username or "").strip().lower())
    if not rec or not rec.get("deleted_at"):
        return None
    elapsed = time.time() - rec["deleted_at"]
    remaining = DELETE_GRACE_DAYS - (elapsed / 86400)
    return max(0, remaining)

def purge_expired():
    """Remove accounts whose backout window has closed. Returns names."""
    gone = []
    now = time.time()
    with _LOCK:
        data = _load()
        for name, rec in list(data["users"].items()):
            started = rec.get("deleted_at")
            if not started:
                continue
            if (now - started) / 86400 >= DELETE_GRACE_DAYS:
                del data["users"][name]
                gone.append(name)
        if gone:
            _save(data)
    for name in gone:
        log.info(f"'{name}' deleted - the {DELETE_GRACE_DAYS}-day window closed")
    return gone

def remove_user(username):
    username = str(username or "").strip().lower()
    with _LOCK:
        data = _load()
        if username not in data["users"]:
            return False
        del data["users"][username]
        _save(data)
    expire_now(username)
    log.info(f"'{username}' removed")
    return True

ROLE_ORDER = {MEMBER: 0, ADMIN: 1, OWNER: 2}

def can_manage(actor, target):
    """May `actor` change `target`? Returns (ok, reason)."""
    actor = str(actor or "").strip().lower()
    target = str(target or "").strip().lower()

    if not actor or not target:
        return False, "no such account"

    data = _load()
    if target not in data["users"]:
        return False, "no such account"
    if actor not in data["users"]:
        return False, "no such account"

    a_role, t_role = role_of(actor), role_of(target)

    if t_role == OWNER and actor != target:
        return False, "that is the owner account. Only the owner can change it."
    if a_role == MEMBER:
        return False, "only an admin can manage accounts."
    if a_role == ADMIN and t_role == ADMIN and actor != target:
        return False, "admins cannot change other admins. Ask the owner."
    if a_role == ADMIN and t_role == OWNER:
        return False, "that is the owner account."
    return True, "ok"

def set_role(actor, target, role):
    target = str(target or "").strip().lower()
    role = str(role or "").strip().lower()
    if role not in (OWNER, ADMIN, MEMBER):
        return False, f"unknown role '{role}'"

    ok, why = can_manage(actor, target)
    if not ok:
        return False, why
    if role == OWNER:
        return False, ("there is only one owner, and it is set at signup. "
                       "It cannot be reassigned.")

    with _LOCK:
        data = _load()
        rec = data["users"][target]
        was = role_of(target)
        rec["role"] = role
        rec["admin"] = role in (ADMIN, OWNER)
        _save(data)

    log.info(f"{actor} set {target} to {role} (was {was})")
    return True, f"{target} is now {role}"

def promote(actor, target):
    if role_of(target) == ADMIN:
        return False, f"{target} is already an admin"
    return set_role(actor, target, ADMIN)

def demote(actor, target):
    if role_of(target) == OWNER:
        return False, "that is the owner account. It cannot be demoted."
    if role_of(target) == MEMBER:
        return False, f"{target} is already a member"
    return set_role(actor, target, MEMBER)

def roster():
    data = _load()
    out = []
    for name, rec in sorted(data["users"].items()):
        out.append({
            "username": name,
            "display": rec.get("display") or name,
            "role": role_of(name),
            "created": rec.get("created"),
            "last_login": rec.get("last_login"),
            "has_email": bool(rec.get("email")),
            "has_phone": bool(rec.get("phone") or rec.get("phones")),
            "phone_count": len(phones_of(name)),
            "active": rec.get("active", True),
            "deleting_in": days_left(name),
            "theme": rec.get("theme", ""),
        })
    return out

def _recent(store, key, now=None):
    now = now or time.time()
    stamps = [t for t in store.get(key, []) if now - t < FAIL_WINDOW]
    if stamps:
        store[key] = stamps
    else:
        store.pop(key, None)
    return stamps

def _check_rate(username, ip=None):
    """May this attempt proceed? Returns (ok, seconds_to_wait)."""
    now = time.time()

    if ip:
        until = _IP_BLOCKED.get(ip)
        if until and until > now:
            return False, int(until - now)
        if until:
            _IP_BLOCKED.pop(ip, None)

    return True, 0

def _record_failure(username, ip=None):
    """Count a failure. Fires the alert and the IP block at thresholds."""
    now = time.time()
    with _LOCK:
        if username:
            _recent(_FAILURES, username, now)
            _FAILURES.setdefault(username, []).append(now)
            count = len(_FAILURES[username])
        else:
            count = 0

        if ip:
            _recent(_IP_FAILURES, ip, now)
            _IP_FAILURES.setdefault(ip, []).append(now)
            ip_count = len(_IP_FAILURES[ip])
        else:
            ip_count = 0

    if count == ALERT_AT:
        _alert(username, "repeated failed sign-in attempts")
    if ip_count >= MAX_FAILURES and ip:
        with _LOCK:
            _IP_BLOCKED[ip] = now + IP_BLOCK_SECONDS
        log.warn(f"{ip} blocked for {IP_BLOCK_SECONDS // 60} minutes "
                 f"after {ip_count} failures")
        _alert(username, "this address has been temporarily blocked")

def _alert(username, reason):
    """Queue a security notice. Nothing is sent unless a sender is set."""
    try:
        from core import notify
    except ImportError:
        log.warn(f"security alert for '{username}': {reason} "
                 f"(no notify module, so nothing was sent)")
        return

    rec = _load()["users"].get(username) or {}
    notify.security_alert(
        username=username,
        email=rec.get("email", ""),
        phone=rec.get("phone", ""),
        reason=reason,
    )

def _clear_failures(username):
    with _LOCK:
        _FAILURES.pop(str(username or "").strip().lower(), None)

def failure_count(username):
    with _LOCK:
        return len(_recent(_FAILURES, str(username or "").strip().lower()))

def blocked_addresses():
    now = time.time()
    return {ip: int(until - now) for ip, until in _IP_BLOCKED.items()
            if until > now}

def login(identifier, password, ip=None):
    """Verify credentials. Returns a session token, or None."""
    username = find_user(identifier)

    if not username:
        _record_failure(None, ip)
        log.warn("failed login: unknown identifier")
        return None

    ok, wait = _check_rate(username, ip)
    if not ok:
        log.warn(f"login blocked for '{username}' ({wait}s remaining)")
        return None

    with _LOCK:
        data = _load()
        rec = data["users"].get(username)

        if rec and not rec.get("active", True):
            log.warn(f"login refused for '{username}': not active")
            return None

        if not rec or not _verify(password, rec["salt"], rec["hash"]):
            _record_failure(username, ip)
            log.warn(f"failed login for '{username}'")
            return None

        _clear_failures(username)
        rec["last_login"] = time.time()
        _save(data)

    token = secrets.token_urlsafe(32)
    now = time.time()
    with _LOCK:
        _SESSIONS[token] = {
            "user": username,
            "created": now,
            "expires": now + SESSION_TTL,
            "last_seen": now,
        }
    log.info(f"'{username}' signed in")
    return token

def logout(token):
    with _LOCK:
        return _SESSIONS.pop(token, None) is not None

def session_user(token):
    if not token:
        return None
    now = time.time()
    with _LOCK:
        sess = _SESSIONS.get(token)
        if not sess:
            return None
        if sess["expires"] < now:
            del _SESSIONS[token]
            return None
        sess["last_seen"] = now
        return sess["user"]

def sessions():
    now = time.time()
    with _LOCK:
        return [
            {"user": s["user"], "created": s["created"],
             "expires": s["expires"], "last_seen": s["last_seen"]}
            for t, s in _SESSIONS.items() if s["expires"] > now
        ]

def expire_now(username=None):
    """Drop sessions, for one user or everyone."""
    with _LOCK:
        if username is None:
            _SESSIONS.clear()
            return
        username = str(username).strip().lower()
        for token in [t for t, s in _SESSIONS.items() if s["user"] == username]:
            del _SESSIONS[token]

def status():
    data = _load()
    return {
        "enabled": enabled(),
        "users": len(data["users"]),
        "owner": owner_name(),
        "active_sessions": len(sessions()),
        "blocked_addresses": len(blocked_addresses()),
    }

def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="orbital-auth",
        description="Manage Orbital accounts. Off unless you use this.",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("add", help="create an account")
    p.add_argument("username")
    p.add_argument("--admin", action="store_true")
    p.add_argument("--email", default="")
    p.add_argument("--phone", default="")

    p = sub.add_parser("remove", help="delete an account")
    p.add_argument("username")
    p.add_argument("--as", dest="actor", default="")

    p = sub.add_parser("phones", help="list or set phone numbers")
    p.add_argument("username")
    p.add_argument("--set", nargs="*", default=None,
                   metavar="LABEL=NUMBER",
                   help="replace the list, e.g. personal=4238037918 "
                        "work=8436961825")

    p = sub.add_parser("passwd", help="change a password")
    p.add_argument("username")

    p = sub.add_parser("rename", help="change a username")
    p.add_argument("old")
    p.add_argument("new")

    p = sub.add_parser("promote", help="make someone an admin")
    p.add_argument("username")
    p.add_argument("--as", dest="actor", default="")

    p = sub.add_parser("demote", help="make someone a member")
    p.add_argument("username")
    p.add_argument("--as", dest="actor", default="")

    p = sub.add_parser("deactivate", help="refuse future logins")
    p.add_argument("username")

    p = sub.add_parser("reactivate", help="allow logins again")
    p.add_argument("username")

    sub.add_parser("roster", help="every account and its role")
    sub.add_parser("list", help="list accounts")
    sub.add_parser("status", help="show whether auth is on")
    sub.add_parser("sessions", help="show live sessions")
    sub.add_parser("purge", help="delete accounts past their window")
    sub.add_parser("disable", help="turn accounts off")

    args = ap.parse_args(argv)

    if args.cmd == "add":
        pw = getpass.getpass("Password: ")
        again = getpass.getpass("Again: ")
        if pw != again:
            print("Passwords do not match.")
            return 1
        try:
            r = add_user(args.username, pw, admin=args.admin,
                         email=args.email, phone=args.phone)
        except ValueError as exc:
            print(f"Failed: {exc}")
            return 1
        print(f"Account '{r['username']}' created ({r['role']}).")
        print()
        print("  RECOVERY CODE - write this down, it is shown once:")
        print()
        print(f"      {r['recovery_code']}")
        print()
        print("  Accounts are now REQUIRED. Restart the engine to apply.")
        return 0

    if args.cmd == "roster":
        rows = roster()
        if not rows:
            print("No accounts.")
            return 0
        for r in rows:
            last = r.get("last_login")
            when = (time.strftime("%Y-%m-%d %H:%M", time.localtime(last))
                    if last else "never")
            flags = []
            if not r["active"]:
                flags.append("INACTIVE")
            if r["deleting_in"] is not None:
                flags.append(f"deletes in {r['deleting_in']:.1f}d")
            if r["has_email"]:
                flags.append("email")
            if r["has_phone"]:
                flags.append("phone")
            tail = f"  [{', '.join(flags)}]" if flags else ""
            print(f"  {r['username']:<16} {r['role']:<8} "
                  f"last login: {when}{tail}")
        return 0

    if args.cmd == "rename":
        try:
            r = rename(args.old, args.new)
        except ValueError as exc:
            print(f"Refused: {exc}")
            return 1
        print(f"{r['username']} - and '{r['released']}' is free again.")
        return 0

    if args.cmd == "promote":
        actor = args.actor or owner_name()
        ok, msg = promote(actor, args.username)
        print(msg if ok else f"Refused: {msg}")
        return 0 if ok else 1

    if args.cmd == "demote":
        actor = args.actor or owner_name()
        ok, msg = demote(actor, args.username)
        print(msg if ok else f"Refused: {msg}")
        return 0 if ok else 1

    if args.cmd in ("deactivate", "reactivate"):
        fn = deactivate if args.cmd == "deactivate" else reactivate
        try:
            fn(args.username)
        except ValueError as exc:
            print(f"Refused: {exc}")
            return 1
        print(f"{args.username} {args.cmd}d.")
        return 0

    if args.cmd == "purge":
        gone = purge_expired()
        if not gone:
            print("Nothing past its window.")
            return 0
        for name in gone:
            print(f"  deleted: {name}")
        return 0

    if args.cmd == "remove":
        actor = args.actor or owner_name()
        target = str(args.username).strip().lower()
        if not actor:
            print("No owner account exists, so nothing can be removed here.")
            return 1
        ok, why = can_manage(actor, target)
        if not ok:
            print(f"Refused: {why}")
            return 1
        if target == actor:
            print("Refused: you cannot remove your own account.")
            return 1
        print("Removed." if remove_user(target) else "No such user.")
        return 0

    if args.cmd == "phones":
        if args.set is None:
            found = phones_of(args.username)
            if not found:
                print(f"  {args.username} has no numbers")
                return 0
            print()
            for p in found:
                label = p.get("label") or "(unlabelled)"
                print(f"  {label:<14} {p['number']}")
            print()
            return 0

        entries = []
        for item in args.set:
            if "=" in item:
                label, _, number = item.partition("=")
                entries.append({"label": label, "number": number})
            else:
                entries.append({"label": "", "number": item})
        try:
            clean = set_phones(args.username, entries)
        except ValueError as exc:
            print(f"  refused: {exc}")
            return 1
        print()
        for p in clean:
            print(f"  {p['label'] or '(unlabelled)':<14} {p['number']}")
        print()
        return 0

    if args.cmd == "passwd":
        pw = getpass.getpass("New password: ")
        again = getpass.getpass("Again: ")
        if pw != again:
            print("Passwords do not match.")
            return 1
        try:
            set_password(args.username, pw)
        except ValueError as exc:
            print(f"Failed: {exc}")
            return 1
        print("Password changed. Live sessions for that user were ended.")
        return 0

    if args.cmd in ("list", "roster"):
        return main(["roster"])

    if args.cmd == "status":
        st = status()
        print(f"  accounts required : {'yes' if st['enabled'] else 'no'}")
        print(f"  accounts          : {st['users']}")
        print(f"  owner             : {st['owner'] or '(none yet)'}")
        print(f"  active sessions   : {st['active_sessions']}")
        print(f"  blocked addresses : {st['blocked_addresses']}")
        return 0

    if args.cmd == "sessions":
        live = sessions()
        if not live:
            print("  none")
            return 0
        for s in live:
            mins = int((s["expires"] - time.time()) / 60)
            print(f"  {s['user']:<16} expires in {mins} min")
        return 0

    if args.cmd == "disable":
        if os.path.exists(ACCOUNTS_FILE):
            backup = ACCOUNTS_FILE + ".disabled"
            os.replace(ACCOUNTS_FILE, backup)
            print(f"Accounts off. The file is at {backup}")
            print("Put it back to turn them on again.")
        else:
            print("Already off.")
        return 0

    return 0

if __name__ == "__main__":
    sys.exit(main())