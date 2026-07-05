@echo off
setlocal
cd /d "%~dp0"
title CardPilot

echo ===============================================
echo Starting CardPilot
echo ===============================================
echo.

where py >nul 2>nul
if errorlevel 1 (
  echo Python launcher "py" was not found.
  echo Install Python from python.org and tick "Add Python to PATH".
  pause
  exit /b 1
)

if not exist .venv\Scripts\python.exe (
  echo Creating local virtual environment...
  py -m venv .venv
  if errorlevel 1 (
    echo Failed to create virtual environment.
    pause
    exit /b 1
  )
)

echo Installing/updating dependencies...
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (
  echo Dependency installation failed.
  pause
  exit /b 1
)

echo.
echo Opening CardPilot at http://127.0.0.1:8000
echo Keep this window open while using the website.
echo Stop the app with CTRL+C.
echo.
start "" http://127.0.0.1:8000
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
pause
