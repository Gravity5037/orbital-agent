import os, sys, subprocess

def launch():
    base = r"C:\Orbital"
    target = os.path.join(base, "gui", "orbital_login_gui.py")
    if os.path.exists(target):
        pyw = sys.executable.replace("python.exe", "pythonw.exe")
        subprocess.Popen([pyw, target], cwd=base)
    else:
        print("[!] Login GUI entry point not found!")

if __name__ == "__main__":
    launch()
