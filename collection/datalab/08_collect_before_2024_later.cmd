@echo off
cd /d "%~dp0"
echo This optional job adds 2020-01 through 2023-12 later.
py collect_datalab_periods.py --periods 202001:202106,202107:202212,202301:202312
echo.
echo Exit code: %errorlevel%
pause
