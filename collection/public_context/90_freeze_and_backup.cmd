@echo off
setlocal
cd /d "%~dp0"
if not exist collected_data mkdir collected_data
echo ===============================================================
echo Creating final MySQL backup. Enter the MySQL root password.
echo ===============================================================
mysqldump -u root -p --single-transaction --routines --triggers --events tour_earlywarning > collected_data\tour_earlywarning_freeze_20260922.sql
if errorlevel 1 goto :error
call .venv\Scripts\activate.bat
py freeze_manifest.py
if errorlevel 1 goto :error
echo.
echo [OK] Final backup and freeze manifest created.
echo No new data collection after 2026-09-22 23:59:59 KST.
pause
exit /b 0
:error
echo.
echo [ERROR] Freeze failed. Check the message above and run again.
pause
exit /b 2

