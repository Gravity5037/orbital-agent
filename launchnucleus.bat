@echo off
cls
echo Starting Nucleus Engine
start /B python engine.py
timeout /t 2
cd dist
start Orbital.exe
cd ..
