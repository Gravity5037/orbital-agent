@echo off
REM Stop the Orbital engine. It runs detached, so find it by port.
echo Stopping Orbital...

for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":5000" ^| findstr "LISTENING"') do (
    echo   stopping PID %%p
    taskkill /F /PID %%p >nul 2>&1
)

echo.
echo Done. Nothing is listening on port 5000.
timeout /t 2 >nul
