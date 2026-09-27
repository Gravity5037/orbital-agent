import os
import subprocess
import shutil

def setup_silent_startup():
    orbital_dir = r"C:\Orbital"
    if not os.path.exists(orbital_dir):
        os.makedirs(orbital_dir, exist_ok=True)

    vbs_content = '''Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "C:\\Orbital"

' Launch background engine silently (window style 0 = hidden)
WshShell.Run "python engine.py", 0, False
WScript.Sleep 1000

' Launch autonomous evolution & self-healing loop silently
WshShell.Run "python evolution_loop.py", 0, False
WScript.Sleep 1000

' Launch main GUI/App
If CreateObject("Scripting.FileSystemObject").FileExists("dist\\Orbital.exe") Then
    WshShell.Run "dist\\Orbital.exe", 1, False
Else
    WshShell.Run "pythonw orbital_login_gui.py", 0, False
End If
'''

    vbs_path = os.path.join(orbital_dir, "silent.vbs")
    with open(vbs_path, "w", encoding="utf-8") as f:
        f.write(vbs_content)
    print(f"[✔] Updated silent script at: {vbs_path}")

    # Resolve Windows Startup folder (%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup)
    appdata = os.environ.get("APPDATA")
    if appdata:
        startup_folder = os.path.join(appdata, r"Microsoft\Windows\Start Menu\Programs\Startup")
        if os.path.exists(startup_folder):
            startup_vbs = os.path.join(startup_folder, "Launch_Orbital_Silent.vbs")
            shutil.copy2(vbs_path, startup_vbs)
            print(f"[✔] Added to Windows Startup: {startup_vbs}")
        else:
            print("[!] Startup folder not found directly, registering via Windows Registry Run Key...")
            ps_cmd = f'Set-ItemProperty -Path "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run" -Name "OrbitalSilent" -Value "wscript.exe \\"{vbs_path}\\""'
            subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], check=False)

    # Launch immediately in background
    subprocess.run(["wscript.exe", vbs_path], check=False)
    print("[✔] Background services & Evolution Loop launched silently!")

if __name__ == "__main__":
    setup_silent_startup()
