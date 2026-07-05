@echo off
setlocal
cd /d "%~dp0"
title CardPilot checks

echo ===============================================
echo Running CardPilot full check
echo ===============================================
echo.

where py >nul 2>nul
if errorlevel 1 (
  echo Python launcher "py" was not found.
  pause
  exit /b 1
)

if not exist .venv\Scripts\python.exe (
  echo Creating local virtual environment...
  py -m venv .venv
)

.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe scripts\check_all.py

echo.
pause
