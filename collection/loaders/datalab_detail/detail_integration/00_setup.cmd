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

if not exist ".env" (
  if exist "..\all_received_loader\.env" (
    copy /Y "..\all_received_loader\.env" ".env" >nul
  ) else (
    copy /Y ".env.example" ".env" >nul
  )
)

echo.
echo [OK] Setup completed.
echo Check .env before running integration.
pause
exit /b 0

:error
echo.
echo [ERROR] Setup failed.
pause
exit /b 1
