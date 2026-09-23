@echo off
cd /d "%~dp0"
set "DATA_DIR=%~dp0.."

echo ================================================================
echo [1/3] Collecting 2023-01-01 through 2024-12-31
echo ================================================================
py collect_naver_all.py --data-dir "%DATA_DIR%" --start 2023-01-01 --end 2024-12-31 --output naver_period_202301_202412.csv --progress naver_progress_202301_202412.json --report naver_period_202301_202412_report.txt
if errorlevel 1 goto error

echo.
echo ================================================================
echo [2/3] Collecting 2024-07-01 through 2026-08-31
echo ================================================================
py collect_naver_all.py --data-dir "%DATA_DIR%" --start 2024-07-01 --end 2026-08-31 --output naver_period_202407_202608.csv --progress naver_progress_202407_202608.json --report naver_period_202407_202608_report.txt
if errorlevel 1 goto error

echo.
echo ================================================================
echo [3/3] Validating overlap and merging periods
echo ================================================================
py merge_naver_periods.py
if errorlevel 1 goto error

echo.
echo [OK] Created naver_all_daily_202301_202608.csv
echo Next: run 02_check_mysql_load.cmd
pause
exit /b 0

:error
echo.
echo [FAIL] Collection or merge stopped. Review the error and run this file again.
echo Completed API calls will be reused from the progress JSON files.
pause
exit /b 1
