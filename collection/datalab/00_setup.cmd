@echo off
cd /d "%~dp0"
py -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo [FAIL] playwright installation failed.
  pause
  exit /b 1
)
echo.
echo [OK] setup completed.
pause
