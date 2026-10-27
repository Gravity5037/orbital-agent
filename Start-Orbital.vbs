' Start Orbital with no window at all.
' VBScript's Run(..., 0) hides the console completely - better than
' pythonw, which still creates one briefly.
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' The folder this script sits in.
here = fso.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = here

' 0 = hidden window, False = don't wait for it to finish
sh.Run "python.exe start.py --background", 0, False

' Give it a moment, then open the interface.
WScript.Sleep 4000
sh.Run "http://127.0.0.1:5000/", 1, False