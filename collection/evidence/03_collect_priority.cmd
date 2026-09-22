@echo off
setlocal
cd /d "%~dp0"

py collect_event_evidence.py --tiers P1,P2 --limit 100 --display 10
set CODE=%ERRORLEVEL%
echo.
echo Exit code: %CODE%
pause
exit /b %CODE%

