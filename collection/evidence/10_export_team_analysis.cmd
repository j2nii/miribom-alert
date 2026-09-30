@echo off
setlocal
cd /d "%~dp0"

py export_team_analysis.py
if errorlevel 1 goto :error

echo.
echo [OK] Team analysis CSV files created in team_analysis_export.
pause
exit /b 0

:error
echo.
echo [ERROR] Team analysis export failed.
pause
exit /b 1
