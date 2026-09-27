import os
import sys
import json
import shutil
import subprocess

def package_and_clean_orbital():
    print("=============================================================")
    print("  ORBITAL PORTABLE & REPOSITORY MASTER PACKAGER v26          ")
    print("=============================================================")

    base_dir = r"C:\Orbital"
    if not os.path.exists(base_dir):
        os.makedirs(base_dir, exist_ok=True)

    os.chdir(base_dir)

    subdirs = ["core", "gui", "users", "shared", "web_files", "Nucleus", "assets"]

    print("[1/5] Setting up neat folder architecture in C:\\Orbital...")
    for d in subdirs:
        dir_path = os.path.join(base_dir, d)
        os.makedirs(dir_path, exist_ok=True)

    shortcut_creator_code = r'''import os
import sys
import subprocess

ps_script = """
$WshShell = New-Object -ComObject WScript.Shell
$DesktopPath = [System.IO.Path]::Combine($env:USERPROFILE, "Desktop")
$ShortcutPath = [System.IO.Path]::Combine($DesktopPath, "Launch Orbital.lnk")

$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = "pythonw.exe"
$Shortcut.Arguments = "C:\\Orbital\\orbital_login_gui.py"
$Shortcut.WorkingDirectory = "C:\\Orbital"
$Shortcut.Description = "Launch Orbital OS Master Gateway"
if (Test-Path "C:\\Orbital\\assets\\logo.ico") {
    $Shortcut.IconLocation = "C:\\Orbital\\assets\\logo.ico"
}
$Shortcut.Save()
Write-Host "[✔] Desktop Shortcut created successfully directly on Desktop: $ShortcutPath"
"""

def create_desktop_shortcut():
    print("[*] Creating Desktop Shortcut at C:\\Users\\<User>\\Desktop\\Launch Orbital.lnk...")
    try:
        res = subprocess.run(["powershell", "-Command", ps_script], capture_output=True, text=True, check=True)
        print(res.stdout.strip())
    except Exception as e:
        print(f"[!] Desktop Shortcut creation error: {e}")

if __name__ == "__main__":
    create_desktop_shortcut()
'''

    with open(os.path.join(base_dir, "create_desktop_shortcut.py"), "w", encoding="utf-8") as f:
        f.write(shortcut_creator_code)

    asset_info = {
        "app_name": "Orbital Workstation",
        "logo_name": "Orbital Alien Planet Assistant Logo",
        "assets": ["logo.png", "logo.ico", "banner.png"],
        "color_theme": "Midnight Obsidian / Cyan Accent"
    }
    with open(os.path.join(base_dir, "assets", "theme_assets.json"), "w", encoding="utf-8") as f:
        json.dump(asset_info, f, indent=4)

    ignore_patterns = shutil.ignore_patterns("*.pyc", "__pycache__", ".git", ".venv", "*.tmp")
    export_dir = r"C:\Orbital_Portable_FlashDrive"
    if os.path.exists(export_dir):
        shutil.rmtree(export_dir, ignore_errors=True)

    shutil.copytree(base_dir, export_dir, ignore=ignore_patterns)

    launch_bat = """@echo off
TITLE Orbital Master Portable Gateway
cd /d "%~dp0"
echo [1/2] Verifying Desktop Shortcut...
python create_desktop_shortcut.py
echo [2/2] Launching Orbital Workstation Gateway...
python orbital_login_gui.py
pause
"""
    with open(os.path.join(export_dir, "LAUNCH_ORBITAL_PORTABLE.bat"), "w", encoding="utf-8") as f:
        f.write(launch_bat)

    try:
        subprocess.run([sys.executable, os.path.join(base_dir, "create_desktop_shortcut.py")], check=False)
    except Exception as e:
        pass

    print("=============================================================")
    print("   [✔] CLEANUP & PACKAGING COMPLETE!                        ")
    print("   - Directory cleaned & organized: C:\\Orbital             ")
    print("   - Portable payload ready for Flashdrive: C:\\Orbital_Portable_FlashDrive ")
    print("   - Shortcut placed directly on Desktop: Launch Orbital.lnk ")
    print("=============================================================")

if __name__ == "__main__":
    package_and_clean_orbital()