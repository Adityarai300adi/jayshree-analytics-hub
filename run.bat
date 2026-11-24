@echo off
setlocal
cd /d "%~dp0"
title Jayshree Analytics Hub

where py >nul 2>nul
if %errorlevel%==0 (set PY=py -3) else (set PY=python)
%PY% --version >nul 2>nul
if errorlevel 1 goto nopython

if not exist .venv\Scripts\activate.bat (
  echo Creating virtual environment...
  %PY% -m venv .venv
  if errorlevel 1 goto failed
)
call .venv\Scripts\activate.bat
echo Checking packages...
pip install -q -r requirements.txt
if errorlevel 1 echo WARNING: package install failed. Check your internet connection, then run this file again.
echo.
python app.py
echo.
echo ===== The server has stopped. If an error is shown above, take a screenshot of it. =====
pause
exit /b

:nopython
echo Python was not found. Install Python 3.9 or newer from python.org and tick "Add Python to PATH".
pause
exit /b 1

:failed
echo Could not create the virtual environment.
pause
exit /b 1
