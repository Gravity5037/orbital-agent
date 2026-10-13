import time, os, sys
sys.path.append(r"C:\Orbital")
from core.ralph_heal_loop import RalphHealLoop
def run():
    healer = RalphHealLoop()
    healer.log("Daemon started. Monitoring C:\\Orbital...")
    targets = [r"C:\Orbital\run_orbital.py", r"C:\Orbital\engine.py", r"C:\Orbital\gui\orbital_login_gui.py"]
    while True:
        for t in targets:
            healer.inspect_and_repair(t)
        time.sleep(5)
if __name__=="__main__": run()
