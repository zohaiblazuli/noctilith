@echo off
REM Start the SPHEREx Time Explorer and open it in your browser.
REM Double-click this file, or run it from a terminal. Close the window (or Ctrl+C) to stop.
REM First time? Run setup.bat once.
cd /d "%~dp0"
title SPHEREx Time Explorer

REM Use the environment made by setup.bat if it exists, otherwise system Python.
set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

"%PY%" -c "import fastapi, astropy, reproject" 2>nul
if errorlevel 1 (
  echo Packages are missing. Running setup first...
  call setup.bat || exit /b 1
  set "PY=.venv\Scripts\python.exe"
)

echo Starting server at http://localhost:8000  (close this window to stop)
start "" /b cmd /c "timeout /t 3 >nul & start http://localhost:8000"
"%PY%" -m uvicorn server.app:app --port 8000
pause
