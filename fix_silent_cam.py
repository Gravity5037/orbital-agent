p = r"C:\Orbital\engine.py"
with open(p, "r", encoding="utf-8") as f:
    code = f.read()

# Replace python.exe with pythonw.exe using the DETACHED / CREATE_NO_WINDOW flag
old_target = 'subprocess.Popen(["python.exe", r"C:\\Orbital\\orbital_vision.py"])'
new_target = 'subprocess.Popen(["pythonw.exe", r"C:\\Orbital\\orbital_vision.py"], creationflags=0x08000000)'

if old_target in code:
    code = code.replace(old_target, new_target)
    with open(p, "w", encoding="utf-8") as f:
        f.write(code)
    print("[✔] Silent window execution patched.")
else:
    # If already using different quotes or spacing
    import re
    code = re.sub(r'subprocess\.Popen\(\["python\.exe",\s*r?"C:\\\\Orbital\\\\orbital_vision\.py"\]\)', new_target, code)
    with open(p, "w", encoding="utf-8") as f:
        f.write(code)
    print("[✔] Regex patch applied.")
