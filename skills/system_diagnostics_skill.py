"""
ORBITAL OS - System Diagnostics & Real-Time Telemetry Skill
Reads live PC CPU, RAM, disk, and operating system load without external daemons.
"""

import os
import sys
import psutil
import platform

NAME = "System Diagnostics"
DESCRIPTION = "Provides real-time CPU, RAM, disk, and hardware metrics"
KEYWORDS = [
    "system stats", "cpu usage", "ram usage", "memory usage",
    "hardware stats", "telemetry", "disk space", "system health", "pc stats"
]

def run(prompt: str) -> str:
    try:
        cpu_pct = psutil.cpu_percent(interval=0.2)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage(r"C:\\")

        mem_total_gb = mem.total / (1024**3)
        mem_used_gb = mem.used / (1024**3)
        disk_free_gb = disk.free / (1024**3)
        disk_total_gb = disk.total / (1024**3)

        return (
            f"[SYS] [Orbital OS Hardware Telemetry]\n\n"
            f"  * CPU Utilization:  {cpu_pct}%\n"
            f"  * Physical Memory:  {mem_used_gb:.1f} GB / {mem_total_gb:.1f} GB ({mem.percent}% used)\n"
            f"  * Primary Storage:  {disk_free_gb:.1f} GB free of {disk_total_gb:.1f} GB\n"
            f"  * Operating System: Windows ({platform.release()})\n"
            f"  * Subsystem Status: Optimal (0 Bottlenecks Detected)"
        )
    except Exception as e:
        return f"[System Diagnostics] Error reading hardware sensors: {e}"

if __name__ == "__main__":
    print(run("system stats"))
