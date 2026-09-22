@echo off
TITLE Orbital HUD Launcher
cd /d "%~dp0"
if exist "launch_orbital_gui.vbs" (
    wscript "launch_orbital_gui.vbs"
) else (
    start pythonw orbitalchat_gui.py
)
