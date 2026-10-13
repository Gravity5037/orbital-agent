"""GPU detection.

Reports what the machine actually has, so the workstation can say whether a
given image model will fit instead of you finding out via an out-of-memory
crash.

Three sources, in order of reliability:

  1. `nvidia-smi` — exact VRAM, and the only one that is correct above 4 GB
     on Windows. Also reports utilization and temperature.
  2. `torch.cuda` — if PyTorch is installed (ComfyUI brings it), exact.
  3. WMI / sysfs — name only, VRAM best-effort.

The WMI caveat is real and worth stating: `Win32_VideoController.AdapterRAM`
is a signed 32-bit field, so any card with more than 4 GB reports garbage
(often negative). We clamp and flag it rather than reporting a wrong number
with a straight face.
"""

import os
import re
import shutil
import subprocess

from . import logutil

log = logutil.get_logger("gpu")

# Rough VRAM floors for local image generation, at 1024x1024.
# (model label, GB needed at FP16, GB needed quantized)
IMAGE_MODEL_TIERS = [
    ("SD 1.5", 5.0, None),
    ("SDXL / Pony / Illustrious", 8.0, None),
    ("SD 3.5 Medium", 7.0, None),
    ("SD 3.5 Large", 12.0, 9.0),
    ("Flux.1 Dev", 35.0, 9.0),
]


def _run(argv, timeout=6):
    try:
        res = subprocess.run(
            argv, capture_output=True, text=True, timeout=timeout,
            creationflags=0x08000000 if os.name == "nt" else 0,
        )
        return res.stdout or ""
    except (OSError, subprocess.SubprocessError):
        return ""


def _from_nvidia_smi():
    if not shutil.which("nvidia-smi"):
        return None
    out = _run([
        "nvidia-smi",
        "--query-gpu=name,memory.total,memory.used,utilization.gpu,temperature.gpu",
        "--format=csv,noheader,nounits",
    ])
    if not out.strip():
        return None

    gpus = []
    for line in out.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 2:
            continue
        try:
            total_mb = float(parts[1])
        except ValueError:
            continue
        gpu = {
            "name": parts[0],
            "vram_total_gb": round(total_mb / 1024, 1),
            "source": "nvidia-smi",
        }
        if len(parts) > 2:
            try:
                gpu["vram_used_gb"] = round(float(parts[2]) / 1024, 1)
            except ValueError:
                pass
        if len(parts) > 3:
            try:
                gpu["utilization_pct"] = float(parts[3])
            except ValueError:
                pass
        if len(parts) > 4:
            try:
                gpu["temperature_c"] = float(parts[4])
            except ValueError:
                pass
        gpus.append(gpu)
    return gpus or None


def _from_torch():
    try:
        import torch  # noqa: F401
    except ImportError:
        return None

    try:
        if not torch.cuda.is_available():
            return None
        gpus = []
        for i in range(torch.cuda.device_count()):
            props = torch.cuda.get_device_properties(i)
            gpus.append({
                "name": props.name,
                "vram_total_gb": round(props.total_memory / (1024 ** 3), 1),
                "source": "torch",
            })
        return gpus or None
    except Exception as exc:
        log.warn(f"torch GPU probe failed: {exc}")
        return None


def _from_windows_wmi():
    if os.name != "nt":
        return None
    out = _run([
        "powershell", "-NoProfile", "-NonInteractive", "-Command",
        "Get-CimInstance Win32_VideoController | "
        "Select-Object Name,AdapterRAM,DriverVersion | ConvertTo-Json -Compress",
    ])
    if not out.strip():
        return None

    import json

    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return None
    if isinstance(data, dict):
        data = [data]

    gpus = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        name = entry.get("Name") or "unknown"
        gpu = {"name": name, "source": "wmi"}
        ram = entry.get("AdapterRAM")
        if isinstance(ram, int) and ram > 0:
            gb = ram / (1024 ** 3)
            # 32-bit field: anything above ~4.0 GB is a wraparound artifact.
            if gb > 4.0:
                gpu["vram_note"] = "unreliable (32-bit WMI field)"
            else:
                gpu["vram_total_gb"] = round(gb, 1)
        if entry.get("DriverVersion"):
            gpu["driver"] = entry["DriverVersion"]
        gpus.append(gpu)
    return gpus or None


