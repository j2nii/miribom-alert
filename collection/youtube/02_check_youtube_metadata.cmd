@echo off
setlocal
cd /d "%~dp0\..\.."
py collection\youtube\backfill_youtube_metadata.py
if errorlevel 1 exit /b 1
echo.
echo [OK] Dry-run validation completed. Database was not changed.
pause
