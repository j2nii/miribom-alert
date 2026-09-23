@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo [ERROR] Run 00_setup.cmd first.
  pause
  exit /b 1
)
.venv\Scripts\python.exe load_festival_events.py --commit
set rc=%errorlevel%
echo.
if %rc%==0 echo [OK] Festival events loaded and validated.
pause
exit /b %rc%

