@echo off
setlocal
cd /d "%~dp0"

mysql --default-character-set=utf8mb4 -u yaho_loader -p tour_earlywarning < 31_create_evidence_analysis_views.sql
if errorlevel 1 goto :error

echo.
echo [OK] Analysis evidence views created.
echo Main view: tour_earlywarning.vw_anomaly_episode_top_evidence
echo Top 3 view: tour_earlywarning.vw_anomaly_episode_evidence_top3
pause
exit /b 0

:error
echo.
echo [ERROR] Failed to create analysis evidence views.
pause
exit /b 1
