"""Generation job queue, routed across the hive.

Diffusion generation takes seconds (images) to minutes (video). Blocking an
HTTP handler on it would make the whole engine unresponsive, and the old
design had no notion of a job at all — `/draw` returned instantly with a lie.

So: submit returns a job id immediately, workers do the generation, and the
client polls. Jobs are mirrored to disk so a restart doesn't lose the record.

Two things this does beyond a plain queue:

  * **Routing.** Each job is sent to the least-loaded ComfyUI instance that
    can run it. With several machines this is linear throughput scaling with
    no communication overhead — see core/backends.py for why that beats
    splitting a single image.
  * **Failover.** If the chosen backend fails, the job is retried on the next
    best one rather than being lost.

Worker count is configurable. Unlike a single machine, where more workers
just contend for one GPU, extra workers here let several backends run in
parallel.
"""

import json
import os
import queue
import threading
import time
import uuid

from . import config, logutil, nebula

log = logutil.get_logger("jobs")

HISTORY_LIMIT = 500
JOBS_FILE = os.path.join(config.STATE_DIR, "jobs.json")
WORKER_COUNT = int(os.environ.get("ORBITAL_WORKERS", "4"))
MAX_ATTEMPTS = int(os.environ.get("ORBITAL_JOB_ATTEMPTS", "3"))

_QUEUE = queue.Queue()
_JOBS = {}
_LOCK = threading.Lock()
_WORKERS = []

# Ids created by submit() in *this* process. Anything else found in the
# persisted file belongs to a previous run, and a job from a previous run
# that still says "queued" or "running" is orphaned.
_SUBMITTED = set()


