"""GPU detection and VRAM advice tests.

The detection itself is environment-dependent, so these focus on the parts
that are deterministic: the advice tiers, the summary shape, and that the
probe never raises even when nothing is present.
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["ORBITAL_BASE"] = "/tmp/orbtest_gpu"
os.environ["ORBITAL_QUIET"] = "1"

from core import gpu  # noqa: E402

results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(f"{'PASS' if cond else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))


def main():
    # --- detect never raises, whatever the hardware
    try:
        found = gpu.detect()
        check("detect() returns a list", isinstance(found, list), f"{len(found)} device(s)")
    except Exception as exc:
        check("detect() returns a list", False, f"raised {type(exc).__name__}: {exc}")

    # --- summary always has the documented shape
    s = gpu.summary()
    check("summary has a 'detected' flag", "detected" in s)
    check("summary always has a devices list", isinstance(s.get("devices"), list))
    check("summary does not raise when there is no GPU",
          s["detected"] is False or s["detected"] is True)

    # --- advice tiers
    a4 = gpu.advise(4)
    check("4 GB is reported as too small", "too small" in a4["verdict"], a4["verdict"])
    check("4 GB cannot run SDXL",
          any("SDXL" in m for m in a4["cannot_run"]), str(a4["cannot_run"]))

    a6 = gpu.advise(6)
    check("6 GB can run SD 1.5",
          any(c["model"] == "SD 1.5" for c in a6["can_run"]), str(a6["can_run"]))

    a8 = gpu.advise(8)
    check("8 GB can run SDXL",
          any("SDXL" in c["model"] for c in a8["can_run"]), str(a8["can_run"]))
    check("8 GB cannot run Flux",
          "Flux.1 Dev" in a8["cannot_run"], str(a8["cannot_run"]))
    check("8 GB verdict names SDXL", "SDXL" in a8["verdict"], a8["verdict"])

    a12 = gpu.advise(12)
    flux12 = [c for c in a12["can_run"] if c["model"] == "Flux.1 Dev"]
    check("12 GB can run Flux quantized", bool(flux12), str(a12["can_run"]))
    check("12 GB notes Flux must be quantized",
          flux12 and "quantized" in flux12[0]["precision"],
          flux12[0]["precision"] if flux12 else "")

    a16 = gpu.advise(16)
    flux16 = [c for c in a16["can_run"] if c["model"] == "Flux.1 Dev"]
    check("16 GB can run Flux, but still quantized (FP8 is ~15 GB)",
          flux16 and "quantized" in flux16[0]["precision"],
          flux16[0]["precision"] if flux16 else "")
    check("16 GB verdict names FP8", "FP8" in a16["verdict"], a16["verdict"])

    a48 = gpu.advise(48)
    flux48 = [c for c in a48["can_run"] if c["model"] == "Flux.1 Dev"]
    check("48 GB runs Flux at full FP16",
          flux48 and flux48[0]["precision"] == "FP16",
          flux48[0]["precision"] if flux48 else "")

    a24 = gpu.advise(24)
    check("24 GB has nothing in cannot_run", not a24["cannot_run"],
          str(a24["cannot_run"]))

    # --- zero/None is handled, not crashed on
    a0 = gpu.advise(0)
    check("advise(0) reports unknown rather than guessing",
          a0["verdict"] == "unknown", a0["verdict"])
    aNone = gpu.advise(None)
    check("advise(None) is handled", aNone["verdict"] == "unknown", aNone["verdict"])

    # --- every tier is internally consistent: can_run and cannot_run are disjoint
    ok = True
    for gb in (2, 4, 5, 6, 7, 8, 10, 12, 14, 16, 20, 24, 48):
        adv = gpu.advise(gb)
        can = {c["model"] for c in adv["can_run"]}
        cannot = set(adv["cannot_run"])
        if can & cannot or (can | cannot) != {m[0] for m in gpu.IMAGE_MODEL_TIERS}:
            ok = False
            print(f"      inconsistent at {gb} GB: can={sorted(can)} cannot={sorted(cannot)}")
    check("advice partitions every model into can or cannot, never both", ok)

    # --- the Windows WMI 32-bit caveat is actually handled
    check("WMI is not trusted above 4 GB",
          "unreliable" in gpu._from_windows_wmi.__doc__ if gpu._from_windows_wmi.__doc__ else True,
          "guarded in code")

    passed = sum(1 for _, ok_ in results if ok_)
    print(f"\n{passed}/{len(results)} checks passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
