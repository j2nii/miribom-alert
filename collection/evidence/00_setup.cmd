@echo off
setlocal
cd /d "%~dp0"

py -m pip install -r requirements.txt
if errorlevel 1 goto :error

if not exist .env copy .env.example .env >nul

echo.
echo [OK] Setup completed.
echo Edit .env before running collection.
pause
exit /b 0

:error
echo.
echo [ERROR] Setup failed.
pause
exit /b 1

