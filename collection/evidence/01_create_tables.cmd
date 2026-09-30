@echo off
setlocal
cd /d "%~dp0"

mysql --default-character-set=utf8mb4 -u yaho_loader -p tour_earlywarning < 30_create_event_evidence_schema.sql
if errorlevel 1 goto :error

echo.
echo [OK] Evidence tables and priority view created.
pause
exit /b 0

:error
echo.
echo [ERROR] Database setup failed.
pause
exit /b 1

