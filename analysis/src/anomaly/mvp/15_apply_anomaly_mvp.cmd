@echo off
setlocal
cd /d "%~dp0"

echo ===============================================================
echo [1/3] Creating anomaly base tables
echo ===============================================================
mysql --default-character-set=utf8mb4 -u yaho_loader -p tour_earlywarning < 12_create_anomaly_base.sql
if errorlevel 1 goto :error

echo.
echo ===============================================================
echo [2/3] Creating daily feature and anomaly views
echo ===============================================================
mysql --default-character-set=utf8mb4 -u yaho_loader -p tour_earlywarning < 13_create_anomaly_views.sql
if errorlevel 1 goto :error

echo.
echo ===============================================================
echo [3/3] Validating anomaly MVP
echo ===============================================================
mysql --default-character-set=utf8mb4 -u yaho_loader -p tour_earlywarning < 14_validate_anomaly_mvp.sql
if errorlevel 1 goto :error

echo.
echo [OK] Anomaly MVP completed.
echo Candidate view: tour_earlywarning.vw_anomaly_candidate_context
pause
exit /b 0

:error
echo.
echo [ERROR] Stopped. Copy the full error output for review.
pause
exit /b 1

