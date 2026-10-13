"""Shared logging.

The original code spawned every daemon with stdout/stderr pointed at DEVNULL,
which is why the healer crashed invisibly for who-knows-how-long. Everything
now logs to a file *and* to the console, so a failure is always visible
somewhere.
"""

import os
import sys
import time

from . import config

_MAX_BYTES = 2 * 1024 * 1024  # rotate at 2 MB


class Logger:
    """Small file+console logger. No third-party dependency."""

    def __init__(self, name):
        config.ensure_dirs()
        self.name = name
        self.path = os.path.join(config.LOG_DIR, f"{name}.log")
        self._quiet = os.environ.get("ORBITAL_QUIET") == "1"

    def _write(self, level, msg):
        line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [{level}] [{self.name}] {msg}"
        try:
            if os.path.exists(self.path) and os.path.getsize(self.path) > _MAX_BYTES:
                os.replace(self.path, self.path + ".1")
        except OSError:
            pass
        try:
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        except OSError:
            pass
        if not self._quiet:
            try:
                print(line, flush=True)
            except Exception:
                pass

    def info(self, msg):
        self._write("INFO", msg)

    def warn(self, msg):
        self._write("WARN", msg)

    def error(self, msg):
        self._write("ERROR", msg)

    def exception(self, msg):
        self._write("ERROR", msg)
        import traceback

        self._write("ERROR", traceback.format_exc())


def get_logger(name):
    return Logger(name)


def tail(path, lines=200):
    """Last N lines of a file, for the /api/logs endpoint."""
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read().splitlines()[-lines:]
    except OSError as exc:
        return [f"<unreadable: {exc}>"]
