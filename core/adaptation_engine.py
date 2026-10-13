import os, sys, json, subprocess, platform

class OrbitalAdaptationEngine:
    def __init__(self, base_dir=r"C:\Orbital"):
        self.base_dir = base_dir
        self.skills_path = os.path.join(base_dir, "skills_manifest.json")

    def inspect_environment(self):
        return {
            "os": platform.system(),
            "arch": platform.machine(),
            "python": platform.python_version(),
            "portable_mode": not os.path.exists(r"C:\Windows")
        }

    def generate_live_boot_recipe(self, target_type="chromebook"):
        """Generates ignition/boot configuration for flashing live USB devices."""
        recipe_path = os.path.join(self.base_dir, f"boot_{target_type}.sh")
        script = f"""#!/bin/sh
# Orbital Bare-Metal Deployment Script
# Target: {target_type} ({platform.machine()})
echo "[*] Initializing Orbital Live Node..."
apk add --no-cache python3 py3-pip git || apt update && apt install -y python3 python3-pip
git clone https://github.com/Gravity5037/orbital-agent.git /opt/orbital
cd /opt/orbital
python3 -m pip install -r requirements.txt || true
python3 core/engine.py &
python3 core/gibberlink_mesh.py
"""
        with open(recipe_path, "w", encoding="utf-8") as f:
            f.write(script)
        return recipe_path

if __name__ == "__main__":
    eng = OrbitalAdaptationEngine()
    print("[✔] Adaptation Engine Active:", eng.inspect_environment())
