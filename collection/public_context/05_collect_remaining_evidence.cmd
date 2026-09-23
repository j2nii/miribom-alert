@echo off
setlocal
cd /d "%~dp0"
call .venv\Scripts\activate.bat
py deadline_guard.py
if errorlevel 1 goto :closed
set "EVIDENCE_DIR=%~dp0..\event_evidence_collector"
set "DETAIL_DIR=%~dp0..\detail_integration"
if not exist "%EVIDENCE_DIR%\collect_event_evidence.py" goto :missing
if not exist "%DETAIL_DIR%\apply_integration.py" goto :missing_detail
pushd "%EVIDENCE_DIR%"
py collect_event_evidence.py --tiers P1,P2,P3 --limit 0 --display 10
if errorlevel 1 goto :failed_popd
py collect_targeted_evidence.py --tiers P1,P2,P3 --limit 0 --display 10
if errorlevel 1 goto :failed_popd
call 07_create_analysis_views.cmd
if errorlevel 1 goto :failed_popd
call 09_create_analysis_ready_view.cmd
if errorlevel 1 goto :failed_popd
call 10_export_team_analysis.cmd
if errorlevel 1 goto :failed_popd
popd

echo.
echo ===============================================================
echo Refreshing enriched anomaly snapshots and team integration CSVs
echo ===============================================================
pushd "%DETAIL_DIR%"
".venv\Scripts\python.exe" apply_integration.py --enriched-only
if errorlevel 1 goto :failed_detail_popd
".venv\Scripts\python.exe" export_integration_results.py
if errorlevel 1 goto :failed_detail_popd
popd
echo.
echo [OK] Remaining evidence collection and all final exports completed.
pause
exit /b 0
:failed_popd
popd
echo [ERROR] Evidence collection failed. Run this file again before the cutoff.
pause
exit /b 2
:failed_detail_popd
popd
echo [ERROR] Detail integration refresh failed. Check detail_integration and run again.
pause
exit /b 2
:missing
echo [ERROR] Sibling folder event_evidence_collector was not found.
pause
exit /b 2
:missing_detail
echo [ERROR] Sibling folder detail_integration was not found.
pause
exit /b 2
:closed
echo [CLOSED] New collection is disabled after the hard cutoff.
pause
exit /b 2
