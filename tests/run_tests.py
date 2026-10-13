"""Run every Orbital test and report a combined result.

Checks for optional dependencies first, so a missing package reads as
"install this" rather than as a wall of test failures.
"""

import importlib
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SUITES = [
    "test_oostate.py",
    "test_merge.py",
    "test_continuity.py",
    "test_gpu.py",
    "test_artifacts.py",
    "test_dataset.py",
    "test_evals.py",
    "test_integrations.py",
    "test_ui_endpoints.py",
    "test_backends.py",
    "test_nebula.py",
    "test_draw_api.py",
    "test_video.py",
    "test_tools.py",
    "test_accounts.py",
    "test_identity.py",
    "test_engine.py",
    "test_mesh.py",
    "test_supervisor.py",
    "test_integration.py",
]


def preflight():
    """Report missing optional dependencies before running anything."""
    needed = {
        "psutil": "CPU/RAM telemetry, and several suites",
        "websockets": "the mesh, and the integration suites",
    }
    missing = []
    for mod, why in needed.items():
        try:
            importlib.import_module(mod)
        except ImportError:
            missing.append((mod, why))

    if missing:
        print("=" * 70)
        print("MISSING DEPENDENCIES")
        print("=" * 70)
        for mod, why in missing:
            print(f"  {mod:<12} {why}")
        print()
        print("  Install with:")
        print("      pip install " + " ".join(m for m, _ in missing))
        print()
        print("  Some suites will fail until then. Continuing anyway.")
        print("=" * 70)
        print()
    return missing


def main():
    preflight()
    failed = []
    for suite in SUITES:
        print(f"\n{'=' * 70}\n{suite}\n{'=' * 70}")
        proc = subprocess.run([sys.executable, os.path.join(HERE, suite)])
        if proc.returncode != 0:
            failed.append(suite)

    print(f"\n{'=' * 70}")
    if failed:
        print(f"FAILED: {', '.join(failed)}")
        return 1
    print(f"All {len(SUITES)} suites passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
