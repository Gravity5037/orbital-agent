Set Shell = CreateObject("WScript.Shell")
SubDir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
Shell.Run "pythonw.exe " & Chr(34) & SubDir & "\engine.py" & Chr(34), 0, False
