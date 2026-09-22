@echo off
setlocal
cd /d "%~dp0"

py export_event_review.py --output event_review_candidates.csv --per-episode 5
set CODE=%ERRORLEVEL%
echo.
echo Exit code: %CODE%
pause
exit /b %CODE%

