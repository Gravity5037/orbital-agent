@echo off
TITLE Orbital Vision + Nucleus Launcher
cls
echo ============================================================
echo   ORBITAL UNCONSTRAINED VISION + NUCLEUS ORCHESTRATOR
echo ============================================================
echo [1/2] Starting Background Nucleus Engine...
if exist "%~dp0launch_nucleus.vbs" (
    wscript "%~dp0launch_nucleus.vbs"
) else (
    start /b cmd /c "%~dp0launchnucleus.bat"
)

echo [2/2] Launching Unconstrained Vision Engine...
python "%~dp0setup_orbital_sd.py"
pause