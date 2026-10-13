"""Nebula — the image generation engine.

This is the module the old tree faked. `core/engine.py` used to answer
`/draw` with the string "Procedural matrix synthesis complete... Rendered into
local visual cache." No image, no model, no cache. This talks to a real
backend and returns real bytes.

Backend: ComfyUI (https://github.com/comfyanonymous/ComfyUI), which is the
standard local image server. It exposes:

    POST /prompt            submit a workflow graph, get a prompt_id
    GET  /history/<id>      poll for completion and output filenames
    GET  /view?...          fetch the actual image bytes
    GET  /object_info/...   introspect available nodes and model files

We build the workflow graph programmatically rather than asking you to export
one from the UI. A checkpoint-to-PNG graph is a handful of nodes and building
it in code means the resolution, steps, seed and prompt are all parameters.

Design notes:

  * HTTP polling, not WebSocket. The engine is thread-based, and polling
    /history is a few lines with no extra dependency. WebSocket previews are
    nicer for interactive UIs; this is a service call.
  * Generation is slow (seconds to minutes). `generate()` is blocking and
    callers are expected to run it off the request thread.
  * Every failure is explicit. No backend, no checkpoint, timeout, OOM — each
    raises with a message that says which.
"""

import json
import os
import random
import time
import urllib.error
import urllib.parse
import urllib.request

from . import config, logutil

log = logutil.get_logger("nebula")

COMFY_BASE = os.environ.get("ORBITAL_COMFY", "http://127.0.0.1:8188")
DEFAULT_CHECKPOINT = os.environ.get("ORBITAL_CHECKPOINT", "")
DEFAULT_WIDTH = int(os.environ.get("ORBITAL_IMAGE_WIDTH", "1024"))
DEFAULT_HEIGHT = int(os.environ.get("ORBITAL_IMAGE_HEIGHT", "1024"))
DEFAULT_STEPS = int(os.environ.get("ORBITAL_IMAGE_STEPS", "28"))
DEFAULT_CFG = float(os.environ.get("ORBITAL_IMAGE_CFG", "7.0"))
DEFAULT_SAMPLER = os.environ.get("ORBITAL_IMAGE_SAMPLER", "dpmpp_2m")
DEFAULT_SCHEDULER = os.environ.get("ORBITAL_IMAGE_SCHEDULER", "karras")
DEFAULT_NEGATIVE = os.environ.get(
    "ORBITAL_NEGATIVE",
    "lowres, bad anatomy, bad hands, extra digits, jpeg artifacts, "
    "watermark, signature, text, blurry, worst quality",
)
GENERATE_TIMEOUT = int(os.environ.get("ORBITAL_IMAGE_TIMEOUT", "600"))

# Directory for generated images. Served by the engine at /api/image/<name>.
OUTPUT_DIR = os.path.join(config.BASE_DIR, "images")


class NebulaError(RuntimeError):
    """Base class for image generation failures."""


class BackendDown(NebulaError):
    """ComfyUI is not reachable."""


class NoCheckpoint(NebulaError):
    """ComfyUI is running but has no usable checkpoint."""


class GenerationFailed(NebulaError):
    """The job was submitted but did not produce an image."""


