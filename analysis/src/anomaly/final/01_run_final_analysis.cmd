@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo [ERROR] Run 00_setup.cmd first.
  pause
  exit /b 1
)
.venv\Scripts\python.exe run_final_analysis.py
set rc=%errorlevel%
echo.
if %rc%==0 echo [OK] Final anomaly analysis completed.
pause
exit /b %rc%

