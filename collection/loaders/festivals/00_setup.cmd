@echo off
setlocal
cd /d "%~dp0"
py -m venv .venv
if errorlevel 1 goto :error
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
if errorlevel 1 goto :error
python -m pip install -r requirements.txt
if errorlevel 1 goto :error
if not exist .env copy .env.example .env >nul
echo.
echo [OK] Setup completed. Edit .env before continuing.
pause
exit /b 0
:error
echo.
echo [ERROR] Setup failed.
pause
exit /b 1

