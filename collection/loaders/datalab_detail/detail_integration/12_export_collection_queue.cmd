@echo off
setlocal
cd /d "%~dp0"
".venv\Scripts\python.exe" export_integration_results.py
set "exit_code=%errorlevel%"
echo.
if "%exit_code%"=="0" echo [OK] Team CSV files created.
pause
exit /b %exit_code%
