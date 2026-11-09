@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0PUBLISH_PUBLIC.ps1"
if errorlevel 1 (
  echo.
  echo Publishing was not completed. Review the error above.
)
echo.
pause
