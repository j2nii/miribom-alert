@echo off
setlocal
cd /d "%~dp0"

echo ===============================================================
echo [1/2] Creating targeted-search checkpoint
echo ===============================================================
mysql --default-character-set=utf8mb4 -u yaho_loader -p tour_earlywarning < 32_create_targeted_checkpoint.sql
if errorlevel 1 goto :error

echo.
echo ===============================================================
echo [2/2] Collecting targeted event evidence
echo ===============================================================
py collect_targeted_evidence.py --tiers P1,P2 --limit 100 --display 10 --delay 0.5
if errorlevel 1 goto :error

echo.
echo [OK] Targeted evidence collection completed.
echo Next: 07_create_analysis_views.cmd
pause
exit /b 0

:error
echo.
echo [ERROR] Targeted evidence collection stopped.
echo Run this same command again to resume completed checkpoints.
pause
exit /b 1
