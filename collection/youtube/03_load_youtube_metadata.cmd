@echo off
setlocal
cd /d "%~dp0\..\.."
py collection\youtube\backfill_youtube_metadata.py --refresh-api --commit
if errorlevel 1 exit /b 1
echo.
echo [OK] YouTube metadata refreshed and loaded.
pause
