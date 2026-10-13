"""Token gate for the local API.

The original engine accepted unauthenticated POSTs from any origin and piped
the body into PowerShell. This module is the replacement: a random token
generated on first run, stored in state/engine.token with owner-only
permissions, compared in constant time.
"""

import hmac
import os
import secrets
import stat

from . import config

_TOKEN = None


def _lock_down(path):
    """Best-effort chmod 600. No-op where the OS doesn't support it."""
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


def get_token():
    """Load the token, creating it on first call."""
    global _TOKEN
    if _TOKEN:
        return _TOKEN

    config.ensure_dirs()

    env = os.environ.get("ORBITAL_TOKEN")
    if env:
        _TOKEN = env
        return _TOKEN

    if os.path.exists(config.TOKEN_FILE):
        try:
            with open(config.TOKEN_FILE, "r", encoding="utf-8") as fh:
                existing = fh.read().strip()
            if existing:
                _TOKEN = existing
                _lock_down(config.TOKEN_FILE)
                return _TOKEN
        except OSError:
            pass

    _TOKEN = secrets.token_urlsafe(32)
    with open(config.TOKEN_FILE, "w", encoding="utf-8") as fh:
        fh.write(_TOKEN)
    _lock_down(config.TOKEN_FILE)
    return _TOKEN


def check(supplied):
    """Constant-time comparison. Returns False for anything falsy."""
    if not supplied:
        return False
    return hmac.compare_digest(str(supplied), get_token())
