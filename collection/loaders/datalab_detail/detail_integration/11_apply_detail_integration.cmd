@echo off
setlocal
cd /d "%~dp0"
".venv\Scripts\python.exe" apply_integration.py
set "exit_code=%errorlevel%"
echo.
if "%exit_code%"=="0" echo [OK] Detail integration completed.
pause
exit /b %exit_code%
