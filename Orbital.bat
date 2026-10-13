@echo off
REM ===========================================================================
REM  Orbital - start in the background and open the interface.
REM
REM  Starts the engine detached (no console window), waits for it to answer,
REM  then opens the browser. One instance only.
REM
REM  The folder this file sits in IS the install. Copy it anywhere.
REM ===========================================================================

cd /d "%~dp0"

REM --- already running? just open the UI ---------------------------------
netstat -ano | findstr ":5000" | findstr "LISTENING" >nul 2>&1
if %errorlevel%==0 (
    echo Orbital is already running. Opening the interface...
    start "" http://127.0.0.1:5000/
    exit /b 0
)

echo Starting Orbital...

REM --- start detached -----------------------------------------------------
REM  pythonw = no console window. Output goes to logs\, not a terminal.
start "" /B pythonw start.py

REM --- wait for it to answer, up to 30 seconds ----------------------------
set /a tries=0
:wait
set /a tries+=1
timeout /t 1 /nobreak >nul
curl -s -o nul http://127.0.0.1:5000/api/ping 2>nul
if %errorlevel%==0 goto ready
if %tries% lss 30 goto wait

echo.
echo  Orbital did not start within 30 seconds.
echo  Check the log:  %~dp0logs\startup.log
echo.
pause
exit /b 1

:ready
echo Orbital is up. Opening the interface...
start "" http://127.0.0.1:5000/
exit /b 0
