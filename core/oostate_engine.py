"""
ORBITAL OS - OOSTATE.BIN High-Throughput Memory-Mapped Binary State Engine
Implements the continuous byte-level state tracking and sovereign failover protocol
between Pole 1 (Host Runtime) and Pole 2 (Sovereign Core).
"""

import os
import sys
import time
import mmap
import struct
import zlib
import ctypes

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

OOSTATE_FILE_PATH = r"C:\Orbital\OOSTATE.BIN"
MAGIC_HEADER = 0x4F4F5354  # "OOST" in little-endian

class OrbitalStateHeader(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("magic_header", ctypes.c_uint32),       # 0x4F4F5354
        ("state_version", ctypes.c_uint64),      # Monotonic increment
        ("timestamp_epoch", ctypes.c_uint64),    # Nanosecond timestamp
        ("active_pole_id", ctypes.c_uint32),     # 0x01 = Pole 1, 0x02 = Pole 2
        ("ring_head_offset", ctypes.c_uint64),   # Lock-free ring pointer
        ("system_flags", ctypes.c_uint32),       # Bitmask
        ("cpu_registers", ctypes.c_uint8 * 512), # FXSAVE / XSAVE state
        ("agent_memory_ptr", ctypes.c_uint64),   # Cognitive graph pointer
        ("telemetry_ring", ctypes.c_uint8 * 4096),# Sensor ring buffer
        ("crc32_checksum", ctypes.c_uint32)      # Integrity verification hash
    ]

HEADER_SIZE = ctypes.sizeof(OrbitalStateHeader)
PAGE_ALIGNED_SIZE = ((HEADER_SIZE + 4095) // 4096) * 4096  # 4KB page aligned

class OOStateManager:
    def __init__(self, filepath=OOSTATE_FILE_PATH):
        self.filepath = filepath
        self.file_obj = None
        self.mmap_obj = None
        self.version = 0
        self._init_storage()

    def _init_storage(self):
        """Initializes and memory-maps the OOSTATE.BIN backing file."""
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        if not os.path.exists(self.filepath) or os.path.getsize(self.filepath) < PAGE_ALIGNED_SIZE:
            with open(self.filepath, "wb") as f:
                f.write(b"\x00" * PAGE_ALIGNED_SIZE)

        self.file_obj = open(self.filepath, "r+b")
        self.mmap_obj = mmap.mmap(self.file_obj.fileno(), PAGE_ALIGNED_SIZE)
        
        # Check existing header or bootstrap
        self.mmap_obj.seek(0)
        existing_magic = struct.unpack("<I", self.mmap_obj.read(4))[0]
        if existing_magic != MAGIC_HEADER:
            self.commit_state(active_pole=1, flags=0x01)
        else:
            self.read_state()

    def commit_state(self, active_pole=1, flags=0x00, cpu_reg_bytes=None, telemetry_bytes=None):
        """Atomically writes and flushes updated state to the memory-mapped backing store."""
        self.version += 1
        epoch_ns = time.time_ns()

        header = OrbitalStateHeader()
        header.magic_header = MAGIC_HEADER
        header.state_version = self.version
        header.timestamp_epoch = epoch_ns
        header.active_pole_id = active_pole
        header.ring_head_offset = HEADER_SIZE
        header.system_flags = flags
        header.agent_memory_ptr = 0x7FFF00000000 + (self.version * 64)

        if cpu_reg_bytes:
            ctypes.memmove(ctypes.addressof(header.cpu_registers), cpu_reg_bytes[:512], min(len(cpu_reg_bytes), 512))
        if telemetry_bytes:
            ctypes.memmove(ctypes.addressof(header.telemetry_ring), telemetry_bytes[:4096], min(len(telemetry_bytes), 4096))

        # Calculate CRC32 over all bytes excluding the checksum itself
        raw_header = ctypes.string_at(ctypes.addressof(header), HEADER_SIZE - 4)
        header.crc32_checksum = zlib.crc32(raw_header) & 0xFFFFFFFF

        # Write to mmap buffer
        self.mmap_obj.seek(0)
        self.mmap_obj.write(ctypes.string_at(ctypes.addressof(header), HEADER_SIZE))
        self.mmap_obj.flush()
        return self.version

    def read_state(self):
        """Reads and validates the current state from OOSTATE.BIN."""
        self.mmap_obj.seek(0)
        data = self.mmap_obj.read(HEADER_SIZE)
        header = OrbitalStateHeader.from_buffer_copy(data)

        # Verify integrity
        raw_to_check = data[:-4]
        expected_crc = zlib.crc32(raw_to_check) & 0xFFFFFFFF
        is_valid = (header.crc32_checksum == expected_crc) and (header.magic_header == MAGIC_HEADER)

        self.version = header.state_version
        return {
            "valid": is_valid,
            "magic": hex(header.magic_header),
            "state_version": header.state_version,
            "timestamp_epoch_ns": header.timestamp_epoch,
            "active_pole_id": header.active_pole_id,
            "active_pole_name": "Pole 1 (Host Runtime)" if header.active_pole_id == 1 else "Pole 2 (Sovereign Core)",
            "system_flags": bin(header.system_flags),
            "crc32_match": is_valid
        }

    def trigger_sovereign_failover(self, panic_code=0xDEADBEEF):
        """
        Simulates autonomous sovereign failover: transitions hardware ownership
        from Pole 1 to Pole 2 with zero state loss.
        """
        print(f"[⚠️ FAILOVER TRIGGERED] Host kernel interrupt panic code: {hex(panic_code)}")
        print("[⚡ MIGRATION] Remapping IOMMU translation tables to Pole 2 UEFI handlers...")
        self.commit_state(active_pole=2, flags=0x80 | 0x02)
        state = self.read_state()
        print(f"[✔ FAILOVER COMPLETE] Sovereign Core Active: {state['active_pole_name']} | Version: {state['state_version']}")
        return state

    def close(self):
        if self.mmap_obj:
            self.mmap_obj.close()
        if self.file_obj:
            self.file_obj.close()

if __name__ == "__main__":
    manager = OOStateManager()
    print("Initial State:", manager.read_state())
    print("Committing test state increment...")
    manager.commit_state(active_pole=1, flags=0x01)
    print("Updated State:", manager.read_state())
    print("\nTesting Sovereign Failover...")
    manager.trigger_sovereign_failover()
    manager.close()
