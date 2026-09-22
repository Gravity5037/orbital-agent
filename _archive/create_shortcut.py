import os
import subprocess

vbs_code = """
Set WshShell = WScript.CreateObject("WScript.Shell")
strDesktop = WshShell.SpecialFolders("Desktop")
Set oLink = WshShell.CreateShortcut(strDesktop & "\\Orbital.lnk")
oLink.TargetPath = "C:\\Orbital\\LAUNCH_ORBITAL.bat"
oLink.WorkingDirectory = "C:\\Orbital"
oLink.WindowStyle = 1

icoPath = "C:\\Orbital\\assets\\orbital_planet_icon.ico"
If CreateObject("Scripting.FileSystemObject").FileExists(icoPath) Then
    oLink.IconLocation = icoPath & ", 0"
End If

oLink.Description = "Launch Orbital Autonomous Agent"
oLink.Save
"""

with open("temp_shortcut.vbs", "w") as f:
    f.write(vbs_code)

subprocess.run(["cscript", "//Nologo", "temp_shortcut.vbs"])

if os.path.exists("temp_shortcut.vbs"):
    os.remove("temp_shortcut.vbs")

print("✨ Desktop shortcut created with orbital planet icon!")