"""
ORBITAL OS - Bluetooth Low Energy (BLE) Environmental Sensing Engine
Implements log-distance path loss proximity modeling and multi-antenna Angle-of-Arrival (AoA)
phase estimation for device-free and beacon-based spatial vectoring.
"""

import sys
import math
import time

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

class BLESensingEngine:
    def __init__(self, ref_rssi_1m=-59.0, path_loss_exponent=2.4, frequency_ghz=2.44):
        self.ref_rssi_1m = ref_rssi_1m
        self.path_loss_exponent = path_loss_exponent
        self.frequency_ghz = frequency_ghz
        # Speed of light c / f (m)
        self.wavelength = 0.299792458 / self.frequency_ghz
        self.ant_spacing = self.wavelength / 2.0  # Half-wavelength spacing

        self.tracked_devices = {}

    def estimate_distance_from_rssi(self, rssi):
        """
        Log-distance path loss inversion:
        RSSI = -10 * n * log10(d) + A  ==>  d = 10^((A - RSSI) / (10 * n))
        """
        if rssi >= 0:
            return 0.1
        exponent = (self.ref_rssi_1m - rssi) / (10.0 * self.path_loss_exponent)
        dist = math.pow(10.0, exponent)
        return round(dist, 2)

    def calculate_aoa_angle(self, phase_diff_rad):
        """
        Calculates Angle-of-Arrival (AoA) theta (in degrees) from phase difference delta_phi:
        delta_phi = (2 * pi * d_ant / lambda) * sin(theta)
        For d_ant = lambda / 2: delta_phi = pi * sin(theta) ==> theta = arcsin(delta_phi / pi)
        """
        arg = (phase_diff_rad * self.wavelength) / (2.0 * math.pi * self.ant_spacing)
        arg = max(min(arg, 1.0), -1.0)  # Clamp domain for arcsin
        theta_rad = math.asin(arg)
        return round(math.degrees(theta_rad), 2)

    def ingest_ble_packet(self, mac_address, rssi, phase_diff_rad=0.0):
        """Ingests a BLE frame and updates target spatial vector."""
        dist = self.estimate_distance_from_rssi(rssi)
        aoa_deg = self.calculate_aoa_angle(phase_diff_rad)

        record = {
            "mac": mac_address,
            "rssi": rssi,
            "estimated_distance_m": dist,
            "aoa_angle_deg": aoa_deg,
            "timestamp": time.time()
        }
        self.tracked_devices[mac_address] = record
        return record

    def get_tracked_targets(self):
        return list(self.tracked_devices.values())

if __name__ == "__main__":
    ble = BLESensingEngine()
    print("Testing BLE Sensing Engine...")
    p1 = ble.ingest_ble_packet("AA:BB:CC:11:22:33", -68, phase_diff_rad=0.52)
    p2 = ble.ingest_ble_packet("DD:EE:FF:44:55:66", -82, phase_diff_rad=-0.85)
    print("Beacon 1:", p1)
    print("Beacon 2:", p2)