# ------------------------------------------------------------------ HTTP
def _request(path, data=None, timeout=30, raw=False, base=None):
    url = (base or COMFY_BASE).rstrip("/") + path
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body)
    if body:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = resp.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise NebulaError(f"ComfyUI returned HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise BackendDown(f"ComfyUI unreachable at {COMFY_BASE}: {exc.reason}") from exc
    if raw:
        return payload
    try:
        return json.loads(payload.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise NebulaError(f"ComfyUI returned non-JSON from {path}") from exc


def health(timeout=3, base=None):
    """(reachable: bool, detail). detail is a checkpoint list or an error."""
    try:
        data = _request("/object_info/CheckpointLoaderSimple", timeout=timeout, base=base)
    except NebulaError as exc:
        return False, str(exc)

    try:
        ckpts = data["CheckpointLoaderSimple"]["input"]["required"]["ckpt_name"][0]
    except (KeyError, IndexError, TypeError):
        return True, []
    return True, list(ckpts)


def checkpoints(timeout=5, base=None):
    ok, detail = health(timeout=timeout, base=base)
    return detail if ok else []


def pick_checkpoint(preferred=None, base=None):
    """Resolve which checkpoint to use, or raise with the available list."""
    wanted = preferred or DEFAULT_CHECKPOINT
    available = checkpoints(base=base)

    if not available:
        raise NoCheckpoint(
            f"ComfyUI at {COMFY_BASE} has no checkpoints installed. "
            f"Put a .safetensors file in ComfyUI/models/checkpoints/"
        )
    if wanted and wanted in available:
        return wanted
    if wanted:
        # Tolerate a name given without the .safetensors suffix.
        for name in available:
            if name.startswith(wanted):
                return name
        log.warn(f"checkpoint '{wanted}' not found; falling back to '{available[0]}'")
    return available[0]


# -------------------------------------------------------------- workflow
def build_workflow(
    prompt,
    negative=None,
    checkpoint=None,
    width=DEFAULT_WIDTH,
    height=DEFAULT_HEIGHT,
    steps=DEFAULT_STEPS,
    cfg=DEFAULT_CFG,
    sampler=DEFAULT_SAMPLER,
    scheduler=DEFAULT_SCHEDULER,
    seed=None,
    batch_size=1,
    filename_prefix="orbital",
    loras=None,
):
    """Build a ComfyUI API-format graph: checkpoint -> sample -> decode -> save.

    `loras` is an optional list of {"name": ..., "strength": ...} dicts, each
    inserted as a LoraLoader between the checkpoint and the text encoders.
    """
    if seed is None:
        seed = random.randint(0, 2**32 - 1)

    graph = {
        "4": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": checkpoint},
        },
        "5": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": int(width), "height": int(height),
                       "batch_size": int(batch_size)},
        },
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "seed": int(seed),
                "steps": int(steps),
                "cfg": float(cfg),
                "sampler_name": sampler,
                "scheduler": scheduler,
                "denoise": 1.0,
                "model": ["4", 0],
                "positive": ["6", 0],
                "negative": ["7", 0],
                "latent_image": ["5", 0],
            },
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
        },
        "9": {
            "class_type": "SaveImage",
            "inputs": {"filename_prefix": filename_prefix, "images": ["8", 0]},
        },
    }

    # Chain LoRA loaders if requested.
    model_src = ["4", 0]
    clip_src = ["4", 1]
    for i, lora in enumerate(loras or []):
        node_id = f"lora_{i}"
        graph[node_id] = {
            "class_type": "LoraLoader",
            "inputs": {
                "lora_name": lora["name"],
                "strength_model": float(lora.get("strength", 1.0)),
                "strength_clip": float(lora.get("strength_clip", lora.get("strength", 1.0))),
                "model": model_src,
                "clip": clip_src,
            },
        }
        model_src = [node_id, 0]
        clip_src = [node_id, 1]

    graph["6"] = {
        "class_type": "CLIPTextEncode",
        "inputs": {"clip": clip_src, "text": prompt},
    }
    graph["7"] = {
        "class_type": "CLIPTextEncode",
        "inputs": {"clip": clip_src, "text": negative if negative is not None else DEFAULT_NEGATIVE},
    }
    graph["3"]["inputs"]["model"] = model_src

    return graph, seed


# ------------------------------------------------------------ generation
def submit(graph, base=None):
    """Queue a workflow. Returns the prompt_id."""
    result = _request("/prompt", {"prompt": graph}, timeout=30, base=base)
    if "prompt_id" not in result:
        raise GenerationFailed(f"ComfyUI did not return a prompt_id: {result}")
    return result["prompt_id"]


