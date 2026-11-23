@echo off
rem Double-click this file to start the Smart Home Energy Manager.
cd /d "%~dp0"
title Smart Home Energy Manager

set PY=
where python >nul 2>nul && python -c "import sys" >nul 2>nul && set PY=python
if not defined PY (
  where py >nul 2>nul && set PY=py -3
)
if not defined PY (
  echo.
  echo Python was not found on this computer.
  echo 1. Download Python 3.10 or newer from https://www.python.org/downloads/
  echo 2. During installation tick "Add python.exe to PATH".
  echo 3. Double-click start.bat again.
  echo.
  start "" https://www.python.org/downloads/
  pause
  exit /b 1
)

echo Starting the website. The browser will open automatically.
echo Keep this window open while you use the site. Close it to stop.
echo.
%PY% app.py %*
pause
