@echo off
setlocal
mysql -u yaho_loader -p tour_earlywarning < "%~dp004_validate_youtube_metadata.sql"
if errorlevel 1 exit /b 1
echo.
echo [OK] YouTube metadata validation completed.
pause
