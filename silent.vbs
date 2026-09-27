Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "C:\Orbital"

' Launch background engine silently (window style 0 = hidden)
WshShell.Run "python engine.py", 0, False
WScript.Sleep 1000

' Launch autonomous evolution & self-healing loop silently
WshShell.Run "python evolution_loop.py", 0, False
WScript.Sleep 1000

' Launch main GUI/App
If CreateObject("Scripting.FileSystemObject").FileExists("dist\Orbital.exe") Then
    WshShell.Run "dist\Orbital.exe", 1, False
Else
    WshShell.Run "pythonw orbital_login_gui.py", 0, False
End If
