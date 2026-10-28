@echo off
setlocal
cd /d "%~dp0"
python tools\export_dojo_moves.py --capture
if errorlevel 1 (
  echo.
  echo Export stopped. See the message above; your saves are unchanged.
  pause
  exit /b 1
)
pause
