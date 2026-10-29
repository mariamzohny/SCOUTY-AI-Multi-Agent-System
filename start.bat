@echo off
setlocal
cd /d "%~dp0"
title SCOUTY v5.1.4 - Personalized Job Search
set PYTHONIOENCODING=utf-8
set "PYTHON_EXE=python"
where py >nul 2>&1
if not errorlevel 1 set "PYTHON_EXE=py -3"
%PYTHON_EXE% --version >nul 2>&1
if errorlevel 1 (
  echo ERROR: Python 3 is not installed or not available in PATH.
  echo Install Python 3.10 or newer from https://www.python.org/downloads/
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  echo Creating a local Python environment...
  %PYTHON_EXE% -m venv .venv
  if errorlevel 1 (
    echo ERROR: Could not create Python environment. Ensure Python venv is available.
    pause
    exit /b 1
  )
)
set "APP_PY=.venv\Scripts\python.exe"
echo Checking dependencies...
"%APP_PY%" -m pip install -r requirements.txt --disable-pip-version-check
if errorlevel 1 (
  echo ERROR: Dependency installation failed. Check your internet connection and error messages above.
  pause
  exit /b 1
)
netstat -ano | findstr /R /C:":8050 .*LISTENING" >nul
if not errorlevel 1 (
  echo Port 8050 is already in use. A SCOUTY instance may already be running.
  echo Open http://127.0.0.1:8050/api/version to identify it.
  pause
  exit /b 1
)
echo Starting SCOUTY at http://127.0.0.1:8050/
start "" "http://127.0.0.1:8050/"
"%APP_PY%" -m uvicorn app:app --host 127.0.0.1 --port 8050
if errorlevel 1 echo ERROR: SCOUTY server stopped with an error. Review messages above.
pause
