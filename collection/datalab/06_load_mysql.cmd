@echo off
cd /d "%~dp0"
py load_datalab_mysql.py datalab_monthly_update_202401_202608.csv --commit
pause
