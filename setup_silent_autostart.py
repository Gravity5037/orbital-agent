import os
import sys
import subprocess

BASE_DIR = r"C:\Orbital"
CORE_DIR = os.path.join(BASE_DIR, "core")
GUI_DIR = os.path.join(BASE_DIR, "gui")

os.makedirs(CORE_DIR, exist_ok=True)
os.makedirs(GUI_DIR, exist_ok=True)

vbs_path = os.path.join(BASE_DIR, "launch_orbital_silent.vbs")
run_path = os.path.join(BASE_DIR, "run_orbital.py")

with open(vbs_path, "w", encoding="utf-8") as f:
    f.write('Set WshShell = CreateObject("WScript.Shell")\n\' Launch Background Daemons Silently (0 = Hidden Window, False = Do Not Wait)\nWshShell.Run "pythonw C:\\Orbital\\healer_daemon.py", 0, False\nWshShell.Run "pythonw C:\\Orbital\\core\\csi_sensing_engine.py", 0, False\nWshShell.Run "pythonw C:\\Orbital\\core\\gibberlink_mesh.py", 0, False\nWshShell.Run "pythonw C:\\Orbital\\core\\spatial_map_engine.py", 0, False\n\n\' Launch User-Facing Login Gateway in Normal Visible Mode (1 = Normal Window, False = Do Not Wait)\nWshShell.Run "python C:\\Orbital\\gui\\orbital_login_gui.py", 1, False\n')

with open(run_path, "w", encoding="utf-8") as f:
    f.write('import os\nimport sys\nimport subprocess\nimport time\n\nBASE_DIR = r"C:\\Orbital"\n\n# Windows flag to hide subprocess console windows completely\nCREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0\n\ndef launch_silent_background_services():\n    services = [\n        os.path.join(BASE_DIR, "healer_daemon.py"),\n        os.path.join(BASE_DIR, "core", "csi_sensing_engine.py"),\n        os.path.join(BASE_DIR, "core", "gibberlink_mesh.py"),\n        os.path.join(BASE_DIR, "core", "spatial_map_engine.py")\n    ]\n    \n    print("[Orbital OS] Spawning background services silently...")\n    for svc in services:\n        if os.path.exists(svc):\n            try:\n                subprocess.Popen(\n                    [sys.executable.replace("python.exe", "pythonw.exe"), svc],\n                    creationflags=CREATE_NO_WINDOW,\n                    stdout=subprocess.DEVNULL,\n                    stderr=subprocess.DEVNULL\n                )\n                print(f" [✔] Silent Service Active: {os.path.basename(svc)}")\n            except Exception as e:\n                print(f" [!] Error spawning {svc}: {e}")\n\ndef launch_visible_ui():\n    gui_script = os.path.join(BASE_DIR, "gui", "orbital_login_gui.py")\n    if os.path.exists(gui_script):\n        print("[Orbital OS] Launching Cyber-Organic Workstation GUI...")\n        subprocess.Popen([sys.executable, gui_script])\n    else:\n        chat_script = os.path.join(BASE_DIR, "orbitalchat.py")\n        if os.path.exists(chat_script):\n            subprocess.Popen([sys.executable, chat_script])\n\nif __name__ == "__main__":\n    launch_silent_background_services()\n    time.sleep(1)\n    launch_visible_ui()\n')

print("[✔] Created silent VBS launcher: " + vbs_path)
print("[✔] Created master orchestrator: " + run_path)

# Update Windows Desktop Shortcut to point to launch_orbital_silent.vbs
ps_script = f'''
$WshShell = New-Object -ComObject WScript.Shell
$DesktopPath = [System.IO.Path]::Combine([System.Environment]::GetFolderPath("Desktop"), "Orbital OS.lnk")
$Shortcut = $WshShell.CreateShortcut($DesktopPath)
$Shortcut.TargetPath = "wscript.exe"
$Shortcut.Arguments = "`"{C:\Orbital\launch_orbital_silent.vbs}`""
$Shortcut.WorkingDirectory = "C:\Orbital"
if (Test-Path "C:\Orbital\orbital_logo.ico") {
    $Shortcut.IconLocation = "C:\Orbital\orbital_logo.ico"
}
$Shortcut.Save()
write-host "[✔] Desktop Shortcut updated to launch silently!"
'''

ps_file = os.path.join(BASE_DIR, "update_shortcut.ps1")
with open(ps_file, "w", encoding="utf-8") as f:
    f.write(ps_script)

print("[✔] Stealth Autostart Pipeline Configured Successfully!")
