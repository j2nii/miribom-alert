@echo off
cd /d "%~dp0"
py collect_datalab_periods.py --limit 1
echo.
echo Exit code: %errorlevel%
pause
