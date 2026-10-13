"""Video generation — Wan 2.2 via ComfyUI.

Same backend as Nebula (ComfyUI), different graph and a much bigger cost.
Text-to-video and image-to-video, using Wan 2.2's models:

    TI2V-5B      one dense 5B model, does both t2v and i2v at 720p/24fps.
                 ~10 GB FP16, ~5.4 GB GGUF Q8, ~3.4 GB Q4_K_M.
                 Runs on an 8 GB card with ComfyUI's native offloading.
    T2V-A14B     mixture-of-experts, two ~14B files. ~28.6 GB FP16 per
                 expert, ~14.3 GB FP8, ~9.7 GB Q4_K_M. Only one expert is on
                 the GPU at a time; both need space in system RAM.

Node layout differs from image generation. Wan models are loaded piecemeal
(UNETLoader + CLIPLoader + VAELoader) rather than through a single
CheckpointLoaderSimple, because the 5B and 14B checkpoints do not bundle the
text encoder or VAE.

Cost warning, stated plainly because it surprises people: a 5-second 720p
clip is roughly 9 minutes on an RTX 4090 with the 5B model. Going from 480p to
720p roughly triples it. This is not an interactive operation, which is why it
goes through the same job queue as images.
"""

import os
import random
import time

from . import config, logutil, nebula

log = logutil.get_logger("video")

# --- default model files. Set these to match what you actually downloaded. ---
DEFAULT_UNET = os.environ.get("ORBITAL_VIDEO_UNET", "wan2.2_ti2v_5B_fp16.safetensors")
DEFAULT_CLIP = os.environ.get(
    "ORBITAL_VIDEO_CLIP", "umt5_xxl_fp8_e4m3fn_scaled.safetensors"
)
DEFAULT_VAE = os.environ.get("ORBITAL_VIDEO_VAE", "wan2.2_vae.safetensors")

# --- generation defaults, sized for the 5B model -------------------------
DEFAULT_WIDTH = int(os.environ.get("ORBITAL_VIDEO_WIDTH", "704"))
DEFAULT_HEIGHT = int(os.environ.get("ORBITAL_VIDEO_HEIGHT", "480"))
DEFAULT_LENGTH = int(os.environ.get("ORBITAL_VIDEO_LENGTH", "49"))  # frames
DEFAULT_FPS = int(os.environ.get("ORBITAL_VIDEO_FPS", "16"))
DEFAULT_STEPS = int(os.environ.get("ORBITAL_VIDEO_STEPS", "30"))
DEFAULT_CFG = float(os.environ.get("ORBITAL_VIDEO_CFG", "5.0"))
DEFAULT_SHIFT = float(os.environ.get("ORBITAL_VIDEO_SHIFT", "8.0"))
DEFAULT_SAMPLER = os.environ.get("ORBITAL_VIDEO_SAMPLER", "uni_pc")
DEFAULT_SCHEDULER = os.environ.get("ORBITAL_VIDEO_SCHEDULER", "simple")
DEFAULT_NEGATIVE = os.environ.get(
    "ORBITAL_VIDEO_NEGATIVE",
    "lowres, bad anatomy, bad hands, extra digits, watermark, text, "
    "blurry, jittery, distorted, static frame",
)
VIDEO_TIMEOUT = int(os.environ.get("ORBITAL_VIDEO_TIMEOUT", "3600"))

OUTPUT_DIR = os.path.join(config.BASE_DIR, "videos")

