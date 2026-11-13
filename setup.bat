@echo off
REM One-time setup for the SPHEREx Time Explorer.
REM Checks Python, creates a private Python environment (.venv) in this folder,
REM installs every package from requirements.txt, and checks the install worked.
REM Afterwards, double-click start.bat to run the app.
setlocal
cd /d "%~dp0"
title SPHEREx Time Explorer - setup

echo === SPHEREx Time Explorer setup ===
echo.

REM 1. Find Python (python, or the "py" launcher that ships with Windows installs)
set "PY="
python --version >nul 2>&1 && set "PY=python"
if not defined PY (
  py -3 --version >nul 2>&1 && set "PY=py -3"
)
if not defined PY (
  echo Python was not found.
  echo Install Python 3.12 from https://www.python.org/downloads/
  echo and tick "Add python.exe to PATH" in the installer, then run setup.bat again.
  pause
  exit /b 1
)

REM 2. Require Python 3.10 or newer
%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"
if errorlevel 1 (
  echo This app needs Python 3.10 or newer. You have:
  %PY% --version
  pause
  exit /b 1
)
for /f "delims=" %%v in ('%PY% --version') do echo Found %%v

REM 3. Create the virtual environment (skipped if it already exists)
if exist ".venv\Scripts\python.exe" (
  echo Using existing environment in .venv
) else (
  echo Creating Python environment in .venv ...
  %PY% -m venv .venv
  if errorlevel 1 (
    echo Could not create the environment.
    pause
    exit /b 1
  )
)
set "VPY=.venv\Scripts\python.exe"

REM 4. Install packages
echo.
echo Installing packages (this can take a few minutes the first time) ...
"%VPY%" -m pip install --upgrade pip --quiet
"%VPY%" -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo Package install failed. Check your internet connection and try again.
  pause
  exit /b 1
)

REM 5. Folders the app writes to
if not exist "cache" mkdir cache

REM 6. Check the install
echo.
"%VPY%" -c "import fastapi, uvicorn, httpx, astropy, reproject, numpy, scipy; print('All packages import correctly.')"
if errorlevel 1 (
  echo Something is missing from the install. Try deleting the .venv folder and running setup.bat again.
  pause
  exit /b 1
)

REM 7. Node is optional (only used for the frontend tests)
node --version >nul 2>&1
if errorlevel 1 (
  echo Note: Node.js not found. That's fine; it's only needed to run the frontend tests.
)

echo.
echo === Setup complete ===
echo Double-click start.bat to launch the app, then open http://localhost:8000
echo Optional: run  .venv\Scripts\python.exe scripts\precache.py  to pre-download the demo spots.
echo.
pause
endlocal
