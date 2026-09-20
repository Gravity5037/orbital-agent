@echo off
TITLE Orbital Agent - Laptop Launcher
cls
cd /d "%~dp0"
echo ============================================================
echo   ORBITAL AGENT — LAPTOP LAUNCHER
echo ============================================================
echo.
echo [1/3] Setting CPU Mode (OLLAMA_NO_GPU=1)...
setx OLLAMA_NO_GPU 1 >nul 2>&1
set OLLAMA_NO_GPU=1

echo [2/3] Cleaning up existing processes and starting Ollama...
taskkill /F /IM "ollama app.exe" >nul 2>&1
taskkill /F /IM ollama.exe >nul 2>&1
timeout /t 2 /nobreak >nul
start "" ollama serve
timeout /t 3 /nobreak >nul

echo [3/3] Launching Orbital Chat...
echo ------------------------------------------------------------
python orbitalchat.py
pause
