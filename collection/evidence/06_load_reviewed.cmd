@echo off
setlocal
cd /d "%~dp0"

py apply_reviewed_events.py event_review_candidates.csv --commit
set CODE=%ERRORLEVEL%
echo.
echo Exit code: %CODE%
pause
exit /b %CODE%

