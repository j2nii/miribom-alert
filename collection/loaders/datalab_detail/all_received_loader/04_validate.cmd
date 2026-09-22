@echo off
setlocal
cd /d "%~dp0"
".venv\Scripts\python.exe" load_all_received.py --validate
set "exit_code=%errorlevel%"
echo.
if "%exit_code%"=="0" echo [OK] Validation completed.
pause
exit /b %exit_code%
