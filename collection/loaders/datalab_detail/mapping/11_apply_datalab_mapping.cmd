@echo off
setlocal
cd /d "%~dp0"

echo ===============================================================
echo [1/3] Creating DataLab region mapping
echo ===============================================================
mysql --default-character-set=utf8mb4 -u yaho_loader -p tour_earlywarning < 08_create_datalab_region_mapping.sql
if errorlevel 1 goto :error

echo.
echo ===============================================================
echo [2/3] Creating canonical monthly views
echo ===============================================================
mysql --default-character-set=utf8mb4 -u yaho_loader -p tour_earlywarning < 09_create_datalab_canonical_view.sql
if errorlevel 1 goto :error

echo.
echo ===============================================================
echo [3/3] Validating mapping and views
echo ===============================================================
mysql --default-character-set=utf8mb4 -u yaho_loader -p tour_earlywarning < 10_validate_datalab_mapping.sql
if errorlevel 1 goto :error

echo.
echo [OK] DataLab mapping completed.
echo Team query view: tour_earlywarning.vw_datalab_canonical_monthly
pause
exit /b 0

:error
echo.
echo [ERROR] Stopped. Copy the error output and send it for review.
pause
exit /b 1