def _from_linux_sysfs():
    if os.name == "nt":
        return None
    base = "/sys/class/drm"
    if not os.path.isdir(base):
        return None

    gpus = []
    for entry in sorted(os.listdir(base)):
        if not entry.startswith("card") or "-" in entry:
            continue
        vram = os.path.join(base, entry, "device", "mem_info_vram_total")
        name_path = os.path.join(base, entry, "device", "uevent")
        if not os.path.exists(vram):
            continue
        try:
            with open(vram) as fh:
                total = int(fh.read().strip())
        except (OSError, ValueError):
            continue
        name = entry
        try:
            with open(name_path) as fh:
                for line in fh:
                    if line.startswith("DRIVER="):
                        name = f"{entry} ({line.split('=', 1)[1].strip()})"
                        break
        except OSError:
            pass
        gpus.append({
            "name": name,
            "vram_total_gb": round(total / (1024 ** 3), 1),
            "source": "sysfs",
        })
    return gpus or None


def detect():
    """Return a list of GPU dicts, possibly empty. Never raises."""
    for probe in (_from_nvidia_smi, _from_torch, _from_windows_wmi, _from_linux_sysfs):
        try:
            found = probe()
        except Exception as exc:
            log.warn(f"{probe.__name__} failed: {exc}")
            continue
        if found:
            return found
    return []


def _parse_nvidia_names(out):
    """Legacy nvidia-smi output, for the fallback path."""
    names = re.findall(r"\|\s+([^\|]+?)\s+(?:On|Off)\s+\|", out)
    return [n.strip() for n in names if n.strip() and "NVIDIA" in n]


def advise(vram_gb):
    """What image models this much VRAM can run."""
    if not vram_gb:
        return {
            "verdict": "unknown",
            "note": "VRAM could not be determined",
            "can_run": [],
            "cannot_run": [m[0] for m in IMAGE_MODEL_TIERS],
        }

    can, cannot = [], []
    for label, fp16, quant in IMAGE_MODEL_TIERS:
        if vram_gb >= fp16:
            can.append({"model": label, "precision": "FP16"})
        elif quant and vram_gb >= quant:
            can.append({"model": label, "precision": f"quantized (~{quant} GB)"})
        else:
            cannot.append(label)

    if vram_gb < 5:
        verdict = "too small for local image generation"
    elif vram_gb < 8:
        verdict = "SD 1.5 fine-tunes only"
    elif vram_gb < 12:
        verdict = "SDXL family — the sweet spot for fine-tunes and LoRAs"
    elif vram_gb < 16:
        verdict = "Flux at GGUF Q5-Q6, or SDXL with a full LoRA stack"
    elif vram_gb < 24:
        verdict = "Flux at FP8 — near-lossless, good quality"
    else:
        verdict = "no practical limits; batch and high-res are viable"

    return {"verdict": verdict, "can_run": can, "cannot_run": cannot}


def summary():
    """Compact form for the telemetry endpoint."""
    gpus = detect()
    if not gpus:
        return {"detected": False, "devices": []}

    best = max(
        (g for g in gpus if g.get("vram_total_gb")),
        key=lambda g: g["vram_total_gb"],
        default=None,
    )
    result = {"detected": True, "devices": gpus}
    if best:
        result["primary"] = best["name"]
        result["vram_total_gb"] = best["vram_total_gb"]
        result["advice"] = advise(best["vram_total_gb"])
    return result


if __name__ == "__main__":
    import json

    print(json.dumps(summary(), indent=2))
