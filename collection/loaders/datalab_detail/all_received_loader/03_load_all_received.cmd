@echo off
setlocal
cd /d "%~dp0"
".venv\Scripts\python.exe" load_all_received.py --commit
set "exit_code=%errorlevel%"
echo.
if "%exit_code%"=="0" echo [OK] All received data loaded.
pause
exit /b %exit_code%
