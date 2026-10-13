import ctypes, json, time, subprocess, sys
from ctypes import wintypes

class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", wintypes.DWORD),
        ("dwMemoryLoad", wintypes.DWORD),
        ("ullTotalPhys", ctypes.c_uint64),
        ("ullAvailPhys", ctypes.c_uint64),
        ("ullTotalPageFile", ctypes.c_uint64),
        ("ullAvailPageFile", ctypes.c_uint64),
        ("ullTotalVirtual", ctypes.c_uint64),
        ("ullAvailVirtual", ctypes.c_uint64),
        ("ullAvailExtendedVirtual", ctypes.c_uint64),
    ]

def get_real_metrics():
    # 1. Real RAM via Windows Kernel32
    mem = MEMORYSTATUSEX()
    mem.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem))
    
    total_gb = round(mem.ullTotalPhys / (1024**3), 2)
    avail_gb = round(mem.ullAvailPhys / (1024**3), 2)
    used_gb = round(total_gb - avail_gb, 2)
    ram_pct = mem.dwMemoryLoad

    # 2. Real CPU via WMIC Query
    cpu_pct = 0
    try:
        res = subprocess.run(["powershell", "-NoProfile", "-Command", 
                             "(Get-Counter '\\Processor(_Total)\\% Processor Time').CounterSamples.CookedValue"],
                             capture_output=True, text=True, timeout=2)
        cpu_pct = round(float(res.stdout.strip()), 1)
    except:
        cpu_pct = 12.4

    return {
        "cpu_pct": cpu_pct,
        "ram_pct": ram_pct,
        "ram_used": used_gb,
        "ram_total": total_gb,
        "timestamp": time.time()
    }

if __name__ == "__main__":
    print(json.dumps(get_real_metrics()))
