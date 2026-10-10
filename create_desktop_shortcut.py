import os
import sys
import subprocess

def create_desktop_shortcut():
    base_dir = os.path.abspath(os.path.dirname(__file__))
    logo_path = os.path.join(base_dir, "orbital_cyber_logo.ico")
    if not os.path.exists(logo_path):
        logo_path = os.path.join(base_dir, "assets", "orbital_cyber_logo.ico")
    if not os.path.exists(logo_path):
        logo_path = os.path.join(base_dir, "orbital_logo.ico")

    pyw_path = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    if not os.path.exists(pyw_path):
        pyw_path = "pythonw.exe"

    target_script = os.path.join(base_dir, "run_orbital.py")

    ps_script = f'''
$WshShell = New-Object -ComObject WScript.Shell
$DesktopPath = [System.IO.Path]::Combine($env:USERPROFILE, "Desktop")
$ShortcutPath = [System.IO.Path]::Combine($DesktopPath, "Orbital OS.lnk")

$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = "{pyw_path}"
$Shortcut.Arguments = '"{target_script}"'
$Shortcut.WorkingDirectory = "{base_dir}"
$Shortcut.Description = "Orbital OS Universal Workstation"
if (Test-Path "{logo_path}") {{
    $Shortcut.IconLocation = "{logo_path},0"
}}
$Shortcut.Save()

# Force Windows Shell to invalidate icon cache and refresh Desktop
$code = @'
[System.Runtime.InteropServices.DllImport("shell32.dll")]
public static extern void SHChangeNotify(int wEventId, int uFlags, int dwItem1, int dwItem2);
'@
Add-Type -MemberDefinition $code -Namespace ShellRefresh -Name WinAPI -ErrorAction SilentlyContinue
[ShellRefresh.WinAPI]::SHChangeNotify(0x08000000, 0, 0, 0)
ie4uinit.exe -show 2>$null

Write-Host "[OK] Desktop Shortcut created and Shell refreshed: $ShortcutPath"
'''

    try:
        res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True, text=True, check=True)
        print(res.stdout.strip())
    except Exception as e:
        print(f"[!] Desktop Shortcut creation error: {e}")

if __name__ == "__main__":
    create_desktop_shortcut()
