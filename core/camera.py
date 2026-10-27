"""Camera — local webcam, and remote phone cameras over the mesh.

Two very different problems, handled separately.

**Local webcam.** OpenCV, straightforward. Capture, save, and optionally a
motion-detection loop. The old orbital_vision.py had the beginnings of this.

**Phone camera.** The hard part is not video, it is platform policy:

  * Android permits a foreground service to hold the camera. A background
    app is killed. So a phone "camera node" has to stay open.
  * iOS is stricter. Background camera access is not permitted at all; the
    app must be foregrounded. No workaround exists at the application layer.
  * Both platforms require the user to grant permission per app, once.

The workable design is therefore: the phone runs a small app that streams
over the LAN, and Orbital consumes that stream. Tailscale makes the phone
reachable from anywhere without exposing it to the internet. That is what
this module does — it consumes a stream, it does not make the platform
cooperate.

Three input types are supported:
  * a local device index        — 0, 1, ... for USB webcams
  * an MJPEG/HTTP URL           — most phone camera apps offer one
  * an RTSP URL                 — IP cameras and some phone apps

Requires: opencv-python. Install with `pip install opencv-python`.
"""

import os
import time

from . import config, logutil

log = logutil.get_logger("camera")

CAPTURE_DIR = os.path.join(config.BASE_DIR, "captures")

# Motion detection defaults.
MOTION_THRESHOLD = int(os.environ.get("ORBITAL_MOTION_THRESHOLD", "25"))
MOTION_MIN_AREA = int(os.environ.get("ORBITAL_MOTION_MIN_AREA", "1500"))
MOTION_COOLDOWN = float(os.environ.get("ORBITAL_MOTION_COOLDOWN", "3.0"))


class CameraError(RuntimeError):
    """Base class for camera failures."""


class NoBackend(CameraError):
    """OpenCV is not installed."""


class CameraUnavailable(CameraError):
    """The source could not be opened."""


def _cv2():
    try:
        import cv2
        return cv2
    except ImportError:
        raise NoBackend(
            "opencv-python is not installed. Install it with:\n"
            "    pip install opencv-python"
        )


def available():
    """(ok, detail). detail is the version, or why it is unavailable."""
    try:
        cv2 = _cv2()
        return True, cv2.__version__
    except NoBackend as exc:
        return False, str(exc)


def _open(source, timeout=10):
    """Open a capture source. Accepts an index, a URL, or a numeric string."""
    cv2 = _cv2()

    if isinstance(source, str) and source.isdigit():
        source = int(source)

    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        raise CameraUnavailable(
            f"could not open camera source {source!r}. "
            "For a webcam try 0. For a phone, check the URL is reachable "
            "and the app is streaming."
        )

    # Warm up: the first few frames from many cameras are black or corrupt.
    deadline = time.time() + timeout
    frame = None
    while time.time() < deadline:
        ok, candidate = cap.read()
        if ok and candidate is not None and candidate.size > 0:
            frame = candidate
            break
        time.sleep(0.1)

    if frame is None:
        cap.release()
        raise CameraUnavailable(f"opened {source!r} but got no usable frames")

    return cap, frame


def snapshot(source=0, save=True, name=None):
    """Grab a single frame. Returns {path, width, height, bytes}."""
    cv2 = _cv2()
    cap, frame = _open(source)
    try:
        height, width = frame.shape[:2]
        result = {"source": str(source), "width": width, "height": height}

        if save:
            os.makedirs(CAPTURE_DIR, exist_ok=True)
            if not name:
                name = f"snap-{time.strftime('%Y%m%d-%H%M%S')}.jpg"
            path = os.path.join(CAPTURE_DIR, name)
            ok = cv2.imwrite(path, frame)
            if not ok:
                raise CameraError(f"could not write {path}")
            result["path"] = path
            result["bytes"] = os.path.getsize(path)

        result["frame"] = frame
        return result
    finally:
        cap.release()


def stream_info(source=0):
    """What this source reports about itself, without keeping it open."""
    cv2 = _cv2()
    cap, _frame = _open(source)
    try:
        return {
            "source": str(source),
            "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            "fps": round(cap.get(cv2.CAP_PROP_FPS), 1),
        }
    finally:
        cap.release()


