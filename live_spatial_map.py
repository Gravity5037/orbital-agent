"""
ORBITAL OS - Live 3D Spatial Occupancy Mapper
CLI / Real-time pipeline connecting physical OpenCV camera & LiDAR to Orbital perception.
"""

import sys
import time
from core.spatial_map_engine import SpatialMapEngine

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

def run_spatial_monitor(duration_seconds=5):
    print("=============================================================")
    print("      ORBITAL OS: LIVE 3D SPATIAL OCCUPANCY MONITOR          ")
    print("=============================================================")
    engine = SpatialMapEngine(camera_index=0)
    
    start = time.time()
    try:
        while time.time() - start < duration_seconds:
            occupants = engine.process_camera_frame()
            telem = engine.get_spatial_telemetry()
            print(f"[🛰️ Spatial Ping] Camera Attached: {telem['hardware_camera_attached']} | Occupants: {len(occupants)} | Time: {round(time.time() - start, 1)}s")
            for occ in occupants:
                coords = occ['coords_3d']
                print(f"    -> {occ['id']} at (X={coords[0]}m, Y={coords[1]}m, Z={coords[2]}m) | Confidence: {occ['confidence']}")
            time.sleep(1.0)
    finally:
        engine.release()
    print("=============================================================")
    print("  [✔] 3D Spatial Occupancy Stream Complete.")
    print("=============================================================")

if __name__ == "__main__":
    run_spatial_monitor(3)
