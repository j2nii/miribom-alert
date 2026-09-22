@echo off
cd /d "%~dp0"
py -m pip install -r requirements.txt
if errorlevel 1 goto error
echo.
echo [OK] Setup completed.
pause
exit /b 0

:error
echo.
echo [FAIL] Package installation failed.
pause
exit /b 1
