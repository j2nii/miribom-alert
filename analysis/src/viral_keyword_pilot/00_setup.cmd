@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe py -m venv .venv
if errorlevel 1 goto :error
call .venv\Scripts\activate.bat
python -m pip install -r requirements.txt
if errorlevel 1 goto :error
if not exist .env copy .env.example .env >nul
echo [OK] Setup completed. Edit .env.
pause
exit /b 0
:error
echo [ERROR] Setup failed.
pause
exit /b 1
