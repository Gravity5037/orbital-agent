Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "python engine.py", 0, False
WScript.Sleep 1000
WshShell.Run "dist\Orbital.exe", 1, False