def _load():
    """Load job history from disk. Returns the ids that came from disk.

    Those ids matter: a job loaded from disk that still says "running" or
    "queued" belongs to a process that is gone. A job submitted in *this*
    process with status "queued" is legitimately waiting its turn and must
    not be swept.
    """
    if not os.path.exists(JOBS_FILE):
        return set()
    try:
        with open(JOBS_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            _JOBS.update(data)
            return set(data)
    except (OSError, json.JSONDecodeError) as exc:
        log.warn(f"could not read job history: {exc}")
    return set()


def _persist():
    config.ensure_dirs()
    tmp = JOBS_FILE + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(_JOBS, fh, indent=2)
        os.replace(tmp, JOBS_FILE)
    except OSError as exc:
        log.warn(f"could not persist job history: {exc}")


def _trim():
    if len(_JOBS) <= HISTORY_LIMIT:
        return
    ordered = sorted(_JOBS.items(), key=lambda kv: kv[1].get("created", 0))
    for job_id, _rec in ordered[: len(_JOBS) - HISTORY_LIMIT]:
        _JOBS.pop(job_id, None)


def submitted_here():
    """Job ids this process created. Used to distinguish orphans from work."""
    return set(_SUBMITTED)


def submit(prompt, kind="image", backend=None, **params):
    """Queue a generation. Returns the job record immediately.

    kind is "image" or "video". backend pins the job to one node by name;
    otherwise the router picks.
    """
    job_id = uuid.uuid4().hex
    record = {
        "id": job_id,
        "kind": kind,
        "status": "queued",
        "prompt": prompt,
        "params": {k: v for k, v in params.items() if k != "data"},
        "pinned_backend": backend,
        "backend": None,
        "attempts": 0,
        "created": time.time(),
        "started": None,
        "finished": None,
        "result": None,
        "error": None,
    }
    with _LOCK:
        _JOBS[job_id] = record
        _SUBMITTED.add(job_id)
        _trim()
        _persist()
    _QUEUE.put(job_id)
    return record


def get(job_id):
    with _LOCK:
        rec = _JOBS.get(job_id)
        return dict(rec) if rec else None


def list_jobs(limit=50):
    with _LOCK:
        recs = sorted(_JOBS.values(), key=lambda r: r.get("created", 0), reverse=True)
        return [dict(r) for r in recs[:limit]]


def _pick_backend(kind, exclude):
    """Route to the best node, or None if nothing can take it."""
    from . import backends as backends_mod

    chosen = backends_mod.choose(kind=kind, exclude=exclude)
    if chosen:
        return chosen
    return None


def _run_one(job_id):
    with _LOCK:
        rec = _JOBS.get(job_id)
        if not rec:
            return
        rec["status"] = "running"
        rec["started"] = time.time()
        prompt = rec["prompt"]
        params = dict(rec["params"])
        kind = rec.get("kind", "image")
        pinned = rec.get("pinned_backend")
        _persist()

    tried = []
    last_error = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        if pinned:
            from . import backends as backends_mod

            target = backends_mod.get(pinned)
            if target is None:
                last_error = f"pinned backend '{pinned}' is not configured"
                break
        else:
            target = _pick_backend(kind, exclude=set(tried))

        if target is None:
            last_error = (
                f"no reachable backend can run a {kind} job"
                + (f" (tried: {', '.join(tried)})" if tried else "")
            )
            break

        with _LOCK:
            rec = _JOBS[job_id]
            rec["backend"] = target.name
            rec["attempts"] = attempt
            _persist()

        log.info(f"job {job_id[:8]} ({kind}) attempt {attempt} on {target.name}")
        started = time.time()
        try:
            if kind == "video":
                from . import video as video_mod

                result = video_mod.generate_video(prompt, base=target.url, **params)
            else:
                result = nebula.generate(prompt, base=target.url, **params)

            result.pop("data", None)
            result["backend"] = target.name
            elapsed = time.time() - started
            target.record_success(elapsed)

            with _LOCK:
                rec = _JOBS[job_id]
                rec["status"] = "done"
                rec["result"] = result
                rec["finished"] = time.time()
                _persist()
            log.info(f"job {job_id[:8]} ({kind}) done on {target.name}: {result.get('path')}")
            return

        except nebula.NebulaError as exc:
            last_error = str(exc)
            target.record_failure()
            tried.append(target.name)
            log.warn(
                f"job {job_id[:8]} failed on {target.name} "
                f"(attempt {attempt}/{MAX_ATTEMPTS}): {exc}"
            )

        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            target.record_failure()
            tried.append(target.name)
            log.exception(f"job {job_id[:8]} crashed on {target.name}")

    with _LOCK:
        rec = _JOBS[job_id]
        rec["status"] = "failed"
        rec["error"] = last_error
        rec["finished"] = time.time()
        _persist()
    log.error(f"job {job_id[:8]} ({kind}) failed after {len(tried)} attempt(s): {last_error}")


def _worker_loop(index):
    log.info(f"worker {index} started")
    while True:
        job_id = _QUEUE.get()
        try:
            if job_id is None:
                break
            _run_one(job_id)
        except Exception as exc:
            log.error(f"worker {index} error: {exc}")
        finally:
            _QUEUE.task_done()
    log.info(f"worker {index} stopped")


def start_worker(count=None):
    """Start the worker pool. Idempotent.

    With one backend, extra workers just contend for the same GPU, so the
    default scales with the number of configured backends.
    """
    global _WORKERS
    alive = [w for w in _WORKERS if w.is_alive()]
    if alive:
        return _WORKERS

    with _LOCK:
        orphaned = set(_load()) - _SUBMITTED
        swept = 0
        for job_id in orphaned:
            rec = _JOBS.get(job_id)
            if rec and rec.get("status") in ("running", "queued"):
                rec["status"] = "failed"
                rec["error"] = "interrupted by a restart"
                rec["finished"] = time.time()
                swept += 1
        if swept:
            log.info(f"marked {swept} orphaned job(s) from a previous run as failed")
        _persist()

    if count is None:
        try:
            from . import backends as backends_mod

            n_backends = max(1, len(backends_mod.registry()))
        except Exception:
            n_backends = 1
        count = max(1, min(WORKER_COUNT, n_backends))

    _WORKERS = [
        threading.Thread(target=_worker_loop, args=(i,),
                         name=f"gen-worker-{i}", daemon=True)
        for i in range(count)
    ]
    for w in _WORKERS:
        w.start()
    log.info(f"started {count} generation worker(s)")
    return _WORKERS


def stop_worker():
    for _ in _WORKERS:
        _QUEUE.put(None)
