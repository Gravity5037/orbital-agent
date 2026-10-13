Set WshShell = CreateObject("WScript.Shell")
SubDir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
LlamaPath = SubDir & "\llama-server.exe"
ModelPath = SubDir & "\Nucleus\model.gguf"
EnginePy = SubDir & "\engine.py"

Dim FSO
Set FSO = CreateObject("Scripting.FileSystemObject")

If FSO.FileExists(LlamaPath) Then
    WshShell.Run "powershell -Command ""Start-Process -FilePath '" & LlamaPath & "' -ArgumentList '-m " & ModelPath & " --port 11434 -c 4096' -WindowStyle Hidden""", 0, False
ElseIf FSO.FileExists(EnginePy) Then
    WshShell.Run "pythonw.exe """ & EnginePy & """", 0, False
End If
WScript.Sleep 1000
