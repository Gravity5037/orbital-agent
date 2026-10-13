import os
import subprocess

ps_script = '''
$WshShell = New-Object -ComObject WScript.Shell
$DesktopPath = [System.IO.Path]::Combine($env:USERPROFILE, "Desktop")
$ShortcutPath = [System.IO.Path]::Combine($DesktopPath, "Launch Orbital.lnk")

$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = "pythonw.exe"
$Shortcut.Arguments = "C:\Orbital_FlashDrive\orbital_login_gui.py"
$Shortcut.WorkingDirectory = "C:\Orbital_FlashDrive"
$Shortcut.Description = "Launch Orbital OS Identity Gateway"
$Shortcut.Save()
Write-Host "Shortcut created at $ShortcutPath"
'''

def create_shortcut():
    try:
        subprocess.run(["powershell", "-Command", ps_script], check=True)
        print("Desktop shortcut created successfully!")
    except Exception as e:
        print(f"Shortcut error: {e}")

if __name__ == "__main__":
    create_shortcut()
