"""Supervisor test: prove it restarts a crashing service and gives up cleanly.

The old healer crashed on iteration one and never restarted anything. This
test points the supervisor at a deliberately crashing module and asserts that
it restarts it, backs off, and eventually gives up rather than looping
forever.
"""

import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["ORBITAL_BASE"] = "/tmp/orbtest"
os.environ["ORBITAL_QUIET"] = "1"

from core import supervisor  # noqa: E402

results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(f"{'PASS' if cond else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))


def main():
    # Point the supervisor at a module that exits immediately.
    supervisor.SERVICES = [{"name": "crashy", "module": "tests.crashing_service"}]
    supervisor.BACKOFF_BASE = 1.1   # keep the test quick
    supervisor.BACKOFF_CAP = 3.0
    supervisor.HEALTH_INTERVAL = 0.15
    supervisor.MAX_RESTARTS = 3

    marker = os.path.join("/tmp/orbtest", "crash_marker.txt")
    if os.path.exists(marker):
        os.remove(marker)

    svc = supervisor.Service(supervisor.SERVICES[0])

    check("service starts with no process", svc.proc is None)
    svc.poll()
    check("first poll spawns the process", svc.proc is not None,
          f"pid={svc.proc.pid if svc.proc else None}")

    # Let it crash and be restarted repeatedly.
    deadline = time.time() + 25
    while time.time() < deadline and not svc.given_up:
        svc.poll()
        time.sleep(0.1)

    check("supervisor restarted the crashing service", svc.restarts >= 2,
          f"restarts={svc.restarts}")
    check("supervisor gave up instead of looping forever", svc.given_up,
          f"restarts={svc.restarts}, limit={supervisor.MAX_RESTARTS}")
    check("no process left running after giving up",
          svc.proc is None or svc.proc.poll() is not None)

    # Prove the children genuinely launched (not just ModuleNotFoundError).
    spawns = 0
    if os.path.exists(marker):
        with open(marker, encoding="utf-8") as fh:
            spawns = len(fh.read().split())
    check("each restart actually launched the child process", spawns >= 3,
          f"marker lines={spawns}")

    # The log must contain the transitions — this is what was invisible before.
    log_path = os.path.join("/tmp/orbtest", "logs", "supervisor.log")
    check("supervisor log file exists", os.path.exists(log_path), log_path)
    if os.path.exists(log_path):
        with open(log_path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        check("log records the restart", "restart" in text.lower())
        check("log records giving up", "giving up" in text.lower())

    passed = sum(1 for _, ok in results if ok)
    print(f"\n{passed}/{len(results)} checks passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
