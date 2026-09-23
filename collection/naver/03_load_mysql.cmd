@echo off
cd /d "%~dp0"
py load_naver_mysql.py naver_all_daily_202301_202608.csv --commit
if errorlevel 1 goto error
echo.
echo [OK] MySQL load completed.
echo Next: mysql -u yaho_loader -p tour_earlywarning ^< 04_validate_mysql.sql
pause
exit /b 0

:error
echo.
echo [FAIL] MySQL load failed and the transaction was rolled back.
pause
exit /b 1
