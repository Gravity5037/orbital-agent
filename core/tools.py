"""Tools — what Orbital can actually do, exposed to the model.

The problem this solves: without it, the model answers "I can't see your
camera" or "I'm unable to generate images" — both false. Orbital has those
capabilities; the model just doesn't know it's part of a system that does.

Two mechanisms, used together:

  **Native tool calling.** Ollama supports it for most models. We declare
  each tool with a JSON schema, the model decides when to call one, we
  execute it and feed the result back. This is the correct mechanism and it
  works well on qwen2.5 and llama3.x.

  **A capability preamble.** Some models don't support tools at all (your
  dolphin-llama3 is one), and even good ones sometimes refuse out of habit
  rather than ignorance. So the system prompt also states plainly what
  Orbital can do. Belt and braces: the preamble stops false refusals, the
  tool loop actually does the work.

Tools are deliberately narrow. Each one does a single thing, returns a
compact result, and fails with a message the model can act on rather than a
stack trace it can't.
"""

import json
import os
import time

from . import config, logutil

log = logutil.get_logger("tools")

MAX_TOOL_ROUNDS = 4          # how many call/respond cycles before giving up
TOOL_TIMEOUT = 180


class ToolError(RuntimeError):
    """A tool failed. The message is written for the model to read."""


# ---------------------------------------------------------------- schemas
# Ollama expects OpenAI-shaped function definitions.
def _fn(name, description, properties=None, required=None):
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties or {},
                "required": required or [],
            },
        },
    }


SCHEMAS = [
    _fn("get_time",
        "Get the current date and time on this machine. Use this instead of "
        "saying you cannot access real-time information."),
    _fn("get_system_info",
        "Get this machine's hardware and software details: CPU, RAM, GPU and "
        "VRAM, disk space, Python version, node name. Use this when asked "
        "about the system, the computer, or what hardware Orbital is running on.",
        {"detail": {"type": "string",
                    "enum": ["summary", "full"],
                    "description": "how much detail to return"}}),
    _fn("list_files",
        "List files in a directory on this machine. Use this when asked about "
        "files, folders, or what is installed.",
        {"path": {"type": "string",
                  "description": "absolute path, or a name under the Orbital directory"}},
        ["path"]),
    _fn("read_file",
        "Read the contents of a text file on this machine.",
        {"path": {"type": "string", "description": "absolute path to the file"},
         "max_lines": {"type": "integer",
                       "description": "maximum lines to return, default 200"}},
        ["path"]),
    _fn("generate_image",
        "Generate an image from a text description. Use this whenever the user "
        "asks for a picture, drawing, illustration or image to be created.",
        {"prompt": {"type": "string",
                    "description": "what the image should show"},
         "width": {"type": "integer"},
         "height": {"type": "integer"}},
        ["prompt"]),
    _fn("check_image_backend",
        "Check whether image generation is available and which model files "
        "are installed."),
    _fn("capture_camera",
        "Take a photo with a camera attached to this machine.",
        {"source": {"type": "string",
                    "description": "camera index (0, 1, ...) or a stream URL. Default 0."}}),
    _fn("list_cameras",
        "List cameras attached to this machine."),
    _fn("hue_lights",
        "List the Philips Hue lights and their current state."),
    _fn("hue_control",
        "Turn Philips Hue lights on or off, set brightness, or activate a scene.",
        {"target": {"type": "string",
                    "description": "a light name, or 'all' for every light"},
         "on": {"type": "boolean"},
         "brightness_pct": {"type": "integer", "description": "0 to 100"},
         "scene": {"type": "string"}},
        ["target"]),
    _fn("spotify_now",
        "What is currently playing on Spotify."),
    _fn("spotify_control",
        "Control Spotify playback.",
        {"action": {"type": "string",
                    "enum": ["play", "pause", "next", "previous", "volume"],
                    "description": "what to do"},
         "query": {"type": "string",
                   "description": "for play: a song, artist or album to search for"},
         "volume": {"type": "integer", "description": "for volume: 0 to 100"}},
        ["action"]),
    _fn("system_status",
        "Report the health of Orbital itself: engine, text model, image "
        "backend, and which integrations are configured."),
]