# Wan 2.2 wants frame counts of the form 4n+1.
def snap_frames(n):
    """Round a frame count to the nearest 4n+1 that Wan accepts."""
    n = max(5, int(n))
    return ((n - 1) // 4) * 4 + 1


class VideoError(nebula.NebulaError):
    """Video generation failure."""


def health(timeout=3, base=None):
    """Is the video stack present? Returns (ok, detail).

    Unlike the image check, this needs three separate model files, so it
    reports which are missing rather than just up/down. `base` overrides the
    ComfyUI endpoint, for probing another node in the hive.
    """
    try:
        info = nebula._request("/object_info/UNETLoader", timeout=timeout, base=base)
    except nebula.NebulaError as exc:
        return False, str(exc)

    def options(node, field):
        try:
            return list(info[node]["input"]["required"][field][0])
        except (KeyError, IndexError, TypeError):
            return []

    unets = options("UNETLoader", "unet_name")
    if not unets:
        return False, "no diffusion models in ComfyUI/models/diffusion_models/"

    clips, vaes = [], []
    try:
        clip_info = nebula._request("/object_info/CLIPLoader", timeout=timeout, base=base)
        clips = list(clip_info["CLIPLoader"]["input"]["required"]["clip_name"][0])
    except (nebula.NebulaError, KeyError, IndexError, TypeError):
        pass
    try:
        vae_info = nebula._request("/object_info/VAELoader", timeout=timeout, base=base)
        vaes = list(vae_info["VAELoader"]["input"]["required"]["vae_name"][0])
    except (nebula.NebulaError, KeyError, IndexError, TypeError):
        pass

    missing = []
    if DEFAULT_UNET not in unets:
        missing.append(f"diffusion model '{DEFAULT_UNET}'")
    if DEFAULT_CLIP not in clips:
        missing.append(f"text encoder '{DEFAULT_CLIP}'")
    if DEFAULT_VAE not in vaes:
        missing.append(f"VAE '{DEFAULT_VAE}'")

    if missing:
        return False, "missing: " + ", ".join(missing)
    return True, {"unets": unets, "clips": clips, "vaes": vaes}


def build_t2v_workflow(
    prompt,
    negative=None,
    unet=DEFAULT_UNET,
    clip=DEFAULT_CLIP,
    vae=DEFAULT_VAE,
    width=DEFAULT_WIDTH,
    height=DEFAULT_HEIGHT,
    length=DEFAULT_LENGTH,
    fps=DEFAULT_FPS,
    steps=DEFAULT_STEPS,
    cfg=DEFAULT_CFG,
    shift=DEFAULT_SHIFT,
    sampler=DEFAULT_SAMPLER,
    scheduler=DEFAULT_SCHEDULER,
    seed=None,
    filename_prefix="orbital_vid",
    loras=None,
    format="webm",
):
    """Build a Wan 2.2 text-to-video graph in ComfyUI API format."""
    if seed is None:
        seed = random.randint(0, 2**32 - 1)
    length = snap_frames(length)

    graph = {
        "1": {"class_type": "UNETLoader",
              "inputs": {"unet_name": unet, "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader",
              "inputs": {"clip_name": clip, "type": "wan"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": vae}},
        "4": {"class_type": "ModelSamplingSD3",
              "inputs": {"model": ["1", 0], "shift": float(shift)}},
        "5": {"class_type": "CLIPTextEncode",
              "inputs": {"clip": ["2", 0], "text": prompt}},
        "6": {"class_type": "CLIPTextEncode",
              "inputs": {"clip": ["2", 0],
                         "text": negative if negative is not None else DEFAULT_NEGATIVE}},
        "7": {"class_type": "EmptyHunyuanLatentVideo",
              "inputs": {"width": int(width), "height": int(height),
                         "length": length, "batch_size": 1}},
        "8": {"class_type": "KSampler",
              "inputs": {"seed": int(seed), "steps": int(steps), "cfg": float(cfg),
                         "sampler_name": sampler, "scheduler": scheduler,
                         "denoise": 1.0, "model": ["4", 0],
                         "positive": ["5", 0], "negative": ["6", 0],
                         "latent_image": ["7", 0]}},
        "9": {"class_type": "VAEDecode",
              "inputs": {"samples": ["8", 0], "vae": ["3", 0]}},
    }

    # Optional LoRA chain, inserted before ModelSamplingSD3.
    model_src = ["1", 0]
    for i, lora in enumerate(loras or []):
        node_id = f"lora_{i}"
        graph[node_id] = {
            "class_type": "LoraLoaderModelOnly",
            "inputs": {
                "lora_name": lora["name"],
                "strength_model": float(lora.get("strength", 1.0)),
                "model": model_src,
            },
        }
        model_src = [node_id, 0]
    if loras:
        graph["4"]["inputs"]["model"] = model_src

    if format == "webm":
        graph["10"] = {"class_type": "SaveWEBM",
                       "inputs": {"images": ["9", 0], "filename_prefix": filename_prefix,
                                  "codec": "vp9", "fps": float(fps), "crf": 20.0}}
    else:
        # SaveAnimatedWEBP is universally available; VHS_VideoCombine is not.
        graph["10"] = {"class_type": "SaveAnimatedWEBP",
                       "inputs": {"images": ["9", 0], "filename_prefix": filename_prefix,
                                  "fps": float(fps), "lossless": False,
                                  "quality": 85, "method": "default"}}

    return graph, seed, length


def build_i2v_workflow(
    image_name,
    prompt,
    negative=None,
    unet=DEFAULT_UNET,
    clip=DEFAULT_CLIP,
    vae=DEFAULT_VAE,
    width=DEFAULT_WIDTH,
    height=DEFAULT_HEIGHT,
    length=DEFAULT_LENGTH,
    fps=DEFAULT_FPS,
    steps=DEFAULT_STEPS,
    cfg=DEFAULT_CFG,
    shift=DEFAULT_SHIFT,
    sampler=DEFAULT_SAMPLER,
    scheduler=DEFAULT_SCHEDULER,
    seed=None,
    filename_prefix="orbital_i2v",
    format="webm",
    loras=None,
):
    """Image-to-video: animate an existing image already in ComfyUI's input dir."""
    if seed is None:
        seed = random.randint(0, 2**32 - 1)
    length = snap_frames(length)

    graph = {
        "1": {"class_type": "UNETLoader",
              "inputs": {"unet_name": unet, "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader",
              "inputs": {"clip_name": clip, "type": "wan"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": vae}},
        "4": {"class_type": "ModelSamplingSD3",
              "inputs": {"model": ["1", 0], "shift": float(shift)}},
        "5": {"class_type": "CLIPTextEncode",
              "inputs": {"clip": ["2", 0], "text": prompt}},
        "6": {"class_type": "CLIPTextEncode",
              "inputs": {"clip": ["2", 0],
                         "text": negative if negative is not None else DEFAULT_NEGATIVE}},
        "7": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "8": {"class_type": "WanImageToVideo",
              "inputs": {"positive": ["5", 0], "negative": ["6", 0],
                         "vae": ["3", 0], "width": int(width), "height": int(height),
                         "length": length, "batch_size": 1,
                         "start_image": ["7", 0]}},
        "9": {"class_type": "KSampler",
              "inputs": {"seed": int(seed), "steps": int(steps), "cfg": float(cfg),
                         "sampler_name": sampler, "scheduler": scheduler,
                         "denoise": 1.0, "model": ["4", 0],
                         "positive": ["8", 0], "negative": ["8", 1],
                         "latent_image": ["8", 2]}},
        "10": {"class_type": "VAEDecode",
               "inputs": {"samples": ["9", 0], "vae": ["3", 0]}},
        "11": {"class_type": "SaveWEBM",
               "inputs": {"images": ["10", 0], "filename_prefix": filename_prefix,
                          "codec": "vp9", "fps": float(fps), "crf": 20.0}},
    }

    # Optional LoRA chain, inserted before ModelSamplingSD3.
    model_src = ["1", 0]
    for i, lora in enumerate(loras or []):
        node_id = f"lora_{i}"
        graph[node_id] = {
            "class_type": "LoraLoaderModelOnly",
            "inputs": {
                "lora_name": lora["name"],
                "strength_model": float(lora.get("strength", 1.0)),
                "model": model_src,
            },
        }
        model_src = [node_id, 0]
    if loras:
        graph["4"]["inputs"]["model"] = model_src

    return graph, seed, length


def generate_video(
    prompt,
    mode="t2v",
    image_name=None,
    negative=None,
    width=DEFAULT_WIDTH,
    height=DEFAULT_HEIGHT,
    length=DEFAULT_LENGTH,
    fps=DEFAULT_FPS,
    steps=DEFAULT_STEPS,
    cfg=DEFAULT_CFG,
    seed=None,
    loras=None,
    unet=None,
    clip=None,
    vae=None,
    format="webm",
    timeout=VIDEO_TIMEOUT,
    base=None,
):
    """Generate a video. Blocking, and slow — expect minutes.

    Returns a dict with path, seed, frames, fps, duration, elapsed.
    `base` overrides the ComfyUI endpoint, for hive routing.
    """
    ok, detail = health(base=base)
    if not ok:
        raise nebula.NoCheckpoint(f"video stack incomplete — {detail}")

    kwargs = dict(
        negative=negative,
        unet=unet or DEFAULT_UNET,
        clip=clip or DEFAULT_CLIP,
        vae=vae or DEFAULT_VAE,
        width=width, height=height, length=length, fps=fps,
        steps=steps, cfg=cfg, seed=seed, loras=loras, format=format,
    )

    if mode == "i2v":
        if not image_name:
            raise VideoError("i2v requires image_name")
        graph, used_seed, frames = build_i2v_workflow(image_name, prompt, **kwargs)
    else:
        graph, used_seed, frames = build_t2v_workflow(prompt, **kwargs)

    duration = frames / float(fps) if fps else 0
    log.info(
        f"queuing {mode} {width}x{height} {frames}f @{fps}fps "
        f"(~{duration:.1f}s of video) seed={used_seed}"
    )

    started = time.time()
    prompt_id = nebula.submit(graph, base=base)
    entry = nebula.wait_for(prompt_id, timeout=timeout, base=base)

    # Video output nodes report under 'images' too, but the filename differs.
    files = []
    for _node_id, node_out in (entry.get("outputs") or {}).items():
        for key in ("images", "gifs", "videos"):
            for item in node_out.get(key, []) or []:
                files.append(item)

    if not files:
        raise VideoError(
            f"job {prompt_id} finished but produced no video output: "
            f"{list(entry.get('outputs') or {})}"
        )

    first = files[0]
    data = nebula.fetch_image(
        first["filename"], first.get("subfolder", ""), first.get("type", "output"),
        base=base,
    )

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ext = os.path.splitext(first["filename"])[1] or ".webm"
    path = os.path.join(OUTPUT_DIR, f"{prompt_id[:8]}{ext}")
    tmp = path + ".tmp"
    with open(tmp, "wb") as fh:
        fh.write(data)
    os.replace(tmp, path)

    result = {
        "path": path,
        "seed": used_seed,
        "prompt_id": prompt_id,
        "filename": first["filename"],
        "frames": frames,
        "fps": fps,
        "duration": round(duration, 2),
        "bytes": len(data),
        "elapsed": round(time.time() - started, 2),
        "mode": mode,
    }
    log.info(
        f"generated {first['filename']} — {duration:.1f}s of video in "
        f"{result['elapsed']}s ({result['bytes']} bytes)"
    )
    return result


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) > 1:
        p = " ".join(sys.argv[1:])
        print(json.dumps(generate_video(p), indent=2))
    else:
        print(json.dumps(health(), indent=2))
