$WshShell = New-Object -comObject WScript.Shell
$Desktop = [System.Environment]::GetFolderPath('Desktop')
$Shortcut = $WshShell.CreateShortcut("$Desktop\Orbital HUD.lnk")
$Shortcut.TargetPath = "wscript.exe"
$Shortcut.Arguments = '"C:\Orbital\launch_orbital_gui.vbs"'
$Shortcut.WorkingDirectory = "C:\Orbital"
$Shortcut.Description = "Orbital Windowless Copyable Single-Window HUD OS"
$Shortcut.Save()
