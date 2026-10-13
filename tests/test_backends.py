"""Backend routing tests.

The properties that matter for a hive:

  * least-loaded node wins
  * a node that can't do the job type is skipped
  * a dead node is skipped
  * a node with repeated failures is circuit-broken, then recovers
  * weights let a beefier machine absorb more load
  * a pinned job goes where it was told
  * failover retries elsewhere rather than losing the job
"""

import os
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "/tmp/orbtest_backends"
os.environ["ORBITAL_BASE"] = BASE
os.environ["ORBITAL_QUIET"] = "1"

sys.path.insert(0, ROOT)

results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(f"{'PASS' if cond else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))


def start_fake(port, extra=None):
    env = dict(os.environ)
    env["FAKE_COMFY_PORT"] = str(port)
    env.update(extra or {})
    return subprocess.Popen(
        [sys.executable, os.path.join(ROOT, "tests", "fake_comfy.py")], env=env
    )


def wait_up(port, timeout=10):
    import socket

    deadline = time.time() + timeout
    while time.time() < deadline:
        s = socket.socket()
        s.settimeout(0.4)
        try:
            s.connect(("127.0.0.1", port))
            return True
        except Exception:
            time.sleep(0.15)
        finally:
            s.close()
    return False


def main():
    shutil.rmtree(BASE, ignore_errors=True)
    os.makedirs(BASE, exist_ok=True)

    # Two fake ComfyUI instances: one image-only, one image+video.
    # Port 8188 is the "local" default; 8191 and 8192 are pool members.
    procs = []
    try:
        # alpha (8191) reports load 2 so least-loaded routing is deterministic.
        # beta (8192) is image-only, which exercises capability filtering.
        procs.append(start_fake(8188, {"FAKE_COMFY_LOAD": "0"}))
        procs.append(start_fake(8191, {"FAKE_COMFY_LOAD": "2"}))
        procs.append(start_fake(8192, {"FAKE_COMFY_NO_VIDEO": "1",
                                       "FAKE_COMFY_LOAD": "0"}))
        for port in (8188, 8191, 8192):
            if not wait_up(port):
                check(f"fake backend on {port} started", False)
                return 1
        check("three fake backends started", True)

        os.environ["ORBITAL_BACKENDS"] = (
            "alpha=http://127.0.0.1:8191,"
            "beta=http://127.0.0.1:8192,"
            "ghost=http://127.0.0.1:8399"
        )
        os.environ["ORBITAL_COMFY"] = "http://127.0.0.1:8188"

        from core import backends

        reg = backends.registry(force_reload=True)
        names = [b.name for b in reg]
        check("registry includes all configured backends", len(reg) == 4,
              str(names))
        check("registry includes the local instance", "local" in names, str(names))

        # ---------------------------------------------------- reachability
        report = {r["name"]: r for r in backends.status_report(deep=True)}
        check("live backends report reachable",
              report["alpha"]["reachable"] and report["beta"]["reachable"],
              f"alpha={report['alpha']['reachable']} beta={report['beta']['reachable']}")
        check("the queue probe reads real load",
              report["alpha"]["load"] == 2, str(report["alpha"]["load"]))
        check("the dead backend reports unreachable",
              report["ghost"]["reachable"] is False, str(report["ghost"]["error"])[:50])

        # --------------------------------------------------- capability
        check("alpha reports image capability", report["alpha"]["can_image"])
        check("beta reports no video capability",
              report["beta"]["can_video"] is False,
              f"can_video={report['beta']['can_video']}")
        check("alpha reports video capability", report["alpha"]["can_video"])

        # ------------------------------------------------------- routing
        pick = backends.choose(kind="image")
        check("an image job routes to a reachable node",
              pick is not None and pick.name != "ghost", str(pick))
        check("the least-loaded node is preferred over a busy one",
              pick is not None and pick.name in ("beta", "local"),
              f"chose {pick} (alpha has load 2)")
        check("a dead node is never chosen",
              all(backends.choose(kind="image").name != "ghost" for _ in range(5)))

        vpick = backends.choose(kind="video")
        check("a video job avoids the node without video models",
              vpick is not None and vpick.name != "beta",
              str(vpick))

        cands = [b.name for b in backends.candidates(kind="video")]
        check("video candidates exclude non-capable nodes",
              "beta" not in cands, str(cands))

        # ------------------------------------------ least-loaded wins
        # Real load comes from the fakes: alpha reports 2, others 0.
        check("busy node is not chosen while idle nodes exist",
              pick.name != "alpha", f"chose {pick}")

        # --------------------------------------------------- weighting
        # Compare like with like. Pin all three capable nodes to known loads
        # so the only variable is weight: local 3, alpha 2, beta 1.
        for name, load in (("local", 3), ("alpha", 2), ("beta", 1)):
            b = backends.get(name)
            b._status = {"reachable": True, "running": 0,
                         "pending": load, "load": load}
            b._status_at = time.time() + 3600
        base_pick = backends.choose(kind="image")
        check("unweighted, the lighter node wins",
              base_pick is not None and base_pick.name == "beta",
              f"chose {base_pick} (alpha 2, beta 1)")

        backends.get("alpha").weight = 100.0
        backends.get("alpha")._status_at = 0.0
        pick3 = backends.choose(kind="image")
        check("a high-weight node wins despite carrying more load",
              pick3 is not None and pick3.name == "alpha",
              f"chose {pick3} (alpha load 2 / weight 100 vs beta load 1)")
        backends.get("alpha").weight = 1.0
        backends.get("alpha")._status_at = 0.0
        backends.get("beta")._status_at = 0.0

        # -------------------------------------------------- exclusions
        pick4 = backends.choose(kind="image", exclude={"alpha", "beta", "local"})
        check("excluding everything yields no route", pick4 is None, str(pick4))

        pick5 = backends.choose(kind="image", exclude={"alpha"})
        check("exclusions are honoured",
              pick5 is not None and pick5.name != "alpha", str(pick5))

        # ---------------------------------------------- circuit breaker
        g = backends.get("ghost")
        check("a dead node starts available (cooldown not yet tripped)",
              g.is_available())
        for _ in range(backends.FAILURE_THRESHOLD):
            g.record_failure()
        check("repeated failures trip the circuit breaker",
              g.is_available() is False)
        check("a tripped node is excluded from routing",
              all((backends.choose(kind="image") or g).name != "ghost"
                  for _ in range(3)))
        g.record_success()
        check("a success resets the breaker", g.is_available() is True)

        # ------------------------------------------------------ totals
        t = backends.totals()
        check("totals count configured backends", t["configured"] == 4,
              str(t["configured"]))
        check("totals count reachable backends", t["reachable"] == 3,
              str(t["reachable"]))
        check("totals count video-capable nodes", t["video_capable"] >= 1,
              str(t["video_capable"]))

        # ------------------------------------------------ real dispatch
        from core import nebula

        r = nebula.generate("router test", base=backends.get("alpha").url,
                            width=64, height=64, steps=2)
        check("an explicit base override generates on that node",
              bool(r.get("path")) and os.path.exists(r["path"]), str(r.get("path")))

        # ------------------------------------------------------ failover
        from core import jobs

        jobs._JOBS.clear()
        job = jobs.submit("failover test", width=64, height=64, steps=2)
        check("submit accepts a backend pin field", "pinned_backend" in job)
        check("unpinned job records no backend yet", job["pinned_backend"] is None)

        jobs.start_worker(count=1)
        deadline = time.time() + 40
        rec = None
        while time.time() < deadline:
            rec = jobs.get(job["id"])
            if rec["status"] in ("done", "failed"):
                break
            time.sleep(0.25)

        check("a routed job completes", rec["status"] == "done",
              f"{rec['status']}: {rec.get('error')}")
        check("the completed job names the node that ran it",
              bool(rec.get("backend")), str(rec.get("backend")))
        check("the result records the backend",
              rec.get("result", {}).get("backend") == rec.get("backend"),
              str(rec.get("result", {}).get("backend")))
        check("the job records an attempt count", rec.get("attempts") == 1,
              str(rec.get("attempts")))

        # Pinned job goes where told.
        jobs._JOBS.clear()
        pinned = jobs.submit("pinned test", backend="beta",
                             width=64, height=64, steps=2)
        deadline = time.time() + 40
        while time.time() < deadline:
            rec2 = jobs.get(pinned["id"])
            if rec2["status"] in ("done", "failed"):
                break
            time.sleep(0.25)
        check("a pinned job runs on the named backend",
              rec2.get("backend") == "beta", str(rec2.get("backend")))
        check("a pinned job succeeds", rec2["status"] == "done",
              f"{rec2['status']}: {rec2.get('error')}")

        # Unknown pin fails clearly rather than silently rerouting.
        jobs._JOBS.clear()
        bad = jobs.submit("bad pin", backend="nonexistent",
                          width=64, height=64, steps=2)
        deadline = time.time() + 20
        while time.time() < deadline:
            rec3 = jobs.get(bad["id"])
            if rec3["status"] in ("done", "failed"):
                break
            time.sleep(0.25)
        check("an unknown backend pin fails with a clear message",
              rec3["status"] == "failed" and "not configured" in (rec3["error"] or ""),
              str(rec3.get("error"))[:60])

        # -------------------------------- orphan sweep must not eat live work
        # Regression: a job submitted *before* the worker pool starts is
        # already in jobs.json, so a naive "sweep everything queued" pass
        # would mark it failed. Only jobs inherited from a previous process
        # may be swept.
        jobs._JOBS.clear()
        jobs._SUBMITTED.clear()
        pending = jobs.submit("pre-start job", width=64, height=64, steps=2)
        check("a job submitted before the pool starts is not orphaned",
              pending["status"] == "queued")
        # Simulate a fresh process loading that file.
        jobs._SUBMITTED.discard(pending["id"])
        jobs.start_worker(count=1)
        rec4 = jobs.get(pending["id"])
        check("start_worker does not sweep jobs created in this process",
              rec4["status"] in ("queued", "running", "done"),
              f"status={rec4['status']}")

    finally:
        for p in procs:
            if p.poll() is None:
                try:
                    p.terminate()
                    p.wait(timeout=5)
                except Exception:
                    p.kill()

    passed = sum(1 for _, ok in results if ok)
    print(f"\n{passed}/{len(results)} checks passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
