import os
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
