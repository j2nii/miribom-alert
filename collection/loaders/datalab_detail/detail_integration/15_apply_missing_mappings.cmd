@echo off
setlocal
cd /d "%~dp0"
".venv\Scripts\python.exe" apply_integration.py --mapping-fix
set "exit_code=%errorlevel%"
echo.
if "%exit_code%"=="0" echo [OK] Missing region mappings applied and features rebuilt.
pause
exit /b %exit_code%