def _history(prompt_id, base=None):
    return _request(f"/history/{prompt_id}", timeout=15, base=base)


def wait_for(prompt_id, timeout=GENERATE_TIMEOUT, poll=0.6, base=None):
    """Poll /history until the job finishes. Returns its output record."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        hist = _history(prompt_id, base=base)
        if prompt_id in hist:
            entry = hist[prompt_id]
            status = entry.get("status", {})
            if status.get("status_str") == "error" or status.get("completed") is False:
                msgs = status.get("messages", [])
                raise GenerationFailed(f"ComfyUI reported an error: {msgs}")
            if entry.get("outputs"):
                return entry
        time.sleep(poll)
    raise GenerationFailed(
        f"generation did not finish within {timeout}s — the image may be too "
        f"large for your GPU, or the model may be offloading to CPU"
    )


def fetch_image(filename, subfolder="", folder_type="output", base=None):
    params = urllib.parse.urlencode(
        {"filename": filename, "subfolder": subfolder, "type": folder_type}
    )
    return _request(f"/view?{params}", timeout=60, raw=True, base=base)


def save_image(data, name=None):
    """Write image bytes to the output dir. Returns the path."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    if not name:
        name = f"{time.strftime('%Y%m%d-%H%M%S')}-{random.randint(1000, 9999)}.png"
    path = os.path.join(OUTPUT_DIR, name)
    tmp = path + ".tmp"
    with open(tmp, "wb") as fh:
        fh.write(data)
    os.replace(tmp, path)
    return path


def generate(
    prompt,
    negative=None,
    checkpoint=None,
    width=DEFAULT_WIDTH,
    height=DEFAULT_HEIGHT,
    steps=DEFAULT_STEPS,
    cfg=DEFAULT_CFG,
    sampler=DEFAULT_SAMPLER,
    scheduler=DEFAULT_SCHEDULER,
    seed=None,
    loras=None,
    save=True,
    timeout=GENERATE_TIMEOUT,
    base=None,
):
    """Generate one image. Blocking — call this off the request thread.

    Returns a dict: {"path", "seed", "prompt_id", "filename", "bytes"}.
    Raises BackendDown, NoCheckpoint, GenerationFailed, or NebulaError.

    `base` overrides the ComfyUI endpoint, which is how the router sends work
    to another machine in the hive.
    """
    ckpt = pick_checkpoint(checkpoint, base=base)

    graph, used_seed = build_workflow(
        prompt=prompt,
        negative=negative,
        checkpoint=ckpt,
        width=width,
        height=height,
        steps=steps,
        cfg=cfg,
        sampler=sampler,
        scheduler=scheduler,
        seed=seed,
        loras=loras,
    )

    log.info(f"queuing {width}x{height} {steps}step on '{ckpt}' seed={used_seed}")
    started = time.time()
    prompt_id = submit(graph, base=base)
    entry = wait_for(prompt_id, timeout=timeout, base=base)

    outputs = entry.get("outputs", {})
    images = []
    for node_id, node_out in outputs.items():
        for img in node_out.get("images", []) or []:
            images.append(img)

    if not images:
        raise GenerationFailed(
            f"job {prompt_id} completed but produced no images: {list(outputs)}"
        )

    first = images[0]
    data = fetch_image(
        first["filename"], first.get("subfolder", ""), first.get("type", "output"),
        base=base,
    )

    result = {
        "seed": used_seed,
        "prompt_id": prompt_id,
        "filename": first["filename"],
        "bytes": len(data),
        "elapsed": round(time.time() - started, 2),
        "checkpoint": ckpt,
        "count": len(images),
    }

    if save:
        result["path"] = save_image(data, f"{prompt_id[:8]}.png")
    else:
        result["data"] = data

    log.info(
        f"generated {result['filename']} in {result['elapsed']}s "
        f"({result['bytes']} bytes)"
    )
    return result
