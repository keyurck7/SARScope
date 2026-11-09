@echo off
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
py -3.12 bootstrap.py viewer %*
if errorlevel 1 (
  echo.
  echo See the error above. Read WINDOWS_GITHUB_SETUP.md for help.
)
pause
