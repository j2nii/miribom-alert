@echo off
setlocal
cd /d "%~dp0"

py collect_event_evidence.py --tiers P1 --limit 10 --display 10
set CODE=%ERRORLEVEL%
echo.
echo Exit code: %CODE%
pause
exit /b %CODE%

