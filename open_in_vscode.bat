@echo off
rem Double-click to open this project in Visual Studio Code.
cd /d "%~dp0"
where code >nul 2>nul
if %errorlevel%==0 (
  start "" code .
  exit /b 0
)
if exist "%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe" (
  start "" "%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe" .
  exit /b 0
)
if exist "%ProgramFiles%\Microsoft VS Code\Code.exe" (
  start "" "%ProgramFiles%\Microsoft VS Code\Code.exe" .
  exit /b 0
)
echo VS Code was not found on this computer.
echo Download it from https://code.visualstudio.com/ and run this file again.
start "" https://code.visualstudio.com/
pause