SCHEMA_BY_NAME = {s["function"]["name"]: s for s in SCHEMAS}


# ------------------------------------------------------------ preamble
def capability_preamble():
    """Plain statement of what Orbital can do.

    This exists because a model asked "can you see my camera" will otherwise
    answer from its training as a text-only chatbot and say no. It is not
    lying; it simply does not know it is the reasoning part of a larger
    system. Saying so explicitly is the cheapest fix.
    """
    lines = [
        "You are the reasoning core of Orbital, a local system with real "
        "capabilities. You are NOT a bare chatbot. Do not claim you lack "
        "these abilities — you have them, and you can invoke them:",
        "",
        "  - You CAN read this machine's hardware: CPU, RAM, GPU, VRAM, disk.",
        "  - You CAN read the current date and time.",
        "  - You CAN list and read files on this machine.",
        "  - You CAN generate images, if an image backend is running.",
        "  - You CAN take photos with a camera attached to this machine.",
        "  - You CAN control Philips Hue lights, if one is paired.",
        "  - You CAN control Spotify playback, if authorised.",
        "",
        "When the user asks for something in that list, USE THE TOOL. Never "
        "reply that you cannot access real-time information, see the system, "
        "or generate images. If a tool fails, say what failed and why.",
    ]

    # State plainly what is actually available right now, so the model does
    # not promise something the machine cannot deliver.
    available, unavailable = _current_capabilities()
    if available:
        lines.append("")
        lines.append("Available right now: " + ", ".join(available) + ".")
    if unavailable:
        lines.append("Not currently available: " + ", ".join(unavailable) + ".")

    return "\n".join(lines)


def _current_capabilities():
    available = ["system information", "time", "file access"]
    unavailable = []

    try:
        from . import nebula
        ok, _ = nebula.health(timeout=2)
        (available if ok else unavailable).append("image generation")
    except Exception:
        unavailable.append("image generation")

    try:
        from . import hue
        ok, _ = hue.health(timeout=2)
        (available if ok else unavailable).append("Hue lights")
    except Exception:
        unavailable.append("Hue lights")

    try:
        from . import spotify
        ok, _ = spotify.health(timeout=3)
        (available if ok else unavailable).append("Spotify")
    except Exception:
        unavailable.append("Spotify")

    try:
        from . import camera
        ok, _ = camera.available()
        if ok:
            cams = camera.probe(range(2))
            if cams:
                available.append("camera")
            else:
                unavailable.append("camera")
        else:
            unavailable.append("camera")
    except Exception:
        unavailable.append("camera")

    return available, unavailable


# ---------------------------------------------------------- execution
def _resolve_path(path):
    """Accept an absolute path, or a bare name under the Orbital directory."""
    path = os.path.expanduser(str(path))
    if os.path.isabs(path):
        return path
    return os.path.join(config.BASE_DIR, path)


def execute(name, args):
    """Run a tool. Returns a compact result the model can read.

    Raises ToolError with a readable message on failure — never a traceback.
    """
    if name not in SCHEMA_BY_NAME:
        raise ToolError(f"unknown tool '{name}'")

    handler = _HANDLERS.get(name)
    if not handler:
        raise ToolError(f"tool '{name}' is declared but not implemented")

    log.info(f"tool: {name}({json.dumps(args, separators=(',', ':'))[:120]})")
    try:
        return handler(args or {})
    except ToolError:
        raise
    except Exception as exc:
        raise ToolError(f"{name} failed: {type(exc).__name__}: {exc}") from exc


# --------------------------------------------------------- individual
def _get_time(_args):
    now = time.localtime()
    return {
        "time": time.strftime("%H:%M:%S", now),
        "date": time.strftime("%A, %d %B %Y", now),
        "timezone": time.strftime("%Z", now),
        "unix": int(time.time()),
    }


