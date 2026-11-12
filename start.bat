@echo off
REM Start the SPHEREx Time Explorer and open it in your browser.
REM Double-click this file, or run it from a terminal. Close the window (or Ctrl+C) to stop.
cd /d "%~dp0"
title SPHEREx Time Explorer

python -c "import fastapi, astropy, reproject" 2>nul
if errorlevel 1 (
  echo Installing Python packages (first run only^)...
  python -m pip install -r requirements.txt || (echo Package install failed. & pause & exit /b 1)
)

echo Starting server at http://localhost:8000  (close this window to stop)
start "" /b cmd /c "timeout /t 3 >nul & start http://localhost:8000"
python -m uvicorn server.app:app --port 8000
pause
