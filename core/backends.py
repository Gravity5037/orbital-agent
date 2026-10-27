"""Backend registry and routing across the hive.

The mesh (core/mesh.py) connects nodes. This decides which node *does the
work*. Those are different problems, and this is the one that actually buys
you throughput.

Why this and not splitting one image across machines: intra-image
parallelism needs device-to-device activation transfer on every step. For
SDXL that is ~10 MB per step, which over a relayed Tailscale link costs
~17 s against a ~6 s local generation. It loses. The only intra-image split
that survives a network is CFG parallelism (one 0.13 MB latent all-gather per
step), and that requires running xDiT rather than ComfyUI.

Splitting a *batch* across machines needs no communication at all and scales
linearly. That is what this module does.

    ORBITAL_BACKENDS=desktop=http://100.64.0.5:8188,laptop=http://100.64.0.9:8188

Each entry is a ComfyUI instance. Jobs are routed to the least-loaded backend
that is actually capable of running them, with failover.
"""

import json
import socket
import time
import urllib.error
import urllib.parse
import urllib.request

from . import config, logutil

log = logutil.get_logger("backends")

# How long a probe result stays fresh. Probing on every job would add
# latency and hammer the backends.
STATUS_TTL = float(config.BACKEND_STATUS_TTL)

# After this many consecutive failures, stop routing to a backend for a while.
FAILURE_THRESHOLD = 3
COOLDOWN = 60.0

# Capability probes are heavier (three model-file lookups), so cache longer.
CAPABILITY_TTL = 300.0


class Backend:
    """One ComfyUI instance that can accept work."""

    __slots__ = (
        "name", "url", "weight",
        "_status", "_status_at",
        "_capability", "_capability_at",
        "_failures", "_down_until", "_jobs_done", "_total_seconds",
    )

    def __init__(self, name, url, weight=1.0):
        self.name = name
        self.url = url.rstrip("/")
        self.weight = float(weight)
        self._status = None
        self._status_at = 0.0
        self._capability = None
        self._capability_at = 0.0
        self._failures = 0
        self._down_until = 0.0
        self._jobs_done = 0
        self._total_seconds = 0.0

    # ------------------------------------------------------------ probing
    def _get(self, path, timeout=5):
        req = urllib.request.Request(self.url + path)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def probe(self, force=False):
        """Reachability and current load. Cached for STATUS_TTL."""
        now = time.time()
        if not force and self._status and (now - self._status_at) < STATUS_TTL:
            return self._status

        status = {"reachable": False, "running": 0, "pending": 0, "error": None}
        try:
            queue = self._get("/queue", timeout=4)
            status["reachable"] = True
            status["running"] = len(queue.get("queue_running") or [])
            status["pending"] = len(queue.get("queue_pending") or [])
        except urllib.error.URLError as exc:
            status["error"] = f"unreachable: {exc.reason}"
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            status["error"] = f"bad response: {exc}"
        except Exception as exc:
            status["error"] = f"{type(exc).__name__}: {exc}"

        status["load"] = status["running"] + status["pending"]
        status["name"] = self.name
        status["url"] = self.url
        status["checked_at"] = now

        self._status = status
        self._status_at = now
        return status

    def capability(self, force=False):
        """What this backend can generate: image and/or video. Cached longer."""
        now = time.time()
        if not force and self._capability and (now - self._capability_at) < CAPABILITY_TTL:
            return self._capability

        cap = {"image": False, "video": False, "checkpoints": [], "error": None}
        try:
            info = self._get("/object_info/CheckpointLoaderSimple", timeout=5)
            ckpts = info["CheckpointLoaderSimple"]["input"]["required"]["ckpt_name"][0]
            cap["checkpoints"] = list(ckpts)
            cap["image"] = bool(ckpts)
        except Exception as exc:
            cap["error"] = f"{type(exc).__name__}: {exc}"

        # Video needs three separate model files present.
        try:
            from . import video as video_mod

            ok, _detail = video_mod.health(timeout=4, base=self.url)
            cap["video"] = bool(ok)
        except Exception:
            cap["video"] = False

        self._capability = cap
        self._capability_at = now
        return cap

    # ------------------------------------------------------- circuit state
    def is_available(self):
        return time.time() >= self._down_until

    def record_success(self, seconds=0.0):
        self._failures = 0
        self._down_until = 0.0
        self._jobs_done += 1
        self._total_seconds += float(seconds or 0)

    def record_failure(self):
        self._failures += 1
        if self._failures >= FAILURE_THRESHOLD:
            self._down_until = time.time() + COOLDOWN
            log.warn(
                f"{self.name}: {self._failures} consecutive failures, "
                f"pausing for {COOLDOWN:.0f}s"
            )

    def stats(self):
        return {
            "name": self.name,
            "url": self.url,
            "weight": self.weight,
            "jobs_completed": self._jobs_done,
            "avg_seconds": round(self._total_seconds / self._jobs_done, 1)
            if self._jobs_done else None,
            "consecutive_failures": self._failures,
            "available": self.is_available(),
        }

    def __repr__(self):
        return f"<Backend {self.name} {self.url}>"