def _get_system_info(args):
    detail = args.get("detail", "summary")
    info = {
        "node": config.node_id(),
        "platform": __import__("platform").platform(),
        "python": __import__("platform").python_version(),
    }

    try:
        import psutil
        vm = psutil.virtual_memory()
        info["cpu_count"] = psutil.cpu_count(logical=True)
        info["cpu_percent"] = psutil.cpu_percent(interval=0.3)
        info["ram_total_gb"] = round(vm.total / (1024 ** 3), 1)
        info["ram_used_gb"] = round(vm.used / (1024 ** 3), 1)
        if detail == "full":
            du = psutil.disk_usage(os.path.abspath(os.sep))
            info["disk_total_gb"] = round(du.total / (1024 ** 3), 1)
            info["disk_free_gb"] = round(du.free / (1024 ** 3), 1)
    except ImportError:
        info["psutil"] = "not installed"

    try:
        from . import gpu
        devices = gpu.detect()
        if devices:
            info["gpu"] = [
                {"name": d["name"], "vram_gb": d.get("vram_total_gb"),
                 "driver": d.get("driver")}
                for d in devices
            ]
            best = max((d for d in devices if d.get("vram_total_gb")),
                       key=lambda d: d["vram_total_gb"], default=None)
            if best:
                info["gpu_advice"] = gpu.advise(best["vram_total_gb"])["verdict"]
    except Exception:
        pass

    if detail == "full":
        try:
            from . import nucleus
            ok, models = nucleus.health(timeout=2)
            if ok:
                info["models_installed"] = models
                info["model_in_use"] = config.MODEL
        except Exception:
            pass

    return info


def _list_files(args):
    path = _resolve_path(args.get("path", config.BASE_DIR))
    if not os.path.isdir(path):
        if os.path.isfile(path):
            return {"path": path, "note": "this is a file, not a directory",
                    "size_bytes": os.path.getsize(path)}
        raise ToolError(f"no such directory: {path}")

    entries = []
    try:
        for name in sorted(os.listdir(path))[:200]:
            full = os.path.join(path, name)
            entry = {"name": name}
            try:
                entry["type"] = "dir" if os.path.isdir(full) else "file"
                if entry["type"] == "file":
                    entry["size"] = os.path.getsize(full)
            except OSError:
                entry["type"] = "unknown"
            entries.append(entry)
    except PermissionError as exc:
        raise ToolError(f"permission denied reading {path}") from exc

    return {"path": path, "count": len(entries), "entries": entries}


def _read_file(args):
    path = _resolve_path(args.get("path", ""))
    if not path or not os.path.exists(path):
        raise ToolError(f"no such file: {path}")
    if os.path.isdir(path):
        raise ToolError(f"{path} is a directory, not a file")

    limit = int(args.get("max_lines", 200) or 200)
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            lines = fh.read().splitlines()
    except PermissionError as exc:
        raise ToolError(f"permission denied reading {path}") from exc
    except OSError as exc:
        raise ToolError(f"could not read {path}: {exc}") from exc

    return {
        "path": path,
        "total_lines": len(lines),
        "returned": min(limit, len(lines)),
        "content": "\n".join(lines[:limit]),
    }


def _generate_image(args):
    from . import jobs, nebula

    ok, detail = nebula.health(timeout=3)
    if not ok:
        raise ToolError(
            "no image backend is running, so I cannot generate an image. "
            f"({detail})"
        )

    prompt = str(args.get("prompt", "")).strip()
    if not prompt:
        raise ToolError("no prompt given")

    params = {}
    if args.get("width"):
        params["width"] = int(args["width"])
    if args.get("height"):
        params["height"] = int(args["height"])

    job = jobs.submit(prompt, **params)
    return {
        "queued": True,
        "job_id": job["id"],
        "prompt": prompt,
        "note": ("Image queued. It will appear in the chat and in the gallery "
                 "when finished. Generation takes time, so tell the user it is "
                 "in progress rather than waiting."),
    }


def _check_image_backend(_args):
    from . import nebula

    ok, detail = nebula.health(timeout=3)
    if ok:
        return {"available": True, "checkpoints": detail}
    return {"available": False, "reason": str(detail)}


