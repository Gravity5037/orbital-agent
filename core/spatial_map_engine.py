"""
ORBITAL OS - 3D Spatial Occupancy Mapping Engine
Processes live OpenCV camera feeds and USB LiDAR point cloud streams
to produce real-time 3D room coordinates and occupancy matrices.
"""

import os
import sys
import time
import math
import numpy as np
import cv2

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

class SpatialMapEngine:
    def __init__(self, camera_index=0, grid_resolution=50):
        self.camera_index = camera_index
        self.grid_resolution = grid_resolution
        self.cap = None
        self.bg_subtractor = None
        self.has_camera = False
        
        # 3D Room Grid: -5.0m to +5.0m in X/Y plane
        self.room_grid = np.zeros((grid_resolution, grid_resolution), dtype=np.float32)
        self.detected_occupants = []
        self.lidar_points = []
        self._init_camera()

    def _init_camera(self):
        """Attempts to open physical OpenCV camera."""
        try:
            self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY)
            if self.cap.isOpened():
                # Test read frame
                ret, frame = self.cap.read()
                if ret and frame is not None:
                    self.has_camera = True
                    self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(history=100, varThreshold=40, detectShadows=True)
                    print(f"[🛰️ Spatial Map] Hardware optical camera active on index {self.camera_index}")
                    return
            if self.cap:
                self.cap.release()
                self.cap = None
        except Exception as e:
            print(f"[!] Camera initialization skipped: {e}")
        print("[🛰️ Spatial Map] No physical optical camera found. Simulation mode active.")

    def process_camera_frame(self):
        """Processes one frame from the optical feed and returns 3D candidate occupant positions."""
        occupants = []
        if self.has_camera and self.cap:
            ret, frame = self.cap.read()
            if ret and frame is not None:
                fg_mask = self.bg_subtractor.apply(frame)
                # Dilation to fill contours
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
                fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)
                contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                h, w, _ = frame.shape

                for cnt in contours:
                    area = cv2.contourArea(cnt)
                    if area > 1200:  # Minimum body mass contour threshold
                        x, y, bw, bh = cv2.boundingRect(cnt)
                        # Project 2D bounding box to simulated 3D room frame (meters)
                        norm_x = (x + bw / 2.0 - w / 2.0) / (w / 2.0)
                        depth_est = max(0.5, 3.5 * (1.0 - min(bh / h, 0.9)))
                        pos_x = float(norm_x * depth_est * 0.8)
                        pos_y = float(depth_est)
                        pos_z = float((h - (y + bh)) / h * 1.8)
                        occupants.append({
                            "id": f"occupant_{len(occupants)+1}",
                            "coords_3d": [round(pos_x, 2), round(pos_y, 2), round(pos_z, 2)],
                            "bbox": [x, y, bw, bh],
                            "confidence": min(round(float(area) / 10000.0, 2), 0.99)
                        })
        else:
            # Synthetic spatial harmonic projection for hardware-free development
            t = time.time()
            sim_x = round(1.2 * math.sin(t * 0.8), 2)
            sim_y = round(2.5 + 0.5 * math.cos(t * 0.8), 2)
            sim_z = 0.95
            occupants.append({
                "id": "occupant_sim_1",
                "coords_3d": [sim_x, sim_y, sim_z],
                "bbox": [100, 100, 60, 140],
                "confidence": 0.88
            })

        self.detected_occupants = occupants
        self._update_occupancy_grid()
        return occupants

    def ingest_lidar_scan(self, points):
        """
        Ingests a list of (angle_deg, distance_m) tuples from a USB LiDAR sensor.
        """
        self.lidar_points = []
        for angle, dist in points:
            if dist > 0.1 and dist < 12.0:
                rad = math.radians(angle)
                lx = dist * math.sin(rad)
                ly = dist * math.cos(rad)
                self.lidar_points.append((round(lx, 2), round(ly, 2)))
        self._update_occupancy_grid()

    def _update_occupancy_grid(self):
        """Projects detected positions and LiDAR points onto the 2D room matrix."""
        grid = np.zeros((self.grid_resolution, self.grid_resolution), dtype=np.float32)
        scale = self.grid_resolution / 10.0  # 10m room span (-5m to +5m)
        mid = self.grid_resolution // 2

        # Occupants
        for occ in self.detected_occupants:
            gx = int(mid + occ["coords_3d"][0] * scale)
            gy = int(mid + occ["coords_3d"][1] * scale)
            if 0 <= gx < self.grid_resolution and 0 <= gy < self.grid_resolution:
                grid[gx, gy] = occ["confidence"]

        # LiDAR points
        for lx, ly in self.lidar_points:
            gx = int(mid + lx * scale)
            gy = int(mid + ly * scale)
            if 0 <= gx < self.grid_resolution and 0 <= gy < self.grid_resolution:
                grid[gx, gy] = 1.0

        self.room_grid = grid

    def get_spatial_telemetry(self):
        """Returns clean telemetry dict for UI HUD and autonomous perception loop."""
        return {
            "hardware_camera_attached": self.has_camera,
            "detected_occupants_count": len(self.detected_occupants),
            "occupants": self.detected_occupants,
            "lidar_points_count": len(self.lidar_points),
            "timestamp": time.time()
        }

    def release(self):
        if self.cap:
            self.cap.release()
            self.cap = None

if __name__ == "__main__":
    spatial = SpatialMapEngine()
    print("Testing Spatial Map Engine frame capture...")
    occupants = spatial.process_camera_frame()
    print("Detected Occupants:", occupants)
    print("Telemetry:", spatial.get_spatial_telemetry())
    spatial.release()
