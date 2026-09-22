@echo off
setlocal
cd /d "%~dp0"
py -m venv .venv
if errorlevel 1 goto :error
set "PYTHON=%CD%\.venv\Scripts\python.exe"
"%PYTHON%" -m pip install --upgrade pip
if errorlevel 1 goto :error
rem Install the Windows time-zone database first so Asia/Seoul is available.
"%PYTHON%" -m pip install tzdata==2025.2
if errorlevel 1 goto :error
"%PYTHON%" -m pip install -r requirements.txt
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
