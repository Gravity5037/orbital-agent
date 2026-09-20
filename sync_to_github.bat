@echo off
title Orbital Core - Build, Test & GitHub Sync
cd /d C:\Users\fugly\orbital

echo ===================================================
echo [1/5] Configuring Git Identity & Remote URL...
echo ===================================================
git config --global user.name "Gravity5037"
git config --global user.email "317018587+Gravity5037@users.noreply.github.com"
git remote set-url origin https://github.com/Gravity5037/orbital-agent.git

echo.
echo ===================================================
echo [2/5] Checking .gitignore for target/...
echo ===================================================
if not exist .gitignore (
    echo target/ > .gitignore
)

echo.
echo ===================================================
echo [3/5] Running Cargo Check & Security Tests...
echo ===================================================
call cargo check
if %errorlevel% neq 0 (
    echo [ERROR] cargo check failed! Aborting sync.
    pause
    exit /b %errorlevel%
)

call cargo test --all-targets
if %errorlevel% neq 0 (
    echo [ERROR] cargo test failed! Aborting sync.
    pause
    exit /b %errorlevel%
)

echo.
echo ===================================================
echo [4/5] Commit SHA:
echo ===================================================
git rev-parse HEAD

echo.
echo ===================================================
echo [5/5] Staging, Committing & Pushing to GitHub...
echo ===================================================
git add .
git commit -m "Auto-sync & test pass"
git push -u origin main

echo.
echo ===================================================
echo SUCCESS: Orbital Core compiled, tested, and synced!
echo ===================================================
pause