p = r"C:\Orbital\run_orbital.py"

code = """import os, sys, subprocess

BASE = r"C:\Orbital"

def sync_latest_code():
    try:
        # Silently fetch and fast-forward latest commits from GitHub
        subprocess.run(["git", "-C", BASE, "pull", "--rebase", "origin", "main"], 
                       capture_output=True, timeout=10, creationflags=0x08000000)
    except Exception:
        pass

def launch():
    sync_latest_code()
    # Start background engine
    subprocess.Popen([sys.executable.replace("python.exe", "pythonw.exe"), os.path.join(BASE, "engine.py")], cwd=BASE)
    # Launch browser interface
    gui = os.path.join(BASE, "gui", "cyber_organic_workstation.html")
    if os.path.exists(gui):
        os.startfile(gui)

if __name__ == "__main__":
    launch()
"""

with open(p, "w", encoding="utf-8") as f:
    f.write(code)

print("[✔] Auto-updater deployed: Every launch pulls the latest code from GitHub.")
