@echo off
setlocal
cd /d "%~dp0"

mysql --default-character-set=utf8mb4 -u yaho_loader -p tour_earlywarning < 33_create_analysis_ready_view.sql
if errorlevel 1 goto :error

echo.
echo [OK] Analysis-ready views created.
echo Main: tour_earlywarning.vw_anomaly_analysis_ready
echo Explained: tour_earlywarning.vw_anomaly_analysis_explained
echo Unresolved: tour_earlywarning.vw_anomaly_analysis_unresolved
pause
exit /b 0

:error
echo.
echo [ERROR] Failed to create analysis-ready views.
pause
exit /b 1
