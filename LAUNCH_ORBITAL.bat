@echo off
TITLE Orbital OS Master Workstation
cd /d "%~dp0"
where pythonw >nul 2>&1
if %errorlevel% equ 0 (
    start "" pythonw run_orbital.py
) else (
    start "" python run_orbital.py
)
