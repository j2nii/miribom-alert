@echo off
setlocal
cd /d "%~dp0"
".venv\Scripts\python.exe" load_all_received.py --scan-only
set "exit_code=%errorlevel%"
echo.
if "%exit_code%"=="0" echo [OK] Scan completed. Database was not changed.
pause
exit /b %exit_code%
