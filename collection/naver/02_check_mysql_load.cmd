@echo off
cd /d "%~dp0"
py load_naver_mysql.py naver_all_daily_202301_202608.csv
if errorlevel 1 goto error
echo.
echo [OK] Validation completed. The database was not changed.
pause
exit /b 0

:error
echo.
echo [FAIL] Validation failed. The database was not changed.
pause
exit /b 1
