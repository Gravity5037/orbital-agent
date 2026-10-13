"""Video generation tests.

Covers the Wan 2.2 graph construction, frame-count snapping, the three-file
model requirement, and that a real video file lands on disk. Generation speed
is not tested — the fake backend is instant, real video is minutes.
"""

import os
import shutil
import signal
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "/tmp/orbtest_video"
os.environ["ORBITAL_BASE"] = BASE
os.environ["ORBITAL_QUIET"] = "1"

sys.path.insert(0, ROOT)

from core import nebula, video  # noqa: E402

results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(f"{'PASS' if cond else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))


def start_fake(extra=None, port=8188):
    env = dict(os.environ)
    env["FAKE_COMFY_PORT"] = str(port)
    env.update(extra or {})
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

    # ------------------------------------------------- frame-count snapping
    check("frame counts snap to 4n+1", video.snap_frames(50) == 49, str(video.snap_frames(50)))
    check("exact 4n+1 values are preserved", video.snap_frames(81) == 81)
    check("tiny values are clamped to the minimum",
          video.snap_frames(1) == 5 and video.snap_frames(0) == 5,
          str(video.snap_frames(1)))
    ok = all((video.snap_frames(n) - 1) % 4 == 0 for n in range(1, 200))
    check("every snapped value satisfies 4n+1", ok)

    # ------------------------------------------------------ graph: t2v
    g, seed, frames = video.build_t2v_workflow(
        "a test clip", width=512, height=320, length=49, fps=16, steps=10, seed=7
    )
    check("t2v graph loads unet, clip and vae separately",
          all(k in g for k in ("1", "2", "3"))
          and g["1"]["class_type"] == "UNETLoader"
          and g["2"]["class_type"] == "CLIPLoader"
          and g["3"]["class_type"] == "VAELoader")
    check("t2v graph applies the shift via ModelSamplingSD3",
          g["4"]["class_type"] == "ModelSamplingSD3"
          and g["4"]["inputs"]["model"] == ["1", 0])
    check("t2v graph samples from the shifted model",
          g["8"]["inputs"]["model"] == ["4", 0])
    check("t2v graph wires positive and negative prompts",
          g["8"]["inputs"]["positive"] == ["5", 0]
          and g["8"]["inputs"]["negative"] == ["6", 0])
    check("t2v graph uses a video latent, not an image latent",
          g["7"]["class_type"] == "EmptyHunyuanLatentVideo")
    check("t2v resolution and length are applied",
          g["7"]["inputs"]["width"] == 512
          and g["7"]["inputs"]["height"] == 320
          and g["7"]["inputs"]["length"] == 49)
    check("t2v seed is honoured", seed == 7)
    check("t2v decodes with the Wan VAE",
          g["9"]["inputs"]["vae"] == ["3", 0])
    check("t2v output node is a video writer",
          g["10"]["class_type"] == "SaveWEBM")
    check("t2v passes fps to the encoder", g["10"]["inputs"]["fps"] == 16.0)

    # LoRA chain
    gl, _, _ = video.build_t2v_workflow(
        "p", loras=[{"name": "lightx2v.safetensors", "strength": 1.0}]
    )
    check("a video LoRA is inserted before the sampler",
          "lora_0" in gl
          and gl["4"]["inputs"]["model"] == ["lora_0", 0]
          and gl["lora_0"]["inputs"]["model"] == ["1", 0])
    check("video LoRAs use LoraLoaderModelOnly (no clip input)",
          gl["lora_0"]["class_type"] == "LoraLoaderModelOnly")

    # webp fallback
    gw, _, _ = video.build_t2v_workflow("p", format="webp")
    check("webp format selects SaveAnimatedWEBP",
          gw["10"]["class_type"] == "SaveAnimatedWEBP")

    # ------------------------------------------------------ graph: i2v
    gi, iseed, iframes = video.build_i2v_workflow(
        "input.png", "animate this", width=512, height=320, length=33, seed=9
    )
    check("i2v loads the source image",
          gi["7"]["class_type"] == "LoadImage"
          and gi["7"]["inputs"]["image"] == "input.png")
    check("i2v uses WanImageToVideo",
          gi["8"]["class_type"] == "WanImageToVideo")
    check("i2v passes the image as start_image",
          gi["8"]["inputs"]["start_image"] == ["7", 0])
    check("i2v samples from the WanImageToVideo latent",
          gi["9"]["inputs"]["latent_image"] == ["8", 2])
    check("i2v takes prompts from WanImageToVideo outputs",
          gi["9"]["inputs"]["positive"] == ["8", 0]
          and gi["9"]["inputs"]["negative"] == ["8", 1])
    check("i2v seed is honoured", iseed == 9)
    check("i2v length snaps to 4n+1", iframes == 33, str(iframes))

    # ---------------------------------------------- backend down
    ok_down, detail_down = video.health(timeout=2)
    check("video health reports down when nothing is listening",
          ok_down is False, str(detail_down)[:60])
    try:
        video.generate_video("x")
        check("generate_video raises when the backend is down", False, "no exception")
    except nebula.NebulaError:
        check("generate_video raises when the backend is down", True)

    # ---------------------------------------------- backend up
    fake = start_fake()
    try:
        if not wait_up():
            check("fake ComfyUI started", False)
            return 1
        check("fake ComfyUI started", True)

        ok, detail = video.health(timeout=3)
        check("video health is satisfied with all three files present",
              ok is True, str(detail)[:70])

        result = video.generate_video(
            "a test clip", width=256, height=256, length=17, fps=8, steps=2
        )
        check("video generation returns a result", isinstance(result, dict))
        check("the result reports frames", result.get("frames") == 17,
              str(result.get("frames")))
        check("the result reports a duration",
              result.get("duration") == round(17 / 8, 2), str(result.get("duration")))
        check("the result reports elapsed time", result.get("elapsed") is not None)
        check("the result reports a byte count", result.get("bytes", 0) > 0,
              f"{result.get('bytes')} bytes")

        path = result.get("path")
        check("a video file was written", bool(path) and os.path.exists(path), str(path))
        if path and os.path.exists(path):
            check("the video file is non-trivial", os.path.getsize(path) > 10,
                  f"{os.path.getsize(path)} bytes")
            check("the file has a video extension",
                  path.endswith(".webm"), os.path.basename(path))
        check("video output dir is under the base dir",
              video.OUTPUT_DIR.startswith(BASE), video.OUTPUT_DIR)

        # i2v end-to-end
        r2 = video.generate_video(
            "animate", mode="i2v", image_name="start.png",
            width=256, height=256, length=9, fps=8, steps=2,
        )
        check("i2v generation completes", bool(r2.get("path")), str(r2.get("path")))
        check("i2v result records the mode", r2.get("mode") == "i2v")

        try:
            video.generate_video("x", mode="i2v")
            check("i2v without an image is refused", False, "no exception")
        except video.VideoError as exc:
            check("i2v without an image is refused", True, str(exc)[:40])

        fake.terminate()
        fake.wait(timeout=5)
        time.sleep(0.4)

        # ---- missing video models
        nov = start_fake({"FAKE_COMFY_NO_VIDEO": "1"})
        try:
            if wait_up():
                ok3, detail3 = video.health(timeout=3)
                check("missing video models are reported",
                      ok3 is False and "no diffusion models" in str(detail3).lower(),
                      str(detail3)[:70])
                try:
                    video.generate_video("x")
                    check("generate_video refuses when models are missing", False,
                          "no exception")
                except nebula.NebulaError as exc:
                    check("generate_video refuses when models are missing", True,
                          str(exc)[:50])
            else:
                check("no-video fake started", False)
        finally:
            nov.terminate()
            nov.wait(timeout=5)

        # ---- backend error
        fail = start_fake({"FAKE_COMFY_FAIL": "1"})
        try:
            if wait_up():
                try:
                    video.generate_video("x", width=256, height=256, length=9, steps=1)
                    check("a video backend error surfaces", False, "no exception")
                except nebula.NebulaError as exc:
                    check("a video backend error surfaces", True,
                          f"{type(exc).__name__}: {str(exc)[:40]}")
            else:
                check("failing fake started", False)
        finally:
            fail.terminate()
            fail.wait(timeout=5)

    finally:
        if fake.poll() is None:
            try:
                fake.send_signal(signal.SIGTERM)
                fake.wait(timeout=5)
            except Exception:
                fake.kill()

    passed = sum(1 for _, ok_ in results if ok_)
    print(f"\n{passed}/{len(results)} checks passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
