Set WshShell = CreateObject("WScript.Shell") 
WshShell.Run "pythonw C:\Orbital\healer_daemon.py", 0, False 
WshShell.Run "python C:\Orbital\run_orbital.py", 1, False 