# ------------------------------------------------------------------ registry
_BACKENDS = None


def _derive_name(url):
    try:
        parsed = urllib.parse.urlparse(url)
        host = parsed.hostname or "backend"
        port = parsed.port
        return f"{host}:{port}" if port else host
    except Exception:
        return url


def registry(force_reload=False):
    """All configured backends. Always includes the local one last."""
    global _BACKENDS
    if _BACKENDS is not None and not force_reload:
        return _BACKENDS

    backends = []
    seen = set()

    for entry in config.backends():
        url = entry["url"]
        name = entry.get("name") or _derive_name(url)
        if name in seen:
            continue
        seen.add(name)
        backends.append(Backend(name, url, entry.get("weight", 1.0)))

    # The local instance is always a candidate, even if not listed.
    local_url = config.COMFY_BASE
    if not any(b.url.rstrip("/") == local_url.rstrip("/") for b in backends):
        backends.append(Backend("local", local_url, 1.0))

    _BACKENDS = backends
    if len(backends) > 1:
        log.info(
            "backend pool: " + ", ".join(f"{b.name} ({b.url})" for b in backends)
        )
    return backends


def get(name):
    for b in registry():
        if b.name == name:
            return b
    return None


QUALITY_TIERS = [
    (100, ("flux",)),
    (80, ("pony", "illustrious", "noobai", "hassaku", "realvis",
          "juggernaut", "dreamshaper")),
    (60, ("sdxl", "sd_xl")),
    (40, ("sd3", "stable-diffusion-3")),
    (20, ("v1-5", "sd15", "sd_15")),
    (10, ()),
]


def quality_of(backend):
    """Best model tier this backend has, from its installed checkpoints."""
    try:
        cap = backend.capability()
    except Exception:
        return 0, "unreachable"
    names = [str(c).lower() for c in cap.get("checkpoints", [])]
    if not names:
        return 0, "no checkpoints"
    best_score, best_label = 0, "unknown"
    for score, markers in QUALITY_TIERS:
        for n in names:
            if any(m in n for m in markers):
                if score > best_score:
                    best_score, best_label = score, n
        if best_score:
            break
    return best_score, best_label


def _score(backend, status):
    """Lower is better. Quality dominates; load only breaks ties."""
    quality, _label = quality_of(backend)
    load_penalty = status["load"] / max(backend.weight, 0.01)
    return -quality + (load_penalty * 0.01)


def choose(kind="image", exclude=()):
    """Pick the best backend for this job type. None if none can do it.

    Ordering: reachable, capable, not in cooldown, then least loaded.
    """
    candidates = []
    for b in registry():
        if b.name in exclude:
            continue
        if not b.is_available():
            continue

        status = b.probe()
        if not status["reachable"]:
            continue

        cap = b.capability()
        if not cap.get(kind):
            continue

        candidates.append((_score(b, status), b, status))

    if not candidates:
        return None

    candidates.sort(key=lambda item: (item[0], item[1].name))
    best_score, best, status = candidates[0]
    log.info(
        f"routing {kind} job to {best.name} "
        f"(load {status['load']}, {len(candidates)} candidate(s))"
    )
    return best


def candidates(kind="image"):
    """Every backend that could run this job type, best first."""
    out = []
    for b in registry():
        if not b.is_available():
            continue
        status = b.probe()
        if not status["reachable"]:
            continue
        if not b.capability().get(kind):
            continue
        out.append((_score(b, status), b))
    out.sort(key=lambda item: (item[0], item[1].name))
    return [b for _s, b in out]


def status_report(deep=False):
    """Everything the UI and /api/backends need."""
    report = []
    for b in registry():
        status = b.probe(force=deep)
        cap = b.capability(force=deep)
        entry = dict(b.stats())
        entry.update({
            "reachable": status["reachable"],
            "load": status.get("load", 0),
            "running": status.get("running", 0),
            "pending": status.get("pending", 0),
            "error": status.get("error"),
            "can_image": cap.get("image", False),
            "can_video": cap.get("video", False),
            "checkpoints": cap.get("checkpoints", [])[:8],
        })
        report.append(entry)
    return report


def totals():
    """Aggregate capacity, for the telemetry panel."""
    report = status_report()
    reachable = [r for r in report if r["reachable"]]
    return {
        "configured": len(report),
        "reachable": len(reachable),
        "total_load": sum(r["load"] for r in reachable),
        "image_capable": sum(1 for r in reachable if r["can_image"]),
        "video_capable": sum(1 for r in reachable if r["can_video"]),
        "jobs_completed": sum(r["jobs_completed"] for r in report),
    }
