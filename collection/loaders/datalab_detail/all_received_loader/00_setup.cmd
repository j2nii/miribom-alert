@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  py -3 -m venv .venv
  if errorlevel 1 goto :error
)

".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :error
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :error

if not exist ".env" copy /Y ".env.example" ".env" >nul
echo.
echo [OK] Setup completed.
echo Edit .env: MYSQL_PASSWORD and three source paths.
pause
exit /b 0

:error
echo.
echo [ERROR] Setup failed.
pause
exit /b 1
