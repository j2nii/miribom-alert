@echo off
setlocal
cd /d "%~dp0"
".venv\Scripts\python.exe" load_all_received.py --create-schema
set "exit_code=%errorlevel%"
echo.
if "%exit_code%"=="0" echo [OK] Tables and views created.
pause
exit /b %exit_code%
