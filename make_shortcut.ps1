$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("C:\Users\fugly\Desktop\Launch Orbital.lnk")
$Shortcut.TargetPath = "C:\Users\fugly\AppData\Local\Python\pythoncore-3.14-64\pythonw.exe"
$Shortcut.Arguments = '"C:\Orbital_FlashDrive\orbital_login_gui.py"'
$Shortcut.WorkingDirectory = "C:\Orbital_FlashDrive"
$Shortcut.Description = "Launch Orbital Unified Agent OS"
$Shortcut.Save()