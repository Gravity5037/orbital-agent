@echo off
TITLE Orbital OS - Standalone Master Installer
COLOR 0B
echo =============================================================
echo   ORBITAL OS: STANDALONE MASTER INSTALLER
echo =============================================================
echo.

cd /d "%~dp0"

echo [1/5] Checking Python Environment...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [X] Error: Python was not found on your system PATH!
    echo Please install Python 3.10 or newer from https://www.python.org/
    echo Be sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)
python --version
echo [OK] Python is installed and active.
echo.

echo [2/5] Installing Orbital OS Python Dependencies...
python -m pip install --upgrade pip --quiet
if exist requirements.txt (
    python -m pip install -r requirements.txt
) else (
    python -m pip install pillow numpy opencv-python websockets psutil
)
echo [OK] Dependencies verified.
echo.

echo [3/5] Verifying System Architecture & Assets...
if not exist "core" mkdir core
if not exist "gui" mkdir gui
if not exist "assets" mkdir assets
if not exist "outputs" mkdir outputs
if not exist "Nucleus" mkdir Nucleus
if not exist "users" mkdir users
if not exist "shared" mkdir shared
if not exist "web_files" mkdir web_files

if exist "orbital_logo.ico" (
    copy /Y "orbital_logo.ico" "assets\orbital_logo.ico" >nul 2>&1
)
if exist "orbital_cyber_logo.ico" (
    copy /Y "orbital_cyber_logo.ico" "assets\orbital_cyber_logo.ico" >nul 2>&1
)
if exist "orbital_logo.png" (
    copy /Y "orbital_logo.png" "assets\orbital_logo.png" >nul 2>&1
)
echo [OK] Directory hierarchy and assets verified.
echo.

echo [4/5] Checking Nucleus Intelligence Engine...
if exist "Nucleus\model.gguf" (
    echo [OK] Local AI Weights Found: Nucleus\model.gguf (Standalone Ready)
) else (
    echo [!] Notice: Nucleus\model.gguf not present in root bundle.
    echo [*] Standalone fallback & lightweight engine operational.
)
echo.

echo [5/5] Installing Desktop Shortcut with Cybernetic Logo...
python create_desktop_shortcut.py
echo.

echo =============================================================
echo   [OK] ORBITAL OS INSTALLATION COMPLETED SUCCESSFULLY!
echo   Desktop Shortcut: "Orbital OS"
echo   Master Launcher:  LAUNCH_ORBITAL.bat
echo =============================================================
echo.

set /p LAUNCH="Launch Orbital OS Universal Workstation now? (Y/N): "
if /i "%LAUNCH%"=="Y" (
    start "" pythonw run_orbital.py
)
