@echo off
cd /d "%~dp0"
py collect_datalab_periods.py
echo.
echo Exit code: %errorlevel%
pause