def _capture_camera(args):
    from . import camera

    source = args.get("source", 0)
    if isinstance(source, str) and source.isdigit():
        source = int(source)

    try:
        result = camera.snapshot(source)
    except camera.CameraError as exc:
        raise ToolError(str(exc)) from exc

    return {
        "captured": True,
        "path": result.get("path"),
        "width": result["width"],
        "height": result["height"],
    }


def _list_cameras(_args):
    from . import camera

    ok, detail = camera.available()
    if not ok:
        raise ToolError(f"camera support is not installed: {detail}")
    found = camera.probe(range(4))
    return {"count": len(found), "cameras": found}


def _hue_lights(_args):
    from . import hue

    try:
        return {"lights": hue.lights()}
    except hue.HueError as exc:
        raise ToolError(str(exc)) from exc


def _hue_control(args):
    from . import hue

    target = str(args.get("target", "")).strip()
    if not target:
        raise ToolError("no light specified")

    try:
        if args.get("scene"):
            hue.set_group(target, scene=args["scene"])
            return {"ok": True, "scene": args["scene"], "target": target}

        if target.lower() in ("all", "every", "everyone"):
            changed = hue.all_lights(on=args.get("on"),
                                     brightness_pct=args.get("brightness_pct"))
            return {"ok": True, "changed": changed}

        hue.set_light(target, on=args.get("on"),
                      brightness_pct=args.get("brightness_pct"))
        return {"ok": True, "light": target,
                "on": args.get("on"),
                "brightness_pct": args.get("brightness_pct")}
    except hue.HueError as exc:
        raise ToolError(str(exc)) from exc


def _spotify_now(_args):
    from . import spotify

    try:
        cur = spotify.now_playing()
    except spotify.SpotifyError as exc:
        raise ToolError(str(exc)) from exc
    if not cur:
        return {"playing": False, "note": "nothing is playing"}
    return cur


def _spotify_control(args):
    from . import spotify

    action = str(args.get("action", "")).lower()
    try:
        if action == "play":
            query = args.get("query")
            if query:
                track = spotify.play_search(query)
                return {"ok": True, "playing": track}
            spotify.play()
            return {"ok": True, "action": "resumed"}
        if action == "pause":
            spotify.pause()
            return {"ok": True, "action": "paused"}
        if action == "next":
            spotify.next_track()
            return {"ok": True, "action": "next"}
        if action == "previous":
            spotify.previous_track()
            return {"ok": True, "action": "previous"}
        if action == "volume":
            pct = int(args.get("volume", 50))
            spotify.set_volume(pct)
            return {"ok": True, "volume": pct}
        raise ToolError(f"unknown spotify action '{action}'")
    except spotify.SpotifyError as exc:
        raise ToolError(str(exc)) from exc


def _system_status(_args):
    from . import nucleus

    status = {"node": config.node_id(), "model": config.MODEL}

    ok, models = nucleus.health(timeout=2)
    status["text_backend"] = {
        "available": ok,
        "models": models if ok else [],
        "error": None if ok else models,
    }

    for name, label in (("nebula", "image_backend"),
                        ("hue", "hue"),
                        ("spotify", "spotify"),
                        ("camera", "camera")):
        try:
            module = __import__(f"core.{name}", fromlist=["health"])
            ok, detail = module.health(timeout=3)
            status[label] = {"available": ok, "detail": str(detail)[:120]}
        except Exception as exc:
            status[label] = {"available": False, "error": str(exc)[:120]}

    return status


_HANDLERS = {
    "get_time": _get_time,
    "get_system_info": _get_system_info,
    "list_files": _list_files,
    "read_file": _read_file,
    "generate_image": _generate_image,
    "check_image_backend": _check_image_backend,
    "capture_camera": _capture_camera,
    "list_cameras": _list_cameras,
    "hue_lights": _hue_lights,
    "hue_control": _hue_control,
    "spotify_now": _spotify_now,
    "spotify_control": _spotify_control,
    "system_status": _system_status,
}


def names():
    return sorted(_HANDLERS)
