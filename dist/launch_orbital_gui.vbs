Set Shell = CreateObject("WScript.Shell")
SubDir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)

' 1. Start Nucleus Engine silently
Shell.Run "wscript.exe " & Chr(34) & SubDir & "\launch_nucleus_silent.vbs" & Chr(34), 0, False

' 2. Start Mesh Gateway silently
Shell.Run "pythonw.exe " & Chr(34) & SubDir & "\gibberlink_websocket_gateway-v2.py" & Chr(34), 0, False

' 3. Start Single-Window Orbital HUD GUI
Shell.Run "pythonw.exe " & Chr(34) & SubDir & "\orbitalchat_gui.py" & Chr(34), 0, False
