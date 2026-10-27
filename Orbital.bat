@echo off
cd /d C:\Users\fugly\Projects\orbital-agent
taskkill /F /IM python.exe >nul 2>&1
set ORBITAL_BASE=C:\Users\fugly\Projects\orbital-agent
set ORBITAL_TOKEN=none
start "" http://127.0.0.1:5000/
python start.py