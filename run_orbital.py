import os
import sys
import subprocess
import socket

base = r"C:\Orbital"
if os.path.exists(base):
    os.chdir(base)
if base not in sys.path:
    sys.path.insert(0, base)
core_dir = os.path.join(base, "core")
if os.path.exists(core_dir) and core_dir not in sys.path:
    sys.path.insert(0, core_dir)

# 1. Ensure background Nucleus AI engine (engine.py) is active
try:
    engine_path = os.path.join(base, "engine.py")
    if os.path.exists(engine_path):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        res = sock.connect_ex(('127.0.0.1', 11434))
        sock.close()
        if res != 0:
            pyw = sys.executable.replace("python.exe", "pythonw.exe")
            subprocess.Popen([pyw, engine_path], cwd=base)
except Exception:
    pass

# 2. Launch Orbital Master GUI
import tkinter as tk
import orbital_login_gui

def main():
    root = tk.Tk()
    # Brand window titlebar and taskbar with cybernetic icon
    for ico in [
        os.path.join(base, "orbital_cyber_logo.ico"),
        os.path.join(base, "assets", "orbital_cyber_logo.ico"),
        os.path.join(base, "orbital_logo.ico")
    ]:
        if os.path.exists(ico):
            try:
                root.iconbitmap(ico)
                break
            except Exception:
                pass

    app = orbital_login_gui.OrbitalAuthApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
