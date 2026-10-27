"""Supervisor — starts and restarts the daemons.

Replaces healer_daemon.py + the "Ralph" loop, which never worked:

  * healer_daemon called healer.inspect_and_repair(), a method that does not
    exist, and crashed on its first iteration — invisibly, because it was
    spawned with stderr=DEVNULL
  * run_full_diagnostic_and_heal() only *reported*; it never restarted
    anything, and its one "repair" rewrote C:\\Orbital into C:\\\\Orbital

What this does instead is the boring, correct thing: spawn each service,
watch it, restart it with exponential backoff, give up after N failures, and
log every transition to logs/supervisor.log.

Run:  python -m core.supervisor            (foreground, verbose)
      pythonw -m core.supervisor           (background on Windows)
"""

import os
import signal
import subprocess
import sys
import time

from . import config, logutil

log = logutil.get_logger("supervisor")

# Directory containing the `core` package — the code root, which is not
# necessarily config.BASE_DIR (the data root).
CODE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MAX_RESTARTS = 5
BACKOFF_BASE = 2.0
BACKOFF_CAP = 60.0
HEALTH_INTERVAL = 5.0

# Each service declares the port it binds. The supervisor checks the
# port before spawning: a process orphaned by a force-kill keeps it,
# and spawning into that wall gives five restarts and no explanation.
SERVICES = [
    {"name": "engine", "module": "core.engine", "port": "ENGINE_PORT"},
    {"name": "mesh", "module": "core.mesh", "port": "MESH_PORT"},
]


def port_holder(port, host="127.0.0.1"):
    """Is anything already bound to this port? True or False.

    A bind test, not a connect test: we want to know whether we can
    take the port, not whether something answers on it.
    """
    import socket as _socket

    probe = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
    try:
        probe.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1)
        probe.bind((host, int(port)))
        return False          # we got it, so nobody else has it
    except OSError:
        return True           # in use
    finally:
        probe.close()


class Service:
    def __init__(self, spec):
        self.name = spec["name"]
        self.module = spec["module"]
        self.port_attr = spec.get("port")
        self.proc = None
        self.restarts = 0
        self.next_start = 0.0
        self.given_up = False

    def spawn(self):
        # Check the port before spawning. An orphan from a force-killed
        # supervisor keeps it, and spawning into that produces five
        # silent restarts. Name the holder instead.
        if getattr(self, "port_attr", None):
            port = getattr(config, self.port_attr, None)
            if port and port_holder(port):
                log.error(
                    f"{self.name}: port {port} is already in use - not "
                    f"spawning. Something is still running from an "
                    f"earlier session. Find it with:  netstat -ano | "
                    f"findstr :{port}"
                )
                self.given_up = True
                return

        argv = [sys.executable, "-m", self.module]
        creationflags = 0
        if os.name == "nt":
            creationflags = 0x08000000  # CREATE_NO_WINDOW

        # The child must be able to import `core`. BASE_DIR is the *data*
        # directory and may not be the code root (they differ whenever
        # ORBITAL_BASE points elsewhere), so we pass the package's real
        # parent on PYTHONPATH and run from there.
        env = dict(os.environ)
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = CODE_ROOT + (os.pathsep + existing if existing else "")

        # Note: output goes to the child's own log file via core.logutil,
        # so we do NOT discard stdout/stderr here. That was the bug.
        self.proc = subprocess.Popen(
            argv,
            cwd=CODE_ROOT,
            env=env,
            creationflags=creationflags,
        )
        log.info(f"{self.name}: started pid={self.proc.pid} ({self.module})")

    def poll(self):
        """Advance state. Called on every supervisor tick."""
        now = time.time()

        if self.given_up:
            return

        if self.proc is None:
            if now >= self.next_start:
                self.spawn()
            return

        code = self.proc.poll()
        if code is None:
            return  # still running

        self.restarts += 1
        if self.restarts > MAX_RESTARTS:
            log.error(
                f"{self.name}: exited ({code}) and hit the {MAX_RESTARTS}-restart "
                f"limit — giving up. Check logs/{self.name}.log"
            )
            self.given_up = True
            return

        delay = min(BACKOFF_BASE ** self.restarts, BACKOFF_CAP)
        log.warn(
            f"{self.name}: exited (code={code}); restart {self.restarts}/"
            f"{MAX_RESTARTS} in {delay:.0f}s"
        )
        self.proc = None
        self.next_start = now + delay

    def stop(self):
        if self.proc and self.proc.poll() is None:
            log.info(f"{self.name}: terminating pid={self.proc.pid}")
            try:
                self.proc.terminate()
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                log.warn(f"{self.name}: did not exit, killing")
                self.proc.kill()
            except Exception as exc:
                log.warn(f"{self.name}: stop failed: {exc}")


def main():
    config.ensure_dirs()
    log.info("=" * 60)
    log.info(f"Supervisor starting. Base dir: {config.BASE_DIR}")
    log.info(f"Logs: {config.LOG_DIR}")

    ok, detail = _nucleus_preflight()
    if not ok:
        log.warn(
            "Nucleus backend is not reachable. The engine will still run, "
            "but chat will report the failure honestly instead of faking a reply."
        )

    services = [Service(s) for s in SERVICES]
    stopping = {"flag": False}

    def _handle_signal(signum, _frame):
        log.info(f"signal {signum} received, shutting down")
        stopping["flag"] = True

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, _handle_signal)
        except (ValueError, OSError):
            pass  # not on the main thread, or unsupported

    try:
        while not stopping["flag"]:
            for svc in services:
                svc.poll()
            time.sleep(HEALTH_INTERVAL)
    finally:
        for svc in services:
            svc.stop()
        log.info("Supervisor stopped.")
    return 0


def _nucleus_preflight():
    try:
        from . import nucleus

        return nucleus.health(timeout=3)
    except Exception as exc:
        return False, str(exc)


if __name__ == "__main__":
    raise SystemExit(main())
