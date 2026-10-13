import os

path = r"C:\Orbital\engine.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

old_run = 'subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=60)'
new_run = 'subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=60, cwd=r"C:\\Orbital")'

if old_run in content:
    content = content.replace(old_run, new_run)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    with open(r"C:\Orbital\core\engine.py", "w", encoding="utf-8") as f:
        f.write(content)
    print("[✔] Pinned working directory to C:\\Orbital")
else:
    print("[!] Target string not found or already patched.")