def watch_motion(source=0, duration=None, on_motion=None, save=True):
    """Watch for motion. Blocking; call off the request thread.

    Diffs consecutive frames against a threshold. Crude but effective for
    "did something move", which is all most uses need.

    duration — seconds to watch, or None to run until interrupted
    on_motion — callback(result) fired when motion is detected
    """
    cv2 = _cv2()
    cap, previous = _open(source)
    previous_gray = cv2.cvtColor(previous, cv2.COLOR_BGR2GRAY)
    previous_gray = cv2.GaussianBlur(previous_gray, (21, 21), 0)

    started = time.time()
    last_event = 0.0
    events = []

    log.info(f"watching {source!r} for motion")
    try:
        while True:
            if duration and (time.time() - started) > duration:
                break

            ok, frame = cap.read()
            if not ok or frame is None:
                time.sleep(0.05)
                continue

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (21, 21), 0)

            delta = cv2.absdiff(previous_gray, gray)
            thresh = cv2.threshold(delta, MOTION_THRESHOLD, 255,
                                   cv2.THRESH_BINARY)[1]
            thresh = cv2.dilate(thresh, None, iterations=2)
            contours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL,
                                           cv2.CHAIN_APPROX_SIMPLE)

            moved = any(cv2.contourArea(c) >= MOTION_MIN_AREA for c in contours)
            previous_gray = gray

            now = time.time()
            if moved and (now - last_event) > MOTION_COOLDOWN:
                last_event = now
                event = {
                    "ts": now,
                    "source": str(source),
                    "elapsed": round(now - started, 1),
                }
                if save:
                    os.makedirs(CAPTURE_DIR, exist_ok=True)
                    name = f"motion-{time.strftime('%Y%m%d-%H%M%S')}.jpg"
                    path = os.path.join(CAPTURE_DIR, name)
                    if cv2.imwrite(path, frame):
                        event["path"] = path
                events.append(event)
                log.info(f"motion at {event['elapsed']}s")
                if on_motion:
                    try:
                        on_motion(event)
                    except Exception as exc:
                        log.warn(f"on_motion callback failed: {exc}")

            time.sleep(0.03)
    except KeyboardInterrupt:
        log.info("motion watch interrupted")
    finally:
        cap.release()

    return events


def probe(sources=None):
    """Check which local camera indices actually work.

    Only probes local indices — never URLs, because probing an unknown URL
    is a network request to somewhere you may not control.
    """
    cv2 = _cv2()
    sources = sources if sources is not None else range(4)
    found = []
    for idx in sources:
        cap = cv2.VideoCapture(idx)
        try:
            if cap.isOpened():
                ok, frame = cap.read()
                if ok and frame is not None and frame.size > 0:
                    h, w = frame.shape[:2]
                    found.append({"index": idx, "width": w, "height": h})
        finally:
            cap.release()
    return found


def phone_url(host, port=8080, path="/video"):
    """Build the usual MJPEG URL for a phone camera app.

    Many Android apps (IP Webcam, DroidCam, and similar) serve MJPEG on
    /video or /videofeed. Over Tailscale use the phone's 100.x address.
    """
    host = host.replace("http://", "").replace("https://", "").rstrip("/")
    if not path.startswith("/"):
        path = "/" + path
    return f"http://{host}:{port}{path}"


def handle(text):
    """Chat commands. Returns (reply, meta) or None."""
    t = text.strip()
    low = t.lower()

    if low in ("/snapshot", "/cam"):
        try:
            result = snapshot(0)
            return (f"Captured {result['width']}x{result['height']} -> "
                    f"{result.get('path', '(not saved)')}",
                    {"kind": "camera", "result": {k: v for k, v in result.items()
                                                  if k != "frame"}})
        except CameraError as exc:
            return (f"Camera: {exc}", {"kind": "camera", "ok": False})

    if low == "/cameras":
        try:
            found = probe()
        except CameraError as exc:
            return (f"Camera: {exc}", {"kind": "camera", "ok": False})
        if not found:
            return ("No local cameras found.", {"kind": "camera"})
        lines = [f"  {c['index']}: {c['width']}x{c['height']}" for c in found]
        return ("Cameras:\n" + "\n".join(lines), {"kind": "camera"})

    if low.startswith("/snapshot "):
        source = t[10:].strip()
        if not source:
            # A bare /snapshot means the default camera.
            # It parsed to '' and VideoCapture('') failed.
            source = 0
        elif source.isdigit():
            source = int(source)
        try:
            result = snapshot(source)
            return (f"Captured from {source}: {result['width']}x{result['height']}",
                    {"kind": "camera"})
        except CameraError as exc:
            return (f"Camera: {exc}", {"kind": "camera", "ok": False})

    return None


def main():
    import sys

    if len(sys.argv) < 2:
        print("usage: python -m core.camera [probe|snapshot [src]|info <src>]")
        return 1

    cmd = sys.argv[1].lower()

    if cmd == "probe":
        ok, detail = available()
        if not ok:
            print(detail)
            return 1
        print(f"OpenCV {detail}")
        found = probe()
        if not found:
            print("No local cameras found.")
            return 1
        for c in found:
            print(f"  {c['index']}: {c['width']}x{c['height']}")
        return 0

    if cmd == "snapshot":
        source = sys.argv[2] if len(sys.argv) > 2 else 0
        if str(source).isdigit():
            source = int(source)
        try:
            result = snapshot(source)
            print(f"{result['width']}x{result['height']} -> {result.get('path')}")
            return 0
        except CameraError as exc:
            print(f"Failed: {exc}")
            return 1

    if cmd == "info" and len(sys.argv) > 2:
        source = sys.argv[2]
        if source.isdigit():
            source = int(source)
        try:
            print(stream_info(source))
            return 0
        except CameraError as exc:
            print(f"Failed: {exc}")
            return 1

    print(f"unknown command '{cmd}'")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
