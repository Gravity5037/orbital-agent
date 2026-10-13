p = r"C:\Orbital\engine.py"
with open(p, "r", encoding="utf-8") as f:
    c = f.read()

# Ensure engine spawns orbital_vision.py silently via pythonw with no console window
import re
c = re.sub(
    r'subprocess\.Popen\(\[.*orbital_vision\.py"\].*?\)',
    'subprocess.Popen(["pythonw.exe", r"C:\\Orbital\\orbital_vision.py"], creationflags=0x08000000)',
    c
)

with open(p, "w", encoding="utf-8") as f:
    f.write(c)
print("[✔] Engine hooked to Liquid Glass vision window.")
