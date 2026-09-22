@echo off
TITLE Orbital Nucleus Engine Launcher
cls
echo ============================================================
echo   ORBITAL CORE v0.4.0 — NUCLEUS STANDALONE ENGINE
echo ============================================================
echo [1/2] Starting Nucleus Local AI Engine (llama-server)...
start /b "" llama-server.exe -m Nucleus\model.gguf --port 11434 -c 4096

echo [2/2] Launching Orbital App...
timeout /t 2 /nobreak >nul
if exist dist\Orbital.exe (
    start "" dist\Orbital.exe
) else (
    python orbitalchat.py
)
