"""A module that exits immediately, to exercise the supervisor's restart path.

It appends a line to a marker file before exiting, so the test can prove the
process actually started each time rather than failing to launch.
"""
import os
import sys

marker = os.path.join(os.environ.get("ORBITAL_BASE", "/tmp/orbtest"), "crash_marker.txt")
try:
    with open(marker, "a", encoding="utf-8") as fh:
        fh.write("spawned\n")
except OSError:
    pass

sys.exit(3)
