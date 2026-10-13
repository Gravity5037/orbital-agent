Set WshShell = CreateObject("WScript.Shell")
' 1. Silently terminate any stale instances
WshShell.Run "powershell -NoProfile -Command ""Stop-Process -Name 'python','pythonw' -Force -ErrorAction SilentlyContinue""", 0, True
' 2. Start engine.py invisibly
WshShell.Run "pythonw.exe C:\Orbital\engine.py", 0, False
' 3. Open Cyber-Organic Workstation in default browser
WshShell.Run "cmd /c start file:///C:/Orbital/gui/cyber_organic_workstation.html", 0, False
