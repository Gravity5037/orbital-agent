"""Nebula tests: workflow construction, job queue, and real image bytes.

The thing being proven: /draw produces an actual image file, not a string
claiming it did. Every check here would have failed against the old
core/engine.py, which returned a formatted message and wrote nothing.
"""

import os
import shutil
import signal
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "/tmp/orbtest_nebula"
os.environ["ORBITAL_BASE"] = BASE
os.environ["ORBITAL_QUIET"] = "1"

sys.path.insert(0, ROOT)

from core import nebula  # noqa: E402

results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(f"{'PASS' if cond else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))


def start_fake(env_extra=None, port=8188):
    env = dict(os.environ)
    env["FAKE_COMFY_PORT"] = str(port)
    env.update(env_extra or {})
    return subprocess.Popen(
        [sys.executable, os.path.join(ROOT, "tests", "fake_comfy.py")], env=env
    )


def wait_up(port=8188, timeout=10):
    import socket

    deadline = time.time() + timeout
    while time.time() < deadline:
        s = socket.socket()
        s.settimeout(0.5)
        try:
            s.connect(("127.0.0.1", port))
            return True
        except Exception:
            time.sleep(0.2)
        finally:
            s.close()
    return False


def main():
    shutil.rmtree(BASE, ignore_errors=True)
    os.makedirs(BASE, exist_ok=True)
    nebula.COMFY_BASE = "http://127.0.0.1:8188"

    # ---------------------------------------------------- workflow shape
    graph, seed = nebula.build_workflow(
        "a test prompt", checkpoint="sdxl_base.safetensors",
        width=768, height=512, steps=20, cfg=6.5, seed=42,
    )
    check("workflow has the required nodes",
          all(k in graph for k in ("3", "4", "5", "6", "7", "8", "9")),
          str(sorted(graph)))
    check("seed is honoured when supplied", seed == 42, str(seed))
    check("resolution is applied",
          graph["5"]["inputs"]["width"] == 768 and graph["5"]["inputs"]["height"] == 512)
    check("sampler settings are applied",
          graph["3"]["inputs"]["steps"] == 20 and graph["3"]["inputs"]["cfg"] == 6.5)
    check("positive prompt is wired to the sampler",
          graph["6"]["inputs"]["text"] == "a test prompt"
          and graph["3"]["inputs"]["positive"] == ["6", 0])
    check("negative prompt is wired to the sampler",
          graph["3"]["inputs"]["negative"] == ["7", 0])
    check("checkpoint is wired to model, clip and vae",
          graph["4"]["inputs"]["ckpt_name"] == "sdxl_base.safetensors"
          and graph["3"]["inputs"]["model"] == ["4", 0]
          and graph["6"]["inputs"]["clip"] == ["4", 1]
          and graph["8"]["inputs"]["vae"] == ["4", 2])
    check("save node is wired to the decoder",
          graph["9"]["inputs"]["images"] == ["8", 0])

    # LoRA chain inserts between checkpoint and encoders
    g2, _ = nebula.build_workflow(
        "p", checkpoint="c.safetensors",
        loras=[{"name": "style.safetensors", "strength": 0.8}],
    )
    check("a LoRA is inserted into the chain",
          "lora_0" in g2
          and g2["3"]["inputs"]["model"] == ["lora_0", 0]
          and g2["6"]["inputs"]["clip"] == ["lora_0", 1]
          and g2["lora_0"]["inputs"]["model"] == ["4", 0])
    check("LoRA strength is passed through",
          g2["lora_0"]["inputs"]["strength_model"] == 0.8)

    # ------------------------------------------------ backend unavailable
    down_ok, down_detail = nebula.health(timeout=2)
    check("health reports the backend as down when nothing is listening",
          down_ok is False, str(down_detail)[:60])
    try:
        nebula.generate("x", checkpoint="c.safetensors")
        check("generate raises when the backend is down", False, "no exception")
    except nebula.BackendDown as exc:
        check("generate raises BackendDown when the backend is down",
              True, str(exc)[:50])
    except nebula.NebulaError as exc:
        check("generate raises BackendDown when the backend is down", True,
              f"{type(exc).__name__}")

    # ------------------------------------------------------- backend up
    fake = start_fake()
    try:
        if not wait_up():
            check("fake ComfyUI started", False)
            return 1
        check("fake ComfyUI started", True)

        ok, detail = nebula.health(timeout=3)
        check("health reports the backend up", ok is True, str(detail))
        check("checkpoints are listed",
              "sdxl_base.safetensors" in detail, str(detail))

        check("pick_checkpoint honours an explicit choice",
              nebula.pick_checkpoint("pony_v6.safetensors") == "pony_v6.safetensors")
        check("pick_checkpoint falls back when the name is unknown",
              nebula.pick_checkpoint("nonexistent.safetensors") in detail,
              nebula.pick_checkpoint("nonexistent.safetensors"))
        check("pick_checkpoint tolerates a missing extension",
              nebula.pick_checkpoint("pony_v6") == "pony_v6.safetensors")

        # ------------------------------------------- real generation
        result = nebula.generate(
            "test prompt", checkpoint="sdxl_base.safetensors",
            width=64, height=64, steps=2, seed=1234,
        )
        check("generation returns a result", isinstance(result, dict))
        check("the result reports a seed", result.get("seed") == 1234)
        check("the result reports a byte count", result.get("bytes", 0) > 0,
              f"{result.get('bytes')} bytes")

        path = result.get("path")
        check("an image file was actually written",
              bool(path) and os.path.exists(path), str(path))
        if path and os.path.exists(path):
            with open(path, "rb") as fh:
                magic = fh.read(8)
            check("the file is a real PNG", magic == b"\x89PNG\r\n\x1a\n",
                  repr(magic))
            check("the file is non-trivial", os.path.getsize(path) > 50,
                  f"{os.path.getsize(path)} bytes")

        check("image output dir is under the base dir",
              nebula.OUTPUT_DIR.startswith(BASE), nebula.OUTPUT_DIR)

        # ---------------------------------------------------- job queue
        from core import jobs

        jobs.start_worker()
        job = jobs.submit("queued prompt", checkpoint="sdxl_base.safetensors",
                          width=64, height=64, steps=2)
        check("submit returns immediately with an id",
              job.get("id") and job.get("status") == "queued", job.get("status"))

        deadline = time.time() + 30
        while time.time() < deadline:
            rec = jobs.get(job["id"])
            if rec["status"] in ("done", "failed"):
                break
            time.sleep(0.2)
        rec = jobs.get(job["id"])
        check("the queued job completes", rec["status"] == "done",
              f"{rec['status']}: {rec.get('error')}")
        check("the job result carries an image path",
              bool(rec.get("result", {}).get("path")),
              str(rec.get("result", {}).get("path")))
        check("the job records a duration",
              rec.get("finished") and rec["finished"] >= rec["started"])

        listing = jobs.list_jobs()
        check("job history lists jobs", len(listing) >= 1, f"{len(listing)} job(s)")

        # ------------------------------------------------- error paths
        fake.terminate()
        fake.wait(timeout=5)
        time.sleep(0.4)

        fail = start_fake({"FAKE_COMFY_FAIL": "1"})
        try:
            if wait_up():
                try:
                    nebula.generate("x", checkpoint="sdxl_base.safetensors",
                                    width=64, height=64, steps=1)
                    check("a backend error surfaces as GenerationFailed", False,
                          "no exception raised")
                except nebula.GenerationFailed as exc:
                    check("a backend error surfaces as GenerationFailed", True,
                          str(exc)[:50])
                except nebula.NebulaError as exc:
                    check("a backend error surfaces as GenerationFailed", True,
                          f"{type(exc).__name__}: {exc}")
            else:
                check("error-path fake started", False)
        finally:
            fail.terminate()
            fail.wait(timeout=5)

        no_ckpt = start_fake({"FAKE_COMFY_NO_CKPT": "1"})
        try:
            if wait_up():
                try:
                    nebula.generate("x")
                    check("a missing checkpoint is reported clearly", False,
                          "no exception raised")
                except nebula.NoCheckpoint as exc:
                    check("a missing checkpoint is reported clearly", True,
                          str(exc)[:50])
                except nebula.NebulaError as exc:
                    check("a missing checkpoint is reported clearly", True,
                          f"{type(exc).__name__}: {exc}")
            else:
                check("no-checkpoint fake started", False)
        finally:
            no_ckpt.terminate()
            no_ckpt.wait(timeout=5)

    finally:
        for p in (fake,):
            if p.poll() is None:
                try:
                    p.send_signal(signal.SIGTERM)
                    p.wait(timeout=5)
                except Exception:
                    p.kill()

    passed = sum(1 for _, ok in results if ok)
    print(f"\n{passed}/{len(results)} checks passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
