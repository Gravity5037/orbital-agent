"""A stand-in ComfyUI server for tests.

Implements just enough of the real API surface to exercise both the image and
video clients:

    GET  /object_info/<Node>   -> available models for that loader
    POST /prompt               -> {prompt_id}
    GET  /history/<id>         -> completed job + outputs
    GET  /view?filename=...    -> PNG bytes (or a WebM stub)

Set FAKE_COMFY_FAIL=1 to make every generation report an error,
FAKE_COMFY_NO_CKPT=1 to report no checkpoints, and FAKE_COMFY_NO_VIDEO=1 to
report no video models.
"""

import json
import os
import struct
import time
import uuid
import zlib
from http.server import BaseHTTPRequestHandler, HTTPServer

CHECKPOINTS = ["sdxl_base.safetensors", "pony_v6.safetensors"]
UNETS = ["wan2.2_ti2v_5B_fp16.safetensors", "wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors"]
CLIPS = ["umt5_xxl_fp8_e4m3fn_scaled.safetensors"]
VAES = ["wan2.2_vae.safetensors"]
JOBS = {}


def tiny_png(width=8, height=8, rgb=(0, 229, 255)):
    """A real, valid PNG."""

    def chunk(tag, data):
        payload = tag + data
        return (
            struct.pack(">I", len(data))
            + payload
            + struct.pack(">I", zlib.crc32(payload) & 0xFFFFFFFF)
        )

    raw = b""
    for _ in range(height):
        raw += b"\x00" + bytes(rgb) * width

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def tiny_webm():
    """Minimal EBML header — enough to be recognisable as WebM, not playable."""
    return b"\x1a\x45\xdf\xa3" + b"\x00" * 60


def _opts(pairs):
    return {"input": {"required": {k: [v, {}] for k, v in pairs.items()}}}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]

        if path == "/queue":
            # Busy-ness is configurable so routing can be tested: set
            # FAKE_COMFY_LOAD=<n> to report n queued items.
            try:
                load = int(os.environ.get("FAKE_COMFY_LOAD", "0"))
            except ValueError:
                load = 0
            running = [[0, "job"]] if load > 0 else []
            pending = [[i, "job"] for i in range(max(0, load - 1))]
            return self._json(200, {"queue_running": running, "queue_pending": pending})

        if path.startswith("/object_info/"):
            node = path.rsplit("/", 1)[-1]
            no_video = os.environ.get("FAKE_COMFY_NO_VIDEO") == "1"
            table = {
                "CheckpointLoaderSimple": _opts({
                    "ckpt_name": [] if os.environ.get("FAKE_COMFY_NO_CKPT") == "1" else CHECKPOINTS,
                }),
                "UNETLoader": _opts({"unet_name": [] if no_video else UNETS}),
                "CLIPLoader": _opts({"clip_name": [] if no_video else CLIPS}),
                "VAELoader": _opts({"vae_name": [] if no_video else VAES}),
            }
            if node in table:
                return self._json(200, {node: table[node]})
            return self._json(404, {})

        if path.startswith("/history/"):
            pid = path.rsplit("/", 1)[-1]
            job = JOBS.get(pid)
            return self._json(200, {pid: job} if job else {})

        if path.startswith("/view"):
            fname = "x.webm"
            from urllib.parse import parse_qs, urlparse

            q = parse_qs(urlparse(self.path).query)
            fname = (q.get("filename") or ["x.png"])[0]
            data = tiny_webm() if fname.endswith(".webm") else tiny_png()
            self.send_response(200)
            self.send_header(
                "Content-Type", "video/webm" if fname.endswith(".webm") else "image/png"
            )
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        if self.path != "/prompt":
            self.send_response(404)
            self.end_headers()
            return

        n = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(n) or b"{}")
        graph = body.get("prompt", {})

        # Detect what kind of job this is from the node types present.
        classes = {v.get("class_type") for v in graph.values() if isinstance(v, dict)}
        is_video = bool(classes & {"SaveWEBM", "SaveAnimatedWEBP", "WanImageToVideo"})

        pid = uuid.uuid4().hex
        if os.environ.get("FAKE_COMFY_FAIL") == "1":
            JOBS[pid] = {
                "status": {"status_str": "error", "completed": False,
                           "messages": [["execution_error", {"node": "8"}]]},
                "outputs": {},
                "_graph": graph,
            }
        elif is_video:
            JOBS[pid] = {
                "status": {"status_str": "success", "completed": True},
                "outputs": {
                    "10": {"images": [{"filename": f"{pid[:8]}.webm",
                                       "subfolder": "", "type": "output"}]}
                },
                "_graph": graph,
                "_kind": "video",
            }
        else:
            JOBS[pid] = {
                "status": {"status_str": "success", "completed": True},
                "outputs": {
                    "9": {"images": [{"filename": f"{pid[:8]}_00001_.png",
                                      "subfolder": "", "type": "output"}]}
                },
                "_graph": graph,
                "_kind": "image",
            }
        time.sleep(0.05)
        self._json(200, {"prompt_id": pid, "number": 1, "node_errors": {}})


if __name__ == "__main__":
    port = int(os.environ.get("FAKE_COMFY_PORT", "8188"))
    HTTPServer(("127.0.0.1", port), H).serve_forever()
