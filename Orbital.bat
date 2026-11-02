@echo off
REM Start Orbital from wherever this file lives.
cd /d "%~dp0"
REM No ORBITAL_BASE: config.py derives the base from its own location.
set "ORBITAL_BASE="
set ORBITAL_TOKEN=none
taskkill /F /IM python.exe >nul 2>&1
start "" http://127.0.0.1:5000/
python start.py
