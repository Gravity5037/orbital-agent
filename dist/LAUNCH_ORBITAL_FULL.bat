@echo off
TITLE Orbital Master Launcher
start pythonw "%~dp0engine.py"
start pythonw "%~dp0gibberlink_websocket_gateway-v2.py"
start pythonw "%~dp0orbitalchat_gui.py"
