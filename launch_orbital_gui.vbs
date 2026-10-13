Set Shell = CreateObject("WScript.Shell")
SubDir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
Shell.Run "pythonw.exe " & Chr(34) & SubDir & "\orbitalchat_gui.py" & Chr(34), 0, False
